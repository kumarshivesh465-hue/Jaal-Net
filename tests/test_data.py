"""Contract tests for data.py per CONTRACTS.md section 5."""

import networkx as nx
import pytest

from config import (
    INDIAN_STATE_CODES,
    RING_IDS,
    THRESHOLD_BLOCK,
    THRESHOLD_MONITOR,
    THRESHOLD_STEPUP,
)
from data import (
    RINGS,
    build_neighborhood_graph,
    build_ring_graph,
    generate_transaction,
    initial_stream,
)

VALID_ACTIONS = {"ALLOW", "MONITOR", "STEP_UP", "BLOCK"}
VALID_EDGE_TYPES = {"ring", "layering", "circular", "normal"}


# ---------- generate_transaction ----------

def test_generate_transaction_returns_valid_object():
    txn = generate_transaction(1)
    assert txn.txn_id.startswith("UPI-")
    assert isinstance(txn.amount, float)
    assert txn.amount > 0
    assert 0 <= txn.score <= 100
    assert txn.action in VALID_ACTIONS
    assert txn.state in INDIAN_STATE_CODES
    assert isinstance(txn.device_change, bool)
    assert 0.0 <= txn.ip_risk <= 1.0


def test_generate_transaction_action_matches_score():
    """Action must be consistent with config thresholds."""
    for i in range(200):
        txn = generate_transaction(i)
        if txn.score < THRESHOLD_MONITOR:
            assert txn.action == "ALLOW", f"score={txn.score} action={txn.action}"
        elif txn.score < THRESHOLD_STEPUP:
            assert txn.action == "MONITOR", f"score={txn.score} action={txn.action}"
        elif txn.score < THRESHOLD_BLOCK:
            assert txn.action == "STEP_UP", f"score={txn.score} action={txn.action}"
        else:
            assert txn.action == "BLOCK", f"score={txn.score} action={txn.action}"


def test_generate_transaction_ring_id_is_valid_or_none():
    for i in range(500):
        txn = generate_transaction(i)
        assert txn.ring_id is None or txn.ring_id in RING_IDS


def test_generate_transaction_explanation_sums_to_roughly_one():
    txn = generate_transaction(1)
    weights = [w for _, w in txn.explanation]
    assert all(w >= 0 for w in weights)
    assert 0.05 <= sum(weights) <= 1.05


def test_generate_transaction_explanation_sorted_descending():
    txn = generate_transaction(1)
    weights = [w for _, w in txn.explanation]
    assert weights == sorted(weights, reverse=True)


# ---------- initial_stream ----------

@pytest.mark.parametrize("n", [1, 10, 100, 500])
def test_initial_stream_correct_length(n):
    stream = initial_stream(n)
    assert len(stream) == n


@pytest.mark.parametrize("n", [0, 501, -1])
def test_initial_stream_out_of_range(n):
    with pytest.raises(ValueError):
        initial_stream(n)


def test_initial_stream_is_newest_first():
    stream = initial_stream(30)
    timestamps = [t.timestamp for t in stream]
    assert timestamps == sorted(timestamps, reverse=True)


# ---------- build_ring_graph ----------

@pytest.mark.parametrize("ring_id", RING_IDS)
def test_build_ring_graph_node_count(ring_id):
    G = build_ring_graph(ring_id)
    assert G.number_of_nodes() == len(RINGS[ring_id])
    assert isinstance(G, nx.DiGraph)


@pytest.mark.parametrize("ring_id", RING_IDS)
def test_build_ring_graph_node_attributes(ring_id):
    G = build_ring_graph(ring_id)
    for node in G.nodes:
        assert "score" in G.nodes[node]
        assert 0 <= G.nodes[node]["score"] <= 100


@pytest.mark.parametrize("ring_id", RING_IDS)
def test_build_ring_graph_edge_attributes(ring_id):
    G = build_ring_graph(ring_id)
    assert G.number_of_edges() > 0
    for u, v in G.edges:
        attrs = G.edges[u, v]
        assert "amount" in attrs and attrs["amount"] > 0
        assert "edge_type" in attrs
        assert attrs["edge_type"] in VALID_EDGE_TYPES


@pytest.mark.parametrize("ring_id", RING_IDS)
def test_build_ring_graph_is_connected(ring_id):
    G = build_ring_graph(ring_id)
    assert nx.is_weakly_connected(G)


def test_build_ring_graph_unknown_ring_raises():
    with pytest.raises(ValueError, match="Unknown ring_id"):
        build_ring_graph("RING-999")


# ---------- build_neighborhood_graph ----------

def test_build_neighborhood_graph_contains_txn_endpoints(sample_txn):
    G = build_neighborhood_graph(sample_txn, hops=2)
    assert sample_txn.sender in G.nodes
    assert sample_txn.receiver in G.nodes
    assert G.has_edge(sample_txn.sender, sample_txn.receiver)


def test_build_neighborhood_graph_sender_score_matches_txn(sample_txn):
    G = build_neighborhood_graph(sample_txn, hops=2)
    assert G.nodes[sample_txn.sender]["score"] == sample_txn.score


def test_build_neighborhood_graph_edge_amount_matches_txn(sample_txn):
    G = build_neighborhood_graph(sample_txn, hops=2)
    edge = G.edges[sample_txn.sender, sample_txn.receiver]
    assert edge["amount"] == sample_txn.amount


def test_build_neighborhood_graph_all_nodes_have_scores(sample_txn):
    G = build_neighborhood_graph(sample_txn, hops=2)
    for node in G.nodes:
        assert "score" in G.nodes[node]


@pytest.mark.parametrize("hops", [0, 4, -1])
def test_build_neighborhood_graph_hops_out_of_range(sample_txn, hops):
    with pytest.raises(ValueError):
        build_neighborhood_graph(sample_txn, hops=hops)


@pytest.mark.parametrize("hops", [1, 2, 3])
def test_build_neighborhood_graph_valid_hops(sample_txn, hops):
    G = build_neighborhood_graph(sample_txn, hops=hops)
    assert G.number_of_nodes() >= 2
