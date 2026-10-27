"""Synthetic UPI-shaped transaction graph with planted mule rings.

Generates three files, deterministically, from a single seed:

    <out>/transactions.csv    one row per UPI transaction
    <out>/accounts.csv        one row per account (aggregates + mule flag)
    <out>/ground_truth.json   the planted ring structure

The wallet is UPI-shaped rather than PaySim-shaped: masked account handles,
INR amounts with a small median and a long tail, Indian state codes, device
and IP risk signals, and -- most importantly -- an *account graph* with
planted mule topologies, which is what a GNN-based detector needs and what
PaySim (near-singleton accounts) cannot provide.

Typologies planted (each ring is 4-12 accounts):

  * ``circular_flow``  A -> B -> C -> D -> A, near-equal amounts, whole cycle
    inside a few hours (so the closing return edge lands within 24h).
  * ``layering``       one source -> 3-5 intermediates -> one cash-out,
    amounts ratcheting down at each hop.
  * ``smurfing``       one source -> 10-20 small (Rs 5K-15K) transfers to
    *distinct* receivers inside a 24h burst, repeated over the window.
  * ``cold_start``     a brand-new account whose first transaction is
    high-value and pays an account that is already a ring member.

Interpretation note: the "4-12 members" rule is applied to the ring's mule
accounts.  A smurfing ring therefore has 1 source plus 10-11 distinct
receivers (11-12 members) so that a single burst can genuinely reach 10+
distinct receivers while staying inside the size window.

Account-id format is masked, matching the format the dashboard/backend
already uses for UPI-style handles: ``<A-Z>***<4 digits>``.

References
----------
* PaySim -- "Synthetic Financial Datasets For Fraud Detection" (Lopez-Rojas,
  Elmir & Axelsson), Kaggle.  Source of the log-normal transaction-amount
  shape (small median, long right tail) reused here.
  https://www.kaggle.com/datasets/ealaxi/paysim1
* IBM "Synthetic AML" transaction datasets on Kaggle (Altman et al.,
  *Realistic Synthetic Financial Transactions for Anti-Money Laundering
  Models*, NeurIPS 2023 Datasets & Benchmarks).  Source of the money-
  laundering *typology* patterns -- cycle/circular layering, fan-in/fan-out
  layering and smurfing -- which are re-planted here on a UPI-style graph.
  https://www.kaggle.com/datasets/ealtman2019/ibm-transactions-for-anti-money-laundering-aml
* UPI transaction-graph literature -- publicly described features of real
  UPI mule networks (masked VPA handles, device churn, IP risk, short
  windowed transfer bursts) inform the column set and the per-typology
  behaviour; no real UPI data is used or redistributed here.

CLI
---
    python synth/upi_mule_generator.py --seed 42 --out synth/out
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import random
import string
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

import numpy as np

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

IST = timezone(timedelta(hours=5, minutes=30))
WINDOW_START = datetime(2026, 1, 1, 0, 0, 0, tzinfo=IST)

DEFAULT_SEED = 42
DEFAULT_OUT = os.path.join("synth", "out")
DEFAULT_ACCOUNTS = 20_000
DEFAULT_TXNS = 100_000
DEFAULT_DAYS = 90

STATE_CODES = ["MH", "KA", "TN", "DL", "UP", "GJ", "WB", "RJ", "KL", "TS"]

AMOUNT_MIN = 1.0
AMOUNT_MAX = 200_000.0
MEDIAN_BENIGN_AMOUNT = 800.0
BENIGN_SIGMA = 1.35

BENIGN_DEVICE_CHANGE_RATE = 0.05
FRAUD_DEVICE_CHANGE_RATE = 0.35
BENIGN_BURST_RATE = 0.10          # share of benign txns that repeat within minutes

TYPOLOGY_CIRCULAR = "circular_flow"
TYPOLOGY_LAYERING = "layering"
TYPOLOGY_SMURFING = "smurfing"
TYPOLOGY_COLD_START = "cold_start"

# (typology, number of rings, target fraudulent transactions per ring)
RING_PLAN = [
    (TYPOLOGY_CIRCULAR, 25, 40),
    (TYPOLOGY_LAYERING, 15, 60),
    (TYPOLOGY_SMURFING, 12, 70),
    (TYPOLOGY_COLD_START, 8, 30),
]

TXN_COLUMNS = [
    "txn_id",
    "timestamp",
    "sender_account",
    "receiver_account",
    "amount_inr",
    "sender_state",
    "receiver_state",
    "device_change",
    "ip_risk",
    "is_fraud",
    "ring_id",
]

ACCOUNT_COLUMNS = [
    "account_id",
    "first_seen",
    "txn_count",
    "total_volume_inr",
    "is_mule",
    "ring_id",
]

# Hour-of-day weights (IST). Two humps: late morning and evening.
_HOUR_WEIGHTS = np.array(
    [
        0.2, 0.1, 0.1, 0.1, 0.2, 0.5,  # 00-05
        1.0, 2.0, 3.5, 5.0, 6.0, 5.5,  # 06-11
        5.0, 4.5, 4.0, 3.5, 3.5, 4.0,  # 12-17
        5.5, 6.5, 6.0, 4.0, 2.0, 0.8,  # 18-23
    ],
    dtype=np.float64,
)
_HOUR_WEIGHTS /= _HOUR_WEIGHTS.sum()


@dataclass
class Ring:
    """A planted mule ring and the fraudulent rows it owns."""

    ring_id: str
    typology: str
    members: list[str]
    target_txns: int
    state: str
    txns: list[dict] = field(default_factory=list)

    def add(self, txn: dict) -> None:
        self.txns.append(txn)


# ---------------------------------------------------------------------------
# Small sampling helpers
# ---------------------------------------------------------------------------

def _clamp_amount(value: float) -> float:
    return float(min(AMOUNT_MAX, max(AMOUNT_MIN, value)))


def _sample_amount(rng: np.random.Generator, median: float, sigma: float) -> float:
    """Log-normal INR amount with the requested median, clipped to bounds."""
    value = rng.lognormal(mean=math.log(median), sigma=sigma)
    return round(_clamp_amount(value), 2)


def _masked_ids(n: int, rng: random.Random) -> list[str]:
    """`n` unique masked handles of the form ``<A-Z>***<4 digits>``.

    Returned sorted so the mapping is independent of set iteration order
    (and therefore of PYTHONHASHSEED): reproducibility requires it.
    """
    ids: set[str] = set()
    letters = string.ascii_uppercase
    while len(ids) < n:
        ids.add(f"{rng.choice(letters)}***{rng.randrange(10000):04d}")
    return sorted(ids)


def _benign_time_offsets(n: int, days: int, rng: random.Random,
                         np_rng: np.random.Generator) -> np.ndarray:
    """`n` within-window second offsets, peaking 10-14h and 19-22h IST,
    with weekends slightly quieter."""
    day = np_rng.integers(0, days, size=n)
    # weekend thinning: resample ~20% of weekend transactions onto weekdays
    weekday = (WINDOW_START.weekday() + day) % 7
    weekend = weekday >= 5
    thin = weekend & (np_rng.random(n) < 0.20)
    if thin.any():
        day[thin] = np_rng.integers(0, days, size=int(thin.sum()))

    hour = np_rng.choice(24, size=n, p=_HOUR_WEIGHTS)
    second_of_day = (
        hour * 3600
        + np_rng.integers(0, 3600, size=n)
    )
    return (day * 86400 + second_of_day).astype(np.float64)


def _iso(offset_s: float) -> str:
    return (WINDOW_START + timedelta(seconds=float(offset_s))).isoformat()


def _epoch(offset_s: float) -> int:
    return int((WINDOW_START + timedelta(seconds=float(offset_s))).timestamp())


# ---------------------------------------------------------------------------
# Ring planting
# ---------------------------------------------------------------------------

def _ring_sizes(rng: random.Random) -> dict[str, tuple[int, int]]:
    """Member-count ranges per typology, all inside [4, 12]."""
    return {
        TYPOLOGY_CIRCULAR: (4, 8),
        TYPOLOGY_LAYERING: (5, 9),      # source + 3-5 intermediates + cash-out
        TYPOLOGY_SMURFING: (11, 12),    # source + 10-11 distinct receivers
        TYPOLOGY_COLD_START: (4, 8),    # 1 fresh account + 3-7 existing mules
    }


def _build_rings(account_ids: list[str], rng: random.Random) -> list[Ring]:
    sizes = _ring_sizes(rng)
    pool = list(range(len(account_ids)))
    rng.shuffle(pool)
    ptr = 0

    def take(k: int) -> list[str]:
        nonlocal ptr
        chosen = pool[ptr:ptr + k]
        ptr += k
        return [account_ids[i] for i in chosen]

    rings: list[Ring] = []
    ring_no = 0
    for typology, count, target in RING_PLAN:
        lo, hi = sizes[typology]
        for _ in range(count):
            ring_no += 1
            size = rng.randint(lo, hi)
            if typology == TYPOLOGY_COLD_START and rings:
                # the fresh account feeds an *already flagged* mule
                donor = rng.choice(rings)
                members = take(1) + rng.sample(
                    donor.members, min(len(donor.members), size - 1)
                )
            else:
                members = take(size)
            rings.append(
                Ring(
                    ring_id=f"RING-{ring_no:03d}",
                    typology=typology,
                    members=members,
                    target_txns=target,
                    state=rng.choice(STATE_CODES),
                )
            )
    return rings


def _fraud_signals(ring: Ring, rng: random.Random,
                   np_rng: np.random.Generator) -> tuple[bool, float]:
    """Device-change flag and IP risk for one fraudulent hop.

    Fraudulent hops are riskier than benign traffic, and smurfing (many small
    transfers from one handset) leaves the heaviest device/IP fingerprint.
    """
    if ring.typology == TYPOLOGY_SMURFING:
        device_change = rng.random() < 0.45
        ip_risk = float(np.clip(np_rng.beta(4.0, 2.0), 0.0, 1.0))
    else:
        device_change = rng.random() < FRAUD_DEVICE_CHANGE_RATE
        ip_risk = float(np.clip(np_rng.beta(3.0, 2.0), 0.0, 1.0))
    return device_change, round(ip_risk, 4)


def _emit(ring: Ring, sender: str, receiver: str, amount: float, t: float,
          rng: random.Random, np_rng: np.random.Generator,
          state_of: dict[str, str], sender_state: str | None = None) -> None:
    device_change, ip_risk = _fraud_signals(ring, rng, np_rng)
    ring.add(
        {
            "t": float(t),
            "sender_account": sender,
            "receiver_account": receiver,
            "amount_inr": round(_clamp_amount(amount), 2),
            "sender_state": sender_state or state_of[sender],
            "receiver_state": state_of[receiver],
            "device_change": bool(device_change),
            "ip_risk": ip_risk,
            "is_fraud": 1,
            "ring_id": ring.ring_id,
            "_seq": 0,  # filled in later
        }
    )


def _plant_circular(ring: Ring, rng: random.Random,
                    np_rng: np.random.Generator, days: int,
                    state_of: dict[str, str]) -> None:
    members = ring.members
    n = len(members)
    while len(ring.txns) < ring.target_txns:
        start = rng.uniform(0, max(1.0, days * 86400 - 86400))
        base_amount = float(np_rng.lognormal(math.log(15000.0), 0.6))
        t = start
        for i in range(n):
            # the closing hop (last -> first) is hours after the opening hop,
            # so every ring has a return edge well inside 24h
            _emit(
                ring,
                members[i],
                members[(i + 1) % n],
                base_amount * rng.uniform(0.9, 1.1),
                t,
                rng,
                np_rng,
                state_of,
                sender_state=ring.state,
            )
            t += rng.uniform(300.0, 3600.0)


def _plant_layering(ring: Ring, rng: random.Random,
                    np_rng: np.random.Generator, days: int,
                    state_of: dict[str, str]) -> None:
    members = ring.members
    src, cash_out = members[0], members[-1]
    intermediates = members[1:-1]
    while len(ring.txns) < ring.target_txns:
        start = rng.uniform(0, max(1.0, days * 86400 - 86400))
        current = float(np_rng.lognormal(math.log(50000.0), 0.7))
        t = start
        chain = [src] + intermediates + [cash_out]
        for j in range(len(chain) - 1):
            _emit(ring, chain[j], chain[j + 1], current, t,
                  rng, np_rng, state_of, sender_state=ring.state)
            current *= rng.uniform(0.82, 0.95)   # ratchets down at each hop
            t += rng.uniform(120.0, 1800.0)


def _plant_smurfing(ring: Ring, rng: random.Random,
                    np_rng: np.random.Generator, days: int,
                    state_of: dict[str, str]) -> None:
    source = ring.members[0]
    receivers = ring.members[1:]
    while len(ring.txns) < ring.target_txns:
        burst_start = rng.uniform(0, max(1.0, days * 86400 - 86400))
        burst_size = rng.randint(10, min(20, len(receivers)))
        picked = rng.sample(receivers, burst_size)   # distinct receivers
        for k, receiver in enumerate(picked):
            _emit(
                ring,
                source,
                receiver,
                rng.uniform(5000.0, 15000.0),
                burst_start + rng.uniform(0.0, 86000.0),  # inside the same 24h
                rng,
                np_rng,
                state_of,
                sender_state=ring.state,
            )


def _plant_cold_start(ring: Ring, rng: random.Random,
                      np_rng: np.random.Generator, days: int,
                      state_of: dict[str, str]) -> None:
    fresh, mules = ring.members[0], ring.members[1:]
    # the fresh account's *first* transaction is high value to a known mule
    first = rng.uniform(days * 86400 * 0.5, max(1.0, days * 86400 - 600))
    _emit(ring, fresh, rng.choice(mules),
          float(np_rng.lognormal(math.log(120000.0), 0.4)), first,
          rng, np_rng, state_of, sender_state=ring.state)
    while len(ring.txns) < ring.target_txns:
        _emit(ring, fresh, rng.choice(mules),
              float(np_rng.lognormal(math.log(90000.0), 0.5)),
              first + rng.uniform(60.0, 6 * 3600.0),
              rng, np_rng, state_of, sender_state=ring.state)


_PLANTERS = {
    TYPOLOGY_CIRCULAR: _plant_circular,
    TYPOLOGY_LAYERING: _plant_layering,
    TYPOLOGY_SMURFING: _plant_smurfing,
    TYPOLOGY_COLD_START: _plant_cold_start,
}


# ---------------------------------------------------------------------------
# Top-level generation
# ---------------------------------------------------------------------------

def generate(seed: int = DEFAULT_SEED,
             n_accounts: int = DEFAULT_ACCOUNTS,
             n_txns: int = DEFAULT_TXNS,
             days: int = DEFAULT_DAYS) -> dict:
    """Build the accounts, transactions and ring structure in memory."""
    rng = random.Random(seed)
    np_rng = np.random.default_rng(seed)

    account_ids = _masked_ids(n_accounts, rng)
    state_of = {acc: rng.choice(STATE_CODES) for acc in account_ids}

    rings = _build_rings(account_ids, rng)
    for ring in rings:
        _PLANTERS[ring.typology](ring, rng, np_rng, days, state_of)

    fraud_txns: list[dict] = [txn for ring in rings for txn in ring.txns]
    n_fraud = len(fraud_txns)
    if n_fraud >= n_txns:
        raise ValueError(f"planted {n_fraud} fraudulent txns >= n_txns {n_txns}")

    n_benign = n_txns - n_fraud
    benign_txns: list[dict] = []

    # (1) one baseline transaction per account, so every account has a
    #     first_seen and is reachable in the graph
    baseline_time = _benign_time_offsets(n_accounts, days, rng, np_rng)
    for i, acc in enumerate(account_ids):
        receiver = account_ids[rng.randrange(n_accounts)]
        while receiver == acc:
            receiver = account_ids[rng.randrange(n_accounts)]
        benign_txns.append(
            {
                "t": float(baseline_time[i]),
                "sender_account": acc,
                "receiver_account": receiver,
                "amount_inr": _sample_amount(np_rng, MEDIAN_BENIGN_AMOUNT,
                                             BENIGN_SIGMA),
                "sender_state": state_of[acc],
                "receiver_state": state_of[receiver],
                "device_change": rng.random() < BENIGN_DEVICE_CHANGE_RATE,
                "ip_risk": round(
                    float(np.clip(np_rng.beta(1.5, 8.0), 0.0, 1.0)), 4
                ),
                "is_fraud": 0,
                "ring_id": "",
                "_seq": 0,
            }
        )

    # (2) the rest of the benign traffic. Mostly independent transfers, plus
    #     realistic same-sender bursts (a user splitting a payment over a few
    #     minutes). Without the bursts a velocity_10min feature is degenerate.
    rest = n_benign - len(benign_txns)
    n_burst = int(round(rest * BENIGN_BURST_RATE))
    n_plain = rest - n_burst

    # (2a) independent transfers
    plain_time = _benign_time_offsets(n_plain, days, rng, np_rng)
    plain_sender = np_rng.integers(0, n_accounts, size=n_plain)
    plain_receiver = np_rng.integers(0, n_accounts, size=n_plain)
    plain_amount = np_rng.lognormal(
        mean=math.log(MEDIAN_BENIGN_AMOUNT), sigma=BENIGN_SIGMA, size=n_plain
    )
    plain_ip = np_rng.beta(1.5, 8.0, size=n_plain)
    plain_device = np_rng.random(n_plain) < BENIGN_DEVICE_CHANGE_RATE
    for k in range(n_plain):
        sender = account_ids[int(plain_sender[k])]
        receiver = account_ids[int(plain_receiver[k])]
        if receiver == sender:
            receiver = account_ids[(int(plain_receiver[k]) + 1) % n_accounts]
        benign_txns.append(
            {
                "t": float(plain_time[k]),
                "sender_account": sender,
                "receiver_account": receiver,
                "amount_inr": round(_clamp_amount(float(plain_amount[k])), 2),
                "sender_state": state_of[sender],
                "receiver_state": state_of[receiver],
                "device_change": bool(plain_device[k]),
                "ip_risk": round(float(min(1.0, max(0.0, plain_ip[k]))), 4),
                "is_fraud": 0,
                "ring_id": "",
                "_seq": 0,
            }
        )

    # (2b) bursts: 2-5 same-sender transfers inside a few minutes
    events: list[tuple[int, int]] = []
    remaining = n_burst
    while remaining > 0:
        size = min(remaining, rng.randint(2, 5))
        events.append((rng.randrange(n_accounts), size))
        remaining -= size
    event_time = _benign_time_offsets(len(events), days, rng, np_rng)

    for event_idx, (sender_i, size) in enumerate(events):
        sender = account_ids[sender_i]
        base = float(event_time[event_idx])
        for _ in range(size):
            receiver = account_ids[rng.randrange(n_accounts)]
            while receiver == sender:
                receiver = account_ids[rng.randrange(n_accounts)]
            benign_txns.append(
                {
                    "t": base + rng.uniform(0.0, 540.0),
                    "sender_account": sender,
                    "receiver_account": receiver,
                    "amount_inr": _sample_amount(np_rng, MEDIAN_BENIGN_AMOUNT,
                                                 BENIGN_SIGMA),
                    "sender_state": state_of[sender],
                    "receiver_state": state_of[receiver],
                    "device_change": rng.random() < BENIGN_DEVICE_CHANGE_RATE,
                    "ip_risk": round(
                        float(np.clip(np_rng.beta(1.5, 8.0), 0.0, 1.0)), 4
                    ),
                    "is_fraud": 0,
                    "ring_id": "",
                    "_seq": 0,
                }
            )

    all_txns = fraud_txns + benign_txns
    for i, txn in enumerate(all_txns):
        txn["_seq"] = i
    all_txns.sort(key=lambda t: (t["t"], t["_seq"]))

    for i, txn in enumerate(all_txns):
        txn["txn_id"] = f"UPI-{_epoch(txn['t'])}-{i % 100000:05d}"

    # ring row-bounds in the emitted (time-sorted) order
    order = {id(txn): i for i, txn in enumerate(all_txns)}
    ring_rows: dict[str, list[int]] = {r.ring_id: [] for r in rings}
    for txn in all_txns:
        if txn["ring_id"]:
            ring_rows[txn["ring_id"]].append(order[id(txn)])

    return {
        "account_ids": account_ids,
        "state_of": state_of,
        "rings": rings,
        "txns": all_txns,
        "ring_rows": ring_rows,
        "n_fraud": n_fraud,
    }


def _aggregate_accounts(result: dict) -> list[dict]:
    """Per-account first_seen / count / volume / mule flag."""
    account_ids = result["account_ids"]
    first_seen: dict[str, float] = {}
    count: dict[str, int] = {}
    volume: dict[str, float] = {}
    ring_of: dict[str, str] = {}

    for txn in result["txns"]:
        for role in ("sender_account", "receiver_account"):
            acc = txn[role]
            t = txn["t"]
            if acc not in first_seen or t < first_seen[acc]:
                first_seen[acc] = t
            count[acc] = count.get(acc, 0) + 1
            volume[acc] = volume.get(acc, 0.0) + txn["amount_inr"]

    for ring in result["rings"]:
        for member in ring.members:
            ring_of.setdefault(member, ring.ring_id)

    rows = []
    for acc in account_ids:
        rows.append(
            {
                "account_id": acc,
                "first_seen": _iso(first_seen.get(acc, 0.0)),
                "txn_count": count.get(acc, 0),
                "total_volume_inr": round(volume.get(acc, 0.0), 2),
                "is_mule": 1 if acc in ring_of else 0,
                "ring_id": ring_of.get(acc, ""),
            }
        )
    return rows


def write_outputs(result: dict, out_dir: str) -> dict[str, int]:
    """Write transactions.csv, accounts.csv and ground_truth.json."""
    os.makedirs(out_dir, exist_ok=True)

    txn_path = os.path.join(out_dir, "transactions.csv")
    with open(txn_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=TXN_COLUMNS,
                                extrasaction="ignore")
        writer.writeheader()
        for txn in result["txns"]:
            row = dict(txn)
            row["timestamp"] = _iso(txn["t"])
            writer.writerow(row)

    account_rows = _aggregate_accounts(result)
    acct_path = os.path.join(out_dir, "accounts.csv")
    with open(acct_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=ACCOUNT_COLUMNS)
        writer.writeheader()
        writer.writerows(account_rows)

    ground_truth = {
        "rings": [
            {
                "ring_id": ring.ring_id,
                "members": ring.members,
                "typology": ring.typology,
                "start_txn": min(result["ring_rows"][ring.ring_id]),
                "end_txn": max(result["ring_rows"][ring.ring_id]),
            }
            for ring in result["rings"]
        ]
    }
    gt_path = os.path.join(out_dir, "ground_truth.json")
    with open(gt_path, "w", encoding="utf-8") as fh:
        json.dump(ground_truth, fh, indent=2)

    return {
        "transactions": len(result["txns"]),
        "accounts": len(account_rows),
        "rings": len(result["rings"]),
        "fraud": result["n_fraud"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--out", type=str, default=DEFAULT_OUT)
    parser.add_argument("--accounts", type=int, default=DEFAULT_ACCOUNTS)
    parser.add_argument("--txns", type=int, default=DEFAULT_TXNS)
    parser.add_argument("--days", type=int, default=DEFAULT_DAYS)
    args = parser.parse_args()

    result = generate(args.seed, args.accounts, args.txns, args.days)
    summary = write_outputs(result, args.out)

    print(f"seed={args.seed} out={args.out}")
    print(f"transactions={summary['transactions']} accounts={summary['accounts']}")
    print(f"rings={summary['rings']} fraudulent_txns={summary['fraud']} "
          f"({summary['fraud'] / summary['transactions']:.2%})")


if __name__ == "__main__":
    main()
