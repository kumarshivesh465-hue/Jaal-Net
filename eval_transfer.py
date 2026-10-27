"""
chakravyuh-bench-v0 transfer evaluation (promoted resource B, closes L1
partially — see MODEL_CARD limitation 1).

The benchmark (CC-BY-4.0, ujjwalpardeshi/chakravyuh-bench-v0 on HF) is
conversation-level: scam SMS/WhatsApp/voice scenarios with ground-truth
labels. It has NO account ids, balances, or transaction types, so a direct
6-feature mapping is impossible; this adapter projects scenario metadata
onto the contract in CONTRACTS.md section 7:

  metadata.loss_amount_inr      -> amount            (default: per-category
                                                      median, else 10000)
  metadata.channel/category     -> tx_type           (default: TRANSFER)
  id (sha-256)                  -> sender_embedding  (cold-start hash path)
  id+":recv" (sha-256)          -> receiver_embedding
  (absent)                      -> balance errors    (0.0 = scaler mean
                                                      = "no evidence")

What this measures: does the deployed scoring service rank fraud-relevant
scenarios above benign ones. It does NOT measure GNN transfer (the GNN's
edge inputs don't exist in the bench) — stated honestly in the output.

CC-BY-4.0 attribution: Chakravyuh Team, "Chakravyuh-Bench-v0: A benchmark
for Indian UPI fraud detection", Meta PyTorch OpenEnv Hackathon 2026,
https://huggingface.co/datasets/ujjwalpardeshi/chakravyuh-bench-v0
Test-only split: the dataset card forbids training on these scenarios.

Run:
    ./.venv/Scripts/python eval_transfer.py
"""

import hashlib
import json
import os

import numpy as np
from sklearn.metrics import average_precision_score, roc_auc_score

import config
import inference

SCENARIOS_PATH = os.path.join("data", "chakravyuh", "scenarios.jsonl")
OUT_PATH = os.path.join(config.ARTIFACTS_DIR, "chakravyuh_metrics.json")
DEFAULT_AMOUNT = 10000.0


def _hash_embedding(seed: str) -> list[float]:
    """Deterministic 64-dim embedding for an unknown account.

    Same scheme as the cold-start fallback the backend uses for
    out-of-index accounts (sha-256 digest spread over EMB_DIM slots),
    reimplemented locally because backend._resolve_embedding is a
    private helper, not a CONTRACTS.md function.
    """
    digest = hashlib.sha256(seed.encode("utf-8")).digest()
    return [round(digest[i % len(digest)] / 255.0, 4) for i in range(config.EMB_DIM)]


def _load_scenarios(path: str = SCENARIOS_PATH) -> list[dict]:
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"{path} missing — download scenarios.jsonl from "
            "https://huggingface.co/datasets/ujjwalpardeshi/chakravyuh-bench-v0"
        )
    with open(path, encoding="utf-8") as fh:
        rows = [json.loads(line) for line in fh if line.strip()]
    if not rows:
        raise RuntimeError(f"{path} is empty")
    return rows


def _default_amounts(rows: list[dict]) -> dict[str, float]:
    """Per-category median loss_amount_inr; 10000 where no row has one."""
    by_cat: dict[str, list[float]] = {}
    for r in rows:
        amt = r.get("metadata", {}).get("loss_amount_inr")
        if amt:
            by_cat.setdefault(r["ground_truth"]["category"], []).append(float(amt))
    return {c: float(np.median(v)) for c, v in by_cat.items()}


def _scenario_features(scn: dict, defaults: dict[str, float]) -> dict:
    """Project one scenario onto the 6-feature scoring contract."""
    meta = scn.get("metadata", {})
    cat = scn["ground_truth"]["category"]
    amount = float(meta.get("loss_amount_inr") or defaults.get(cat, DEFAULT_AMOUNT))
    return {
        "sender_embedding": _hash_embedding(scn["id"]),
        "receiver_embedding": _hash_embedding(f"{scn['id']}:recv"),
        "amount": max(amount, 1.0),  # contract requires amount > 0
        "origin_balance_error": 0.0,  # not present in the bench; scaler mean
        "dest_balance_error": 0.0,
        "tx_type": "TRANSFER",  # all scam cash-out paths in the bench are transfers
    }


def run_chakravyuh_eval() -> dict:
    """Score all scenarios through the deployed model and report metrics."""
    rows = _load_scenarios()
    defaults = _default_amounts(rows)
    model = inference.load_model(config.MODEL_PATH)
    print(f"[chakravyuh] model mode: "
          f"{'mock' if model == 'mock' else 'onnx'}  scenarios={len(rows)}")

    labels, scores = [], []
    for scn in rows:
        result = inference.score_transaction(model, _scenario_features(scn, defaults))
        labels.append(1 if scn["ground_truth"]["is_scam"] else 0)
        scores.append(result.score)

    y = np.asarray(labels, dtype=int)
    s = np.asarray(scores, dtype=float)
    if len(np.unique(y)) < 2:
        raise RuntimeError("bench has only one class; cannot compute AUC")

    metrics = {
        "resource": "chakravyuh-bench-v0 (CC-BY-4.0, test-only split)",
        "n": int(len(y)),
        "positives": int(y.sum()),
        "base_rate": round(float(y.mean()), 4),
        "auc_pr": round(float(average_precision_score(y, s)), 4),
        "auc_roc": round(float(roc_auc_score(y, s)), 4),
        "by_difficulty": {},
        "scope_note": (
            "Adapter projects scenario metadata onto the 6-feature contract; "
            "measures scoring-service ranking, not GNN transfer (bench has "
            "no account edges)."
        ),
    }

    for diff in sorted({r["ground_truth"]["difficulty"] for r in rows}):
        mask = np.array([r["ground_truth"]["difficulty"] == diff for r in rows])
        if len(np.unique(y[mask])) == 2:
            metrics["by_difficulty"][diff] = {
                "n": int(mask.sum()),
                "auc_roc": round(float(roc_auc_score(y[mask], s[mask])), 4),
            }

    os.makedirs(config.ARTIFACTS_DIR, exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as fh:
        json.dump(metrics, fh, indent=2)
    print(json.dumps(metrics, indent=2))
    return metrics


if __name__ == "__main__":
    run_chakravyuh_eval()
