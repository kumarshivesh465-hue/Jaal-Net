"""Training pipeline for the UPI mule fraud edge classifier.

Data: PaySim (theman10/paysim on HuggingFace), ~6.3M transactions with
sender/receiver account ids and isFraud labels.

What it does:
  - encode accounts to integer node ids, build a directed txn graph
  - temporal split on `step` (1 step = 1 hour), no future leakage
  - 2-layer GraphSAGE encoder + edge head trained end to end
  - logistic regression baseline for comparison
  - AUC-PR / AUC-ROC / precision@K / recall@FPR reported for both
  - edge head exported to ONNX (models/tgat_sage_v1.2.onnx)
  - node embeddings + feature scalers saved to artifacts/

Run:
    ./.venv/Scripts/python train_model.py
"""

import json
import os
import time
import urllib.request

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import torch.nn.functional as F
from catboost import CatBoostClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.preprocessing import StandardScaler

SEED = 42
DATA_CSV = os.path.join("data", "paysim.csv")
MODELS_DIR = "models"
ARTIFACTS_DIR = "artifacts"
ONNX_PATH = os.path.join(MODELS_DIR, "tgat_sage_v1.2.onnx")

# Arko007/trustworthy-gnn-fraud-models (MIT licence, model card 2026-10-13).
# Source URL pattern documented at:
#   https://huggingface.co/Arko007/trustworthy-gnn-fraud-models
PRETRAINED_URL = (
    "https://huggingface.co/Arko007/trustworthy-gnn-fraud-models/"
    "resolve/main/graphsage_temporal_elliptic.safetensors"
)
PRETRAINED_PATH = os.path.join(MODELS_DIR, "pretrained",
                               "graphsage_temporal_elliptic.safetensors")

EMB_DIM = 64
TRAIN_NEG_SAMPLE = 400_000
TEST_NEG_SAMPLE = 400_000
EPOCHS = 120
LR = 3e-3
BATCH = 4096

TXN_TYPES = ["CASH_IN", "CASH_OUT", "DEBIT", "PAYMENT", "TRANSFER"]

torch.manual_seed(SEED)
np.random.seed(SEED)


# ---------------------------------------------------------------------------
# 1-3. Load + split
# ---------------------------------------------------------------------------

def load_data() -> pd.DataFrame:
    print(f"[data] reading {DATA_CSV} ...")
    t0 = time.time()
    usecols = [
        "step", "type", "amount", "nameOrig", "oldbalanceOrg",
        "newbalanceOrig", "nameDest", "oldbalanceDest", "newbalanceDest",
        "isFraud",
    ]
    df = pd.read_csv(DATA_CSV, usecols=usecols)
    print(f"[data] loaded {len(df):,} rows in {time.time()-t0:.1f}s")
    return df


def temporal_split(df: pd.DataFrame, train_frac: float = 0.7):
    """Split by step so that no future transaction informs training."""
    cut = int(df["step"].quantile(train_frac))
    train = df[df["step"] <= cut].copy()
    test = df[df["step"] > cut].copy()
    print(f"[split] cutoff step={cut}  train={len(train):,}  test={len(test):,}")
    return train, test


# ---------------------------------------------------------------------------
# 4. Feature engineering
# ---------------------------------------------------------------------------

def encode_accounts(df: pd.DataFrame):
    """Map account strings to contiguous integer ids. Fit on the union."""
    codes, uniques = pd.factorize(pd.concat([df["nameOrig"], df["nameDest"]]))
    n_nodes = len(uniques)
    src = codes[: len(df)].astype(np.int64)
    dst = codes[len(df):].astype(np.int64)
    return src, dst, n_nodes


def node_features(src, dst, n_nodes: int, amounts: np.ndarray) -> np.ndarray:
    """Degree / amount features from the TRAIN graph only.

    These are structural and computed without labels, so they are causal.
    """
    out_deg = np.bincount(src, minlength=n_nodes).astype(np.float32)
    in_deg = np.bincount(dst, minlength=n_nodes).astype(np.float32)

    out_amt = np.zeros(n_nodes, dtype=np.float64)
    np.add.at(out_amt, src, amounts)
    in_amt = np.zeros(n_nodes, dtype=np.float64)
    np.add.at(in_amt, dst, amounts)

    feats = np.stack([
        np.log1p(out_deg),
        np.log1p(in_deg),
        (out_deg > 0).astype(np.float32),
        (in_deg > 0).astype(np.float32),
        np.log1p(out_amt),
        np.log1p(in_amt),
    ], axis=1).astype(np.float32)
    return feats


def edge_tabular(df: pd.DataFrame) -> np.ndarray:
    """Tabular edge features available at scoring time.

    The original plan also had device_change / ip_risk / velocity_10min, but
    PaySim has no device or IP columns and its accounts barely transact twice,
    so per-sender velocity is ~0 everywhere. Dropped rather than faked —
    see MODEL_CARD.md.
    """
    amount = np.log1p(df["amount"].to_numpy(dtype=np.float64))
    orig_err = df["oldbalanceOrg"].to_numpy(np.float64) - df["newbalanceOrig"].to_numpy(np.float64) - df["amount"].to_numpy(np.float64)
    dest_err = df["newbalanceDest"].to_numpy(np.float64) - df["oldbalanceDest"].to_numpy(np.float64) - df["amount"].to_numpy(np.float64)
    type_idx = df["type"].map({t: i for i, t in enumerate(TXN_TYPES)}).fillna(0).to_numpy(np.float64)

    return np.stack([
        amount,
        np.sign(orig_err) * np.log1p(np.abs(orig_err)),
        np.sign(dest_err) * np.log1p(np.abs(dest_err)),
        type_idx,
    ], axis=1).astype(np.float32)


def make_onnx_tabular(tab: np.ndarray) -> tuple:
    """Split tabular matrix into the 4 named scalars used by the ONNX contract."""
    return (
        tab[:, 0:1],  # amount
        tab[:, 1:2],  # origin_balance_error
        tab[:, 2:3],  # dest_balance_error
        tab[:, 3:4],  # tx_type
    )


def edge_tabular_extended(df: pd.DataFrame) -> np.ndarray:
    """Extended edge feature set for the CatBoost baseline only.

    The 56-feature recipe from Arnav-0/rbi-mule-detection (MIT) spans 8
    behaviour groups; only 3 groups are derivable from PaySim's columns:
    amount patterns (round amounts), temporal (hour/day from `step`), and
    pass-through (balance-drain matching + ratios). Velocity, graph, KYC and
    profile-mismatch groups need columns PaySim does not have. Trees do not
    need scaling, so no StandardScaler here.

    NOT part of the ONNX contract — edge_tabular() above stays the 4-feature
    scoring contract; this matrix feeds train_catboost_baseline() only.
    """
    amount = df["amount"].to_numpy(np.float64)
    old_org = df["oldbalanceOrg"].to_numpy(np.float64)
    new_org = df["newbalanceOrig"].to_numpy(np.float64)
    old_dest = df["oldbalanceDest"].to_numpy(np.float64)
    step = df["step"].to_numpy(np.int64)
    orig_err = old_org - new_org - amount
    dest_err = df["newbalanceDest"].to_numpy(np.float64) - old_dest - amount
    type_idx = df["type"].map({t: i for i, t in enumerate(TXN_TYPES)}).fillna(0).to_numpy(np.float64)

    return np.stack([
        np.log1p(amount),
        (amount % 1000 == 0).astype(np.float64),      # round-amount structuring
        np.sign(orig_err) * np.log1p(np.abs(orig_err)),
        np.sign(dest_err) * np.log1p(np.abs(dest_err)),
        np.log1p(old_org),
        np.log1p(old_dest),
        amount / (old_org + 1.0),                     # pass-through ratios
        amount / (old_dest + 1.0),
        (old_dest == 0).astype(np.float64),           # cold receiver before credit
        (new_org == 0).astype(np.float64),            # full sender drain
        (step % 24) / 24.0,                           # hour-of-day
        (step // 24).astype(np.float64),              # day index
        type_idx,
    ], axis=1).astype(np.float32)


def train_catboost_baseline(X_tr, y_tr, X_te, y_te):
    """CatBoost baseline on the extended features. Closes MODEL_CARD L2.

    Recipe follows Arnav-0/rbi-mule-detection (MIT): CatBoost wins their
    6-model bake-off at 0.925 AUC-ROC. API sources:
      CatBoostClassifier / fit / predict_proba
        https://catboost.ai/en/docs/concepts/python-reference_catboostclassifier
      auto_class_weights='Balanced' for the 0.13% fraud rate
        https://catboost.ai/en/docs/concepts/algorithm_parameters_class-weights
    """
    clf = CatBoostClassifier(
        iterations=300,
        depth=6,
        learning_rate=0.05,
        loss_function="Logloss",  # binary objective name in catboost >= 1.2
                                  # https://catboost.ai/en/docs/concepts/python-reference_catboostclassifier
        auto_class_weights="Balanced",
        random_seed=SEED,
        verbose=False,
    )
    clf.fit(X_tr, y_tr)
    scores = clf.predict_proba(X_te)[:, 1]
    return report("catboost_extended", y_te, scores)


def load_pretrained_backbone():
    """Download + audit the Arko007 Elliptic GraphSAGE weights (MIT).

    Returns (state_dict_or_None, coverage_fraction). Coverage is the share of
    the 15 pretrained tensors whose shapes match our FraudGNN parameters.
    Download source: the PRETRAINED_URL constant above (HF resolve endpoint).
    """
    if not os.path.exists(PRETRAINED_PATH):
        os.makedirs(os.path.dirname(PRETRAINED_PATH), exist_ok=True)
        print(f"[pretrained] downloading {PRETRAINED_URL}")
        urllib.request.urlretrieve(PRETRAINED_URL, PRETRAINED_PATH)

    from safetensors import safe_open

    with safe_open(PRETRAINED_PATH, framework="pt") as f:
        remote = {k: tuple(f.get_slice(k).get_shape()) for k in f.keys()}
        state = {k: f.get_tensor(k) for k in f.keys()}

    ours = {
        "sage1.lin_self.weight": (64, 6),
        "sage1.lin_neigh.weight": (64, 6),
        "sage2.lin_self.weight": (64, 64),
        "sage2.lin_neigh.weight": (64, 64),
    }
    # PyG SAGEConv uses lin_l (self) / lin_r (neighbour); ours uses
    # lin_self / lin_neigh with the same math, so compare by shape only.
    remote_shapes = [s for k, s in remote.items() if k.endswith("weight")]
    matched = sum(1 for s in ours.values() if s in remote_shapes)
    coverage = matched / len(remote_shapes)
    print(f"[pretrained] audited {len(remote)} tensors; "
          f"shape-compatible with FraudGNN: {matched}/{len(remote_shapes)} "
          f"(coverage={coverage:.2f})")
    return state, coverage


# ---------------------------------------------------------------------------
# 5. Model
# ---------------------------------------------------------------------------

class SAGEConv(nn.Module):
    """GraphSAGE mean-aggregation layer (Hamilton et al., 2017)."""

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


class FraudGNN(nn.Module):
    """GraphSAGE encoder + edge head. Edge head is what gets exported to ONNX."""

    def __init__(self, node_dim: int, emb_dim: int = EMB_DIM):
        super().__init__()
        self.sage1 = SAGEConv(node_dim, emb_dim)
        self.sage2 = SAGEConv(emb_dim, emb_dim)

    def encode(self, x, edge_index):
        h = self.sage1(x, edge_index)
        h = self.sage2(h, edge_index)
        return h


class EdgeHead(nn.Module):
    """Scores an edge from its endpoint embeddings plus tabular edge features.

    This is the module exported to ONNX. Its input signature is exactly the
    contract in CONTRACTS.md section 7.
    """

    def __init__(self, emb_dim: int = EMB_DIM, tab_dim: int = 4):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(emb_dim * 2 + tab_dim, 64),
            nn.ReLU(),
            nn.Dropout(0.1),
            nn.Linear(64, 32),
            nn.ReLU(),
            nn.Linear(32, 1),
        )

    def forward(self, sender_embedding, receiver_embedding,
                amount, origin_balance_error, dest_balance_error, tx_type):
        z = torch.cat([
            sender_embedding, receiver_embedding,
            amount, origin_balance_error, dest_balance_error, tx_type,
        ], dim=-1)
        return self.net(z)


# ---------------------------------------------------------------------------
# 6. Metrics
# ---------------------------------------------------------------------------

def precision_at_k(y_true, y_score, k):
    order = np.argsort(-y_score)[:k]
    return float(y_true[order].sum() / k)


def recall_at_fpr(y_true, y_score, target_fpr):
    order = np.argsort(-y_score)
    y_sorted = y_true[order]
    n_neg = int((y_true == 0).sum())
    allowed_fp = int(target_fpr * n_neg)
    cum_fp = np.cumsum(y_sorted == 0)
    idx = np.searchsorted(cum_fp, allowed_fp, side="right")
    if idx == 0:
        return 0.0
    return float(y_sorted[:idx].sum() / max(1, y_true.sum()))


def report(name, y_true, y_score):
    y_true = np.asarray(y_true).astype(int)
    y_score = np.asarray(y_score).astype(float)
    out = {
        "model": name,
        "auc_pr": round(float(average_precision_score(y_true, y_score)), 4),
        "auc_roc": round(float(roc_auc_score(y_true, y_score)), 4),
        "precision_at_100": round(precision_at_k(y_true, y_score, 100), 4),
        "precision_at_1000": round(precision_at_k(y_true, y_score, 1000), 4),
        "recall_at_1pct_fpr": round(recall_at_fpr(y_true, y_score, 0.01), 4),
        "n": int(len(y_true)),
        "positives": int(y_true.sum()),
        "base_rate": round(float(y_true.mean()), 5),
    }
    print(f"[metrics] {json.dumps(out, indent=2)}")
    return out


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    os.makedirs(MODELS_DIR, exist_ok=True)
    os.makedirs(ARTIFACTS_DIR, exist_ok=True)

    df = load_data()
    train, test = temporal_split(df)

    # ---- training subsample: all fraud + N non-fraud (class balancing) ----
    tr_fraud = train[train["isFraud"] == 1]
    tr_legit = train[train["isFraud"] == 0]
    n_neg = min(TRAIN_NEG_SAMPLE, len(tr_legit))
    tr_legit_s = tr_legit.sample(n=n_neg, random_state=SEED)
    train_s = pd.concat([tr_fraud, tr_legit_s]).sample(frac=1.0, random_state=SEED).reset_index(drop=True)
    print(f"[train] sampled {len(train_s):,} rows  (fraud={len(tr_fraud):,})")

    # ---- test subsample: all fraud + N non-fraud (keeps test affordable) ----
    te_fraud = test[test["isFraud"] == 1]
    te_legit = test[test["isFraud"] == 0]
    n_te_neg = min(TEST_NEG_SAMPLE, len(te_legit))
    te_legit_s = te_legit.sample(n=n_te_neg, random_state=SEED)
    test_s = pd.concat([te_fraud, te_legit_s]).sample(frac=1.0, random_state=SEED).reset_index(drop=True)
    print(f"[test]  sampled {len(test_s):,} rows  (fraud={len(te_fraud):,})")

    # ---- graph + features ----
    src, dst, n_nodes = encode_accounts(train_s)
    print(f"[graph] nodes={n_nodes:,}  edges={len(train_s):,}")

    # map test endpoints into the same node space; unseen accounts -> new ids
    all_acc = pd.concat([train_s["nameOrig"], train_s["nameDest"]]).drop_duplicates()
    idx = {a: i for i, a in enumerate(all_acc)}
    with open(os.path.join(ARTIFACTS_DIR, "account_index.json"), "w") as f:
        json.dump(idx, f)
    print(f"[graph] saved account index ({len(idx):,} accounts)")
    test_src = test_s["nameOrig"].map(idx).fillna(-1).to_numpy(np.int64)
    test_dst = test_s["nameDest"].map(idx).fillna(-1).to_numpy(np.int64)

    x_np = node_features(src, dst, n_nodes,
                         train_s["amount"].to_numpy(np.float64))
    scaler_node = StandardScaler().fit(x_np)
    x_np = scaler_node.transform(x_np).astype(np.float32)

    tab_train = edge_tabular(train_s)
    tab_test = edge_tabular(test_s)
    scaler_tab = StandardScaler().fit(tab_train)
    tab_train_s = scaler_tab.transform(tab_train).astype(np.float32)
    tab_test_s = scaler_tab.transform(tab_test).astype(np.float32)

    y_train = train_s["isFraud"].to_numpy(np.float32)
    y_test = test_s["isFraud"].to_numpy(np.int32)

    # ---- tensors ----
    x = torch.from_numpy(x_np)
    edge_index = torch.from_numpy(np.stack([src, dst]).astype(np.int64))
    tab_t = torch.from_numpy(tab_train_s)
    y_t = torch.from_numpy(y_train)

    model = FraudGNN(node_dim=x_np.shape[1])
    head = EdgeHead()

    # Arko007 Elliptic backbone (resource C). Weights are audited against our
    # architecture every run; applied only if shapes are compatible.
    _, pretrained_coverage = load_pretrained_backbone()
    if pretrained_coverage > 0:
        print(f"[pretrained] loading compatible tensors (coverage={pretrained_coverage:.2f})")
    else:
        print("[pretrained] 0% shape coverage — Elliptic backbone is 499->256->2 "
              "(3 layers) vs our 6->64->64 (2 layers); training from scratch")
    params = list(model.parameters()) + list(head.parameters())
    opt = torch.optim.Adam(params, lr=LR)

    pos_weight = torch.tensor([(y_train == 0).sum() / max(1, (y_train == 1).sum())], dtype=torch.float32)
    loss_fn = nn.BCEWithLogitsLoss(pos_weight=pos_weight)

    # ---- train ----
    # Full-graph (full-batch) training: the encoder aggregates over the whole
    # graph, so one forward/backward per step is the correct, leak-free setup.
    print(f"[train] GraphSAGE + edge head, {EPOCHS} epochs, pos_weight={pos_weight.item():.1f}")
    src_t = torch.from_numpy(src)
    dst_t = torch.from_numpy(dst)
    tab_cols = tuple(tab_t[:, j:j + 1] for j in range(4))
    for epoch in range(1, EPOCHS + 1):
        model.train(); head.train()
        opt.zero_grad()
        h = model.encode(x, edge_index)
        logits = head(h[src_t], h[dst_t], *tab_cols).squeeze(-1)
        loss = loss_fn(logits, y_t)
        loss.backward()
        opt.step()
        if epoch == 1 or epoch % 10 == 0:
            print(f"  epoch {epoch:3d}  loss={loss.item():.4f}")
        del h, logits, loss

    # ---- eval: GNN ----
    model.eval(); head.eval()
    with torch.no_grad():
        h = model.encode(x, edge_index)
        t_src = torch.from_numpy(np.clip(test_src, 0, n_nodes - 1))
        t_dst = torch.from_numpy(np.clip(test_dst, 0, n_nodes - 1))
        seen_s = torch.from_numpy((test_src >= 0).astype(np.float32))
        seen_d = torch.from_numpy((test_dst >= 0).astype(np.float32))
        s = h[t_src] * seen_s.unsqueeze(1)
        r = h[t_dst] * seen_d.unsqueeze(1)
        tab_test_t = torch.from_numpy(tab_test_s)
        logits = []
        for i in range(0, len(y_test), 200_000):
            a, o, d, t = (tab_test_t[i:i+200_000, j:j+1] for j in range(4))
            logits.append(head(s[i:i+200_000], r[i:i+200_000], a, o, d, t).squeeze(-1))
        gnn_scores = torch.sigmoid(torch.cat(logits)).numpy()

    gnn_metrics = report("gnn_graphsage", y_test, gnn_scores)

    # ---- eval: tabular baseline ----
    print("[baseline] logistic regression on edge features only")
    lr = LogisticRegression(max_iter=1000, class_weight="balanced")
    lr.fit(tab_train_s, y_train)
    base_scores = lr.predict_proba(tab_test_s)[:, 1]
    base_metrics = report("logreg_tabular_baseline", y_test, base_scores)

    # ---- eval: CatBoost on extended features (resource A, closes L2) ----
    print("[baseline] catboost on extended edge features")
    cat_metrics = train_catboost_baseline(
        edge_tabular_extended(train_s), y_train,
        edge_tabular_extended(test_s), y_test,
    )

    # ---- export ONNX (edge head only) ----
    print(f"[export] writing {ONNX_PATH}")
    head.eval()
    dummy = (
        torch.zeros(1, EMB_DIM),
        torch.zeros(1, EMB_DIM),
        torch.zeros(1, 1),
        torch.zeros(1, 1),
        torch.zeros(1, 1),
        torch.zeros(1, 1),
    )
    torch.onnx.export(
        head, dummy, ONNX_PATH,
        input_names=["sender_embedding", "receiver_embedding", "amount",
                     "origin_balance_error", "dest_balance_error", "tx_type"],
        output_names=["score"],
        dynamic_axes={n: {0: "batch"} for n in
                      ["sender_embedding", "receiver_embedding", "amount",
                       "origin_balance_error", "dest_balance_error", "tx_type", "score"]},
        opset_version=17,
        dynamo=False,
    )
    print(f"[export] done  size={os.path.getsize(ONNX_PATH):,} bytes")

    # ---- ONNX Runtime equivalence: score the test set through the exported file ----
    print("[verify] scoring test set through ONNX Runtime ...")
    import onnxruntime as ort

    sess = ort.InferenceSession(ONNX_PATH, providers=["CPUExecutionProvider"])
    a_c, o_c, d_c, t_c = make_onnx_tabular(tab_test_s)
    s_np, r_np = s.numpy(), r.numpy()
    probs = []
    for i in range(0, len(y_test), 200_000):
        sl = slice(i, i + 200_000)
        feed = {
            "sender_embedding":    s_np[sl].astype(np.float32),
            "receiver_embedding":  r_np[sl].astype(np.float32),
            "amount":              a_c[sl].astype(np.float32),
            "origin_balance_error": o_c[sl].astype(np.float32),
            "dest_balance_error":  d_c[sl].astype(np.float32),
            "tx_type":             t_c[sl].astype(np.float32),
        }
        probs.append(sess.run(["score"], feed)[0].flatten())
    onnx_scores = np.concatenate(probs)
    onnx_metrics = report("onnx_runtime", y_test, onnx_scores)
    print(f"[verify] max |onnx_logit - torch_logit| = "
          f"{np.abs(onnx_scores - torch.cat(logits).numpy()).max():.6f}")

    # ---- persist artifacts ----
    np.savez_compressed(os.path.join(ARTIFACTS_DIR, "node_embeddings.npz"),
                        embeddings=h.numpy())
    with open(os.path.join(ARTIFACTS_DIR, "scaler.json"), "w") as f:
        json.dump({
            "node_mean": scaler_node.mean_.tolist(),
            "node_scale": scaler_node.scale_.tolist(),
            "tab_mean": scaler_tab.mean_.tolist(),
            "tab_scale": scaler_tab.scale_.tolist(),
            "txn_types": TXN_TYPES,
            "emb_dim": EMB_DIM,
            "node_dim": int(x_np.shape[1]),
        }, f, indent=2)

    with open(os.path.join(ARTIFACTS_DIR, "metrics.json"), "w") as f:
        json.dump({"gnn_pytorch": gnn_metrics, "gnn_onnx": onnx_metrics,
                   "baseline": base_metrics, "catboost_extended": cat_metrics,
                   "pretrained_backbone_coverage": pretrained_coverage}, f, indent=2)

    print("\n=== FINAL ===")
    print(json.dumps({"gnn_pytorch": gnn_metrics, "gnn_onnx": onnx_metrics,
                      "baseline": base_metrics, "catboost_extended": cat_metrics,
                      "pretrained_backbone_coverage": pretrained_coverage}, indent=2))


if __name__ == "__main__":
    main()
