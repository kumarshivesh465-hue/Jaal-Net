"""Unit tests for the load-test harness in scripts/load_test.py.

No network and no server: these cover the arithmetic that decides whether the
budget was met, because a harness that rounds a miss into a pass is worse than
no harness. The script is loaded by path since `scripts/` is not a package.
"""

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def lt():
    spec = importlib.util.spec_from_file_location(
        "load_test_script", ROOT / "scripts" / "load_test.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def make_run(p99, rps=300.0, ring_score=100.0, benign_score=10.0, errors=0,
             legacy_n=33, legacy_planned=33, server_p99=1.0, requests=100):
    """A run dict shaped like run_once()'s return value."""
    return {
        "client": "raw",
        "requests": requests,
        "ok": requests - errors,
        "errors": errors,
        "throughput_rps": rps,
        "latency_ms": {"n": requests, "p50": p99 * 0.9, "p95": p99 * 0.98,
                       "p99": p99, "max": p99},
        "server_latency_ms": {"n": requests, "p50": server_p99,
                              "p95": server_p99, "p99": server_p99},
        "baseline_sequential_ms": {"p50": 3.0},
        "per_payload": {
            "benign": {"n": 34, "p50": p99, "p99": p99,
                       "score_min": benign_score, "score_max": benign_score,
                       "score_p50": benign_score},
            "ring": {"n": 33, "p50": p99, "p99": p99, "score_min": ring_score,
                     "score_max": ring_score, "score_p50": ring_score},
            "legacy": {"n": legacy_n, "p50": p99, "p99": p99,
                       "score_min": 40, "score_max": 40, "score_p50": 40},
        },
        "planned_per_payload": {"benign": 34, "ring": 33, "legacy": legacy_planned},
        "health": {"model_contract": "upi", "embeddings_loaded": 20000,
                   "calibrated": False},
    }


# ---------------------------------------------------------------------------
# Percentile arithmetic
# ---------------------------------------------------------------------------

def test_percentile_is_nearest_rank(lt):
    values = [float(v) for v in range(1, 101)]  # 1..100

    assert lt.percentile(values, 50) == 50.0
    assert lt.percentile(values, 95) == 95.0
    assert lt.percentile(values, 99) == 99.0
    # nearest rank never interpolates: every answer is an input value
    assert lt.percentile([5.0, 1.0, 9.0], 99) == 9.0


def test_percentile_returns_an_observation_not_an_average(lt):
    values = [10.0, 20.0, 30.0]

    assert lt.percentile(values, 50) in values
    assert lt.summary(values)["mean"] == 20.0


def test_summary_p99_is_not_the_mean(lt):
    values = [1.0] * 99 + [1000.0]
    out = lt.summary(values)

    assert out["p50"] == 1.0
    assert out["p99"] == 1.0
    assert out["max"] == 1000.0


# ---------------------------------------------------------------------------
# Budget verdict
# ---------------------------------------------------------------------------

def test_budget_passes_when_every_repeat_is_inside_it(lt):
    run = make_run(p99=250.0)
    checks = lt.check_run(run, [240.0, 250.0, 260.0])

    budget = [c for c in checks if "budget" in c["name"]][0]
    assert budget["passed"] is True


def test_budget_fails_when_one_repeat_exceeds_it(lt):
    """The core honesty rule: 2 of 3 runs under budget is not a pass."""
    run = make_run(p99=280.0)
    checks = lt.check_run(run, [260.0, 280.0, 306.21])

    budget = [c for c in checks if "budget" in c["name"]][0]
    assert budget["passed"] is False
    assert "306.21" in budget["detail"]


def test_budget_detail_reports_the_worst_repeat(lt):
    checks = lt.check_run(make_run(p99=100.0), [90.0, 120.0, 110.0])

    budget = [c for c in checks if "budget" in c["name"]][0]
    assert "120.0" in budget["detail"]


def test_failed_request_fails_the_run(lt):
    checks = lt.check_run(make_run(p99=100.0, errors=2), [100.0])
    errors = [c for c in checks if c["name"] == "no failed requests"][0]

    assert errors["passed"] is False
    assert "2 non-200" in errors["detail"]


def test_ring_must_outscore_benign(lt):
    checks = lt.check_run(make_run(p99=100.0, ring_score=10.0,
                                   benign_score=100.0), [100.0])
    ring = [c for c in checks if "ring" in c["name"]][0]

    assert ring["passed"] is False


def test_missing_legacy_responses_fail_the_check(lt):
    checks = lt.check_run(make_run(p99=100.0, legacy_n=30), [100.0])
    legacy = [c for c in checks if "legacy" in c["name"]][0]

    assert legacy["passed"] is False
    assert "30/33" in legacy["detail"]


# ---------------------------------------------------------------------------
# Aggregation across repeats
# ---------------------------------------------------------------------------

def test_aggregate_headlines_the_median_p99_and_keeps_the_series(lt):
    reps = [make_run(p99=306.21), make_run(p99=272.59), make_run(p99=286.8)]
    agg = lt.aggregate("raw", reps)

    assert agg["repeats"] == 3
    assert agg["p99_ms_median"] == 286.8
    assert agg["p99_ms_best"] == 272.59
    assert agg["p99_ms_worst"] == 306.21
    assert agg["p99_ms_all"] == [306.21, 272.59, 286.8]
    # the representative run is the median one, not the fastest
    assert agg["latency_ms"]["p99"] == 286.8


def test_aggregate_sums_errors_across_repeats(lt):
    agg = lt.aggregate("raw", [make_run(p99=100.0, errors=1),
                               make_run(p99=100.0, errors=2)])

    assert agg["errors"] == 3
    assert agg["requests"] == 200


# ---------------------------------------------------------------------------
# The committed artifact
# ---------------------------------------------------------------------------

ARTIFACT = ROOT / "artifacts" / "load_test.json"


@pytest.mark.skipif(not ARTIFACT.exists(), reason="no load-test artifact")
def test_artifact_headline_agrees_with_its_runs():
    art = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    head = art["headline"]
    run = art["runs"][head["client"]]

    assert head["p99_ms"] == run["p99_ms_median"]
    assert head["p99_ms_worst"] == max(run["p99_ms_all"])
    assert head["client"] == art["headline_client"]
    # the headline client must be the fastest generator in the artifact
    assert head["throughput_rps"] == max(
        r["throughput_rps"] for r in art["runs"].values())


@pytest.mark.skipif(not ARTIFACT.exists(), reason="no load-test artifact")
def test_artifact_budget_verdict_matches_its_numbers():
    art = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    head = art["headline"]

    assert head["passed"] == all(p <= head["budget_ms"] for p in head["p99_ms_all"])


@pytest.mark.skipif(not ARTIFACT.exists(), reason="no load-test artifact")
def test_artifact_records_how_it_was_measured():
    art = json.loads(ARTIFACT.read_text(encoding="utf-8"))

    assert art["concurrency"] >= 1
    assert art["budget_ms"] == 300.0
    assert art["method"]["percentiles"].startswith("nearest-rank")
    assert art["environment"]["python"]
    # a stale artifact from a different harness must not look authoritative
    assert "client_bound" in art["method"]
