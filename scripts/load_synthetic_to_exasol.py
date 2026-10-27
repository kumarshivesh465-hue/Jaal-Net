#!/usr/bin/env python
"""Load the synthetic UPI dataset into Exasol.

    python scripts/load_synthetic_to_exasol.py [--reload]

Reads `synth/out/transactions.csv` + `synth/out/ground_truth.json` and fills
`upi_transactions`, `ring_registry` and `ring_members`.

Mapping notes (documented because the synthetic CSV and the schema differ):
  * `timestamp` (ISO-8601 with +05:30) -> `txn_timestamp` as a naive TIMESTAMP
    in local (IST) wall-clock time; Exasol TIMESTAMP carries no zone.
  * `device_change` (true/false) -> `device_change_flag` BOOLEAN.
  * `ip_risk` -> `ip_risk_score`.
  * `velocity_10min` = 0: the real velocity is a training-time feature and is
    not stored in the CSV.
  * `model_score`, `action_taken`, `model_version` = NULL until scored.
  * `ring_id` empty in the CSV -> NULL.
  * ground-truth `cold_start` -> `mixed` in `ring_registry.pattern_type`,
    because the schema CHECK allows only circular_flow/layering/smurfing/mixed.
  * `avg_score` is 0.00: the rows have not been scored yet.

Idempotence: if `upi_transactions` already holds rows, the script exits without
writing unless `--reload` is passed (which deletes the three tables' rows first).
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TXN_CSV = os.path.join(ROOT, "synth", "out", "transactions.csv")
GT_JSON = os.path.join(ROOT, "synth", "out", "ground_truth.json")

BATCH = 500
PATTERN_MAP = {"circular_flow": "circular_flow", "layering": "layering",
               "smurfing": "smurfing", "cold_start": "mixed"}


def load_env(path: str) -> None:
    if not os.path.isfile(path):
        return
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def sql_str(value: str | None) -> str:
    if value is None or value == "":
        return "NULL"
    return "'" + str(value).replace("'", "''") + "'"


def ts(value: str) -> str:
    """ISO-8601 with offset -> 'YYYY-MM-DD HH:MM:SS' (local wall clock)."""
    parsed = datetime.fromisoformat(value)
    return parsed.strftime("%Y-%m-%d %H:%M:%S")


def parse_bool(value: str) -> str:
    return "TRUE" if str(value).strip().lower() in {"true", "1", "yes"} else "FALSE"


def connect():
    load_env(os.path.join(ROOT, ".env"))
    password = os.environ.get("EXASOL_PASSWORD", "")
    if not password:
        raise SystemExit("EXASOL_PASSWORD not set (checked .env and environment)")
    import pyexasol

    conn = pyexasol.connect(
        dsn=os.environ.get("EXASOL_DSN", "localhost:8563"),
        user=os.environ.get("EXASOL_USER", "sys"),
        password=password,
        compression=True,
        fetch_dict=True,
        lower_ident=True,
        # Disable strict cert validation for Personal edition
        websocket_sslopt={"cert_reqs": __import__("ssl").CERT_NONE},
    )
    conn.execute(f'OPEN SCHEMA "{os.environ.get("EXASOL_SCHEMA", "FRAUD")}"')
    return conn


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--reload", action="store_true",
                    help="delete existing rows before loading")
    args = ap.parse_args()

    for path in (TXN_CSV, GT_JSON):
        if not os.path.isfile(path):
            print(f"missing {path} — run synth/upi_mule_generator.py first",
                  file=sys.stderr)
            return 1

    conn = connect()

    existing = conn.execute("SELECT COUNT(*) AS n FROM upi_transactions").fetchone()
    # lower_ident=True lower-cases the result keys, so a count row is read
    # positionally rather than by column name.
    n_existing = int(next(iter(existing.values()))) if existing else 0
    if n_existing and not args.reload:
        print(f"upi_transactions already holds {n_existing:,} rows; "
              "pass --reload to replace")
        conn.close()
        return 0
    if args.reload:
        print("deleting existing rows (--reload)")
        conn.execute("DELETE FROM ring_members")
        conn.execute("DELETE FROM upi_transactions")
        conn.execute("DELETE FROM ring_registry")

    ring_vol: dict[str, float] = {}
    ring_first: dict[str, str] = {}
    ring_last: dict[str, str] = {}
    member_join: dict[tuple[str, str], str] = {}

    cols = ("txn_id, txn_timestamp, sender_account, receiver_account, "
            "amount_inr, sender_state, receiver_state, device_change_flag, "
            "ip_risk_score, velocity_10min, model_score, action_taken, "
            "ring_id, model_version")

    loaded = 0
    batch: list[str] = []

    def flush() -> None:
        if not batch:
            return
        conn.execute(f"INSERT INTO upi_transactions ({cols}) VALUES "
                     + ", ".join(batch))
        batch.clear()

    with open(TXN_CSV, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            ring = row["ring_id"] or None
            stamp = ts(row["timestamp"])

            if ring:
                amount = float(row["amount_inr"])
                ring_vol[ring] = ring_vol.get(ring, 0.0) + amount
                ring_first[ring] = min(ring_first.get(ring, stamp), stamp)
                ring_last[ring] = max(ring_last.get(ring, stamp), stamp)
                for account in (row["sender_account"], row["receiver_account"]):
                    key = (ring, account)
                    member_join[key] = min(member_join.get(key, stamp), stamp)

            batch.append(
                "(" + ", ".join([
                    sql_str(row["txn_id"]),
                    sql_str(stamp),
                    sql_str(row["sender_account"]),
                    sql_str(row["receiver_account"]),
                    f"{float(row['amount_inr']):.2f}",
                    sql_str(row["sender_state"]),
                    sql_str(row["receiver_state"]),
                    parse_bool(row["device_change"]),
                    f"{float(row['ip_risk']):.3f}",
                    "0", "NULL", "NULL", sql_str(ring), "NULL",
                ]) + ")"
            )
            loaded += 1
            if len(batch) >= BATCH:
                flush()
    flush()

    # ---- rings -----------------------------------------------------------
    ground_truth = json.load(open(GT_JSON, encoding="utf-8"))["rings"]
    ring_rows: list[str] = []
    member_rows: list[str] = []

    for ring in ground_truth:
        ring_id = ring["ring_id"]
        members = list(dict.fromkeys(ring["members"]))
        pattern = PATTERN_MAP.get(ring["typology"], "mixed")
        first = ring_first.get(ring_id) or "2026-01-01 00:00:00"
        last = ring_last.get(ring_id) or first
        ring_rows.append(
            "(" + ", ".join([
                sql_str(ring_id), sql_str(first), sql_str(last),
                str(len(members)),
                f"{ring_vol.get(ring_id, 0.0):.2f}",
                # avg_score: rows are not scored yet (documented above)
                "0.00", sql_str(pattern), sql_str("active"),
            ]) + ")"
        )
        for position, account in enumerate(members):
            if position == 0:
                role = "hub"
            elif position == len(members) - 1:
                role = "cash_out"
            else:
                role = "spoke"
            joined = member_join.get((ring_id, account), first)
            member_rows.append(
                "(" + ", ".join([sql_str(ring_id), sql_str(account),
                                 sql_str(joined), sql_str(role)]) + ")"
            )

    conn.execute(
        "INSERT INTO ring_registry (ring_id, first_detected, last_updated, "
        "account_count, total_volume_inr, avg_score, pattern_type, status) VALUES "
        + ", ".join(ring_rows))

    for start in range(0, len(member_rows), BATCH):
        conn.execute(
            "INSERT INTO ring_members (ring_id, account_id, joined_at, role) "
            "VALUES " + ", ".join(member_rows[start:start + BATCH]))

    txn_count = conn.execute(
        "SELECT COUNT(*) AS n FROM upi_transactions").fetchone()
    ring_count = conn.execute(
        "SELECT COUNT(*) AS n FROM ring_registry").fetchone()
    member_count = conn.execute(
        "SELECT COUNT(*) AS n FROM ring_members").fetchone()

    print(f"loaded {int(next(iter(txn_count.values()))):,} transactions, "
          f"{int(next(iter(ring_count.values())))} rings, "
          f"{int(next(iter(member_count.values())))} ring members "
          f"({loaded:,} rows read)")
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
