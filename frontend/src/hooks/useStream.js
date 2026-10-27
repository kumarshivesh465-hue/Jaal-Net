import { useCallback, useEffect, useRef, useState } from "react";
import {
  initialStream,
  generateTransaction,
  STREAM_BATCH_SIZE,
  MAX_STREAM_SIZE,
  REFRESH_INTERVAL_MS,
} from "../lib/mock.js";
import { fetchHealth, scoreTxn } from "../lib/api.js";

// Live stream engine for the whole console.
//
// Every tick generates STREAM_BATCH_SIZE new transactions (data.py port) and
// prepends them. When the backend is online, each new transaction is POSTed to
// /score and gets the real model's score/action/explanation (unioned by id);
// on failure it keeps its synthetic verdict — the documented fallback path.
// Analyst overrides (Block / Step-Up / Allow) mutate the row and are logged
// into `events` for the audit tab.

export function useStream() {
  const [stream, setStream] = useState(() => initialStream(30));
  const [health, setHealth] = useState({ online: false, checking: true });
  const [isStreaming, setIsStreaming] = useState(true);
  const counter = useRef(1000);
  const pending = useRef(new Set()); // txn ids awaiting a /score union

  const patch = useCallback((txnId, changes) => {
    setStream((prev) =>
      prev.map((t) => (t.txnId === txnId ? { ...t, ...changes } : t))
    );
  }, []);

  // health poll (10s)
  useEffect(() => {
    let alive = true;
    const poll = async () => {
      const h = await fetchHealth();
      if (alive) setHealth({ ...h, checking: false });
    };
    poll();
    const id = setInterval(poll, 10000);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, []);

  // Fetch real Exasol transactions whenever backend is online
  useEffect(() => {
    if (!health.online) return;
    fetch("/api/transactions?limit=40")
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (data && data.length > 0) {
          const mapped = data.map((d) => ({
            txnId: d.txn_id,
            ts: new Date(d.txn_timestamp || Date.now()).getTime(),
            sender: d.sender_account,
            receiver: d.receiver_account,
            amount: parseFloat(d.amount_inr || 1000),
            score: d.model_score != null ? Math.round(d.model_score) : 15,
            action: d.action_taken || "ALLOW",
            state: d.sender_state || "MH",
            deviceChange: !!d.device_change_flag,
            ipRisk: parseFloat(d.ip_risk_score || 0.1),
            ringId: d.ring_id || null,
            model: "Exasol In-Memory DB",
          }));
          setStream(mapped);
        }
      })
      .catch((err) => console.warn("Could not load initial Exasol transactions:", err));
  }, [health.online]);

  // stream tick
  useEffect(() => {
    if (!isStreaming) return;

    const tick = () => {
      counter.current += 1;
      const fresh = Array.from(
        { length: STREAM_BATCH_SIZE },
        () => generateTransaction(counter.current++)
      );
      setStream((prev) => [...fresh, ...prev].slice(0, MAX_STREAM_SIZE));

      if (health.online) {
        fresh.forEach((t) => {
          if (pending.current.has(t.txnId)) return;
          pending.current.add(t.txnId);
          scoreTxn(t).then((res) => {
            if (res) patch(t.txnId, res);
            pending.current.delete(t.txnId);
          });
        });
      }
    };

    const id = setInterval(tick, REFRESH_INTERVAL_MS);
    return () => clearInterval(id);
  }, [isStreaming, health.online, patch]);

  // inject custom transaction from simulator
  const injectTxn = useCallback(
    (customTxn) => {
      setStream((prev) => [customTxn, ...prev].slice(0, MAX_STREAM_SIZE));
      if (health.online) {
        scoreTxn(customTxn).then((res) => {
          if (res) patch(customTxn.txnId, res);
        });
      }
    },
    [health.online, patch]
  );

  const toggleStreaming = useCallback(() => {
    setIsStreaming((prev) => !prev);
  }, []);

  // analyst action: mutate the row in place and log an audit event
  const analystAct = useCallback((txnId, act) => {
    setStream((prev) =>
      prev.map((t) => {
        if (t.txnId !== txnId) return t;
        const score =
          act === "BLOCK" ? Math.max(95, t.score) : act === "ALLOW" ? Math.min(20, t.score) : t.score;
        return {
          ...t,
          action: act,
          score,
          overridden: act,
        };
      })
    );
    return { ts: Date.now(), txnId, act };
  }, []);

  return { stream, health, patch, analystAct, injectTxn, isStreaming, toggleStreaming };
}
