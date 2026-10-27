// API client for the FastAPI backend, with graceful synthetic fallback.
// All calls go through the Vite proxy (/api -> 127.0.0.1:8000), so no CORS
// is needed in dev; the same rewrite maps cleanly onto a production origin.

const BASE = "/api";
const TIMEOUT_MS = 2500;

const withTimeout = async (url, opts = {}) => {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), TIMEOUT_MS);
  try {
    return await fetch(url, { ...opts, signal: ctrl.signal });
  } finally {
    clearTimeout(timer);
  }
};

// ---------------------------------------------------------------- health ----
export async function fetchHealth() {
  try {
    const r = await withTimeout(`${BASE}/health`);
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const body = await r.json();
    return {
      online: true,
      model: body.model_version || "unknown",
      contract: body.model_contract,
      embeddings: body.embeddings_loaded,
      p99: body.p99_ms,
      p99Worst: body.p99_worst_ms,
      calibrated: body.calibrated,
      commit: body.commit,
    };
  } catch {
    return { online: false };
  }
}

// ----------------------------------------------------------------- score ----
// Payload mirrors backend.ScoreRequest; UPI-only fields the mock stream has
// are always sent, balance-drain errors are derived from ip_risk the same way
// the synthetic rim values suggest. The backend returns {score, action,
// explanation[], latency_ms}; on any failure we return null so the caller
// keeps the synthetic verdict (documented fallback behavior).
export async function scoreTxn(t) {
  const body = {
    txn_id: t.txnId,
    sender: t.sender,
    receiver: t.receiver,
    amount: t.amount,
    tx_type: t.ringId ? "TRANSFER" : t.amount > 40000 ? "CASH_OUT" : "PAYMENT",
    velocity_10min: t.ringId ? Math.round(t.ipRisk * 12) : t.deviceChange ? 2 : 0,
    device_change: t.deviceChange,
    ip_risk: t.ipRisk,
    origin_balance_error: -t.ipRisk * 8,
    dest_balance_error: -t.ipRisk * 5,
    sender_state: t.state || null,
    receiver_state: t.receiverState || t.state || null,
  };
  try {
    const r = await withTimeout(`${BASE}/score`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!r.ok) return null;
    const j = await r.json();
    const score = Math.max(0, Math.min(100, Math.round(j.score)));
    return {
      score,
      action: j.action,
      explanation: j.explanation || null,
      latencyMs: j.latency_ms,
      model: "onnx",
    };
  } catch {
    return null; // caller falls back to the synthetic score
  }
}

