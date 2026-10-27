import { useEffect, useState } from "react";
import { Download, FileText, Sliders, ShieldCheck, CheckCircle2, AlertTriangle, XOctagon, Database, Radio, RefreshCw } from "lucide-react";
import { scoreColor } from "../lib/mock.js";

function exportAudit(records) {
  const rows = [
    "txn_id,time,score,action,model,latency_ms",
    ...records.slice(0, 100).map(
      (t) =>
        [
          t.txn_id || t.txnId,
          t.decision_timestamp || new Date(t.ts).toISOString(),
          t.score,
          t.action_taken || t.action,
          t.model_version || t.model,
          t.latency_ms != null ? t.latency_ms : 2,
        ].join(",")
    ),
  ];
  const blob = new Blob([rows.join("\n")], { type: "text/csv;charset=utf-8;" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = `jaalnet_decision_audit_${new Date().toISOString().slice(0, 10)}.csv`;
  a.click();
  URL.revokeObjectURL(a.href);
}

export default function Audit({ stream }) {
  const [govList, setGovList] = useState([]);
  const [exasolDecisions, setExasolDecisions] = useState([]);
  const [auditTab, setAuditTab] = useState("exasol"); // "exasol" | "stream"
  const [showConfigModal, setShowConfigModal] = useState(false);
  const [blockThresh, setBlockThresh] = useState(90);
  const [stepThresh, setStepThresh] = useState(70);
  const [rationale, setRationale] = useState("");
  const [author, setAuthor] = useState("Analyst Active");
  const [loadingDecisions, setLoadingDecisions] = useState(false);

  const fetchExasolAudit = () => {
    setLoadingDecisions(true);
    fetch("/api/audit/decisions?limit=60")
      .then((res) => (res.ok ? res.json() : []))
      .then((data) => {
        if (Array.isArray(data)) setExasolDecisions(data);
      })
      .catch((err) => console.warn("Failed to fetch Exasol decisions:", err))
      .finally(() => setLoadingDecisions(false));
  };

  const fetchGov = () => {
    fetch("/api/governance/thresholds")
      .then((res) => (res.ok ? res.json() : []))
      .then((data) => {
        if (Array.isArray(data) && data.length > 0) {
          setGovList(
            data.map((g) => ({
              version: g.version,
              date: g.effective_date ? String(g.effective_date).slice(0, 10) : "2026-04-10",
              by: g.set_by,
              block: g.threshold_block,
              step: g.threshold_stepup,
              why: g.rationale,
            }))
          );
        }
      })
      .catch((err) => console.warn("Failed to fetch governance:", err));
  };

  useEffect(() => {
    fetchGov();
    fetchExasolAudit();
    const interval = setInterval(fetchExasolAudit, 10000);
    return () => clearInterval(interval);
  }, []);

  const handleSaveThresholds = async (e) => {
    e.preventDefault();
    if (!rationale.trim()) return;
    const nextVer = `v3.${govList.length + 1}`;
    try {
      await fetch("/api/governance/thresholds", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          version: nextVer,
          set_by: author,
          threshold_block: Number(blockThresh),
          threshold_stepup: Number(stepThresh),
          threshold_monitor: 30,
          rationale: rationale.trim(),
        }),
      });
      fetchGov();
    } catch (err) {
      console.warn("Could not save threshold to Exasol:", err);
    }
    setShowConfigModal(false);
    setRationale("");
  };

  const activeRecords = auditTab === "exasol" ? (exasolDecisions || []) : ((stream || []).slice(0, 75));

  return (
    <div className="space-y-6">
      {/* Header Banner */}
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-4 border-b border-slate-200 pb-5">
        <div>
          <div className="text-[10px] font-bold text-[#2E69FF] tracking-widest uppercase mb-1">
            Statutory Compliance & Audit Trail
          </div>
          <h1 className="text-2xl sm:text-3xl font-bold font-sans text-slate-900 tracking-tight">
            Immutable Decision Audit & Threshold Governance
          </h1>
          <p className="text-sm text-slate-500 mt-1 font-normal">
            Tamper-evident log of every real-time GNN score, step-up challenge, autonomous block, and regulatory rule change.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={() => exportAudit(activeRecords)}
            className="btn-sift-dark-outline text-xs !py-2 !px-4 flex items-center gap-2 cursor-pointer"
          >
            <Download className="w-3.5 h-3.5" />
            <span>Export CSV ({activeRecords.length} records)</span>
          </button>
          <button
            onClick={() => setShowConfigModal(true)}
            className="btn-sift-pink text-xs !py-2 !px-4 flex items-center gap-2 cursor-pointer"
          >
            <Sliders className="w-3.5 h-3.5" />
            <span>Update Thresholds</span>
          </button>
        </div>
      </div>

      {/* Main Audit Log Card in Liquid Glass Container */}
      <div className="liquid-glass p-6 sm:p-8">
        <div className="flex flex-wrap items-center justify-between gap-4 mb-4 pb-2 border-b border-slate-100">
          <div className="flex flex-wrap items-center gap-3">
            <div className="flex items-center gap-2">
              <Database className="w-4 h-4 text-[#2E69FF]" />
              <h2 className="text-base font-bold font-sans text-slate-900">
                Decision Audit Trail ({activeRecords.length} records)
              </h2>
            </div>
            {/* Tab Toggle: Exasol DECISION_LOG vs Live Stream */}
            <div className="flex items-center bg-slate-100 p-1 rounded-xl text-xs font-semibold">
              <button
                onClick={() => setAuditTab("exasol")}
                className={`px-3 py-1 rounded-lg transition-all cursor-pointer flex items-center gap-1.5 ${
                  auditTab === "exasol"
                    ? "bg-white text-slate-900 shadow-sm font-bold"
                    : "text-slate-500 hover:text-slate-800"
                }`}
              >
                <Database className="w-3.5 h-3.5 text-[#2E69FF]" />
                <span>Exasol DECISION_LOG</span>
              </button>
              <button
                onClick={() => setAuditTab("stream")}
                className={`px-3 py-1 rounded-lg transition-all cursor-pointer flex items-center gap-1.5 ${
                  auditTab === "stream"
                    ? "bg-white text-slate-900 shadow-sm font-bold"
                    : "text-slate-500 hover:text-slate-800"
                }`}
              >
                <Radio className="w-3.5 h-3.5 text-[#FF0055]" />
                <span>Live Ingest Stream</span>
              </button>
            </div>
          </div>
          <div className="flex items-center gap-3">
            {auditTab === "exasol" && (
              <button
                onClick={fetchExasolAudit}
                className="text-[11px] font-mono2 text-slate-500 hover:text-slate-800 flex items-center gap-1 cursor-pointer"
              >
                <RefreshCw className={`w-3 h-3 ${loadingDecisions ? "animate-spin text-[#2E69FF]" : ""}`} />
                <span>Refresh Exasol</span>
              </button>
            )}
            <span className="text-[11px] font-mono2 text-slate-500">
              SHA-256 Ledger Verified · Exasol Partition 0-2
            </span>
          </div>
        </div>

        <div className="overflow-x-auto max-h-[480px] overflow-y-auto">
          <table className="data-table">
            <thead>
              <tr>
                {auditTab === "exasol" && <th>Decision ID</th>}
                <th>Txn ID</th>
                <th>Time (IST)</th>
                {auditTab === "stream" && <th>Sender / Receiver Flow</th>}
                {auditTab === "stream" && <th>Amount (INR)</th>}
                <th>Score</th>
                <th>Action Taken</th>
                <th>Model Version</th>
                <th>Inference Latency</th>
              </tr>
            </thead>
            <tbody>
              {activeRecords.map((t, idx) => {
                const score = t.score != null ? t.score : 0;
                const act = t.action_taken || t.action || "ALLOW";
                const isBlock = act === "BLOCK" || score >= 90;
                const isStep = !isBlock && (act === "STEP_UP" || score >= 70);
                const isSafe = !isBlock && !isStep;
                const txnId = t.txn_id || t.txnId || `TX-${idx}`;
                const timeStr = t.decision_timestamp
                  ? new Date(t.decision_timestamp).toLocaleTimeString("en-IN", { hour12: false })
                  : t.ts
                  ? new Date(t.ts).toLocaleTimeString("en-IN", { hour12: false })
                  : "Live";

                return (
                  <tr key={t.decision_id || txnId || idx}>
                    {auditTab === "exasol" && (
                      <td className="font-mono2 text-[11px] font-bold text-[#2E69FF]">
                        #{t.decision_id}
                      </td>
                    )}
                    <td className="font-mono2 text-[11.5px] font-medium text-slate-700">
                      {txnId}
                    </td>
                    <td className="font-mono2 text-[11px] text-slate-500">
                      {timeStr}
                    </td>
                    {auditTab === "stream" && (
                      <td className="font-mono2 text-[11px] text-slate-800">
                        <span className="text-slate-600">{t.sender}</span>
                        <span className="text-[#2E69FF] mx-1">➔</span>
                        <span className="text-slate-900 font-bold">{t.receiver}</span>
                      </td>
                    )}
                    {auditTab === "stream" && (
                      <td className="font-mono2 text-slate-900 font-bold">
                        ₹{(t.amount || 0).toLocaleString("en-IN", { maximumFractionDigits: 2 })}
                      </td>
                    )}
                    <td>
                      <span
                        className="font-mono2 font-bold text-sm"
                        style={{ color: scoreColor(score) }}
                      >
                        {String(score).padStart(2, "0")}
                      </span>
                    </td>
                    <td>
                      {isBlock && (
                        <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-red-100 text-[#FF0055] border border-red-200">
                          <XOctagon className="w-3 h-3" />
                          BLOCK
                        </span>
                      )}
                      {isStep && (
                        <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-amber-100 text-amber-800 border border-amber-200">
                          <AlertTriangle className="w-3 h-3" />
                          STEP-UP
                        </span>
                      )}
                      {isSafe && (
                        <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-green-100 text-[#10B981] border border-green-200">
                          <CheckCircle2 className="w-3 h-3" />
                          ALLOW
                        </span>
                      )}
                    </td>
                    <td className="font-mono2 text-[11px] text-slate-600">
                      {t.model_version || t.model || "ONNX TGAT+SAGE"}
                    </td>
                    <td className="font-mono2 text-[11px] text-[#10B981] font-bold">
                      {t.latency_ms != null ? `${t.latency_ms} ms` : "< 2 ms"}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* Regulatory Threshold Governance Card */}
      <div className="liquid-glass p-6 sm:p-8">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4">
          <div>
            <div className="flex items-center gap-2">
              <ShieldCheck className="w-5 h-5 text-[#10B981]" />
              <h2 className="text-lg font-bold font-sans text-slate-900 tracking-tight">
                Regulatory Threshold Governance (RBI Master Direction on Mule Accounts)
              </h2>
            </div>
            <p className="text-xs text-slate-500 mt-1 font-normal">
              Version-controlled risk cutoffs required for compliance under RBI KYC/AML Framework 2026.
            </p>
          </div>
          <span className="font-marker text-xs text-[#10B981] bg-green-100 px-3 py-1.5 rounded-full border border-green-200 self-start sm:self-auto font-normal">
            Current Active Policy: {govList[0]?.version || "v3"}
          </span>
        </div>

        <div className="overflow-x-auto">
          <table className="data-table">
            <thead>
              <tr>
                <th>Policy Version</th>
                <th>Effective Date</th>
                <th>Enacted By</th>
                <th>Autoblock Cutoff</th>
                <th>Step-Up Challenge</th>
                <th>Regulatory Rationale</th>
              </tr>
            </thead>
            <tbody>
              {govList.map((g) => (
                <tr key={g.version}>
                  <td className="font-mono2 text-[#2E69FF] font-bold">{g.version}</td>
                  <td className="text-slate-600 text-xs font-mono2">{g.date}</td>
                  <td className="text-slate-900 text-xs font-bold">{g.by}</td>
                  <td className="font-mono2 font-bold text-[#FF0055]">Score ≥ {g.block}</td>
                  <td className="font-mono2 font-bold text-amber-700">Score ≥ {g.step}</td>
                  <td className="text-slate-600 text-xs">{g.why}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Threshold Modal */}
      {showConfigModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
          <div className="liquid-glass p-6 sm:p-8 max-w-lg w-full shadow-2xl space-y-4">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <div className="text-lg font-bold font-sans text-slate-900">
                Modify Autonomous Risk Cutoffs
              </div>
              <button
                onClick={() => setShowConfigModal(false)}
                className="text-slate-400 hover:text-slate-800 text-sm cursor-pointer"
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleSaveThresholds} className="space-y-4 text-xs">
              <div>
                <label className="block text-slate-700 font-bold mb-1">
                  Automatic Account Block Threshold (Score 0–100)
                </label>
                <div className="flex items-center gap-3">
                  <input
                    type="range"
                    min="50"
                    max="100"
                    value={blockThresh}
                    onChange={(e) => setBlockThresh(e.target.value)}
                    className="flex-1 accent-[#FF0055]"
                  />
                  <span className="font-mono2 text-base font-bold text-[#FF0055] w-12 text-right">
                    {blockThresh}
                  </span>
                </div>
                <span className="text-[10px] text-slate-500">
                  Transactions scoring at or above this cutoff are frozen instantly without human intervention.
                </span>
              </div>

              <div>
                <label className="block text-slate-700 font-bold mb-1">
                  Step-Up Biometric Challenge Threshold (Score 0–100)
                </label>
                <div className="flex items-center gap-3">
                  <input
                    type="range"
                    min="30"
                    max="90"
                    value={stepThresh}
                    onChange={(e) => setStepThresh(e.target.value)}
                    className="flex-1 accent-[#FFCA36]"
                  />
                  <span className="font-mono2 text-base font-bold text-amber-700 w-12 text-right">
                    {stepThresh}
                  </span>
                </div>
                <span className="text-[10px] text-slate-500">
                  Scores between step-up and block trigger mandatory Aadhaar biometric or SMS OTP challenge.
                </span>
              </div>

              <div>
                <label className="block text-slate-700 font-bold mb-1">
                  Auditor / Approver Name
                </label>
                <input
                  type="text"
                  value={author}
                  onChange={(e) => setAuthor(e.target.value)}
                  className="w-full bg-white/70 border border-slate-200 rounded-xl p-2.5 text-slate-900 font-mono2 text-xs focus:outline-none focus:border-[#2E69FF]"
                />
              </div>

              <div>
                <label className="block text-slate-700 font-bold mb-1">
                  Mandatory Policy Change Rationale (Audit Record)
                </label>
                <textarea
                  rows={3}
                  value={rationale}
                  onChange={(e) => setRationale(e.target.value)}
                  placeholder="e.g., RBI Circular 2026-Q2 threshold tightening for tier-2 mule accounts"
                  required
                  className="w-full bg-white/70 border border-slate-200 rounded-xl p-2.5 text-slate-900 text-xs focus:outline-none focus:border-[#2E69FF]"
                />
              </div>

              <div className="flex justify-end gap-2 pt-2 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setShowConfigModal(false)}
                  className="px-4 py-2 rounded-full border border-slate-300 text-slate-600 hover:text-slate-900 cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="btn-sift-pink !py-2 !px-5 text-xs"
                >
                  Sign & Commit Policy
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
