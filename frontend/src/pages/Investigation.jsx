import { useEffect, useMemo, useState } from "react";
import GraphCytoscape from "../components/GraphCytoscape.jsx";
import RiskReactor from "../components/RiskReactor.jsx";
import AiInvestigatorDrawer from "../components/AiInvestigatorDrawer.jsx";
import { ScoreBadge, SectionHeader } from "../components/ui.jsx";
import { scoreColor } from "../lib/mock.js";
import { ShieldAlert, Network, Sliders, CheckCircle2, Bot, Sparkles, Loader2 } from "lucide-react";

export default function Investigation({ txn, analystAct, onViewRing }) {
  const [actionFeedback, setActionFeedback] = useState(null);
  const [agentOpen, setAgentOpen] = useState(false);
  const [graphData, setGraphData] = useState(() => ({ nodes: [], edges: [] }));
  const [graphLoading, setGraphLoading] = useState(false);

  useEffect(() => {
    if (!txn?.sender) return;
    setGraphLoading(true);

    const targetUrl = txn.ringId
      ? `/api/rings/${encodeURIComponent(txn.ringId)}`
      : `/api/graph/neighborhood?account=${encodeURIComponent(txn.sender)}&hops=2`;

    fetch(targetUrl)
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (data && data.nodes && data.nodes.length > 1) {
          const nodesWithFocus = data.nodes.map((n) => ({
            ...n,
            focus: n.id === txn.sender ? "source" : n.id === txn.receiver ? "target" : n.focus,
          }));
          const edgesWithFocus = (data.edges || []).map((e) => ({
            ...e,
            focus: (e.source === txn.sender && e.target === txn.receiver) || e.focus,
          }));
          setGraphData({ ...data, nodes: nodesWithFocus, edges: edgesWithFocus });
        } else {
          const receiverId = txn.receiver || (txn.sender?.includes("@") ? "counterparty.merchant@hdfc" : "RETAIL_COUNTERPARTY");
          setGraphData({
            nodes: [
              { id: txn.sender, label: txn.sender, score: txn.score ?? 50, focus: "source" },
              { id: receiverId, label: receiverId, score: 20, focus: "target" },
            ],
            edges: [
              {
                id: "e-direct",
                source: txn.sender,
                target: receiverId,
                amount: txn.amount || 1000,
                type: txn.ringId ? "ring" : "normal",
                score: txn.score ?? 50,
                focus: true,
              },
            ],
          });
        }
      })
      .catch((err) => {
        console.warn("Exasol neighborhood graph fetch error:", err);
        const receiverId = txn.receiver || (txn.sender?.includes("@") ? "counterparty.merchant@hdfc" : "RETAIL_COUNTERPARTY");
        setGraphData({
          nodes: [
            { id: txn.sender, label: txn.sender, score: txn.score ?? 50, focus: "source" },
            { id: receiverId, label: receiverId, score: 20, focus: "target" },
          ],
          edges: [
            {
              id: "e-direct",
              source: txn.sender,
              target: receiverId,
              amount: txn.amount || 1000,
              type: txn.ringId ? "ring" : "normal",
              score: txn.score ?? 50,
              focus: true,
            },
          ],
        });
      })
      .finally(() => setGraphLoading(false));
  }, [txn?.txnId, txn?.sender, txn?.receiver, txn?.ringId]);

  const explanation = useMemo(() => {
    if (!txn) return [];
    if (txn.explanation && txn.explanation.length > 0) return txn.explanation;
    const items = [];
    if (txn.ringId) items.push(["Mule syndicate topology match", 0.42]);
    if (txn.deviceChange) items.push(["New hardware device switch detected", 0.28]);
    if (txn.ipRisk > 0.3) items.push(["High-risk ASN / proxy IP hop", Math.round(txn.ipRisk * 0.3 * 100) / 100]);
    if (txn.amount > 30000) items.push(["High-value burst volume anomaly", 0.18]);
    items.push(["GNN Temporal velocity spike", 0.12]);
    return items.sort((a, b) => b[1] - a[1]);
  }, [txn?.txnId, txn?.model, txn?.score, txn?.ringId, txn?.deviceChange, txn?.ipRisk, txn?.amount]);

  if (!txn)
    return (
      <div className="liquid-glass p-8 text-slate-500 text-center">
        No transaction selected for investigation. Select an alert from the Command Center stream.
      </div>
    );

  const overridden = txn.overridden;

  const handleAction = (actOrTxnId, maybeAct) => {
    const raw = typeof maybeAct === "string" ? maybeAct : typeof actOrTxnId === "string" ? actOrTxnId : "BLOCK";
    const act = ["BLOCK", "STEP_UP", "ALLOW"].includes(raw.toUpperCase()) ? raw.toUpperCase() : "BLOCK";
    analystAct(txn.txnId, act);
    setActionFeedback({
      act,
      msg:
        act === "BLOCK"
          ? `Mule Account ${txn.sender} marked for immediate suspension`
          : act === "STEP_UP"
          ? `Biometric step-up challenge sent for ${txn.txnId}`
          : `Transaction ${txn.txnId} approved and whitelisted`,
      color:
        act === "BLOCK"
          ? "#FF0055"
          : act === "STEP_UP"
          ? "#FF9500"
          : "#10B981",
    });
    setTimeout(() => setActionFeedback(null), 3500);
  };

  return (
    <div className="space-y-6">
      {/* Dossier Header in Liquid Glass Card */}
      <div
        className="liquid-glass p-6 sm:p-8 transition-all"
        style={{ borderLeft: `6px solid ${scoreColor(txn.score)}` }}
      >
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <div className="text-[10px] font-bold tracking-[0.14em] text-slate-500 uppercase flex items-center gap-2">
              <span>ALERT DOSSIER // {txn.txnId}</span>
              <span>•</span>
              <span className="text-[#2E69FF] font-mono2 font-bold">
                {txn.model === "onnx"
                  ? "Scored by ONNX TGAT+SAGE"
                  : "Synthetic Baseline Fallback"}
              </span>
            </div>
            <div className="font-sans text-2xl sm:text-3xl font-bold text-slate-900 mt-2 flex flex-wrap items-center gap-3 tracking-tight">
              <span>
                GNN Risk Score:{" "}
                <span style={{ color: scoreColor(txn.score) }}>
                  {txn.score}/100
                </span>
              </span>
              <span
                className="font-marker text-xs px-3 py-1 rounded-full border border-current font-normal"
                style={{
                  background: `${scoreColor(txn.score)}15`,
                  color: scoreColor(txn.score),
                }}
              >
                {txn.score >= 90
                  ? (txn.ringId ? "CRITICAL MULE RING" : "CRITICAL VELOCITY BURST")
                  : txn.score >= 70
                  ? "VELOCITY BURST"
                  : "ALLOWABLE P2P"}
              </span>
              {overridden && (
                <span className={`px-2.5 py-0.5 rounded-full text-xs font-bold border ${
                  overridden === "BLOCK"
                    ? "bg-red-100 text-[#FF0055] border-red-200"
                    : overridden === "STEP_UP"
                    ? "bg-amber-100 text-amber-800 border-amber-200"
                    : "bg-emerald-100 text-emerald-800 border-emerald-200"
                }`}>
                  AUTONOMOUS ACTION: {overridden}
                </span>
              )}
            </div>
            <div className="font-mono2 text-sm mt-2 text-slate-700">
              <span className="font-bold text-slate-900">{txn.sender}</span>
              <span className="text-[#2E69FF] font-bold"> ➔ </span>
              <span className="font-bold text-slate-900">{txn.receiver}</span>
              <span className="text-[#2E69FF] font-bold">
                {" "}
                · ₹{txn.amount.toLocaleString("en-IN", { maximumFractionDigits: 2 })}
              </span>
              <span className="text-slate-500 font-normal">
                {" "}
                · {new Date(txn.ts).toLocaleTimeString("en-IN", { hour12: false })} IST · State: {txn.state}
              </span>
            </div>
          </div>

          <div className="flex flex-col sm:flex-row items-end sm:items-center gap-3">
            {/* Autonomous AI Investigator Launch Button */}
            <button
              onClick={() => setAgentOpen(true)}
              className="btn-sift-pink text-xs !py-3 !px-5 flex items-center gap-2 cursor-pointer shadow-xl animate-pulse"
            >
              <Bot size={16} />
              <span>Launch AI Investigator Agent</span>
            </button>

            <div className="text-right bg-white/70 backdrop-blur-md p-4 rounded-2xl border border-slate-200/80 shadow-sm">
              <div className="text-[10px] font-bold text-slate-400 tracking-widest uppercase">
                Syndicate Ring
              </div>
              <div className="mt-0.5">
                {txn.ringId ? (
                  <button
                    onClick={() => onViewRing && onViewRing(txn.ringId)}
                    className="font-mono2 text-base font-bold text-[#FF0055] hover:underline flex items-center gap-1 justify-end cursor-pointer"
                    title="Click to explore this ring in Syndicate Explorer"
                  >
                    <span>{txn.ringId}</span>
                    <span className="text-[10px] bg-red-100 text-[#FF0055] px-1.5 py-0.5 rounded font-sans">EXPLORE ➔</span>
                  </button>
                ) : (
                  <span className="font-mono2 text-sm font-semibold text-slate-500">
                    None (Standalone Transaction)
                  </span>
                )}
              </div>
              <div className="text-xs text-slate-500 mt-1">
                IP Risk: <b className="text-slate-800">{Number(txn.ipRisk || 0).toFixed(2)}</b> · Device Anomaly:{" "}
                <b className={txn.deviceChange ? "text-[#FF0055]" : "text-[#10B981]"}>
                  {txn.deviceChange ? "YES" : "NO"}
                </b>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Action Toast Feedback */}
      {actionFeedback && (
        <div
          className="p-3.5 px-5 rounded-2xl border flex items-center justify-between text-xs font-mono2 shadow-lg animate-in fade-in slide-in-from-top-1"
          style={{
            background: "#FFFFFF",
            borderColor: actionFeedback.color,
            borderLeft: `5px solid ${actionFeedback.color}`,
          }}
        >
          <span className="text-slate-900 font-bold">
            Action Recorded: {actionFeedback.msg}
          </span>
          <span
            className="font-bold px-2.5 py-1 rounded-full text-[10px]"
            style={{
              background: `${actionFeedback.color}18`,
              color: actionFeedback.color,
            }}
          >
            {actionFeedback.act}
          </span>
        </div>
      )}

      <div className="grid grid-cols-1 xl:grid-cols-5 gap-6">
        {/* 2-hop topology in Liquid Glass Container */}
        <div className="xl:col-span-3 liquid-glass p-6 space-y-3">
          <SectionHeader>
            2-Hop Subgraph Topology (Cytoscape Matrix)
          </SectionHeader>
          <GraphCytoscape graph={graphData} height={480} />
        </div>

        {/* Reactor + Explanations + Actions */}
        <div className="xl:col-span-2 space-y-6">
          <div className="bg-[#000B29] rounded-3xl border border-slate-800 p-6 shadow-xl">
            <div className="font-sans font-bold text-base text-white mb-2">
              3D Holographic Risk Reactor
            </div>
            <RiskReactor score={txn.score} action={txn.action} height={220} />
          </div>

          <div className="liquid-glass p-6 space-y-4">
            <SectionHeader
              extra={
                <span className="text-[10px] text-slate-400 font-mono2">
                  {txn.model === "onnx"
                    ? "SHAP / GNN GraphSAGE weights"
                    : "Attribution fallback"}
                </span>
              }
            >
              Attribution Signals
            </SectionHeader>

            <div className="space-y-2">
              {explanation.map(([label, weight], idx) => {
                const pct = Math.round(weight * 100);
                return (
                  <div key={idx} className="space-y-1">
                    <div className="flex justify-between text-xs font-mono2">
                      <span className="text-slate-700 capitalize">{label}</span>
                      <span className="font-bold text-slate-900">{pct}%</span>
                    </div>
                    <div className="w-full bg-slate-100 rounded-full h-1.5 overflow-hidden">
                      <div
                        className="h-full rounded-full transition-all duration-500"
                        style={{
                          width: `${pct}%`,
                          background:
                            idx === 0
                              ? "#FF0055"
                              : idx === 1
                              ? "#2E69FF"
                              : idx === 2
                              ? "#FFCA36"
                              : "#10B981",
                        }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>

            <div className="pt-4 border-t border-slate-200">
              <div className="text-[10px] font-bold uppercase tracking-wider text-slate-400 mb-2">
                Analyst Override Action
              </div>
              <div className="grid grid-cols-3 gap-2">
                <button
                  onClick={() => handleAction("ALLOW")}
                  className="px-3 py-2 rounded-xl border border-emerald-300 bg-emerald-50 text-emerald-800 font-bold text-xs hover:bg-emerald-100 transition-colors cursor-pointer"
                >
                  ALLOW
                </button>
                <button
                  onClick={() => handleAction("STEP_UP")}
                  className="px-3 py-2 rounded-xl border border-amber-300 bg-amber-50 text-amber-800 font-bold text-xs hover:bg-amber-100 transition-colors cursor-pointer"
                >
                  STEP-UP
                </button>
                <button
                  onClick={() => handleAction("BLOCK")}
                  className="px-3 py-2 rounded-xl border border-red-300 bg-red-50 text-[#FF0055] font-bold text-xs hover:bg-red-100 transition-colors cursor-pointer"
                >
                  FREEZE
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Autonomous AI Investigator Modal */}
      <AiInvestigatorDrawer
        txn={txn}
        isOpen={agentOpen}
        onClose={() => setAgentOpen(false)}
        onFreezeAccount={(id, act) => handleAction(act || id || "BLOCK")}
      />
    </div>
  );
}
