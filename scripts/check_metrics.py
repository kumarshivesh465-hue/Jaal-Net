#!/usr/bin/env python
"""Regression gate for the metrics artifacts.

Reads every training/evaluation metrics JSON, verifies the fields the project
promises exist, range-checks the metrics, and enforces a floor on AUC-ROC for
trained models. Exits non-zero if anything fails, so CI can gate on it.

    python scripts/check_metrics.py
"""

from __future__ import annotations

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARTIFACTS = os.path.join(ROOT, "artifacts")

# Per-file contract. Keys are dotted paths so nested metrics can be checked
# without reshaping the JSON the trainers already write.
CHECKS: list[dict] = [
    {
        "label": "UPI head",
        "file": "upi_model_metrics.json",
        "required": [
            "train_n", "valid_n", "test_n", "pos_rate",
            "test_auc_pr", "test_auc_roc", "seed", "runtime_s",
        ],
        "auc_roc": "test_auc_roc",
        "auc_pr": "test_auc_pr",
        "runtime_s": "runtime_s",
        # Trained in this repo -> must clear the floor.
        "min_auc_roc": 0.60,
    },
    {
        "label": "DGraphFin GraphSAGE",
        "file": "dgraph_metrics.json",
        "required": ["model", "dataset", "seed", "epochs", "n_nodes", "n_edges",
                     "test_at_final"],
        "auc_roc": "test_at_final.auc_roc",
        "auc_pr": "test_at_final.auc_pr",
        "runtime_s": None,          # trainer does not persist runtime
        "min_auc_roc": 0.60,
    },
    {
        "label": "DGraphFin TGN",
        "file": "dgraph_tgn_metrics.json",
        "required": ["graph", "tgn", "graphsage_full_baseline", "eval_mask"],
        "auc_roc": "tgn.test_auc_roc",
        "auc_pr": "tgn.test_auc_pr",
        "runtime_s": "tgn.runtime_s",
        "min_auc_roc": 0.60,
    },
    {
        "label": "chakravyuh transfer",
        "file": "chakravyuh_metrics.json",
        "required": ["resource", "n", "positives", "auc_pr", "auc_roc",
                     "by_difficulty"],
        "auc_roc": "auc_roc",
        "auc_pr": "auc_pr",
        "runtime_s": None,
        # Transfer eval, not a trained model: no floor. 0.498 is documented
        # chance-level behaviour (MODEL_CARD limitation 1).
        "min_auc_roc": None,
    },
]


def dig(obj: object, dotted: str):
    """Return obj[a][b][c] for 'a.b.c', or raise KeyError."""
    cur = obj
    for part in dotted.split("."):
        if not isinstance(cur, dict) or part not in cur:
            raise KeyError(dotted)
        cur = cur[part]
    return cur


def is_fraction(value: object) -> bool:
    return (isinstance(value, (int, float)) and not isinstance(value, bool)
            and 0.0 <= float(value) <= 1.0)


def check_one(spec: dict) -> tuple[bool, list[str], dict]:
    """Return (ok, problems, display_row)."""
    problems: list[str] = []
    path = os.path.join(ARTIFACTS, spec["file"])
    row = {"label": spec["label"], "file": spec["file"],
           "auc_roc": "n/a", "auc_pr": "n/a", "runtime_s": "n/a"}

    if not os.path.isfile(path):
        return False, [f"{spec['file']}: missing"], row

    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        return False, [f"{spec['file']}: unreadable ({exc})"], row

    # 1. required keys
    for key in spec["required"]:
        try:
            dig(data, key)
        except KeyError:
            problems.append(f"{spec['file']}: missing required key '{key}'")

    # 2. metric ranges
    for field, out_key in ((spec["auc_roc"], "auc_roc"), (spec["auc_pr"], "auc_pr")):
        if not field:
            continue
        try:
            value = dig(data, field)
        except KeyError:
            continue  # already reported as a missing key
        if not is_fraction(value):
            problems.append(
                f"{spec['file']}: {field}={value!r} not in [0, 1]")
        else:
            row[out_key] = f"{float(value):.4f}"

    # 3. trained-model floor
    floor = spec.get("min_auc_roc")
    if floor is not None:
        try:
            auc_roc = float(dig(data, spec["auc_roc"]))
        except (KeyError, TypeError, ValueError):
            auc_roc = None
        if auc_roc is not None and auc_roc < floor:
            problems.append(
                f"{spec['file']}: auc_roc {auc_roc:.4f} < floor {floor:.2f}")

    # 4. runtime sanity, when the file records it
    if spec.get("runtime_s"):
        try:
            runtime = dig(data, spec["runtime_s"])
        except KeyError:
            runtime = None
        if runtime is not None:
            row["runtime_s"] = f"{float(runtime):.1f}"
            if not isinstance(runtime, (int, float)) or float(runtime) <= 0:
                problems.append(
                    f"{spec['file']}: runtime_s={runtime!r} must be > 0")

    return (not problems), problems, row


def main() -> int:
    print(f"metrics root: {ARTIFACTS}\n")
    header = f"{'model':<22} {'file':<30} {'auc_roc':>8} {'auc_pr':>8} {'runtime_s':>10}  verdict"
    print(header)
    print("-" * len(header))

    failures: list[str] = []
    for spec in CHECKS:
        ok, problems, row = check_one(spec)
        verdict = "OK" if ok else "FAIL"
        print(f"{row['label']:<22} {row['file']:<30} {row['auc_roc']:>8} "
              f"{row['auc_pr']:>8} {row['runtime_s']:>10}  {verdict}")
        for problem in problems:
            print(f"    ! {problem}")
            failures.append(problem)

    print()
    if failures:
        print(f"check_metrics: FAIL — {len(failures)} problem(s)", file=sys.stderr)
        return 1
    print(f"check_metrics: OK — {len(CHECKS)} file(s) validated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
