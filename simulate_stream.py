"""
Generate N mock transactions and score each via the FastAPI backend.

Useful for load testing and demo preparation.

Run:
    python simulate_stream.py --count 50
    python simulate_stream.py --count 200 --backend http://localhost:8000
"""

import argparse
import json
import random
import time
import urllib.error
import urllib.request

from data import generate_transaction


def score_one(backend: str, body: dict) -> dict:
    req = urllib.request.Request(
        f"{backend}/score",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=5) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--count",   type=int, default=50)
    parser.add_argument("--backend", type=str, default="http://localhost:8000")
    parser.add_argument("--sleep",   type=float, default=0.05)
    args = parser.parse_args()

    actions = {"ALLOW": 0, "MONITOR": 0, "STEP_UP": 0, "BLOCK": 0}
    latencies = []

    for i in range(args.count):
        txn = generate_transaction(i)
        # backend wants the 6-feature PaySim contract: the 3 tabulars +
        # tx_type, plus sender/receiver for the embedding lookup
        body = {
            "txn_id":                txn.txn_id,
            "sender":                txn.sender,
            "receiver":              txn.receiver,
            "amount":                txn.amount,
            "origin_balance_error":  round(random.uniform(-30, 5), 4),
            "dest_balance_error":    round(random.uniform(-20, 5), 4),
            "tx_type":               random.choice(["CASH_IN", "CASH_OUT", "DEBIT", "PAYMENT", "TRANSFER"]),
        }
        try:
            result = score_one(args.backend, body)
            actions[result["action"]] += 1
            latencies.append(result["latency_ms"])
            print(
                f"[{i+1:03d}] {txn.txn_id}  "
                f"score={result['score']:3d}  "
                f"action={result['action']:8s}  "
                f"latency={result['latency_ms']}ms"
            )
        except urllib.error.URLError as exc:
            print(f"[{i+1:03d}] ERROR: {exc}")
        time.sleep(args.sleep)

    print("\n" + "=" * 60)
    print(f"Total scored:  {args.count}")
    for action, count in actions.items():
        print(f"  {action:8s}: {count}")
    if latencies:
        latencies.sort()
        p50 = latencies[len(latencies) // 2]
        p95 = latencies[int(len(latencies) * 0.95)]
        print(f"Latency P50:   {p50}ms")
        print(f"Latency P95:   {p95}ms")


if __name__ == "__main__":
    main()
