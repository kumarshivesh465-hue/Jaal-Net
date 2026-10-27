"""Train a UPI-shaped fraud model on the synthetic UPI dataset.

Pipeline
--------
1. Load ``synth/out/transactions.csv`` (+ ``accounts.csv`` for sanity checks).
2. Build the sender -> receiver account graph and per-node features from the
   **training split only** (no test-edge leakage into the encoder).
3. Train a 2-layer GraphSAGE node encoder (hidden 64, output 32) jointly with
   an MLP edge head over
   ``concat(sender_emb, receiver_emb, amount, velocity_10min,
   device_change, ip_risk)`` -> 2-class logits, with
   ``BCEWithLogitsLoss(pos_weight = neg/pos)``.
4. Precompute the 32-dim embedding of **all 20,000 accounts** and export the
   edge head to ONNX.

Artifacts written
-----------------
* ``artifacts/upi_node_embeddings.npz``  keys ``account_ids`` (str array),
  ``embeddings`` (float32 [n_accounts, 32]).
* ``artifacts/upi_edge_model.onnx``      the edge classifier head.
* ``artifacts/upi_model_metrics.json``   test metrics + provenance.

Served input contract (the ONNX head)
-------------------------------------
The head is deliberately standalone: it consumes already-derived features, so
a caller reproduces exactly this preprocessing:

    sender_embedding    float32 [1, 32]   from upi_node_embeddings.npz
    receiver_embedding  float32 [1, 32]   from upi_node_embeddings.npz
    amount              float32 [1, 1]    log1p(amount_inr)     <- not raw INR
    velocity_10min      float32 [1, 1]    log1p(prior same-sender txns in 600s)
    device_change       float32 [1, 1]    0.0 / 1.0
    ip_risk             float32 [1, 1]    0.0 - 1.0
    -> score            float32 [1, 2]    logits; softmax, class 1 = fraud

No external scaler is needed at serve time: the node features are standardized
*inside* the encoder (private to training) and the four edge features are fed
on their natural log1p/0-1 scales.

CLI
---
    python train_upi_model.py           # no arguments required

CPU only, fixed seed 42. ``torch.onnx.export`` API:
https://pytorch.org/docs/stable/onnx.html#torch.onnx.export
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import time
from datetime import datetime

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from sklearn.metrics import average_precision_score, roc_auc_score

SEED = 42
DATA_DIR = os.path.join("synth", "out")
ARTIFACTS_DIR = "artifacts"

ONNX_PATH = os.path.join(ARTIFACTS_DIR, "upi_edge_model.onnx")
EMB_PATH = os.path.join(ARTIFACTS_DIR, "upi_node_embeddings.npz")
OUT_PATH = os.path.join(ARTIFACTS_DIR, "upi_model_metrics.json")

EMB_DIM = 32          # encoder output == head embedding input
HIDDEN = 64           # GraphSAGE hidden width
NODE_FEAT_DIM = 6     # degree/volume aggregates built from train edges
TAB_DIM = 4           # amount, velocity_10min, device_change, ip_risk
EPOCHS = 200
LR = 1e-3
WEIGHT_DECAY = 1e-5
EVAL_EVERY = 5
VELOCITY_WINDOW_S = 600.0
TRAIN_FRAC, VALID_FRAC = 0.8, 0.1


# ---------------------------------------------------------------------------
# 1. Data
# ---------------------------------------------------------------------------

def load_transactions(path: str) -> dict:
    """Read transactions.csv into parallel numpy arrays."""
    accounts: list[str] = []
    seen: set[str] = set()
    t, src, dst, amount, device, ip_risk, y = [], [], [], [], [], [], []

    with open(path, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            sender, receiver = row["sender_account"], row["receiver_account"]
            for acc in (sender, receiver):
                if acc not in seen:
                    seen.add(acc)
                    accounts.append(acc)
            # fromisoformat keeps the +05:30 offset honest (np.datetime64
            # drops it and warns); epoch seconds are monotonic either way
            t.append(datetime.fromisoformat(row["timestamp"]).timestamp())
            src.append(sender)
            dst.append(receiver)
            amount.append(float(row["amount_inr"]))
            device.append(1.0 if row["device_change"] == "True" else 0.0)
            ip_risk.append(float(row["ip_risk"]))
            y.append(int(row["is_fraud"]))

    accounts = sorted(accounts)
    index = {acc: i for i, acc in enumerate(accounts)}
    return {
        "accounts": accounts,
        "t": np.asarray(t, dtype=np.float64),
        "src": np.asarray([index[a] for a in src], dtype=np.int64),
        "dst": np.asarray([index[a] for a in dst], dtype=np.int64),
        "amount": np.asarray(amount, dtype=np.float64),
        "device_change": np.asarray(device, dtype=np.float64),
        "ip_risk": np.asarray(ip_risk, dtype=np.float64),
        "y": np.asarray(y, dtype=np.float64),
    }


def compute_velocity(t: np.ndarray, src: np.ndarray,
                     window_s: float = VELOCITY_WINDOW_S) -> np.ndarray:
    """Prior same-sender transaction count inside `window_s` seconds.

    Computed in O(E log E): sort by (sender, time), then for each sender group
    count how many of its earlier rows fall inside the trailing window.
    """
    velocity = np.zeros(len(t), dtype=np.float64)
    order = np.lexsort((t, src))
    src_s, t_s = src[order], t[order]

    i = 0
    n = len(t_s)
    while i < n:
        j = i
        while j < n and src_s[j] == src_s[i]:
            j += 1
        times = t_s[i:j]
        lower = np.searchsorted(times, times - window_s, side="left")
        position = np.arange(j - i)
        velocity[order[i:j]] = position - lower
        i = j
    return velocity


# ---------------------------------------------------------------------------
# 2. Model
# ---------------------------------------------------------------------------

class SAGEConv(nn.Module):
    """GraphSAGE mean-aggregation layer (Hamilton et al., 2017).

    Mirrors the layer used by train_model.py::SAGEConv / the PyG SAGEConv
    mean aggregator, but kept local so the encoder has no PyG-version surface.
    """

    def __init__(self, in_dim: int, out_dim: int):
        super().__init__()
        self.lin_self = nn.Linear(in_dim, out_dim)
        self.lin_neigh = nn.Linear(in_dim, out_dim)

    def forward(self, x: torch.Tensor, edge_index: torch.Tensor) -> torch.Tensor:
        src, dst = edge_index
        n = x.size(0)
        agg = torch.zeros_like(x)
        agg.index_add_(0, dst, x[src])
        deg = torch.zeros(n, device=x.device).index_add_(
            0, dst, torch.ones(src.size(0), device=x.device)
        )
        agg = agg / deg.clamp(min=1).unsqueeze(1)
        return F.relu(self.lin_self(x) + self.lin_neigh(agg))


class GraphSageEncoder(nn.Module):
    """2-layer GraphSAGE: node features -> 32-dim account embedding."""

    def __init__(self, node_dim: int = NODE_FEAT_DIM, hidden: int = HIDDEN,
                 emb_dim: int = EMB_DIM):
        super().__init__()
        self.conv1 = SAGEConv(node_dim, hidden)
        self.conv2 = SAGEConv(hidden, emb_dim)

    def forward(self, x: torch.Tensor, edge_index: torch.Tensor) -> torch.Tensor:
        h = self.conv1(x, edge_index)
        h = F.dropout(h, p=0.1, training=self.training)
        return self.conv2(h, edge_index)


class UPIEdgeHead(nn.Module):
    """Edge classifier exported to ONNX (68 float inputs -> 2 logits)."""

    def __init__(self, emb_dim: int = EMB_DIM, tab_dim: int = TAB_DIM):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(emb_dim * 2 + tab_dim, 64),   # 32 + 32 + 4 = 68
            nn.ReLU(),
            nn.Dropout(0.1),
            nn.Linear(64, 32),
            nn.ReLU(),
            nn.Linear(32, 2),
        )

    def forward(self, sender_embedding, receiver_embedding, amount,
                velocity_10min, device_change, ip_risk):
        z = torch.cat(
            [sender_embedding, receiver_embedding, amount,
             velocity_10min, device_change, ip_risk],
            dim=-1,
        )
        return self.net(z)


class UPIFraudModel(nn.Module):
    """GraphSAGE encoder + edge head, trained end-to-end."""

    def __init__(self):
        super().__init__()
        self.encoder = GraphSageEncoder()
        self.head = UPIEdgeHead()

    def edge_logits(self, z, src, dst, tab):
        """tab is [E, 4]; the head wants four separate [E, 1] columns."""
        return self.head(z[src], z[dst], tab[:, 0:1], tab[:, 1:2],
                         tab[:, 2:3], tab[:, 3:4])


# ---------------------------------------------------------------------------
# 3. Feature assembly and split
# ---------------------------------------------------------------------------

def _standardize(x: np.ndarray) -> np.ndarray:
    return (x - x.mean(axis=0)) / (x.std(axis=0) + 1e-6)


def build_node_features(n_nodes: int, src: np.ndarray, dst: np.ndarray,
                        amount: np.ndarray) -> np.ndarray:
    """Degree/volume aggregates over the training edges, standardized."""
    in_deg = np.bincount(dst, minlength=n_nodes).astype(np.float64)
    out_deg = np.bincount(src, minlength=n_nodes).astype(np.float64)
    sent = np.bincount(src, weights=amount, minlength=n_nodes)
    received = np.bincount(dst, weights=amount, minlength=n_nodes)
    total = in_deg + out_deg
    mean_sent = sent / np.maximum(out_deg, 1.0)

    x = np.stack(
        [in_deg, out_deg, np.log1p(sent), np.log1p(received),
         np.log1p(total), np.log1p(mean_sent)],
        axis=1,
    )
    return _standardize(x).astype(np.float32)


def temporal_split(t: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """80/10/10 by time: oldest rows train, newest rows test."""
    order = np.argsort(t, kind="stable")
    n = len(order)
    train_end = int(n * TRAIN_FRAC)
    valid_end = int(n * (TRAIN_FRAC + VALID_FRAC))
    return order[:train_end], order[train_end:valid_end], order[valid_end:]


def _auc(probs: np.ndarray, labels: np.ndarray) -> tuple[float, float]:
    return (float(average_precision_score(labels, probs)),
            float(roc_auc_score(labels, probs)))


# ---------------------------------------------------------------------------
# 4. Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", default=DATA_DIR)
    parser.add_argument("--epochs", type=int, default=EPOCHS)
    args = parser.parse_args()

    started = time.perf_counter()
    torch.manual_seed(SEED)
    np.random.seed(SEED)

    txn_path = os.path.join(args.data_dir, "transactions.csv")
    print(f"[data] loading {txn_path}")
    data = load_transactions(txn_path)
    n_nodes = len(data["accounts"])
    print(f"[data] {n_nodes:,} accounts, {len(data['y']):,} transactions, "
          f"fraud rate {data['y'].mean():.4f}")

    velocity = compute_velocity(data["t"], data["src"])
    print(f"[data] velocity_10min: mean={velocity.mean():.2f} "
          f"max={velocity.max():.0f}")

    train_idx, valid_idx, test_idx = temporal_split(data["t"])
    print(f"[split] train={len(train_idx):,} valid={len(valid_idx):,} "
          f"test={len(test_idx):,}")

    # graph + node features come from TRAIN edges only (no leakage)
    node_x = torch.tensor(
        build_node_features(n_nodes, data["src"][train_idx],
                            data["dst"][train_idx], data["amount"][train_idx])
    )
    pairs = np.unique(
        np.stack([data["src"][train_idx], data["dst"][train_idx]], axis=1),
        axis=0,
    )
    edge_index = torch.tensor(pairs.T, dtype=torch.long)
    print(f"[graph] {edge_index.size(1):,} unique training edges")

    tab = np.stack(
        [np.log1p(data["amount"]), np.log1p(velocity),
         data["device_change"], data["ip_risk"]],
        axis=1,
    ).astype(np.float32)

    def edge_arrays(idx):
        return (torch.tensor(data["src"][idx]), torch.tensor(data["dst"][idx]),
                torch.tensor(tab[idx]), torch.tensor(data["y"][idx]))

    s_tr, d_tr, tab_tr, y_tr = edge_arrays(train_idx)
    s_va, d_va, tab_va, y_va = edge_arrays(valid_idx)
    s_te, d_te, tab_te, y_te = edge_arrays(test_idx)

    n_pos = float(y_tr.sum())
    n_neg = float(len(y_tr) - n_pos)
    pos_weight = torch.tensor([n_neg / max(n_pos, 1.0)], dtype=torch.float32)
    print(f"[loss] pos_weight={float(pos_weight):.2f} "
          f"(train pos={int(n_pos):,} neg={int(n_neg):,})")

    model = UPIFraudModel()
    optimiser = torch.optim.Adam(model.parameters(), lr=LR,
                                 weight_decay=WEIGHT_DECAY)

    best_state, best_valid_ap = None, -1.0
    for epoch in range(1, args.epochs + 1):
        model.train()
        optimiser.zero_grad()
        z = model.encoder(node_x, edge_index)
        # the head emits 2 logits; class 1 is "fraud", so train that logit
        # against the binary target (softmax[1] is what evaluation reads)
        logits = model.edge_logits(z, s_tr, d_tr, tab_tr)[:, 1]
        loss = F.binary_cross_entropy_with_logits(logits, y_tr,
                                                  pos_weight=pos_weight)
        loss.backward()
        optimiser.step()

        if epoch % EVAL_EVERY == 0 or epoch == args.epochs:
            model.eval()
            with torch.no_grad():
                z = model.encoder(node_x, edge_index)
                valid_logits = model.edge_logits(z, s_va, d_va, tab_va)
                valid_probs = torch.softmax(valid_logits, dim=1)[:, 1].numpy()
            ap, roc = _auc(valid_probs, data["y"][valid_idx])
            if ap > best_valid_ap:
                best_valid_ap = ap
                best_state = {k: v.clone() for k, v in model.state_dict().items()}
            print(f"[train] epoch {epoch:3d} loss={loss.item():.4f} "
                  f"valid_auc_pr={ap:.4f} valid_auc_roc={roc:.4f}"
                  f"{' *' if ap == best_valid_ap else ''}")

    if best_state is not None:
        model.load_state_dict(best_state)
    print(f"[train] best valid AUC-PR = {best_valid_ap:.4f}")

    # ---- test metrics ----
    model.eval()
    with torch.no_grad():
        z = model.encoder(node_x, edge_index)
        test_probs = torch.softmax(
            model.edge_logits(z, s_te, d_te, tab_te), dim=1
        )[:, 1].numpy()
    test_auc_pr, test_auc_roc = _auc(test_probs, data["y"][test_idx])
    print(f"[test] AUC-PR={test_auc_pr:.4f} AUC-ROC={test_auc_roc:.4f}")
    if test_auc_roc < 0.75:
        print("[test] WARNING: AUC-ROC below 0.75 — reported as-is, "
              "no hyper-parameter tuning per spec")

    # ---- account embeddings for ALL accounts ----
    os.makedirs(ARTIFACTS_DIR, exist_ok=True)
    with torch.no_grad():
        embeddings = model.encoder(node_x, edge_index).numpy().astype(np.float32)
    norms = np.linalg.norm(embeddings, axis=1)
    if float(norms.max()) < 1e-6:
        raise RuntimeError("all account embeddings are ~zero; encoder broken")
    print(f"[embed] shape={embeddings.shape} "
          f"norm min={norms.min():.3f} mean={norms.mean():.3f} "
          f"max={norms.max():.3f}")
    np.savez(
        EMB_PATH,
        # fixed-width unicode, not dtype=object: an object array can only be
        # read back with allow_pickle=True, which is both a security smell
        # and incompatible with allow_pickle=False consumers
        account_ids=np.asarray(data["accounts"], dtype="<U16"),
        embeddings=embeddings,
    )
    print(f"[embed] wrote {EMB_PATH}")

    # ---- export the edge head to ONNX ----
    print(f"[export] writing {ONNX_PATH}")
    head = model.head.eval()
    dummy = tuple(torch.zeros(1, d) for d in (EMB_DIM, EMB_DIM, 1, 1, 1, 1))
    torch.onnx.export(
        head, dummy, ONNX_PATH,
        input_names=["sender_embedding", "receiver_embedding", "amount",
                     "velocity_10min", "device_change", "ip_risk"],
        output_names=["score"],
        dynamic_axes={n: {0: "batch"} for n in
                      ["sender_embedding", "receiver_embedding", "amount",
                       "velocity_10min", "device_change", "ip_risk", "score"]},
        opset_version=17,
        dynamo=False,
    )
    print(f"[export] done size={os.path.getsize(ONNX_PATH):,} bytes")

    # ---- ONNX Runtime equivalence check on a slice of the test set ----
    import onnxruntime as ort

    sess = ort.InferenceSession(ONNX_PATH, providers=["CPUExecutionProvider"])
    n_check = 512
    with torch.no_grad():
        head_logits = model.head(
            z[s_te[:n_check]], z[d_te[:n_check]],
            tab_te[:n_check, 0:1], tab_te[:n_check, 1:2],
            tab_te[:n_check, 2:3], tab_te[:n_check, 3:4],
        ).numpy()
    ort_logits = sess.run(
        ["score"],
        {
            "sender_embedding": z[s_te[:n_check]].numpy().astype(np.float32),
            "receiver_embedding": z[d_te[:n_check]].numpy().astype(np.float32),
            "amount": tab_te[:n_check, 0:1].numpy().astype(np.float32),
            "velocity_10min": tab_te[:n_check, 1:2].numpy().astype(np.float32),
            "device_change": tab_te[:n_check, 2:3].numpy().astype(np.float32),
            "ip_risk": tab_te[:n_check, 3:4].numpy().astype(np.float32),
        },
    )[0]
    max_delta = float(np.abs(head_logits - ort_logits).max())
    print(f"[verify] onnxruntime vs torch max logit delta = {max_delta:.2e}")
    if max_delta > 1e-3:
        raise RuntimeError(f"ONNX export mismatch: max delta {max_delta}")

    sha256 = hashlib.sha256(open(ONNX_PATH, "rb").read()).hexdigest()
    runtime_s = round(time.perf_counter() - started, 1)

    metrics = {
        "train_n": int(len(train_idx)),
        "valid_n": int(len(valid_idx)),
        "test_n": int(len(test_idx)),
        "pos_rate": round(float(data["y"].mean()), 4),
        "test_auc_pr": round(test_auc_pr, 4),
        "test_auc_roc": round(test_auc_roc, 4),
        "seed": SEED,
        "runtime_s": runtime_s,
        "model_sha256": sha256,
    }
    with open(OUT_PATH, "w", encoding="utf-8") as fh:
        json.dump(metrics, fh, indent=2)
    print(f"[metrics] wrote {OUT_PATH}")
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
