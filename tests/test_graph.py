"""Contract tests for graph.py per CONTRACTS.md section 6."""

import json
import re

import networkx as nx
import pytest

from config import RING_IDS
from data import build_neighborhood_graph, build_ring_graph
from graph import cytoscape_html


def _extract_elements(html: str) -> dict:
    match = re.search(r"const elements = (\{.*?\});", html, re.DOTALL)
    assert match, "Could not find elements JSON in HTML"
    return json.loads(match.group(1))


def test_cytoscape_html_is_wellformed(sample_txn):
    G = build_neighborhood_graph(sample_txn)
    html = cytoscape_html(G, height=480)
    assert html.startswith("<!DOCTYPE html>")
    assert html.strip().endswith("</html>")
    assert "<html>" in html
    assert "<script" in html
    assert "</script>" in html


def test_cytoscape_html_uses_pinned_version(sample_txn):
    G = build_neighborhood_graph(sample_txn)
    html = cytoscape_html(G, height=480)
    assert "cytoscape@3.28.1" in html
    assert "unpkg.com" in html


def test_cytoscape_html_contains_all_nodes_as_json(sample_txn):
    G = build_neighborhood_graph(sample_txn)
    html = cytoscape_html(G, height=480)
    payload = _extract_elements(html)
    node_ids_in_html = {n["data"]["id"] for n in payload["nodes"]}
    assert node_ids_in_html == set(G.nodes)


def test_cytoscape_html_contains_all_edges_as_json(sample_txn):
    G = build_neighborhood_graph(sample_txn)
    html = cytoscape_html(G, height=480)
    payload = _extract_elements(html)
    edges_in_html = {(e["data"]["source"], e["data"]["target"]) for e in payload["edges"]}
    assert edges_in_html == set(G.edges)


def test_cytoscape_html_has_dark_background(sample_txn):
    G = build_neighborhood_graph(sample_txn)
    html = cytoscape_html(G, height=480)
    assert "#0A0E17" in html


def test_cytoscape_html_respects_height_argument(sample_txn):
    G = build_neighborhood_graph(sample_txn)
    html = cytoscape_html(G, height=333)
    assert "333px" in html


@pytest.mark.parametrize("ring_id", RING_IDS)
def test_cytoscape_html_on_all_rings(ring_id):
    G = build_ring_graph(ring_id)
    html = cytoscape_html(G, height=560)
    assert "<html>" in html
    payload = _extract_elements(html)
    assert len(payload["nodes"]) == G.number_of_nodes()


def test_cytoscape_html_ring_edges_are_pink():
    """Ring edges must render as pink (#EC4899) per CONTRACTS.md."""
    G = build_ring_graph("RING-001")
    html = cytoscape_html(G, height=480)
    payload = _extract_elements(html)
    ring_edges = [e for e in payload["edges"] if e["data"]["edge_type"] == "ring"]
    assert len(ring_edges) > 0
    for e in ring_edges:
        assert e["data"]["color"] == "#EC4899"


def test_cytoscape_html_raises_on_missing_score_attribute():
    G = nx.DiGraph()
    G.add_node("A")  # no score attribute
    G.add_node("B", score=50)
    G.add_edge("A", "B", amount=100.0, edge_type="normal")
    with pytest.raises(ValueError):
        cytoscape_html(G)


def test_cytoscape_html_raises_on_missing_edge_amount():
    G = nx.DiGraph()
    G.add_node("A", score=50)
    G.add_node("B", score=50)
    G.add_edge("A", "B", edge_type="normal")  # no amount
    with pytest.raises(ValueError):
        cytoscape_html(G)


def test_cytoscape_html_raises_on_bad_height(sample_txn):
    G = build_neighborhood_graph(sample_txn)
    with pytest.raises(ValueError):
        cytoscape_html(G, height=50)
