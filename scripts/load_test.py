#!/usr/bin/env python
"""Load test for POST /score (Phase 5 — performance proof).

Fires N requests at a fixed concurrency with a deterministic mix of the three
payload shapes the endpoint actually serves:

  benign  a normal looking UPI pair                    (expected low score)
  ring    RING-001 members from synth/out/ground_truth.json (expected BLOCK)
  legacy  PaySim-only body, no UPI triple              (must still return 200)

Two client implementations, because the generator turned out to matter:

  httpx   httpx.AsyncClient, the obvious choice. On this Windows box it tops
          out near 45 requests/second at any endpoint (measured against
          /health too), so at 100 in flight it measures its own queuing, not
          the service.
  raw     a minimal asyncio HTTP/1.1 client, one connection per request. It
          reaches 450-550 req/s against the same server, so it can actually
          saturate it.

`--client both` (the default) runs both and reports both. Latency is
client-side wall clock, an upper bound that includes queueing and HTTP
overhead; the server's own `latency_ms` is recorded next to it. A run is
flagged `client_bound` when a faster generator on the same server got more
than twice its throughput — at that point its wall clock describes the
generator. The headline (and the budget verdict) comes from the fastest run.

Single worker only: `--workers` is passed through, but 4 workers on this
Windows box accepted connections and then hung requests past the 60 s timeout,
so every number here was taken with one uvicorn worker.

Writes artifacts/load_test.json. Exits non-zero if any request failed, if a
score contract regressed, or if P99 exceeded the budget in the saturating run.

Usage:
    ./.venv/Scripts/python.exe scripts/load_test.py
    ./.venv/Scripts/python.exe scripts/load_test.py --client raw --requests 1000
    ./.venv/Scripts/python.exe scripts/load_test.py --base-url http://localhost:8000
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import os
import platform
import signal
import socket
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT = ROOT / "artifacts" / "load_test.json"

BUDGET_MS = 300.0

# RING-001 members, straight from synth/out/ground_truth.json (circular_flow).
RING_SENDER = "L***7350"
RING_RECEIVER = "H***3681"


def payloads() -> dict[str, dict]:
    """The three request shapes, in the rotation order used by the run."""
    return {
        "benign": {
            "txn_id": "LOAD-BENIGN",
            "sender": "A***4521",
            "receiver": "B***8812",
            "amount": 450.0,
            "origin_balance_error": 0.0,
            "dest_balance_error": 0.0,
            "tx_type": "TRANSFER",
            "velocity_10min": 1,
            "device_change": 0,
            "ip_risk": 0.02,
        },
        "ring": {
            "txn_id": "LOAD-RING",
            "sender": RING_SENDER,
            "receiver": RING_RECEIVER,
            "amount": 49000.0,
            "origin_balance_error": -8.5,
            "dest_balance_error": -5.2,
            "tx_type": "TRANSFER",
            "velocity_10min": 14,
            "device_change": 1,
            "ip_risk": 0.91,
        },
        "legacy": {
            # PaySim-only body: no velocity_10min / device_change / ip_risk.
            "txn_id": "LOAD-LEGACY",
            "sender": "A***4521",
            "receiver": "B***8812",
            "amount": 45000.0,
            "origin_balance_error": -8.5,
            "dest_balance_error": -5.2,
            "tx_type": "TRANSFER",
        },
    }


PAYLOAD_ORDER = ("benign", "ring", "legacy")


def percentile(values: list[float], pct: float) -> float:
    """Nearest-rank percentile: the smallest value v such that pct% of samples
    are <= v. No interpolation, so every number returned is a real observation."""
    if not values:
        return float("nan")
    ordered = sorted(values)
    rank = max(1, math.ceil(pct / 100.0 * len(ordered)))
    return ordered[min(rank, len(ordered)) - 1]


def summary(values: list[float]) -> dict:
    if not values:
        return {}
    return {
        "n": len(values),
        "min": round(min(values), 2),
        "p50": round(percentile(values, 50), 2),
        "p95": round(percentile(values, 95), 2),
        "p99": round(percentile(values, 99), 2),
        "max": round(max(values), 2),
        "mean": round(sum(values) / len(values), 2),
    }


# ---------------------------------------------------------------------------
# Server lifecycle
# ---------------------------------------------------------------------------

def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def start_server(port: int, workers: int, log_path: Path) -> subprocess.Popen:
    """Spawn uvicorn. stdout/stderr go to a file, not a pipe, so a busy server
    can never block on a full pipe buffer."""
    cmd = [
        sys.executable, "-m", "uvicorn", "backend:app",
        "--host", "127.0.0.1", "--port", str(port),
        "--workers", str(workers), "--log-level", "warning",
    ]
    handle = log_path.open("w", encoding="utf-8")
    kwargs: dict[str, Any] = {"cwd": str(ROOT), "stdout": handle, "stderr": handle}
    if os.name == "nt":
        # New process group, so a tree kill can reach `--workers` children:
        # Popen.terminate() only kills the parent and orphans them.
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True
    proc = subprocess.Popen(cmd, **kwargs)
    proc._log_handle = handle  # type: ignore[attr-defined]
    return proc


def stop_server(proc: subprocess.Popen) -> None:
    """Kill the server *and* any worker children."""
    if proc.poll() is None:
        if os.name == "nt":
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                           capture_output=True, check=False)
        else:
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
            except ProcessLookupError:
                pass
    try:
        proc.wait(timeout=15)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=10)
    handle = getattr(proc, "_log_handle", None)
    if handle is not None:
        handle.close()


async def wait_for_health(client: Any, timeout_s: float) -> dict:
    """Poll /health until it answers 200. Works for both client types."""
    deadline = time.perf_counter() + timeout_s
    last: Exception | None = None
    while time.perf_counter() < deadline:
        try:
            status, body = await client.get("/health")
            if status == 200:
                return json.loads(body)
            last = RuntimeError(f"/health returned {status}")
        except Exception as exc:  # not up yet
            last = exc
        await asyncio.sleep(0.5)
    raise RuntimeError(f"server did not become healthy in {timeout_s:.0f}s: {last}")


# ---------------------------------------------------------------------------
# Clients
# ---------------------------------------------------------------------------
# Both expose the same tiny surface: async get(path) and async post(path, dict),
# each returning (status, body_text). That keeps the measurement loop identical
# no matter which generator drives it.

class HttpxClient:
    name = "httpx"

    def __init__(self, base_url: str, concurrency: int, timeout: float) -> None:
        import httpx

        self._limits = httpx.Limits(
            max_connections=concurrency,
            max_keepalive_connections=concurrency,
        )
        self._timeout = timeout
        self._base_url = base_url
        self._client: Any = None

    async def __aenter__(self) -> "HttpxClient":
        import httpx

        self._client = httpx.AsyncClient(
            base_url=self._base_url, timeout=self._timeout, limits=self._limits,
        )
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self._client.aclose()

    async def get(self, path: str) -> tuple[int, str]:
        resp = await self._client.get(path)
        return resp.status_code, resp.text

    async def post(self, path: str, body: dict) -> tuple[int, str]:
        resp = await self._client.post(path, json=body)
        return resp.status_code, resp.text


class RawClient:
    """Minimal HTTP/1.1 over asyncio: one connection per request, no pool.

    Deliberately dumb — it exists to be fast enough that the server, not the
    generator, decides the latencies.
    """

    name = "raw"

    def __init__(self, base_url: str, concurrency: int, timeout: float) -> None:
        parsed = base_url.split("//", 1)[-1]
        host, _, port = parsed.partition(":")
        self._host = host
        self._port = int(port or 80)
        self._timeout = timeout

    async def __aenter__(self) -> "RawClient":
        return self

    async def __aexit__(self, *exc: object) -> None:
        return None

    async def _request(self, method: str, path: str,
                       body: bytes | None) -> tuple[int, str]:
        headers = [f"{method} {path} HTTP/1.1", f"Host: {self._host}",
                   "Connection: close"]
        if body is not None:
            headers += ["Content-Type: application/json",
                        f"Content-Length: {len(body)}"]
        head = ("\r\n".join(headers) + "\r\n\r\n").encode()

        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(self._host, self._port), self._timeout,
        )
        try:
            writer.write(head + (body or b""))
            await writer.drain()
            header_blob = await asyncio.wait_for(
                reader.readuntil(b"\r\n\r\n"), self._timeout,
            )
            lines = header_blob.decode("latin-1").split("\r\n")
            status = int(lines[0].split(" ")[1])
            length = 0
            for line in lines[1:]:
                key, _, value = line.partition(":")
                if key.lower() == "content-length":
                    length = int(value.strip())
            payload = await reader.readexactly(length) if length else b""
            return status, payload.decode("utf-8", "replace")
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass

    async def get(self, path: str) -> tuple[int, str]:
        return await self._request("GET", path, None)

    async def post(self, path: str, body: dict) -> tuple[int, str]:
        return await self._request("POST", path, json.dumps(body).encode())


CLIENTS = {"httpx": HttpxClient, "raw": RawClient}


# ---------------------------------------------------------------------------
# One measured run
# ---------------------------------------------------------------------------

async def run_once(client_cls, base_url: str, args: argparse.Namespace) -> dict:
    scripted = payloads()
    sem = asyncio.Semaphore(args.concurrency)

    async with client_cls(base_url, args.concurrency, args.timeout) as client:
        health = await wait_for_health(client, args.startup_timeout)

        async def one(kind: str, seq: int) -> dict:
            body = dict(scripted[kind])
            body["txn_id"] = f"{body['txn_id']}-{client_cls.name}-{seq:05d}"
            async with sem:
                t0 = time.perf_counter()
                status, text = await client.post("/score", body)
                wall = (time.perf_counter() - t0) * 1000.0
            out = {"kind": kind, "status": status, "wall_ms": wall,
                   "score": None, "server_ms": None}
            if status == 200:
                parsed = json.loads(text)
                out["score"] = parsed.get("score")
                out["server_ms"] = parsed.get("latency_ms")
            else:
                out["error"] = text[:200]
            return out

        # Warmup: sequential, excluded from the statistics but reported.
        warm: list[dict] = []
        for i in range(args.warmup):
            warm.append(await one(PAYLOAD_ORDER[i % len(PAYLOAD_ORDER)], i))

        kinds = [PAYLOAD_ORDER[i % len(PAYLOAD_ORDER)] for i in range(args.requests)]
        t_start = time.perf_counter()
        results = await asyncio.gather(*(one(kind, i) for i, kind in enumerate(kinds)))
        elapsed_s = time.perf_counter() - t_start

    ok = [r for r in results if r["status"] == 200]
    failed = [r for r in results if r["status"] != 200]
    wall_lat = summary([r["wall_ms"] for r in ok])
    server_lat = summary([float(r["server_ms"]) for r in ok
                          if r["server_ms"] is not None])

    per_kind = {}
    for kind in PAYLOAD_ORDER:
        rows = [r for r in ok if r["kind"] == kind]
        scores = [r["score"] for r in rows if r["score"] is not None]
        entry = summary([r["wall_ms"] for r in rows])
        if scores:
            entry["score_min"] = min(scores)
            entry["score_max"] = max(scores)
            entry["score_p50"] = percentile([float(s) for s in scores], 50)
        per_kind[kind] = entry

    return {
        "client": client_cls.name,
        "requests": len(results),
        "ok": len(ok),
        "errors": len(failed),
        "error_samples": [f["error"] for f in failed[:3] if "error" in f],
        "throughput_rps": round(len(ok) / elapsed_s, 2) if elapsed_s else None,
        "wall_seconds": round(elapsed_s, 3),
        "latency_ms": wall_lat,
        "server_latency_ms": server_lat,
        "baseline_sequential_ms": summary([w["wall_ms"] for w in warm]),
        "per_payload": per_kind,
        "planned_per_payload": {k: sum(1 for kind in kinds if kind == k)
                                for k in PAYLOAD_ORDER},
        "health": {
            "model_contract": health.get("model_contract"),
            "embeddings_loaded": health.get("embeddings_loaded"),
            "calibrated": health.get("calibrated"),
        },
    }


def check_run(run: dict, p99_values: list[float]) -> list[dict]:
    """Contract checks. The budget check uses every repeat, not the best one:
    passing one run out of three is not passing."""
    ring_p50 = run["per_payload"]["ring"].get("score_p50")
    benign_p50 = run["per_payload"]["benign"].get("score_p50")
    legacy_n = run["per_payload"]["legacy"].get("n", 0)
    legacy_planned = run["planned_per_payload"]["legacy"]
    worst = max(p99_values) if p99_values else float("nan")
    return [
        {"name": "no failed requests", "passed": run["errors"] == 0,
         "detail": f"{run['errors']} non-200 of {run['requests']}"},
        {"name": "ring payloads score above benign payloads",
         "passed": bool(ring_p50 is not None and benign_p50 is not None
                        and ring_p50 > benign_p50),
         "detail": f"ring p50 score {ring_p50} vs benign {benign_p50}"},
        {"name": "legacy (PaySim-only) payloads all succeed",
         "passed": legacy_n == legacy_planned and legacy_planned > 0,
         "detail": f"{legacy_n}/{legacy_planned} legacy 200s"},
        {"name": f"p99 within {BUDGET_MS:.0f} ms budget on every repeat",
         "passed": all(v == v and v <= BUDGET_MS for v in p99_values),
         "detail": f"worst {worst} ms of {p99_values}"},
    ]


def aggregate(name: str, reps: list[dict]) -> dict:
    """Collapse repeats into one entry.

    The representative run is the one with the median p99, so no single lucky
    or unlucky run becomes the story; the full series is kept alongside it.
    """
    by_p99 = sorted(reps, key=lambda r: r["latency_ms"].get("p99", float("inf")))
    rep = by_p99[len(by_p99) // 2]
    p99s = [float(r["latency_ms"].get("p99", float("nan"))) for r in reps]
    rps = sorted(float(r["throughput_rps"] or 0) for r in reps)

    out = dict(rep)
    out.update({
        "client": name,
        "repeats": len(reps),
        "requests": sum(r["requests"] for r in reps),
        "errors": sum(r["errors"] for r in reps),
        "throughput_rps": round(rps[len(rps) // 2], 2),
        "throughput_rps_all": [round(v, 2) for v in rps],
        "p99_ms_all": [round(v, 2) for v in p99s],
        "p99_ms_median": round(percentile(p99s, 50), 2),
        "p99_ms_best": round(min(p99s), 2),
        "p99_ms_worst": round(max(p99s), 2),
    })
    out["checks"] = check_run(rep, p99s)
    return out


async def main_async(args: argparse.Namespace) -> int:
    server: subprocess.Popen | None = None
    log_path = ROOT / "logs" / "load_test_server.log"

    if args.base_url:
        base_url = args.base_url.rstrip("/")
        workers = None
    else:
        port = args.port or free_port()
        base_url = f"http://127.0.0.1:{port}"
        workers = args.workers
        log_path.parent.mkdir(exist_ok=True)
        server = start_server(port, workers, log_path)
        print(f"spawned uvicorn on {base_url} (workers={workers})")

    try:
        names = ["httpx", "raw"] if args.client == "both" else [args.client]
        runs: dict[str, dict] = {}
        for name in names:
            reps: list[dict] = []
            for r in range(args.repeats):
                print(f"\n--- client: {name} | rep {r + 1}/{args.repeats} | "
                      f"{args.requests} requests, concurrency "
                      f"{args.concurrency} ---")
                run = await run_once(CLIENTS[name], base_url, args)
                reps.append(run)
                lat = run["latency_ms"]
                srv = run["server_latency_ms"]
                print(f"  {run['ok']} ok, {run['errors']} failed "
                      f"({run['throughput_rps']} rps)")
                print(f"  wall  p50 {lat.get('p50')}  p95 {lat.get('p95')}  "
                      f"p99 {lat.get('p99')}  max {lat.get('max')} ms")
                if srv:
                    print(f"  srv   p50 {srv.get('p50')}  p95 {srv.get('p95')}  "
                          f"p99 {srv.get('p99')} ms")
                base = run["baseline_sequential_ms"]
                if base:
                    print(f"  seq   p50 {base.get('p50')} ms (no queueing)")
                for kind in PAYLOAD_ORDER:
                    e = run["per_payload"][kind]
                    if e:
                        print(f"  {kind:<7} n={e['n']:<4} p50 {e['p50']:<8} "
                              f"p99 {e['p99']:<8} score {e.get('score_min')}.."
                              f"{e.get('score_max')}")
            runs[name] = aggregate(name, reps)
            agg = runs[name]
            print(f"  => {name}: median throughput {agg['throughput_rps']} rps "
                  f"{agg['throughput_rps_all']}, p99 {agg['p99_ms_all']} ms")

        # Which generator was the limiter? The slowest one is only trustworthy
        # if a faster generator on the *same server* also saw slower responses;
        # otherwise its wall clock describes the generator. Gate on a 2x gap.
        best = max(runs[n]["throughput_rps"] or 0 for n in runs)
        for name, run in runs.items():
            run["client_bound"] = bool(
                len(runs) > 1 and (run["throughput_rps"] or 0) < 0.5 * best
            )
            if run["client_bound"]:
                print(f"  !! {name} is client-bound: {run['throughput_rps']} rps "
                      f"vs {best} rps from the fastest generator on the same "
                      "server, so its wall latency describes the generator")

        # The headline is the run that could actually saturate the server: the
        # highest throughput. Percentiles from a starved generator describe the
        # generator.
        headline_name = max(runs, key=lambda n: runs[n]["throughput_rps"] or 0)
        headline = runs[headline_name]
        other = [n for n in runs if n != headline_name]
        passed = all(c["passed"] for c in headline["checks"])

        artifact = {
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "target": "/score",
            "base_url": base_url,
            "spawned_server": server is not None,
            "workers": workers,
            "requests_per_run": args.requests,
            "repeats": args.repeats,
            "total_score_requests": headline["requests"],
            "concurrency": args.concurrency,
            "warmup_requests": args.warmup,
            "budget_ms": BUDGET_MS,
            "headline_client": headline_name,
            "headline": {
                "client": headline_name,
                "p50_ms": headline["latency_ms"].get("p50"),
                "p95_ms": headline["latency_ms"].get("p95"),
                "p99_ms": headline["p99_ms_median"],
                "p99_ms_best": headline["p99_ms_best"],
                "p99_ms_worst": headline["p99_ms_worst"],
                "p99_ms_all": headline["p99_ms_all"],
                "server_p99_ms": headline["server_latency_ms"].get("p99"),
                "throughput_rps": headline["throughput_rps"],
                "budget_ms": BUDGET_MS,
                "passed": passed,
            },
            "runs": runs,
            "headline_reason": (
                "the generator that achieved the highest throughput; the "
                "lower-throughput generator is client-bound and its wall "
                "latency describes that client, not the service"
            ),
            "slower_runs": other,
            "method": {
                "percentiles": "nearest-rank, no interpolation",
                "latency": "client wall clock around POST /score, includes "
                           "queueing and HTTP overhead; an upper bound",
                "client_bound": "throughput < 50% of the fastest generator "
                                 "run against the same server",
                "repeats": "median p99 across repeats is the headline; the "
                           "budget check uses the worst repeat",
            },
            "environment": {
                "python": platform.python_version(),
                "platform": platform.platform(),
                "cpu_count": os.cpu_count(),
            },
        }

        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")

        print()
        for check in headline["checks"]:
            print(f"  [{'PASS' if check['passed'] else 'FAIL'}] "
                  f"{check['name']} — {check['detail']}")
        print(f"\nheadline client: {headline_name}")
        print(f"wrote {args.out}")
        return 0 if passed else 1

    finally:
        if server is not None:
            stop_server(server)


def main() -> int:
    parser = argparse.ArgumentParser(description="Load test for POST /score")
    parser.add_argument("--requests", type=int, default=100)
    parser.add_argument("--concurrency", type=int, default=100)
    parser.add_argument("--warmup", type=int, default=5)
    parser.add_argument("--repeats", type=int, default=3,
                        help="measure the burst N times; one burst of 100 p99 "
                             "is the 2nd-worst sample and is not stable")
    parser.add_argument("--client", choices=["httpx", "raw", "both"], default="both")
    parser.add_argument("--workers", type=int, default=1,
                        help="uvicorn workers when this script spawns the server")
    parser.add_argument("--base-url", default=None,
                        help="test an already-running server instead of spawning")
    parser.add_argument("--port", type=int, default=None)
    parser.add_argument("--timeout", type=float, default=60.0)
    parser.add_argument("--startup-timeout", type=float, default=120.0)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    if args.requests < 1 or args.concurrency < 1:
        parser.error("--requests and --concurrency must be >= 1")

    return asyncio.run(main_async(args))


if __name__ == "__main__":
    raise SystemExit(main())
