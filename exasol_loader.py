"""Exasol data access layer. Implements the queries in SCHEMA.md section 6.

Two modes:
  - Live mode: connects to Exasol via pyexasol and executes real queries.
  - Mock mode: returns deterministic in-memory data. Used when the connection
    fails or when EXASOL_PASSWORD is empty.

Switching modes is transparent to callers.
"""

import logging
import os
from datetime import datetime
from typing import Any, Optional

import config

logger = logging.getLogger(__name__)

import threading

_THREAD_LOCAL = threading.local()


def _get_connection():
    """Return a thread-local cached Exasol connection, or None if unavailable.

    Using thread-local connections ensures that concurrent FastAPI request threads
    and background worker threads (like asynchronous decision logging) never conflict
    or share a single websocket transport simultaneously.
    """
    if hasattr(_THREAD_LOCAL, "conn") and _THREAD_LOCAL.conn is not None:
        if not getattr(_THREAD_LOCAL.conn, "is_closed", False):
            return _THREAD_LOCAL.conn
        logger.info("Thread-local Exasol connection was closed; reconnecting")
        _THREAD_LOCAL.conn = None

    password = os.environ.get("EXASOL_PASSWORD", config.EXASOL_PASSWORD)
    if not password:
        logger.info("EXASOL_PASSWORD not set; running in mock mode")
        return None

    try:
        import pyexasol  # type: ignore
        import ssl

        conn = pyexasol.connect(
            dsn=config.EXASOL_DSN,
            user=config.EXASOL_USER,
            password=password,
            schema=config.EXASOL_SCHEMA,
            compression=True,
            # Return {column: value} rows with lower-case keys, which is the
            # shape _row_to_dict and every caller already assume.
            fetch_dict=True,
            lower_ident=True,
            # Disable strict cert validation for Exasol Personal edition
            websocket_sslopt={"cert_reqs": ssl.CERT_NONE},
        )
        _THREAD_LOCAL.conn = conn
        logger.info("Connected to Exasol at %s on thread %s", config.EXASOL_DSN, threading.current_thread().name)
        return conn
    except ImportError:
        logger.warning("pyexasol not installed; running in mock mode")
    except Exception as exc:
        logger.warning("Exasol connection failed (%s); running in mock mode", exc)
    return None


def close_connection() -> None:
    """Close the thread-local cached connection. Safe to call multiple times."""
    if hasattr(_THREAD_LOCAL, "conn") and _THREAD_LOCAL.conn is not None:
        try:
            _THREAD_LOCAL.conn.close()
        except Exception:
            pass
        _THREAD_LOCAL.conn = None


# ----------------------------------------------------------------------------
# Feature / data fetches (SCHEMA.md section 6 approved query patterns)
# ----------------------------------------------------------------------------

def fetch_recent_transactions(limit: int = 200) -> list[dict]:
    """Return the last `limit` transactions, newest first."""
    conn = _get_connection()
    if conn is None:
        return _mock_recent_transactions(limit)

    sql = f"""
        SELECT txn_id, txn_timestamp, sender_account, receiver_account,
               amount_inr, model_score, action_taken, sender_state,
               device_change_flag, ip_risk_score, ring_id
        FROM   upi_transactions
        ORDER BY txn_timestamp DESC
        LIMIT  {int(limit)}
    """
    try:
        result = conn.execute(sql)
        return [_row_to_dict(r) for r in result.fetchall()]
    except Exception as exc:
        logger.error("fetch_recent_transactions failed: %s", exc)
        return _mock_recent_transactions(limit)


def fetch_decision_log(txn_id: str) -> list[dict]:
    """Return all decision log rows for a transaction, newest first."""
    conn = _get_connection()
    if conn is None:
        return _mock_decision_log(txn_id)

    sql = f"""
        SELECT decision_id, txn_id, decision_timestamp, model_version,
               score, threshold_block, threshold_stepup, action_taken,
               explanation_json, feature_vector_json, latency_ms,
               exasol_fetch_ms, gnn_inference_ms, human_override,
               override_by, override_reason
        FROM   decision_log
        WHERE  txn_id = {_sql_literal(txn_id)}
        ORDER BY decision_timestamp DESC
    """
    try:
        result = conn.execute(sql)
        rows = [_row_to_dict(r) for r in result.fetchall()]
        return rows if rows else _mock_decision_log(txn_id)
    except Exception as exc:
        logger.error("fetch_decision_log failed: %s", exc)
        return _mock_decision_log(txn_id)


def fetch_active_thresholds() -> dict:
    """Return the most recent effective threshold row."""
    conn = _get_connection()
    if conn is None:
        return _mock_thresholds()

    sql = f"""
        SELECT version, effective_date, set_by,
               threshold_block, threshold_stepup, threshold_monitor,
               rationale
        FROM   threshold_governance
        WHERE  effective_date <= CURRENT_TIMESTAMP
        ORDER BY effective_date DESC
        LIMIT  1
    """
    try:
        result = conn.execute(sql)
        rows = result.fetchall()
        return _row_to_dict(rows[0]) if rows else _mock_thresholds()
    except Exception as exc:
        logger.error("fetch_active_thresholds failed: %s", exc)
        return _mock_thresholds()


def fetch_ring_members(ring_id: str) -> list[dict]:
    """Return accounts in a ring with their roles."""
    conn = _get_connection()
    if conn is None:
        return _mock_ring_members(ring_id)

    sql = f"""
        SELECT rm.account_id, rm.role, rm.joined_at
        FROM   ring_members rm
        WHERE  rm.ring_id = {_sql_literal(ring_id)}
    """
    try:
        result = conn.execute(sql)
        return [_row_to_dict(r) for r in result.fetchall()]
    except Exception as exc:
        logger.error("fetch_ring_members failed: %s", exc)
        return _mock_ring_members(ring_id)


def count_blocked_volume_24h() -> float:
    """Return total INR blocked in the last 24 hours."""
    conn = _get_connection()
    if conn is None:
        return 0.0

    sql = """
        SELECT COALESCE(SUM(t.amount_inr), 0) AS blocked_inr
        FROM   upi_transactions t
        WHERE  t.action_taken = 'BLOCK'
        AND    t.txn_timestamp > CURRENT_TIMESTAMP - INTERVAL '24' HOUR
    """
    try:
        result = conn.execute(sql)
        rows = result.fetchall()
        if not rows:
            return 0.0
        row = _row_to_dict(rows[0])
        return float(row.get("blocked_inr", 0.0))
    except Exception as exc:
        logger.error("count_blocked_volume_24h failed: %s", exc)
        return 0.0


def insert_decision(
    txn_id: str,
    model_version: str,
    score: int,
    action_taken: str,
    threshold_block: int,
    threshold_stepup: int,
    explanation_json: str,
    feature_vector_json: str,
    latency_ms: int,
    exasol_fetch_ms: Optional[int] = None,
    gnn_inference_ms: Optional[int] = None,
    sender_account: Optional[str] = None,
    receiver_account: Optional[str] = None,
    amount_inr: Optional[float] = None,
    sender_state: Optional[str] = None,
    receiver_state: Optional[str] = None,
    device_change_flag: bool = False,
    ip_risk_score: float = 0.0,
    velocity_10min: int = 0,
) -> bool:
    """Append a decision log row. Returns True on success.

    Ensures the parent transaction exists in upi_transactions first to satisfy
    foreign key constraints.
    """
    conn = _get_connection()
    if conn is None:
        logger.info(
            "MOCK DECISION txn_id=%s score=%d action=%s",
            txn_id, score, action_taken,
        )
        return True

    # 1. Ensure parent transaction exists in upi_transactions to satisfy FK_DECISION_TXN
    try:
        check = conn.execute(f"SELECT 1 FROM upi_transactions WHERE txn_id = {_sql_literal(txn_id)}").fetchone()
        if not check:
            src = sender_account or "UNKNOWN_SENDER"
            dst = receiver_account or "UNKNOWN_RECEIVER"
            amt = float(amount_inr if amount_inr is not None else 1000.0)
            insert_txn_sql = f"""
                INSERT INTO upi_transactions (
                    txn_id, txn_timestamp, sender_account, receiver_account,
                    amount_inr, sender_state, receiver_state, device_change_flag,
                    ip_risk_score, velocity_10min, model_score, action_taken,
                    model_version
                ) VALUES (
                    {_sql_literal(txn_id)}, CURRENT_TIMESTAMP, {_sql_literal(src)}, {_sql_literal(dst)},
                    {amt}, {_sql_literal(sender_state)}, {_sql_literal(receiver_state)},
                    {bool(device_change_flag)}, {float(ip_risk_score)}, {int(velocity_10min)},
                    {int(score)}, {_sql_literal(action_taken)}, {_sql_literal(model_version)}
                )
            """
            conn.execute(insert_txn_sql)
            conn.commit()
    except Exception as exc:
        logger.warning("insert_decision: transaction pre-insert warning: %s", exc)

    # 2. Insert into decision_log
    try:
        next_row = conn.execute(
            "SELECT COALESCE(MAX(decision_id), 0) + 1 FROM decision_log"
        ).fetchone()
        decision_id = int(next(iter(next_row.values()))) if next_row else 1
    except Exception as exc:
        logger.error("insert_decision: could not allocate decision_id: %s", exc)
        return False

    sql = f"""
        INSERT INTO decision_log (
            decision_id, txn_id, decision_timestamp, model_version, score,
            threshold_block, threshold_stepup, action_taken,
            explanation_json, feature_vector_json,
            latency_ms, exasol_fetch_ms, gnn_inference_ms,
            human_override
        ) VALUES (
            {decision_id}, {_sql_literal(txn_id)}, CURRENT_TIMESTAMP,
            {_sql_literal(model_version)}, {int(score)},
            {int(threshold_block)}, {int(threshold_stepup)},
            {_sql_literal(action_taken)},
            {_sql_literal(explanation_json[:4000])},
            {_sql_literal(feature_vector_json[:4000])},
            {int(latency_ms)}, {_sql_literal(exasol_fetch_ms)},
            {_sql_literal(gnn_inference_ms)},
            FALSE
        )
    """
    try:
        conn.execute(sql)
        conn.commit()
        return True
    except Exception as exc:
        logger.error("insert_decision failed: %s", exc)
        return False


# ----------------------------------------------------------------------------
# Internal helpers
# ----------------------------------------------------------------------------

def _sql_literal(value) -> str:
    """Render a Python value as an Exasol SQL literal.

    pyexasol forwards `:name` placeholders to the server as host parameters,
    which this Exasol edition rejects ("Feature not supported: host parameter
    specification"), so the small set of values interpolated into the queries
    above are rendered here instead, with quoting and escaping done in one
    place.
    """
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, (int, float)):
        return str(value)
    return "'" + str(value).replace("'", "''") + "'"


def _row_to_dict(row) -> dict:
    """Normalise a result row to a dict.

    The connection is opened with fetch_dict=True + lower_ident=True, so rows
    arrive as {lower_case_column: value}. Anything else is wrapped as-is so
    callers never crash on an unexpected driver shape.
    """
    if isinstance(row, dict):
        return row
    return {"_raw": row}


# ----------------------------------------------------------------------------
# Mock data (used when Exasol is unavailable)
# ----------------------------------------------------------------------------

def _mock_recent_transactions(limit: int) -> list[dict]:
    from data import initial_stream

    stream = initial_stream(min(limit, 200))
    return [
        {
            "txn_id":             t.txn_id,
            "txn_timestamp":      t.timestamp.isoformat(),
            "sender_account":     t.sender,
            "receiver_account":   t.receiver,
            "amount_inr":         t.amount,
            "model_score":        t.score,
            "action_taken":       t.action,
            "sender_state":       t.state,
            "device_change_flag": t.device_change,
            "ip_risk_score":      t.ip_risk,
            "ring_id":            t.ring_id,
        }
        for t in stream
    ]


def _mock_decision_log(txn_id: str) -> list[dict]:
    return [{
        "decision_id":         1,
        "txn_id":              txn_id,
        "decision_timestamp":  datetime.now().isoformat(),
        "model_version":       config.MODEL_VERSION,
        "score":               87,
        "threshold_block":     config.THRESHOLD_BLOCK,
        "threshold_stepup":    config.THRESHOLD_STEPUP,
        "action_taken":        config.ACTION_STEPUP,
        "explanation_json":    "[]",
        "feature_vector_json": "{}",
        "latency_ms":          87,
        "exasol_fetch_ms":     12,
        "gnn_inference_ms":    52,
        "human_override":      False,
        "override_by":         None,
        "override_reason":     None,
    }]


def _mock_thresholds() -> dict:
    return {
        "version":           "v3",
        "effective_date":    "2026-04-10T09:00:00",
        "set_by":            "r.sharma",
        "threshold_block":   config.THRESHOLD_BLOCK,
        "threshold_stepup":  config.THRESHOLD_STEPUP,
        "threshold_monitor": config.THRESHOLD_MONITOR,
        "rationale":         "RBI circular update",
    }


def _mock_ring_members(ring_id: str) -> list[dict]:
    from data import RINGS

    accounts = RINGS.get(ring_id, [])
    roles = ["hub", "spoke", "spoke", "layering", "spoke",
             "cash_out", "spoke", "hub", "spoke", "layering",
             "spoke", "cash_out"]
    return [
        {
            "account_id": a,
            "role":       roles[i % len(roles)],
            "joined_at":  "2026-04-03T11:22:00",
        }
        for i, a in enumerate(accounts)
    ]


def detect_communities_mpp(min_score: int = 70) -> dict:
    """Execute In-Database MPP community detection via jaalnet_louvain_detector SET script."""
    import time
    conn = _get_connection()
    if conn is None:
        return _mock_detected_communities()

    sql = f"""
    SELECT jaalnet_louvain_detector(sender_account, receiver_account, amount_inr, model_score)
    FROM (
        SELECT sender_account, receiver_account, amount_inr, model_score
        FROM upi_transactions
        WHERE model_score >= {int(min_score)} OR ring_id IS NOT NULL
    )
    """
    try:
        t0 = time.perf_counter()
        rows = [_row_to_dict(r) for r in conn.execute(sql).fetchall()]
        elapsed_ms = int((time.perf_counter() - t0) * 1000)

        clusters_map = {}
        for r in rows:
            cid = r["cluster_id"]
            if cid not in clusters_map:
                clusters_map[cid] = {
                    "cluster_id": cid,
                    "ring_type": r.get("ring_type", "CIRCULAR_LAYER"),
                    "cluster_size": r.get("cluster_size", 0),
                    "total_mule_volume": r.get("total_mule_volume", 0.0),
                    "avg_mule_risk": r.get("avg_mule_risk", 75.0),
                    "members": [],
                }
            clusters_map[cid]["members"].append(r["account_id"])

        clusters = sorted(clusters_map.values(), key=lambda c: c["cluster_size"], reverse=True)
        return {
            "status": "success",
            "execution_mode": "exasol_mpp_in_database",
            "cluster_count": len(clusters),
            "total_accounts_flagged": len(rows),
            "execution_ms": elapsed_ms,
            "clusters": clusters[:15],
        }
    except Exception as exc:
        logger.error("detect_communities_mpp failed: %s", exc)
        return _mock_detected_communities()


def _mock_detected_communities() -> dict:
    return {
        "status": "success",
        "execution_mode": "mock_fallback",
        "cluster_count": 4,
        "total_accounts_flagged": 26,
        "execution_ms": 12,
        "clusters": [
            {
                "cluster_id": 1,
                "ring_type": "CIRCULAR_LAYER",
                "cluster_size": 8,
                "total_mule_volume": 1240000.0,
                "avg_mule_risk": 94.2,
                "members": ["A***1234", "B***5678", "C***9012", "D***3456", "E***7890", "F***2345", "G***6789", "H***0123"]
            },
            {
                "cluster_id": 2,
                "ring_type": "SMURFING_DISPERSION",
                "cluster_size": 7,
                "total_mule_volume": 890000.0,
                "avg_mule_risk": 88.5,
                "members": ["M***4321", "N***8765", "O***2109", "P***6543", "Q***0987", "R***5432", "S***9876"]
            },
            {
                "cluster_id": 3,
                "ring_type": "FUNNEL_COLLECTION",
                "cluster_size": 6,
                "total_mule_volume": 670000.0,
                "avg_mule_risk": 82.1,
                "members": ["X***1111", "Y***2222", "Z***3333", "W***4444", "V***5555", "U***6666"]
            },
            {
                "cluster_id": 4,
                "ring_type": "STAR_HUB",
                "cluster_size": 5,
                "total_mule_volume": 450000.0,
                "avg_mule_risk": 79.4,
                "members": ["K***7777", "L***8888", "J***9999", "I***0000", "H***1212"]
            }
        ]
    }
