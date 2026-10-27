"""
L4 Session B — TGN baseline vs the Session A GraphSAGE baseline.

Goal: close MODEL_CARD limitation 4 ("no temporal attention — GraphSAGE
shipped instead of TGAT/TGN") by measuring what temporal memory buys over
plain GraphSAGE on DGraphFin, same nodes, same split, same test population.

Sampler note (verified 2026-10-14, not assumed):
  - `NeighborLoader` REJECTS `TemporalData` outright:
      ValueError: Expected a 'Data', 'HeteroData', or a tuple of
      'FeatureStore' and 'GraphStore' (got TemporalData)
  - Temporal sampling on a plain `Data` (time_attr=...) needs compiled
    extensions ("'NeighborSampler' requires either 'pyg-lib' or
    'torch-sparse'"), and neither installs here: pyg-lib has no
    distribution for Windows/py3.11, torch-sparse fails to build.
  So temporal mini-batching uses PyG's own TGN mechanism instead:
  `TemporalDataLoader` (time-ordered edge batches) + `LastNeighborLoader`,
  which is exactly what the canonical PyG TGN example does.

Full graph, no subsampling (user decision 2026-10-14): a uniform 500K node
sample retained only 78,950 / 4,300,999 edges = 1.84%, far below the 10%
gate, mean degree 0.32 vs 2.32.

Run (single arm — the GraphSAGE control is NOT re-run; 0.6483 from commit
104ea46 is the reference):
    ./.venv/Scripts/python train_dgraph_tgn.py
"""

import json
import os
import time

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from sklearn.metrics import average_precision_score, roc_auc_score

# TemporalData / TemporalDataLoader — temporal graph batching
# https://pytorch-geometric.readthedocs.io/en/latest/generated/torch_geometric.data.TemporalData.html
# https://pytorch-geometric.readthedocs.io/en/latest/generated/torch_geometric.loader.TemporalDataLoader.html
from torch_geometric.data import TemporalData
from torch_geometric.loader import TemporalDataLoader
# TGNMemory / TransformerConv — memory module + attention aggregation
# https://pytorch-geometric.readthedocs.io/en/latest/generated/torch_geometric.nn.models.TGNMemory.html
# https://pytorch-geometric.readthedocs.io/en/latest/generated/torch_geometric.nn.conv.TransformerConv.html
from torch_geometric.nn import TGNMemory, TransformerConv
# TGN building blocks shipped with PyG (same modules the official TGN example
# uses): https://github.com/pyg-team/pytorch_geometric/blob/master/examples/tgn.py
from torch_geometric.nn.models.tgn import (
    IdentityMessage,
    LastNeighborLoader,
    MeanAggregator,
    TimeEncoder,
)

from train_dgraph import load_dgraph

SEED = 42
MEMORY_DIM = 64
TIME_DIM = 64
# DGraphFin edge_type labels are 1..11 (verified 2026-10-14: min 1, max 11,
# 11 distinct values) — NOT 0..10 — so the one-hot width is derived from the
# data as max+1 rather than hardcoded.
LR = 1e-3
BATCH_EDGES = 100_000     # edges per temporal batch (CPU-tuned)
NEIGHBORS = 10            # last-neighbour sample size per node
MAX_EPOCHS = 10           # hard ceiling from the spec
BUDGET_S = 45 * 60        # wall-clock budget; epoch 1 runtime sets the real cap
OUT_PATH = os.path.join("artifacts", "dgraph_tgn_metrics.json")


class GraphAttentionEmbedding(nn.Module):
    """Neighbour aggregation with relative-time edge features.

    Same structure as the `GraphAttentionEmbedding` in the official PyG TGN
    example (https://github.com/pyg-team/pytorch_geometric/blob/master/examples/tgn.py):
    TransformerConv with edge_attr = [time_encoding(t_src - t_edge), raw_msg].
    """

    def __init__(self, in_channels: int, out_channels: int, msg_dim: int,
                 time_enc: TimeEncoder):
        super().__init__()
        self.time_enc = time_enc
        edge_dim = msg_dim + time_enc.out_channels
        self.conv = TransformerConv(in_channels, out_channels // 2, heads=2,
                                    dropout=0.1, edge_dim=edge_dim)

    def forward(self, x, last_update, edge_index, t, msg):
        rel_t = last_update[edge_index[0]] - t
        rel_t_enc = self.time_enc(rel_t.to(x.dtype))
        edge_attr = torch.cat([rel_t_enc, msg], dim=-1)
        return self.conv(x, edge_index, edge_attr)


class TGNFraudClassifier(nn.Module):
    """TGNMemory (64) + GraphAttentionEmbedding + 2-class MLP head.

    Node features are concatenated to the memory state on purpose: GraphSAGE
    in Session A saw all 17 standardized features, so giving TGN the same
    inputs keeps the head-to-head a comparison of the architecture, not of
    the input set.
    """

    def __init__(self, num_nodes: int, node_dim: int, raw_msg_dim: int,
                 memory_dim: int = MEMORY_DIM, time_dim: int = TIME_DIM):
        super().__init__()
        # TGNMemory(num_nodes, raw_msg_dim, memory_dim, time_dim, message_module, aggregator_module)
        self.memory = TGNMemory(
            num_nodes, raw_msg_dim, memory_dim, time_dim,
            message_module=IdentityMessage(raw_msg_dim, memory_dim, time_dim),
            aggregator_module=MeanAggregator(),
        )
        self.time_enc = TimeEncoder(time_dim)
        self.gnn = GraphAttentionEmbedding(memory_dim + node_dim, memory_dim,
                                           msg_dim=raw_msg_dim, time_enc=self.time_enc)
        self.head = nn.Sequential(
            nn.Linear(memory_dim, 64), nn.ReLU(), nn.Linear(64, 2),
        )

    def embed(self, seed_nodes, x, neighbor_loader, t, msg):
        """Embed `seed_nodes` plus the neighbours the loader samples for them.

        LastNeighborLoader.__call__ returns (n_id, edge_index, e_id) — it
        EXPANDS n_id with the sampled neighbours (verified against the PyG
        source on 2026-10-14), so callers must map results back through the
        returned `n_id`. `e_id` indexes the edges inserted so far, which are
        the globally time-sorted ones (insertion is chronological here).
        """
        n_id, edge_index, e_id = neighbor_loader(seed_nodes)
        z, last_update = self.memory(n_id)              # (n, memory_dim), (n,)
        z = torch.cat([z, x[n_id]], dim=-1)
        z = self.gnn(z, last_update, edge_index, t[e_id], msg[e_id])
        return z, n_id

    @staticmethod
    def _rows_for(seed_nodes, expanded, num_nodes) -> torch.Tensor:
        """Row indices of `seed_nodes` inside the expanded embedding tensor."""
        assoc = torch.full((num_nodes,), -1, dtype=torch.long)
        assoc[expanded] = torch.arange(expanded.size(0))
        return assoc[seed_nodes]


def build_temporal_data(data) -> tuple:
    """Time-sorted TemporalData for temporal mini-batching, plus the one-hot width.

    Returns (td, raw_msg_dim). The width is returned rather than stored on
    `td`: TemporalData.index_select calls .size(0) on every stored attribute,
    so a plain int attribute breaks batching (verified 2026-10-14).

    Edges are sorted by edge_timestamp so TemporalDataLoader yields batches in
    chronological order (TGN's protocol). Node features/labels/masks are kept
    as-is; only the edge stream order changes.

    `t` is cast to int64 on purpose: PyG's TGNMemory registers its
    `last_update` buffer as Long and assigns timestamps into it, so float
    times raise "Index put requires the source and destination dtypes match"
    (verified 2026-10-14). DGraphFin timestamps are integers 1..821, so the
    cast is lossless; the attention embedding casts back to float for the
    time encoding.
    """
    ei = data.edge_index
    order = torch.argsort(data.edge_attr.squeeze(1), stable=True)

    src, dst = ei[0][order], ei[1][order]
    t_sorted = data.edge_attr.squeeze(1)[order].long()
    edge_type = data.edge_type[order]

    # raw message = one-hot(edge_type). Labels are 1..11, so width = max+1.
    raw_msg_dim = int(edge_type.max().item()) + 1
    msg = F.one_hot(edge_type, num_classes=raw_msg_dim).float()

    td = TemporalData(src=src, dst=dst, t=t_sorted, msg=msg)
    td.x = data.x
    td.y = data.y
    td.train_mask = data.train_mask
    td.valid_mask = data.valid_mask
    td.test_mask = data.test_mask
    td.edge_index_all = torch.stack([src, dst], dim=0)
    return td, raw_msg_dim


def _auc(probs: np.ndarray, labels: np.ndarray) -> tuple:
    return (float(average_precision_score(labels, probs)),
            float(roc_auc_score(labels, probs)))


def train_tgn(td: TemporalData, raw_msg_dim: int) -> dict:
    torch.manual_seed(SEED)
    np.random.seed(SEED)

    num_nodes = int(td.x.size(0))
    y, x = td.y, td.x
    model = TGNFraudClassifier(num_nodes, node_dim=x.size(1),
                               raw_msg_dim=raw_msg_dim)
    opt = torch.optim.Adam(model.parameters(), lr=LR)

    epochs_run, runtime_s = 0, 0.0
    cap, epochs_note = MAX_EPOCHS, ""
    t_start = time.time()

    while epochs_run < cap:
        epochs_run += 1
        t_epoch = time.time()
        model.train()
        model.memory.reset_state()                      # fresh memory each epoch
        neighbor_loader = LastNeighborLoader(num_nodes, size=NEIGHBORS)
        loader = TemporalDataLoader(td, batch_size=BATCH_EDGES)

        losses = []
        n_batches = len(loader)
        print(f"[epoch {epochs_run}] starting, {n_batches} batches expected",
              flush=True)
        for b, batch in enumerate(loader, 1):
            seeds = batch.n_id
            neighbor_loader.insert(batch.src, batch.dst)
            z, expanded = model.embed(seeds, x, neighbor_loader, td.t, td.msg)
            out = model.head(z)
            rows = model._rows_for(seeds, expanded, num_nodes)

            batch_loss = None
            in_train = td.train_mask[seeds]
            if in_train.any():
                loss = F.cross_entropy(out[rows[in_train]], y[seeds[in_train]])
                opt.zero_grad()
                loss.backward()
                opt.step()
                batch_loss = float(loss.item())
                losses.append(batch_loss)

            # memory update AFTER the forward pass (canonical TGN ordering:
            # the current batch's own edges must not inform its own embeddings)
            model.memory.update_state(batch.src, batch.dst, batch.t, batch.msg)

            # Detach the memory from autograd before the next batch. In PyG
            # 2.8.1, update_state writes a grad-tracking tensor into the
            # `memory` buffer with an in-place index_put, which turns the
            # buffer into a NON-LEAF node (grad_fn=IndexPutBackward0) whose
            # graph is shared by every later batch's forward pass. Without
            # this detach, the next backward re-traverses an already-freed
            # subgraph: RuntimeError "Trying to backward through the graph a
            # second time" at loss.backward() (reproduced 2026-10-14 on a
            # 3K-node synthetic graph: no detach -> crash on batch 3's
            # backward; with detach -> all batches pass and the GRU/msg
            # gradients stay non-zero).
            model.memory.detach()

            if b % 10 == 0:
                loss_txt = "n/a" if batch_loss is None else f"{batch_loss:.4f}"
                print(f"[epoch {epochs_run}] batch {b}/{n_batches}  "
                      f"loss={loss_txt}", flush=True)

        epoch_s = time.time() - t_epoch
        print(f"  epoch {epochs_run:2d}  batches={len(loader)}  "
              f"loss={np.mean(losses):.4f}  ({epoch_s/60:.2f} min)")

        # wall-clock budget: epoch 1 fixes the cap (<= MAX_EPOCHS)
        if epochs_run == 1:
            affordable = max(1, int(BUDGET_S // max(epoch_s, 1e-9)))
            cap = min(MAX_EPOCHS, affordable)
            epochs_note = (f"capped at {cap} epoch(s): epoch 1 took "
                           f"{epoch_s/60:.1f} min on CPU within a "
                           f"{BUDGET_S//60} min budget")
        print(f"[budget] {epochs_note}")

    runtime_s = time.time() - t_start

    # ---- evaluation on the FULL test mask (183,840 nodes), same population
    # as Session A, so the head-to-head against 0.6483 is apples-to-apples.
    #
    # Two constraints, both observed on 2026-10-14 rather than assumed:
    #
    #  1. Do NOT call model.eval(). That calls TGNMemory.train(False), which
    #     flushes the message store into the memory buffer for ALL 3,700,550
    #     nodes in one GRU call, and died with
    #       RuntimeError: DefaultCPUAllocator: not enough memory: you tried to
    #       allocate 2842022400 bytes
    #     (= 3,700,550 x 64 x 4 bytes x 3 gates, exactly). Leaving the memory
    #     module in train mode keeps the on-the-fly update path
    #     (forward -> _get_updated_memory), which computes memory only for the
    #     nodes actually queried. The dropout lives in `gnn`, so the dropout
    #     layers are switched off explicitly instead.
    #
    #  2. Evaluate in chunks. One full-mask forward expands to ~1.8M nodes
    #     through LastNeighborLoader and needs ~0.5-1 GB for the
    #     TransformerConv edge attributes alone; chunking keeps the peak well
    #     below what a single training batch already sustained.
    model.gnn.eval()
    model.head.eval()
    model.memory.train()   # explicit: no store flush, no 2.84 GB allocation
    test_idx = td.test_mask.nonzero(as_tuple=True)[0]
    EVAL_CHUNK = 10_000
    probs_parts = []
    with torch.no_grad():
        for start in range(0, test_idx.numel(), EVAL_CHUNK):
            chunk = test_idx[start:start + EVAL_CHUNK]
            # neighbour state as accumulated by the final training epoch (the
            # canonical TGN protocol: evaluation uses memory built from the
            # observed stream; no test labels are ever used in the loss)
            z, expanded = model.embed(chunk, x, neighbor_loader, td.t, td.msg)
            rows = model._rows_for(chunk, expanded, num_nodes)
            probs_parts.append(
                torch.softmax(model.head(z[rows]), dim=1)[:, 1].cpu())
    probs = torch.cat(probs_parts).numpy()
    labels = y[test_idx].cpu().numpy()
    test_pr, test_roc = _auc(probs, labels)

    results = {
        "graph": {
            "nodes": num_nodes,
            "edges": int(td.edge_index_all.shape[1]),
            "subsample_nodes": None,
            "subsample_edges": None,
            "subsample_fraction": 1.0,
            "note": ("full graph; no subsampling. A uniform 500K node sample "
                     "retained 78,950/4,300,999 edges = 1.84%, below the 10% "
                     "gate, so full-graph training was chosen (2026-10-14)"),
        },
        "tgn": {
            "test_auc_pr": round(test_pr, 4),
            "test_auc_roc": round(test_roc, 4),
            "epochs": MAX_EPOCHS,
            "epochs_run": epochs_run,
            "runtime_s": round(runtime_s, 1),
            "epochs_note": epochs_note,
            "raw_msg_dim": int(raw_msg_dim),
            "batch_edges": BATCH_EDGES,
            "neighbors": NEIGHBORS,
            "model": "TGNMemory(64) + GraphAttentionEmbedding + MLP head",
        },
        "graphsage_full_baseline": {
            "test_auc_pr": 0.0195,
            "test_auc_roc": 0.6483,
            "note": "from 104ea46, 30 epochs, final epoch; best-ROC epoch 29 = 0.6457",
        },
        "eval_mask": {"name": "test_mask", "n": int(test_idx.numel())},
    }

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as fh:
        json.dump(results, fh, indent=2)
    print(f"[write] {OUT_PATH}")
    print(json.dumps(results, indent=2))
    return results


def main():
    data = load_dgraph()
    td, raw_msg_dim = build_temporal_data(data)
    print(f"[tgn] nodes={td.x.size(0):,} edges={td.msg.size(0):,} "
          f"raw_msg_dim={raw_msg_dim} (one-hot width = max edge_type + 1) "
          f"batch_edges={BATCH_EDGES:,}")
    train_tgn(td, raw_msg_dim)


if __name__ == "__main__":
    main()
