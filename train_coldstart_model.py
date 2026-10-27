"""
Train and export a CatBoost Cold-Start model for JaalNet.

When a transaction involves new/unseen accounts (e.g. accounts not in the 20,000-node
GNN embedding store), routing it to the GNN with pseudo-random hash embeddings
corrupts scoring. This CatBoost tabular model acts as the specialized cold-start
scorer using transaction-level edge features.
"""

import os
import sys
import numpy as np
import pandas as pd
from catboost import CatBoostClassifier
from sklearn.metrics import roc_auc_score, average_precision_score

DATA_PATH = os.path.join("synth", "out", "transactions.csv")
ARTIFACTS_DIR = "artifacts"
ONNX_OUT = os.path.join(ARTIFACTS_DIR, "catboost_coldstart.onnx")
CBM_OUT = os.path.join(ARTIFACTS_DIR, "catboost_coldstart.cbm")
METRICS_OUT = os.path.join(ARTIFACTS_DIR, "catboost_coldstart_metrics.json")
VELOCITY_WINDOW_S = 600.0  # 10 minutes


def compute_velocity(t: np.ndarray, src: np.ndarray, window_s: float = VELOCITY_WINDOW_S) -> np.ndarray:
    velocity = np.zeros(len(t), dtype=np.float32)
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
        velocity[order[i:j]] = (position - lower).astype(np.float32)
        i = j
    return velocity


def main():
    if not os.path.exists(DATA_PATH):
        print(f"Error: dataset not found at {DATA_PATH}", file=sys.stderr)
        return 1

    print(f"Loading UPI transactions from {DATA_PATH}...")
    df = pd.read_csv(DATA_PATH)
    
    # Sort chronologically
    df["ts"] = pd.to_datetime(df["timestamp"], format="ISO8601").astype("int64") // 10**9
    df = df.sort_values("ts").reset_index(drop=True)

    t_arr = df["ts"].values.astype(np.float64)
    # Map sender accounts to int codes for fast grouping
    senders, src_codes = np.unique(df["sender_account"].values, return_inverse=True)
    velocity = compute_velocity(t_arr, src_codes)

    # 4 Core Tabular Edge Features
    X = np.column_stack([
        np.log1p(df["amount_inr"].values.astype(np.float32)),
        np.log1p(velocity),
        (df["device_change"].astype(str) == "True").astype(np.float32),
        df["ip_risk"].values.astype(np.float32),
    ])
    y = df["is_fraud"].values.astype(np.int32)

    n = len(df)
    train_n = int(0.8 * n)
    val_n = int(0.1 * n)
    
    X_train, y_train = X[:train_n], y[:train_n]
    X_val, y_val = X[train_n:train_n + val_n], y[train_n:train_n + val_n]
    X_test, y_test = X[train_n + val_n:], y[train_n + val_n:]

    print(f"Dataset split: Train={len(X_train)}, Val={len(X_val)}, Test={len(X_test)}")
    print(f"Overall Fraud rate: {y.mean() * 100:.2f}%")

    model = CatBoostClassifier(
        iterations=300,
        depth=6,
        learning_rate=0.08,
        loss_function="Logloss",
        eval_metric="PRAUC",
        random_seed=42,
        verbose=50,
    )

    model.fit(
        X_train, y_train,
        eval_set=(X_val, y_val),
        early_stopping_rounds=30,
        verbose=50
    )

    preds_prob = model.predict_proba(X_test)[:, 1]
    auc_roc = roc_auc_score(y_test, preds_prob)
    auc_pr = average_precision_score(y_test, preds_prob)

    print("\n--- Test Set Evaluation ---")
    print(f"CatBoost Cold-Start Test AUC-ROC: {auc_roc:.4f}")
    print(f"CatBoost Cold-Start Test AUC-PR:  {auc_pr:.4f}")

    # Save native CatBoost binary
    os.makedirs(ARTIFACTS_DIR, exist_ok=True)
    model.save_model(CBM_OUT)
    print(f"Saved native model to {CBM_OUT}")

    # Export to ONNX
    try:
        model.save_model(ONNX_OUT, format="onnx")
        print(f"Successfully exported ONNX model to {ONNX_OUT}")
    except Exception as e:
        print(f"Warning: ONNX export via CatBoost threw {e}", file=sys.stderr)

    import json
    metrics = {
        "model_name": "CatBoost-ColdStart-Tabular-v1.0",
        "features": ["log1p_amount", "log1p_velocity_10min", "device_change", "ip_risk"],
        "auc_roc": float(auc_roc),
        "auc_pr": float(auc_pr),
        "test_samples": len(X_test),
        "trained_at": str(df["timestamp"].iloc[-1]),
    }
    with open(METRICS_OUT, "w", encoding="utf-8") as fh:
        json.dump(metrics, fh, indent=2)

    print(f"Wrote metrics to {METRICS_OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
