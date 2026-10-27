"""Unit tests for the L4 Session B TGN training module (`train_dgraph_tgn.py`).

Everything here runs on small synthetic tensors: the real DGraphFin graph is
680MB and gitignored, so no test in this file touches `data/DGraphFin`. There
is deliberately no `integration` marker — the whole module stays in the
default `make test` run and finishes in well under a second.

These tests exist because the module's three fragile contracts were all
discovered the hard way on 2026-10-14 and none of them failed loudly when
broken:

  1. `build_temporal_data` must emit chronologically sorted integer-time
     `TemporalData` — TGNMemory's `last_update` buffer is Long, so a float
     timestamp raises "Index put requires the source and destination dtypes
     match" only once training starts.
  2. `TGNFraudClassifier.embed` must return the loader's *expanded* `n_id`,
     because `LastNeighborLoader` appends sampled neighbours to the seed set.
  3. The training loop must call `memory.detach()` between batches. Without
     it the memory buffer becomes a non-leaf node shared by later batches and
     the next `loss.backward()` raises "Trying to backward through the graph
     a second time".

See MODEL_CARD.md limitation 4 and docs/L4_CLOSURE.md for the measured
head-to-head this module produced.
"""

import numpy as np
import pytest
import torch
import torch.nn.functional as F
from torch_geometric.data import Data, TemporalData
from torch_geometric.loader import TemporalDataLoader
from torch_geometric.nn.models.tgn import LastNeighborLoader

from train_dgraph_tgn import (
    GraphAttentionEmbedding,
    TGNFraudClassifier,
    _auc,
    build_temporal_data,
)

# ---------------------------------------------------------------------------
# synthetic fixtures — no dataset
# ---------------------------------------------------------------------------

# `build_temporal_data` derives the one-hot width as max(edge_type) + 1, so
# these labels are the real label range 1..11 style, not 0-based.
N_NODES_SMALL = 5
N_FEATURES_SMALL = 3


def _tiny_data() -> Data:
    """5 nodes / 4 edges, edge_type in {1, 2}, deliberately unsorted in time."""
    x = torch.arange(N_NODES_SMALL * N_FEATURES_SMALL,
                     dtype=torch.float32).reshape(N_NODES_SMALL, N_FEATURES_SMALL)
    return Data(
        x=x,
        y=torch.tensor([0, 1, 0, 1, 0]),
        edge_index=torch.tensor([[0, 1, 2, 3], [1, 2, 3, 4]]),
        # timestamps 9, 2, 7, 5 -> sorted 2, 5, 7, 9 (edge order 1, 3, 2, 0)
        edge_attr=torch.tensor([9.0, 2.0, 7.0, 5.0]).unsqueeze(1),
        edge_type=torch.tensor([1, 2, 1, 2]),
        train_mask=torch.tensor([True, True, True, False, True]),
        valid_mask=torch.tensor([False, False, False, True, False]),
        test_mask=torch.tensor([False, False, False, False, False]),
    )


BIG_N = 20
BIG_E = 30
BIG_F = 17


def _big_data(seed: int = 0) -> Data:
    """20 nodes / 30 edges / 17 features / edge_type in {1, 2, 3}.

    `train_mask` is all-True on purpose: the loss below is computed only on
    seeds that are in the train mask, so a sparse mask would make the
    regression tests pass vacuously when a batch happens to contain no
    training node.
    """
    torch.manual_seed(seed)
    x = torch.randn(BIG_N, BIG_F)
    y = torch.randint(0, 2, (BIG_N,))
    src = torch.randint(0, BIG_N, (BIG_E,))
    dst = torch.randint(0, BIG_N, (BIG_E,))
    # shuffled integer timestamps in 1..20 (duplicates allowed, stable argsort)
    t = torch.randint(1, 21, (BIG_E,)).float()
    return Data(
        x=x,
        y=y,
        edge_index=torch.stack([src, dst], dim=0),
        edge_attr=t.unsqueeze(1),
        edge_type=torch.randint(1, 4, (BIG_E,)),
        train_mask=torch.ones(BIG_N, dtype=torch.bool),
        valid_mask=torch.zeros(BIG_N, dtype=torch.bool),
        test_mask=torch.zeros(BIG_N, dtype=torch.bool),
    )


# ---------------------------------------------------------------------------
# build_temporal_data contract
# ---------------------------------------------------------------------------

def test_build_temporal_data_returns_tuple():
    """Returns (TemporalData, int) — the width is a return value, not an attr,
    because TemporalData.index_select calls .size(0) on every stored field and
    a scalar attribute would break batching."""
    out = build_temporal_data(_tiny_data())
    assert isinstance(out, tuple)
    assert len(out) == 2
    td, raw_msg_dim = out
    assert isinstance(td, TemporalData)
    assert isinstance(raw_msg_dim, int)


def test_build_temporal_data_sorts_edges_chronologically():
    td, _ = build_temporal_data(_tiny_data())
    assert isinstance(td.t.tolist(), list)
    assert td.t.tolist() == sorted(td.t.tolist())
    # the shuffled input timestamps come out in ascending order
    assert td.t.tolist() == [2, 5, 7, 9]
    # ...and the endpoints travel with their edge (t=2 was edge 1 -> 2)
    assert td.src[0].item() == 1
    assert td.dst[0].item() == 2


def test_build_temporal_data_timestamps_are_int64():
    """Regression guard: PyG's TGNMemory assigns into a Long `last_update`
    buffer, so float timestamps raise a dtype error mid-training."""
    td, _ = build_temporal_data(_tiny_data())
    assert td.t.dtype == torch.int64


def test_build_temporal_data_one_hot_width_is_max_plus_one():
    src = _tiny_data()
    td, raw_msg_dim = build_temporal_data(src)
    # labels are 1..2, not 0..1
    assert src.edge_type.max().item() == 2
    assert raw_msg_dim == 3
    assert td.msg.shape == (src.edge_index.size(1), 3)
    # one-hot rows, in the sorted edge order (edge types 2, 2, 1, 1)
    assert td.msg.argmax(dim=1).tolist() == [2, 2, 1, 1]
    assert torch.allclose(td.msg.sum(dim=1), torch.ones(4))


def test_build_temporal_data_preserves_node_features_and_masks():
    src = _tiny_data()
    td, _ = build_temporal_data(src)
    assert td.x.shape == (N_NODES_SMALL, N_FEATURES_SMALL)
    assert torch.equal(td.x, src.x)
    assert td.y.shape == (N_NODES_SMALL,)
    assert torch.equal(td.y, src.y)
    assert torch.equal(td.train_mask, src.train_mask)
    assert torch.equal(td.valid_mask, src.valid_mask)
    assert torch.equal(td.test_mask, src.test_mask)


def test_build_temporal_data_edge_index_all_shape():
    src = _tiny_data()
    td, _ = build_temporal_data(src)
    assert td.edge_index_all.shape == (2, src.edge_index.size(1))
    # the sorted stream replaces the unsorted edge_index
    assert torch.equal(td.edge_index_all[0], td.src)
    assert torch.equal(td.edge_index_all[1], td.dst)


# ---------------------------------------------------------------------------
# TGNFraudClassifier._rows_for / _auc
# ---------------------------------------------------------------------------

def test_rows_for_maps_seeds_to_expanded_positions():
    """LastNeighborLoader EXPANDS the seed set, so head() must be indexed by
    the position of each seed inside the expanded n_id, not its node id."""
    seeds = torch.tensor([2, 5])
    expanded = torch.tensor([2, 5, 7, 9])
    rows = TGNFraudClassifier._rows_for(seeds, expanded, num_nodes=10)
    assert torch.equal(rows, torch.tensor([0, 1]))


def test_auc_perfect_and_random():
    labels = np.array([0, 0, 1, 1])

    # perfect ranking: every positive scores above every negative
    pr_perfect, roc_perfect = _auc(np.array([0.1, 0.2, 0.8, 0.9]), labels)
    assert pr_perfect == pytest.approx(1.0)
    assert roc_perfect == pytest.approx(1.0)

    # worst ranking: perfectly inverted -> ROC 0.0
    _, roc_worst = _auc(np.array([0.9, 0.8, 0.2, 0.1]), labels)
    assert roc_worst == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# forward pass + the double-backward regression
# ---------------------------------------------------------------------------

def _build_model(td, raw_msg_dim, size=3, seed=0):
    """Model + an EMPTY neighbor loader.

    The loader is deliberately not seeded with edges here: `e_id` from
    `LastNeighborLoader` is a running counter into the stream it has been
    fed, and the module indexes the globally time-sorted stream with it
    (`t[e_id]`, `msg[e_id]`). Feeding the same edges twice therefore pushes
    `e_id` past the end of that stream — each edge may be inserted exactly
    once, which is what the per-batch `insert` below does.
    """
    torch.manual_seed(seed)
    model = TGNFraudClassifier(num_nodes=BIG_N, node_dim=td.x.size(1),
                               raw_msg_dim=raw_msg_dim)
    neighbor_loader = LastNeighborLoader(BIG_N, size=size)
    return model, neighbor_loader


def test_tgn_forward_smoke():
    """One embed + head pass on synthetic tensors, no training loop."""
    td, raw_msg_dim = build_temporal_data(_big_data())
    model, neighbor_loader = _build_model(td, raw_msg_dim)
    assert isinstance(model.gnn, GraphAttentionEmbedding)

    model.memory.reset_state()
    neighbor_loader.insert(td.src, td.dst)
    seeds = torch.arange(BIG_N)
    z, expanded = model.embed(seeds, td.x, neighbor_loader, td.t, td.msg)
    out = model.head(z)

    # the loader expands n_id with sampled neighbours, so z covers at least
    # the seeds; the head emits two class logits (benign / fraud)
    assert z.shape[0] == expanded.size(0)
    assert expanded.size(0) >= seeds.size(0)
    assert z.shape[1] == 64
    assert out.shape[1] == 2


def test_tgn_one_training_step_no_crash():
    """One full loop body: embed -> head -> loss -> backward -> step ->
    update_state -> detach. Regression test for the double-backward bug."""
    td, raw_msg_dim = build_temporal_data(_big_data())
    model, neighbor_loader = _build_model(td, raw_msg_dim)
    opt = torch.optim.Adam(model.parameters(), lr=1e-3)
    model.memory.reset_state()

    loader = TemporalDataLoader(td, batch_size=15)
    losses = []
    for batch in loader:
        seeds = batch.n_id
        neighbor_loader.insert(batch.src, batch.dst)
        z, expanded = model.embed(seeds, td.x, neighbor_loader, td.t, td.msg)
        out = model.head(z)
        rows = model._rows_for(seeds, expanded, BIG_N)

        in_train = td.train_mask[seeds]
        if in_train.any():
            loss = F.cross_entropy(out[rows[in_train]], td.y[seeds[in_train]])
            opt.zero_grad()
            loss.backward()
            opt.step()
            losses.append(float(loss.item()))

        model.memory.update_state(batch.src, batch.dst, batch.t, batch.msg)
        model.memory.detach()

    assert losses, "no batch produced a training loss"
    assert np.isfinite(losses).all()
    assert all(np.isscalar(loss) for loss in losses)


def test_tgn_memory_detach_prevents_double_backward():
    """Two consecutive batches must both backward cleanly.

    Without `memory.detach()` between batches, PyG 2.8.1's in-place
    `index_put` into the memory buffer makes it a non-leaf node whose graph
    the next batch re-traverses, and the second `loss.backward()` raises
    "Trying to backward through the graph a second time".
    """
    td, raw_msg_dim = build_temporal_data(_big_data())
    model, neighbor_loader = _build_model(td, raw_msg_dim)
    opt = torch.optim.Adam(model.parameters(), lr=1e-3)
    model.memory.reset_state()

    loader = TemporalDataLoader(td, batch_size=15)
    batches = list(loader)
    assert len(batches) == 2, "fixture must yield exactly two batches"

    for batch in batches:
        seeds = batch.n_id
        neighbor_loader.insert(batch.src, batch.dst)
        z, expanded = model.embed(seeds, td.x, neighbor_loader, td.t, td.msg)
        out = model.head(z)
        rows = model._rows_for(seeds, expanded, BIG_N)

        in_train = td.train_mask[seeds]
        assert in_train.any(), "fixture must put every node in the train mask"
        loss = F.cross_entropy(out[rows[in_train]], td.y[seeds[in_train]])
        opt.zero_grad()
        loss.backward()          # the second iteration is the regression
        opt.step()

        model.memory.update_state(batch.src, batch.dst, batch.t, batch.msg)
        model.memory.detach()
