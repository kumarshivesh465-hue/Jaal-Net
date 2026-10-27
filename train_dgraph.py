"""
L4 Session A — DGraphFin loader + GraphSAGE node-classifier baseline.

Standalone on purpose: DGraph is NODE-level classification while the
verified PaySim pipeline (train_model.py) is EDGE-level. The two must not
mix, so this script touches neither and nothing here is imported by them.

Dataset: official DGraphFin release (dgraph.xinye.com), verified 2026-10-14
against its shipped Readme (3,700,550 nodes / 4,300,999 edges / classes
0..3, masks = index arrays over the labelled 0/1 nodes, 70/15/15).

Run:
    ./.venv/Scripts/python train_dgraph.py
"""

import json
import os
import time
from copy import deepcopy

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from sklearn.metrics import average_precision_score, roc_auc_score

# torch_geometric.data.Data — the standard graph container
# https://pytorch-geometric.readthedocs.io/en/latest/generated/torch_geometric.data.Data.html
from torch_geometric.data import Data
# SAGEConv — GraphSAGE convolution (Hamilton et al.), mean aggregation
# https://pytorch-geometric.readthedocs.io/en/latest/generated/torch_geometric.nn.conv.SAGEConv.html
from torch_geometric.nn import SAGEConv

DATA_PATH = os.path.join("data", "DGraphFin", "raw", "dgraphfin.npz")
ARTIFACTS_DIR = "artifacts"
OUT_PATH = os.path.join(ARTIFACTS_DIR, "dgraph_metrics.json")

SEED = 42
EPOCHS = 30
LR = 0.01
HIDDEN = 64

# Corrected spec from the 2026-10-14 gate check: edge_index is (E, 2) in the
# official packaging (transposed on load), and the "masks" are int64 index
# arrays over nodes, not boolean vectors.
EXPECTED = {
    "x":              ((3700550, 17), "float64"),
    "y":              ((3700550,), "int64"),
    "edge_index":     ((4300999, 2), "int64"),
    "edge_type":      ((4300999,), "int64"),
    "edge_timestamp": ((4300999,), "int64"),
    "train_mask":     ((857899,), "int64"),
    "valid_mask":     ((183862,), "int64"),
    "test_mask":      ((183840,), "int64"),
}


def load_dgraph(path: str = DATA_PATH) -> Data:
    """Load dgraphfin.npz into a PyG Data object. Stops on any deviation
    from the corrected spec — nothing is silently coerced."""
    if not os.path.exists(path):
        raise FileNotFoundError(f"{path} missing; see MODEL gate check 2026-10-14")

    npz = np.load(path)

    keys = set(npz.keys())
    if keys != set(EXPECTED):
        raise RuntimeError(
            f"unexpected key set.\n  found:    {sorted(keys)}\n"
            f"  expected: {sorted(EXPECTED)}"
        )

    for k, (shape, dtype) in EXPECTED.items():
        if npz[k].shape != shape:
            raise RuntimeError(f"{k}: shape {npz[k].shape} != expected {shape}")
        if npz[k].dtype != np.dtype(dtype):
            raise RuntimeError(f"{k}: dtype {npz[k].dtype} != expected {dtype}")

    x = npz["x"]
    y = npz["y"]

    # z-score standardize the 17 node features across all 3.7M rows. Published
    # DGraphFin baselines standardize, and GraphSAGE underperforms materially
    # without it. This is the same transform as
    # sklearn.preprocessing.StandardScaler (https://scikit-learn.org/stable/modules/generated/sklearn.preprocessing.StandardScaler.html),
    # computed inline to keep peak memory down on the float64 3.7M x 17 array.
    mu = x.mean(axis=0)
    sd = x.std(axis=0)
    sd[sd == 0.0] = 1.0  # constant columns stay constant
    x = ((x - mu) / sd).astype(np.float32)
    # Accumulate the verification stats in float64: numpy otherwise sums a
    # float32 array in float32, so the measurement error (~1e-2 on std) would
    # be read as a standardization failure when the transform itself is exact.
    max_abs_mean = float(np.abs(x.mean(axis=0, dtype=np.float64)).max())
    max_abs_std_dev = float(np.abs(x.std(axis=0, dtype=np.float64) - 1.0).max())
    print(f"[loader] x standardized: max|mean|={max_abs_mean:.2e} "
          f"max|std-1|={max_abs_std_dev:.2e}")
    assert max_abs_mean < 1e-3
    assert max_abs_std_dev < 1e-3
    edge_index = npz["edge_index"]          # (E, 2) row-per-edge in the file
    edge_type = npz["edge_type"]
    edge_timestamp = npz["edge_timestamp"]

    n = x.shape[0]
    e = edge_index.shape[0]

    # masks arrive as index arrays -> build length-N boolean masks
    idx = {k: npz[k] for k in ("train_mask", "valid_mask", "test_mask")}
    for name, arr in idx.items():
        if arr.min() < 0 or arr.max() >= n:
            raise RuntimeError(f"{name}: index out of node range [0, {n})")
    if np.intersect1d(idx["train_mask"], idx["valid_mask"]).size or \
       np.intersect1d(idx["train_mask"], idx["test_mask"]).size or \
       np.intersect1d(idx["valid_mask"], idx["test_mask"]).size:
        raise RuntimeError("masks overlap; expected a disjoint 70/15/15 split")

    bool_masks = {}
    for name, arr in idx.items():
        m = np.zeros(n, dtype=bool)
        m[arr] = True
        bool_masks[name] = torch.from_numpy(m)

    # loss/evals are binary: masked nodes must be classes 0/1 only
    masked_y = y[np.concatenate([idx["train_mask"], idx["valid_mask"], idx["test_mask"]])]
    if not set(np.unique(masked_y)).issubset({0, 1}):
        raise RuntimeError(f"masked nodes carry non-binary labels: {np.unique(masked_y)}")

    data = Data(
        x=torch.tensor(x, dtype=torch.float32),
        y=torch.tensor(y, dtype=torch.long),
        edge_index=torch.tensor(edge_index.T, dtype=torch.long),   # (2, E)
        edge_type=torch.tensor(edge_type, dtype=torch.long),
        edge_attr=torch.tensor(edge_timestamp, dtype=torch.float32).unsqueeze(1),
        train_mask=bool_masks["train_mask"],
        valid_mask=bool_masks["valid_mask"],
        test_mask=bool_masks["test_mask"],
    )

    # gate-check numbers (2026-10-14) — mandatory
    assert data.num_nodes == 3_700_550, data.num_nodes
    assert data.edge_index.shape == (2, 4_300_999), data.edge_index.shape
    assert int(data.train_mask.sum()) == 857_899
    assert int(data.valid_mask.sum()) == 183_862
    assert int(data.test_mask.sum()) == 183_840
    assert n == 3_700_550 and e == 4_300_999

    print(f"[loader] N={n:,}  E={e:,}  "
          f"masks train/valid/test={int(data.train_mask.sum()):,}/"
          f"{int(data.valid_mask.sum()):,}/{int(data.test_mask.sum()):,}")
    return data


class GraphSageNodeClassifier(nn.Module):
    """2-layer GraphSAGE, hidden=64, 2 classes (fraud vs normal)."""

    def __init__(self, in_dim: int, hidden: int = HIDDEN, num_classes: int = 2):
        super().__init__()
        self.conv1 = SAGEConv(in_dim, hidden)
        self.conv2 = SAGEConv(hidden, num_classes)

    def forward(self, data):
        h = F.relu(self.conv1(data.x, data.edge_index))
        h = F.dropout(h, p=0.5, training=self.training)
        return self.conv2(h, data.edge_index)


def _eval_masked(logits: torch.Tensor, y: torch.Tensor, mask: torch.Tensor) -> tuple:
    """AUC-PR / AUC-ROC of softmax fraud prob on the masked nodes."""
    probs = torch.softmax(logits, dim=1)[:, 1].cpu().numpy()
    truth = y[mask].cpu().numpy()
    return (
        float(average_precision_score(truth, probs[mask.cpu().numpy()])),
        float(roc_auc_score(truth, probs[mask.cpu().numpy()])),
    )


def train_gnn_node_classifier(data: Data) -> dict:
    torch.manual_seed(SEED)
    np.random.seed(SEED)

    model = GraphSageNodeClassifier(in_dim=data.x.size(1))
    opt = torch.optim.Adam(model.parameters(), lr=LR)
    # plain cross-entropy on the binary train nodes, as specified
    loss_fn = nn.CrossEntropyLoss()

    # Two snapshots on purpose: PR is noisy at 1.27% prevalence, ROC is more
    # stable. Reporting both makes the sensitivity to the selection criterion
    # visible instead of hiding it behind one number.
    best_roc = {"epoch": -1, "valid_auc_roc": -1.0, "state": None}
    best_pr = {"epoch": -1, "valid_auc_pr": -1.0, "state": None}
    final_valid = {"auc_pr": 0.0, "auc_roc": 0.0}

    for epoch in range(1, EPOCHS + 1):
        t0 = time.time()
        model.train()
        opt.zero_grad()
        logits = model(data)
        loss = loss_fn(logits[data.train_mask], data.y[data.train_mask])
        loss.backward()
        opt.step()

        model.eval()
        with torch.no_grad():
            val_pr, val_roc = _eval_masked(logits, data.y, data.valid_mask)
        final_valid = {"auc_pr": val_pr, "auc_roc": val_roc}
        if val_roc > best_roc["valid_auc_roc"]:
            best_roc = {"epoch": epoch, "valid_auc_roc": val_roc,
                        "state": deepcopy(model.state_dict())}
        if val_pr > best_pr["valid_auc_pr"]:
            best_pr = {"epoch": epoch, "valid_auc_pr": val_pr,
                       "state": deepcopy(model.state_dict())}
        print(f"  epoch {epoch:2d}  loss={loss.item():.4f}  "
              f"valid auc_pr={val_pr:.4f} auc_roc={val_roc:.4f}  "
              f"({time.time()-t0:.1f}s)")

    # each snapshot (plus the final epoch) gets scored on the test set
    snapshots = {
        "test_at_best_roc": {**best_roc, "state": best_roc["state"]},
        "test_at_best_pr": {**best_pr, "state": best_pr["state"]},
        "test_at_final": {"epoch": EPOCHS, "state": deepcopy(model.state_dict())},
    }
    scored = {}
    for name, snap in snapshots.items():
        model.load_state_dict(snap["state"])
        model.eval()
        with torch.no_grad():
            logits = model(data)
            test_pr, test_roc = _eval_masked(logits, data.y, data.test_mask)
        scored[name] = {"epoch": snap["epoch"],
                        "auc_pr": round(test_pr, 4),
                        "auc_roc": round(test_roc, 4)}

    results = {
        "model": "graphsage_node_dgraphfin",
        "dataset": "DGraphFin (official, dgraph.xinye.com)",
        "seed": SEED,
        "epochs": EPOCHS,
        "lr": LR,
        "hidden": HIDDEN,
        "n_nodes": int(data.num_nodes),
        "n_edges": int(data.num_edges),
        "test_at_best_roc": scored["test_at_best_roc"],
        "test_at_best_pr": scored["test_at_best_pr"],
        "final_epoch": {"epoch": EPOCHS,
                        "valid_auc_pr": round(final_valid["auc_pr"], 4),
                        "valid_auc_roc": round(final_valid["auc_roc"], 4)},
        "test_at_final": scored["test_at_final"],
        "test_base_rate": round(
            float(data.y[data.test_mask].float().mean()), 6),
    }
    os.makedirs(ARTIFACTS_DIR, exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(f"[write] {OUT_PATH}")
    print(json.dumps(results, indent=2))
    return results


def main():
    t0 = time.time()
    data = load_dgraph()
    print(f"[train] GraphSAGE node classifier, {EPOCHS} epochs, CPU full-batch")
    train_gnn_node_classifier(data)
    print(f"[done] total {time.time()-t0:.0f}s")


if __name__ == "__main__":
    main()
