#!/usr/bin/env python
"""Calibrate the UPI edge head (temperature scaling + isotonic regression).

    python scripts/calibrate.py [--data-dir synth/out]

Step 4.1 of the hardening plan asked which models have persisted predictions.
None did: `train_upi_model.py` writes the ONNX head and the metrics JSON but
never stores per-row scores, so this script recomputes them from the exported
artifact instead of pretending a stored file exists.

Pipeline (identical to training, so the numbers describe the shipped model):
  1. read ``synth/out/transactions.csv`` and rebuild the temporal 80/10/10 split
  2. load ``artifacts/upi_node_embeddings.npz`` (32-dim, all accounts)
  3. run ``artifacts/upi_edge_model.onnx`` on the validation and test edges
  4. fit temperature T on validation logits by minimising NLL
  5. fit isotonic regression on validation probabilities
  6. report ECE / MCE / NLL / Brier / AUC-ROC / AUC-PR on the **test** split
     for uncalibrated, temperature-scaled and isotonic probabilities

Artifacts written to ``artifacts/calibration/``:
  * ``upi_edge_model_temperature.json``  {"T": ...}  — read by inference.py
  * ``upi_edge_model_calibration.json``  gate table + per-method metrics
  * ``upi_edge_model_reliability.csv``   per-bin rows for every method

Exit status is 0 only when every gate in GATES passes.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np
from scipy.optimize import minimize_scalar
from sklearn.isotonic import IsotonicRegression
from sklearn.metrics import average_precision_score, roc_auc_score

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from train_upi_model import (  # noqa: E402  (path set above)
    ARTIFACTS_DIR,
    DATA_DIR,
    EMB_PATH,
    ONNX_PATH,
    TRAIN_FRAC,
    VALID_FRAC,
    VELOCITY_WINDOW_S,
    compute_velocity,
    load_transactions,
    temporal_split,
)

CALIB_DIR = os.path.join(ARTIFACTS_DIR, "calibration")
TEMPERATURE_PATH = os.path.join(CALIB_DIR, "upi_edge_model_temperature.json")
CALIBRATION_PATH = os.path.join(CALIB_DIR, "upi_edge_model_calibration.json")
RELIABILITY_PATH = os.path.join(CALIB_DIR, "upi_edge_model_reliability.csv")

N_BINS = 15
# Serving applies the fitted temperature only when it is this far from 1.0
# (inference.temperature_is_applied uses the same threshold).
TEMPERATURE_EPS = 0.05
# Probabilities are clamped before taking logs: isotonic regression returns
# exact 0/1 for saturated regions and log(0) is not a number we can report.
PROB_EPS = 1e-6
# MCE is computed over bins holding at least this many test rows. With equal
# width bins on a heavily skewed score distribution (97% of test rows fall in
# the first bin) a single-sample bin can otherwise report a gap of ~1.0 as the
# maximum error; that number is kept as `mce_all_bins` but not gated.
MIN_BIN_COUNT = 50

# Gates: (name, metric, comparison, threshold). A calibrated model has to be
# both accurate and honest; the accuracy gates are the shipped test metrics
# with a small tolerance, the calibration gates are the point of this phase.
GATES = [
    ("test_auc_roc >= 0.98", "auc_roc", "ge", 0.98),
    ("test_auc_pr >= 0.85", "auc_pr", "ge", 0.85),
    ("test_ece <= 0.05", "ece", "le", 0.05),
    ("test_mce <= 0.15", "mce", "le", 0.15),
    ("test_nll <= 0.20", "nll", "le", 0.20),
    ("test_brier <= 0.05", "brier", "le", 0.05),
]


def sigmoid(x: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-x))


def fraud_logit(logits: np.ndarray) -> np.ndarray:
    """2-logit head -> single fraud logit (log-odds of class 1)."""
    if logits.ndim == 2 and logits.shape[1] == 2:
        return logits[:, 1] - logits[:, 0]
    return logits.reshape(-1)


def nll(probs: np.ndarray, labels: np.ndarray) -> float:
    p = np.clip(probs, PROB_EPS, 1 - PROB_EPS)
    return float(-np.mean(labels * np.log(p) + (1 - labels) * np.log(1 - p)))


def brier(probs: np.ndarray, labels: np.ndarray) -> float:
    return float(np.mean((probs - labels) ** 2))


def reliability(probs: np.ndarray, labels: np.ndarray, method: str,
                n_bins: int = N_BINS) -> tuple[list[dict], float, float, float]:
    """Equal-width bins -> (rows, ECE, MCE, MCE over bins >= MIN_BIN_COUNT)."""
    edges = np.linspace(0.0, 1.0, n_bins + 1)
    idx = np.clip(np.digitize(probs, edges[1:-1], right=False), 0, n_bins - 1)
    rows: list[dict] = []
    ece = 0.0
    mce_all = 0.0
    mce_stable = 0.0
    for b in range(n_bins):
        mask = idx == b
        count = int(mask.sum())
        if count == 0:
            continue
        mean_pred = float(probs[mask].mean())
        frac_pos = float(labels[mask].mean())
        gap = abs(mean_pred - frac_pos)
        ece += count / len(probs) * gap
        mce_all = max(mce_all, gap)
        if count >= MIN_BIN_COUNT:
            mce_stable = max(mce_stable, gap)
        rows.append({
            "method": method,
            "bin_lower": round(float(edges[b]), 4),
            "bin_upper": round(float(edges[b + 1]), 4),
            "count": count,
            "mean_pred": round(mean_pred, 6),
            "fraction_pos": round(frac_pos, 6),
        })
    return rows, float(ece), float(mce_stable), float(mce_all)


def metrics(probs: np.ndarray, labels: np.ndarray) -> dict:
    rows, ece, mce, mce_all = reliability(probs, labels, "placeholder")
    return {
        "ece": round(ece, 6),
        "mce": round(mce, 6),
        "mce_all_bins": round(mce_all, 6),
        "nll": round(nll(probs, labels), 6),
        "brier": round(brier(probs, labels), 6),
        "auc_roc": round(float(roc_auc_score(labels, probs)), 6),
        "auc_pr": round(float(average_precision_score(labels, probs)), 6),
    }, rows


def fit_temperature(logits: np.ndarray, labels: np.ndarray) -> tuple[float, float]:
    """Fit T > 0 minimising NLL of sigmoid(logit / T)."""
    def objective(t: float) -> float:
        return nll(sigmoid(logits / t), labels)

    result = minimize_scalar(objective, bounds=(0.05, 20.0), method="bounded",
                             options={"xatol": 1e-6})
    return float(result.x), float(result.fun)


def build_arrays(data_dir: str):
    """Rebuild the training pipeline's valid/test edge tensors and labels."""
    txn_path = os.path.join(data_dir, "transactions.csv")
    if not os.path.isfile(txn_path):
        raise SystemExit(f"missing {txn_path}")
    if not os.path.isfile(ONNX_PATH):
        raise SystemExit(f"missing {ONNX_PATH} — run train_upi_model.py first")
    if not os.path.isfile(EMB_PATH):
        raise SystemExit(f"missing {EMB_PATH} — run train_upi_model.py first")

    data = load_transactions(txn_path)
    velocity = compute_velocity(data["t"], data["src"], VELOCITY_WINDOW_S)

    store = np.load(EMB_PATH, allow_pickle=False)
    stored_ids = [str(x) for x in store["account_ids"]]
    embeddings = store["embeddings"].astype(np.float32)
    if index_ok := (len(stored_ids) == len(data["accounts"])):
        # embeddings were written in sorted account order (same list)
        emb_by_account = dict(zip(stored_ids, embeddings)) if index_ok else {}
    else:
        emb_by_account = dict(zip(stored_ids, embeddings))

    missing = [a for a in data["accounts"] if a not in emb_by_account]
    if missing:
        raise SystemExit(f"{len(missing)} accounts have no embedding, "
                         f"first: {missing[:3]}")
    node_emb = np.stack([emb_by_account[a] for a in data["accounts"]])

    train_idx, valid_idx, test_idx = temporal_split(data["t"])
    tab = np.stack(
        [np.log1p(data["amount"]), np.log1p(velocity),
         data["device_change"], data["ip_risk"]],
        axis=1,
    ).astype(np.float32)
    return data, node_emb, tab, valid_idx, test_idx


def run_head(session, node_emb: np.ndarray, tab: np.ndarray,
             idx: np.ndarray, src: np.ndarray, dst: np.ndarray) -> np.ndarray:
    """Run the ONNX head on one split and return the raw logits."""
    feeds = {
        "sender_embedding": node_emb[src[idx]],
        "receiver_embedding": node_emb[dst[idx]],
        "amount": tab[idx, 0:1],
        "velocity_10min": tab[idx, 1:2],
        "device_change": tab[idx, 2:3],
        "ip_risk": tab[idx, 3:4],
    }
    return np.asarray(session.run(["score"], feeds)[0])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", default=DATA_DIR)
    args = parser.parse_args()

    import onnxruntime as ort

    os.makedirs(CALIB_DIR, exist_ok=True)
    data, node_emb, tab, valid_idx, test_idx = build_arrays(args.data_dir)
    print(f"[data] valid={len(valid_idx):,} test={len(test_idx):,} "
          f"embeddings={node_emb.shape}")

    session = ort.InferenceSession(ONNX_PATH, providers=["CPUExecutionProvider"])

    valid_logit = fraud_logit(
        run_head(session, node_emb, tab, valid_idx, data["src"], data["dst"]))
    test_logit = fraud_logit(
        run_head(session, node_emb, tab, test_idx, data["src"], data["dst"]))
    y_valid = data["y"][valid_idx]
    y_test = data["y"][test_idx]
    print(f"[head] valid pos_rate={y_valid.mean():.4f} "
          f"test pos_rate={y_test.mean():.4f}")

    valid_raw = sigmoid(valid_logit)
    test_raw = sigmoid(test_logit)

    # ---- 4.2a temperature scaling -----------------------------------------
    temperature, valid_nll_at_T = fit_temperature(valid_logit, y_valid)
    print(f"[temperature] T={temperature:.4f} (valid NLL {nll(valid_raw, y_valid):.4f} "
          f"-> {valid_nll_at_T:.4f})")
    test_temp = sigmoid(test_logit / temperature)

    # ---- 4.2b isotonic regression -----------------------------------------
    isotonic = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0)
    isotonic.fit(valid_raw, y_valid)
    test_iso = isotonic.predict(test_raw)
    print(f"[isotonic] knots={len(isotonic.X_thresholds_)}")

    # ---- evaluation on the held-out test split ----------------------------
    results: dict[str, dict] = {}
    reliability_rows: list[dict] = []
    for name, probs in (("uncalibrated", test_raw),
                        ("temperature", test_temp),
                        ("isotonic", test_iso)):
        m, rows = metrics(probs, y_test)
        m["rows"] = rows
        results[name] = m
        reliability_rows.extend(
            {**row, "method": name} for row in rows)
        print(f"[test] {name:12s} ECE={m['ece']:.4f} MCE={m['mce']:.4f} "
              f"(all bins {m['mce_all_bins']:.4f}) NLL={m['nll']:.4f} "
              f"Brier={m['brier']:.4f} AUC-ROC={m['auc_roc']:.4f} "
              f"AUC-PR={m['auc_pr']:.4f}")

    # Serving applies temperature only when the fit is far enough from 1.0.
    applied = abs(temperature - 1.0) > TEMPERATURE_EPS
    served = "temperature" if applied else "uncalibrated"

    gate_rows = []
    gates_pass = True
    for label, key, op, limit in GATES:
        value = results[served][key]
        ok = value >= limit if op == "ge" else value <= limit
        gates_pass = gates_pass and ok
        gate_rows.append({"gate": label, "served_value": value,
                          "threshold": limit, "pass": bool(ok)})
    for row in gate_rows:
        print(f"[gate] {'PASS' if row['pass'] else 'FAIL'}  {row['gate']} "
              f"(served={row['served_value']:.4f})")

    calibration = {
        "model": "upi_edge_model",
        "onnx": ONNX_PATH.replace("\\", "/"),
        "n_bins": N_BINS,
        "min_bin_count_for_mce": MIN_BIN_COUNT,
        "prob_eps": PROB_EPS,
        "valid_n": int(len(valid_idx)),
        "test_n": int(len(test_idx)),
        "pos_rate": round(float(data["y"].mean()), 4),
        "temperature_eps": TEMPERATURE_EPS,
        "temperature_applied_at_serving": bool(applied),
        "served_method": served,
        "uncalibrated": results["uncalibrated"],
        "temperature": {**results["temperature"], "T": round(temperature, 6)},
        "isotonic": {**results["isotonic"],
                     "knots": int(len(isotonic.X_thresholds_))},
        "gates": gate_rows,
        "gates_pass": bool(gates_pass),
    }
    for method in ("uncalibrated", "temperature", "isotonic"):
        calibration[method].pop("rows", None)

    with open(TEMPERATURE_PATH, "w", encoding="utf-8") as fh:
        json.dump({"T": round(temperature, 6),
                   "applied": bool(applied),
                   "fit": "temperature scaling on the validation split",
                   "nll_valid_before": round(nll(valid_raw, y_valid), 6),
                   "nll_valid_after": round(valid_nll_at_T, 6)},
                  fh, indent=2)

    with open(CALIBRATION_PATH, "w", encoding="utf-8") as fh:
        json.dump(calibration, fh, indent=2)

    with open(RELIABILITY_PATH, "w", encoding="utf-8", newline="") as fh:
        fh.write("method,bin_lower,bin_upper,count,mean_pred,fraction_pos\n")
        for row in reliability_rows:
            fh.write(f"{row['method']},{row['bin_lower']},{row['bin_upper']},"
                     f"{row['count']},{row['mean_pred']},{row['fraction_pos']}\n")

    print(f"[write] {TEMPERATURE_PATH}")
    print(f"[write] {CALIBRATION_PATH}")
    print(f"[write] {RELIABILITY_PATH}")
    print(f"[result] gates {'ALL PASS' if gates_pass else 'FAILED'}; "
          f"serving {served}")
    return 0 if gates_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
