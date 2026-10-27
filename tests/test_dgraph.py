"""Tests for the DGraphFin pipeline (L4 Session A loader, Session B TGN wiring).

The 680MB dataset lives at data/DGraphFin/raw/dgraphfin.npz, is gitignored,
and is verified against the 2026-10-14 gate check (3,700,550 nodes /
4,300,999 edges; masks are int64 index arrays over the labelled 0/1 nodes).

Dataset-dependent tests are marked `integration` so the default `make test`
run stays fast. Run them explicitly with:

    ./.venv/Scripts/python -m pytest tests/test_dgraph.py -m integration -q
"""

import os

import numpy as np
import pytest
import torch
from torch_geometric.data import Data

DATA_PATH = os.path.join("data", "DGraphFin", "raw", "dgraphfin.npz")

N_NODES = 3_700_550
N_EDGES = 4_300_999
TRAIN_LABELLED = 857_899
VALID_LABELLED = 183_862
TEST_LABELLED = 183_840

needs_dataset = pytest.mark.skipif(
    not os.path.exists(DATA_PATH),
    reason=f"dataset missing at {DATA_PATH} (680MB, not in git)",
)


@pytest.fixture(scope="module")
def dgraph_data():
    """Load the real dataset once for the whole module (~20s)."""
    from train_dgraph import load_dgraph

    return load_dgraph()


# ---------------------------------------------------------------------------
# loader contract — dataset required
# ---------------------------------------------------------------------------

@needs_dataset
@pytest.mark.integration
def test_load_dgraph_matches_gate_check_numbers(dgraph_data):
    assert dgraph_data.num_nodes == N_NODES
    assert dgraph_data.edge_index.shape == (2, N_EDGES)
    assert int(dgraph_data.train_mask.sum()) == TRAIN_LABELLED
    assert int(dgraph_data.valid_mask.sum()) == VALID_LABELLED
    assert int(dgraph_data.test_mask.sum()) == TEST_LABELLED


@needs_dataset
@pytest.mark.integration
def test_load_dgraph_masks_are_boolean_length_n(dgraph_data):
    for name in ("train_mask", "valid_mask", "test_mask"):
        mask = getattr(dgraph_data, name)
        assert mask.dtype == torch.bool, name
        assert mask.shape == (N_NODES,), name


@needs_dataset
@pytest.mark.integration
def test_load_dgraph_features_are_standardized(dgraph_data):
    x = dgraph_data.x
    assert x.dtype == torch.float32
    # float64 accumulators: numpy sums float32 arrays in float32 otherwise,
    # which reads as a standardization failure when the transform is exact
    x64 = x.to(torch.float64)   # torch std() takes no dtype kwarg
    mean = x64.mean(dim=0).abs().max().item()
    std = (x64.std(dim=0) - 1.0).abs().max().item()
    assert mean < 1e-3, mean
    assert std < 1e-3, std


@needs_dataset
@pytest.mark.integration
def test_load_dgraph_edge_attr_holds_timestamps(dgraph_data):
    assert dgraph_data.edge_attr.shape == (N_EDGES, 1)
    assert dgraph_data.edge_attr.dtype == torch.float32
    assert float(dgraph_data.edge_attr.max()) == 821.0


@needs_dataset
@pytest.mark.integration
def test_load_dgraph_masked_labels_are_binary(dgraph_data):
    labelled = torch.cat([
        dgraph_data.y[dgraph_data.train_mask],
        dgraph_data.y[dgraph_data.valid_mask],
        dgraph_data.y[dgraph_data.test_mask],
    ])
    assert set(labelled.unique().tolist()) <= {0, 1}


# ---------------------------------------------------------------------------
# Session B temporal batching — synthetic data, no dataset needed
# ---------------------------------------------------------------------------

def _tiny_data() -> Data:
    """5 nodes / 4 edges with deliberately unsorted timestamps."""
    x = torch.arange(5 * 3, dtype=torch.float32).reshape(5, 3)
    return Data(
        x=x,
        y=torch.tensor([0, 1, 0, 2, 3]),
        edge_index=torch.tensor([[0, 1, 2, 3], [1, 2, 3, 4]]),
        edge_attr=torch.tensor([9.0, 2.0, 7.0, 5.0]).unsqueeze(1),
        edge_type=torch.tensor([0, 1, 0, 2]),
        train_mask=torch.tensor([True, True, False, False, False]),
        valid_mask=torch.tensor([False, False, True, False, False]),
        test_mask=torch.tensor([False, False, False, True, False]),
    )


def test_build_temporal_data_sorts_edges_chronologically():
    from train_dgraph_tgn import build_temporal_data

    td, _ = build_temporal_data(_tiny_data())
    # integer time on purpose: TGNMemory's last_update buffer is Long
    assert td.t.dtype == torch.long
    assert torch.equal(td.t, torch.tensor([2, 5, 7, 9]))
    assert td.edge_index_all.shape == (2, 4)
    # first sorted edge is the original (1 -> 2)
    assert td.edge_index_all[:, 0].tolist() == [1, 2]


def test_build_temporal_data_one_hot_messages_follow_sorted_order():
    from train_dgraph_tgn import build_temporal_data

    td, raw_msg_dim = build_temporal_data(_tiny_data())
    # tiny data has edge types 0..2, so width is max+1 = 3
    assert raw_msg_dim == 3
    assert td.msg.shape == (4, raw_msg_dim)
    assert torch.allclose(td.msg.sum(dim=1), torch.ones(4))          # one-hot rows
    # timestamps 2,5,7,9 came from edge types 1,2,0,0
    assert td.msg.argmax(dim=1).tolist() == [1, 2, 0, 0]


def test_build_temporal_data_carries_node_attributes():
    from train_dgraph_tgn import build_temporal_data

    src = _tiny_data()
    td, _ = build_temporal_data(src)
    assert torch.equal(td.x, src.x)
    assert torch.equal(td.y, src.y)
    assert torch.equal(td.train_mask, src.train_mask)
    assert torch.equal(td.valid_mask, src.valid_mask)
    assert torch.equal(td.test_mask, src.test_mask)


def test_tgn_forward_produces_two_class_logits():
    from torch_geometric.nn.models.tgn import LastNeighborLoader

    from train_dgraph_tgn import TGNFraudClassifier, build_temporal_data

    td, raw_msg_dim = build_temporal_data(_tiny_data())
    torch.manual_seed(0)
    model = TGNFraudClassifier(num_nodes=5, node_dim=td.x.size(1),
                               raw_msg_dim=raw_msg_dim)
    neighbor_loader = LastNeighborLoader(5, size=2)
    neighbor_loader.insert(td.src, td.dst)

    seeds = torch.arange(5)
    z, expanded = model.embed(seeds, td.x, neighbor_loader, td.t, td.msg)
    assert z.shape[1] == 64
    assert z.shape[0] == expanded.size(0) >= seeds.size(0)   # loader expands n_id
    rows = model._rows_for(seeds, expanded, num_nodes=5)
    out = model.head(z[rows])
    assert out.shape == (5, 2)


def test_tgn_memory_update_changes_embeddings():
    from train_dgraph_tgn import TGNFraudClassifier, build_temporal_data

    td, raw_msg_dim = build_temporal_data(_tiny_data())
    torch.manual_seed(0)
    model = TGNFraudClassifier(num_nodes=5, node_dim=td.x.size(1),
                               raw_msg_dim=raw_msg_dim)
    before, _ = model.memory(torch.tensor([0, 1]))

    model.memory.update_state(td.src[:1], td.dst[:1], td.t[:1], td.msg[:1])
    after, last_update = model.memory(torch.tensor([0, 1]))

    assert not torch.allclose(before, after)
    # the updated edge is 1 -> 2 at t=2.0 (earliest after sorting), so node 1
    # carries the new timestamp while untouched node 0 keeps t=0
    assert int(td.src[0]) == 1
    assert float(last_update[1]) == float(td.t[0])
    assert float(last_update[0]) == 0.0


def test_temporal_data_loader_batch_exposes_tgn_attributes():
    """The training loop reads batch.n_id/src/dst/t/msg — verify that contract
    for real, since a wrong attribute name would only surface mid-training."""
    from torch_geometric.loader import TemporalDataLoader

    from train_dgraph_tgn import build_temporal_data

    td, raw_msg_dim = build_temporal_data(_tiny_data())
    loader = TemporalDataLoader(td, batch_size=2)
    batches = list(loader)
    assert len(batches) == 2

    batch = batches[0]
    for attr in ("n_id", "src", "dst", "t", "msg"):
        assert hasattr(batch, attr), attr
    assert batch.src.numel() == 2 and batch.dst.numel() == 2
    assert batch.t.shape == (2,) and batch.msg.shape == (2, raw_msg_dim)
    assert batch.n_id.numel() >= 2
    # chronological streaming: first batch carries the two earliest edges
    assert batch.t.tolist() == [2, 5]


def test_tgn_training_step_runs_on_a_temporal_batch():
    """One full loop body on synthetic data: embed, head, loss, memory update."""
    from torch_geometric.loader import TemporalDataLoader
    from torch_geometric.nn.models.tgn import LastNeighborLoader

    from train_dgraph_tgn import TGNFraudClassifier, build_temporal_data

    td, raw_msg_dim = build_temporal_data(_tiny_data())
    torch.manual_seed(0)
    model = TGNFraudClassifier(num_nodes=5, node_dim=td.x.size(1),
                               raw_msg_dim=raw_msg_dim)
    neighbor_loader = LastNeighborLoader(5, size=2)

    for batch in TemporalDataLoader(td, batch_size=2):
        seeds = batch.n_id
        neighbor_loader.insert(batch.src, batch.dst)
        z, expanded = model.embed(seeds, td.x, neighbor_loader, td.t, td.msg)
        out = model.head(z)
        rows = model._rows_for(seeds, expanded, 5)
        in_train = td.train_mask[seeds]
        if in_train.any():
            loss = torch.nn.functional.cross_entropy(out[rows[in_train]],
                                                     td.y[seeds[in_train]])
            loss.backward()
        model.memory.update_state(batch.src, batch.dst, batch.t, batch.msg)


@pytest.mark.integration
@needs_dataset
@pytest.mark.parametrize("attr,expected", [
    ("x", (N_NODES, 17)),
    ("edge_index", (2, N_EDGES)),
])
def test_build_temporal_data_shapes_on_real_graph(dgraph_data, attr, expected):
    from train_dgraph_tgn import build_temporal_data

    td, raw_msg_dim = build_temporal_data(dgraph_data)
    assert tuple(getattr(td, attr).shape) == expected
    assert td.msg.shape == (N_EDGES, raw_msg_dim)
    # edge_type labels are 1..11, so the one-hot width is max+1 = 12
    assert raw_msg_dim == 12
    assert td.t.dtype == torch.long
    # edges must come out chronologically sorted
    assert bool(torch.all(td.t[1:] >= td.t[:-1]))


def test_tgn_json_and_paths_are_configured():
    from train_dgraph_tgn import BATCH_EDGES, MAX_EPOCHS, OUT_PATH

    assert OUT_PATH == os.path.join("artifacts", "dgraph_tgn_metrics.json")
    assert MAX_EPOCHS <= 10          # spec ceiling
    assert BATCH_EDGES > 0
