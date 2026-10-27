"""Tests for synth/upi_mule_generator.py.

The generator is deterministic from a seed, so these tests assert on exact
structural properties of the produced dataset rather than on sampled values.

The default-size dataset (20,000 accounts / 100,000 transactions) is built
once per module and reused; the reproducibility test uses a smaller run so
that a second and third generation stay cheap.
"""

import csv
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from synth.upi_mule_generator import (  # noqa: E402
    ACCOUNT_COLUMNS,
    AMOUNT_MAX,
    AMOUNT_MIN,
    DEFAULT_ACCOUNTS,
    DEFAULT_TXNS,
    TYPOLOGY_CIRCULAR,
    TXN_COLUMNS,
    generate,
    write_outputs,
)

# The ring plan plants ~3,000 fraudulent transactions, so any smaller run
# must still leave room for the per-account baseline pass.
SMALL_ACCOUNTS = 1_000
SMALL_TXNS = 5_000


@pytest.fixture(scope="module")
def dataset(tmp_path_factory):
    """The production-size dataset, generated once and written to disk."""
    out_dir = tmp_path_factory.mktemp("upi_synth")
    result = generate()
    summary = write_outputs(result, str(out_dir))
    return {"result": result, "out": str(out_dir), "summary": summary}


def _read_csv(path):
    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        return reader.fieldnames, list(reader)


# ---------------------------------------------------------------------------
# reproducibility
# ---------------------------------------------------------------------------

def test_same_seed_is_reproducible():
    first = generate(seed=42, n_accounts=SMALL_ACCOUNTS, n_txns=SMALL_TXNS)
    second = generate(seed=42, n_accounts=SMALL_ACCOUNTS, n_txns=SMALL_TXNS)

    def fingerprint(res):
        return [
            (t["txn_id"], t["sender_account"], t["receiver_account"],
             t["amount_inr"], t["timestamp"] if "timestamp" in t else t["t"],
             t["is_fraud"], t["ring_id"])
            for t in res["txns"]
        ]

    assert fingerprint(first) == fingerprint(second)
    assert first["account_ids"] == second["account_ids"]


def test_different_seed_changes_the_dataset():
    first = generate(seed=42, n_accounts=SMALL_ACCOUNTS, n_txns=SMALL_TXNS)
    other = generate(seed=7, n_accounts=SMALL_ACCOUNTS, n_txns=SMALL_TXNS)
    assert first["account_ids"] != other["account_ids"]


# ---------------------------------------------------------------------------
# shape: rows and columns (production size)
# ---------------------------------------------------------------------------

def test_transaction_row_count_and_columns(dataset):
    columns, rows = _read_csv(os.path.join(dataset["out"], "transactions.csv"))
    assert columns == TXN_COLUMNS
    assert len(rows) == DEFAULT_TXNS


def test_account_row_count_and_columns(dataset):
    columns, rows = _read_csv(os.path.join(dataset["out"], "accounts.csv"))
    assert columns == ACCOUNT_COLUMNS
    assert len(rows) == DEFAULT_ACCOUNTS


def test_txn_id_format(dataset):
    _, rows = _read_csv(os.path.join(dataset["out"], "transactions.csv"))
    for row in rows[:500]:
        prefix, epoch, suffix = row["txn_id"].split("-")
        assert prefix == "UPI"
        assert epoch.isdigit()
        assert len(suffix) == 5 and suffix.isdigit()


def test_account_ids_are_masked_handles(dataset):
    _, rows = _read_csv(os.path.join(dataset["out"], "accounts.csv"))
    for row in rows[:500]:
        letter, stars, digits = row["account_id"][0], row["account_id"][1:4], row["account_id"][4:]
        assert letter.isalpha() and letter.isupper()
        assert stars == "***"
        assert len(digits) == 4 and digits.isdigit()


# ---------------------------------------------------------------------------
# fraud rate and ring structure
# ---------------------------------------------------------------------------

def test_fraud_rate_within_band(dataset):
    _, rows = _read_csv(os.path.join(dataset["out"], "transactions.csv"))
    fraud = sum(1 for row in rows if row["is_fraud"] == "1")
    rate = fraud / len(rows)
    assert 0.025 <= rate <= 0.035, rate


def test_all_rings_have_4_to_12_members(dataset):
    ground_truth = json.load(open(os.path.join(dataset["out"], "ground_truth.json")))
    assert len(ground_truth["rings"]) == 60
    for ring in ground_truth["rings"]:
        assert 4 <= len(ring["members"]) <= 12, ring["ring_id"]
        assert len(set(ring["members"])) == len(ring["members"]), ring["ring_id"]


def test_all_four_typologies_present(dataset):
    ground_truth = json.load(open(os.path.join(dataset["out"], "ground_truth.json")))
    typologies = {ring["typology"] for ring in ground_truth["rings"]}
    assert typologies == {"circular_flow", "layering", "smurfing", "cold_start"}


def test_circular_flows_have_a_return_edge_within_24h(dataset):
    circular = [
        ring for ring in dataset["result"]["rings"]
        if ring.typology == TYPOLOGY_CIRCULAR
    ]
    assert circular, "no circular rings planted"

    for ring in circular:
        first_member = ring.members[0]
        start = min(txn["t"] for txn in ring.txns)
        returns = [
            txn for txn in ring.txns
            if txn["receiver_account"] == first_member
        ]
        assert returns, f"{ring.ring_id} has no edge back to {first_member}"
        assert any(txn["t"] - start <= 24 * 3600 for txn in returns), ring.ring_id


def test_ring_bounds_are_ordered_row_indices(dataset):
    ground_truth = json.load(open(os.path.join(dataset["out"], "ground_truth.json")))
    for ring in ground_truth["rings"]:
        assert isinstance(ring["start_txn"], int)
        assert isinstance(ring["end_txn"], int)
        assert 0 <= ring["start_txn"] <= ring["end_txn"] < DEFAULT_TXNS


# ---------------------------------------------------------------------------
# value bounds and labels
# ---------------------------------------------------------------------------

def test_amounts_are_positive_and_within_bounds(dataset):
    _, rows = _read_csv(os.path.join(dataset["out"], "transactions.csv"))
    amounts = [float(row["amount_inr"]) for row in rows]
    assert min(amounts) >= AMOUNT_MIN
    assert max(amounts) <= AMOUNT_MAX


def test_labels_and_ring_ids_are_consistent(dataset):
    _, rows = _read_csv(os.path.join(dataset["out"], "transactions.csv"))
    for row in rows:
        assert row["is_fraud"] in {"0", "1"}
        if row["is_fraud"] == "1":
            assert row["ring_id"].startswith("RING-")
        else:
            assert row["ring_id"] == ""


def test_ip_risk_is_a_probability(dataset):
    _, rows = _read_csv(os.path.join(dataset["out"], "transactions.csv"))
    for row in rows[::97]:       # sample to keep it quick
        value = float(row["ip_risk"])
        assert 0.0 <= value <= 1.0


def test_states_are_from_the_documented_set(dataset):
    _, rows = _read_csv(os.path.join(dataset["out"], "transactions.csv"))
    allowed = {"MH", "KA", "TN", "DL", "UP", "GJ", "WB", "RJ", "KL", "TS"}
    for row in rows[::97]:
        assert row["sender_state"] in allowed
        assert row["receiver_state"] in allowed
