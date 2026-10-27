import { useState } from "react";
import {
  ShieldCheck,
  ShieldAlert,
  ShieldX,
  AlertTriangle,
  Store,
  ArrowDownLeft,
  ArrowUpRight,
  CheckCircle2,
  FileBadge,
  Download,
  X,
  Loader2,
  ChevronRight,
  Scan,
  Sparkles,
  Search,
  Info,
} from "lucide-react";

const PRESETS = [
  {
    name: "Sample Regular Customer",
    badge: "Benign Example",
    color: "emerald",
    counterparty: "customer.upi@okhdfcbank",
    amount: 150,
    direction: "INCOMING",
    desc: "Everyday retail customer with clean graph topology",
  },
  {
    name: "Sample Tainted Intermediary",
    badge: "1-Hop Example",
    color: "amber",
    counterparty: "P***8522",
    amount: 45000,
    direction: "INCOMING",
    desc: "Account with direct transactional link to Syndicate RING-001",
  },
  {
    name: "Sample Mule Syndicate Node",
    badge: "Blacklist Example",
    color: "rose",
    counterparty: "L***7350",
    amount: 240000,
    direction: "INCOMING",
    desc: "Confirmed active mule hub in Exasol RING_MEMBERS table",
  },
  {
    name: "Sample Unregistered High-Value Account",
    badge: "Cold-Start Example",
    color: "purple",
    counterparty: "ACC_00099999",
    amount: 95000,
    direction: "OUTGOING",
    desc: "New supplier outside historical graph with velocity burst",
  },
];

export default function MerchantShieldModal({ isOpen, onClose }) {
  const [merchantName, setMerchantName] = useState("Ramesh Kirana & General Store");
  const [direction, setDirection] = useState("INCOMING");
  const [counterparty, setCounterparty] = useState("");
  const [amount, setAmount] = useState("");
  const [isScanning, setIsScanning] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [inputHint, setInputHint] = useState("");

  if (!isOpen) return null;

  const handleRunCheck = async () => {
    if (!counterparty.trim()) {
      setError("Please enter a counterparty UPI VPA or Account ID.");
      return;
    }
    const numAmt = parseFloat(amount);
    if (isNaN(numAmt) || numAmt <= 0) {
      setError("Please enter a valid transaction amount greater than ₹0.");
      return;
    }

    setIsScanning(true);
    setError(null);
    setResult(null);
    setInputHint("");

    try {
      const resp = await fetch("/api/merchant/shield-check", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          merchant_id: merchantName.replace(/\s+/g, "_").toUpperCase(),
          counterparty: counterparty.trim(),
          amount: numAmt,
          direction: direction,
          category: "RETAIL_KIRANA",
        }),
      });

      if (!resp.ok) {
        const errText = await resp.text();
        throw new Error(`Exasol verification failed (HTTP ${resp.status}): ${errText || resp.statusText}`);
      }

      const data = await resp.json();
      setResult(data);
    } catch (err) {
      console.error("MerchantShield check failed:", err);
      setError(err.message || "Failed to reach Exasol backend. Ensure FastAPI server is running on port 8000.");
    } finally {
      setIsScanning(false);
    }
  };

  const handleSelectPreset = (p) => {
    setCounterparty(p.counterparty);
    setAmount(p.amount);
    setDirection(p.direction);
    setResult(null); // Explicitly reset result so user must verify
    setError(null);
    setInputHint(`Loaded preset: ${p.name}. Click "Run Pre-Flight Exasol Verification" to test.`);
  };

  const downloadCert = () => {
    if (!result) return;
    const blob = new Blob([JSON.stringify(result, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `SAFE_PAY_CERT_${result.shield_certificate?.cert_id || "CERT"}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-md">
      <div className="relative w-full max-w-4xl max-h-[92vh] overflow-y-auto bg-[#EEF2F9] dark:bg-slate-950 border border-slate-300 dark:border-slate-800 rounded-3xl shadow-2xl p-6 sm:p-8">
        {/* Close Button */}
        <button
          onClick={onClose}
          className="absolute top-6 right-6 p-2 rounded-full text-slate-500 hover:text-slate-800 dark:hover:text-white hover:bg-slate-200 dark:hover:bg-slate-800 transition cursor-pointer"
          title="Close"
        >
          <X className="w-5 h-5" />
        </button>

        {/* Header */}
        <div className="flex items-center gap-3 mb-2">
          <div className="p-2.5 rounded-2xl bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20">
            <ShieldCheck className="w-7 h-7" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-xl font-bold text-slate-900 dark:text-white tracking-tight">
                JaalNet MerchantShield™
              </h2>
              <span className="px-2.5 py-0.5 text-xs font-semibold rounded-full bg-emerald-500/15 text-emerald-700 dark:text-emerald-300 border border-emerald-500/30">
                Pre-Flight Defense
              </span>
            </div>
            <p className="text-xs sm:text-sm text-slate-500 dark:text-slate-400">
              Real-time Exasol Graph Distance Analysis & Police Debit Lien Safeguard (MHA 1930 / I4C)
            </p>
          </div>
        </div>

        {/* Problem Context Banner */}
        <div className="my-3 p-3.5 rounded-2xl bg-blue-500/10 border border-blue-500/20 text-blue-900 dark:text-blue-200 text-xs leading-relaxed flex items-start gap-2.5">
          <Info className="w-4 h-4 text-blue-600 dark:text-blue-400 shrink-0 mt-0.5" />
          <div>
            <strong>How It Works:</strong> Enter any customer UPI ID or vendor account. When you click <strong>Run Pre-Flight Exasol Verification</strong>, the system executes a real-time multi-hop graph query in Exasol memory to check if the account is within 0, 1, or 2 hops of an active mule syndicate. If the account is new, the CatBoost cold-start model evaluates velocity risk.
          </div>
        </div>

        {/* Config Grid */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
          {/* Merchant Profile */}
          <div className="p-3.5 rounded-2xl bg-white/70 dark:bg-slate-900/70 border border-slate-200 dark:border-slate-800">
            <label className="block text-[11px] font-semibold uppercase tracking-wider text-slate-500 mb-1.5 flex items-center gap-1.5">
              <Store className="w-3.5 h-3.5 text-slate-400" /> Your Merchant Name
            </label>
            <select
              value={merchantName}
              onChange={(e) => {
                setMerchantName(e.target.value);
                setResult(null);
              }}
              className="w-full text-xs font-medium bg-transparent text-slate-800 dark:text-slate-200 outline-none cursor-pointer"
            >
              <option value="Ramesh Kirana & General Store">Ramesh Kirana & General Store</option>
              <option value="Sharma Electronics & Mobile">Sharma Electronics & Mobile</option>
              <option value="Modern Agri B2B Supplies">Modern Agri B2B Wholesale</option>
            </select>
          </div>

          {/* Direction */}
          <div className="p-3.5 rounded-2xl bg-white/70 dark:bg-slate-900/70 border border-slate-200 dark:border-slate-800">
            <label className="block text-[11px] font-semibold uppercase tracking-wider text-slate-500 mb-1.5">
              Payment Direction
            </label>
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => {
                  setDirection("INCOMING");
                  setResult(null);
                }}
                className={`flex-1 py-1.5 px-2 rounded-xl text-xs font-semibold flex items-center justify-center gap-1.5 transition cursor-pointer ${
                  direction === "INCOMING"
                    ? "bg-emerald-600 text-white shadow-sm"
                    : "bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 hover:bg-slate-200"
                }`}
              >
                <ArrowDownLeft className="w-3.5 h-3.5" /> Customer QR
              </button>
              <button
                type="button"
                onClick={() => {
                  setDirection("OUTGOING");
                  setResult(null);
                }}
                className={`flex-1 py-1.5 px-2 rounded-xl text-xs font-semibold flex items-center justify-center gap-1.5 transition cursor-pointer ${
                  direction === "OUTGOING"
                    ? "bg-blue-600 text-white shadow-sm"
                    : "bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 hover:bg-slate-200"
                }`}
              >
                <ArrowUpRight className="w-3.5 h-3.5" /> Vendor Payout
              </button>
            </div>
          </div>

          {/* Amount */}
          <div className="p-3.5 rounded-2xl bg-white/70 dark:bg-slate-900/70 border border-slate-200 dark:border-slate-800">
            <label className="block text-[11px] font-semibold uppercase tracking-wider text-slate-500 mb-1.5">
              Amount (INR)
            </label>
            <div className="relative">
              <span className="absolute left-3 top-2 text-xs font-bold text-slate-400">₹</span>
              <input
                type="number"
                value={amount}
                onChange={(e) => {
                  setAmount(e.target.value);
                  setResult(null);
                }}
                placeholder="e.g. 5000"
                className="w-full pl-7 pr-3 py-1.5 text-xs font-semibold rounded-xl bg-slate-100 dark:bg-slate-800 text-slate-900 dark:text-white outline-none focus:ring-2 focus:ring-emerald-500"
              />
            </div>
          </div>
        </div>

        {/* Counterparty Input & Presets */}
        <div className="p-4 rounded-2xl bg-white/70 dark:bg-slate-900/70 border border-slate-200 dark:border-slate-800 mb-4">
          <label className="block text-xs font-semibold uppercase tracking-wider text-slate-600 dark:text-slate-300 mb-2">
            Counterparty (Customer UPI VPA or Supplier Account)
          </label>
          <div className="flex flex-col sm:flex-row gap-2 mb-3">
            <div className="relative flex-1">
              <Search className="w-4 h-4 text-slate-400 absolute left-3 top-2.5" />
              <input
                type="text"
                value={counterparty}
                onChange={(e) => {
                  setCounterparty(e.target.value);
                  setResult(null); // Clear previous result when input changes
                }}
                placeholder="Type any UPI handle (e.g. user@oksbi, P***8522, L***7350)..."
                className="w-full pl-9 pr-4 py-2 text-sm font-mono rounded-xl bg-slate-100 dark:bg-slate-800 text-slate-900 dark:text-white outline-none border border-transparent focus:border-emerald-500"
              />
            </div>
            <button
              onClick={handleRunCheck}
              disabled={isScanning || !counterparty.trim() || !amount}
              className="px-6 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white font-semibold text-sm flex items-center justify-center gap-2 shadow-lg shadow-emerald-600/25 disabled:opacity-50 transition cursor-pointer"
            >
              {isScanning ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" /> Querying Exasol...
                </>
              ) : (
                <>
                  <Scan className="w-4 h-4" /> Run Pre-Flight Exasol Verification
                </>
              )}
            </button>
          </div>

          {inputHint && (
            <div className="text-xs text-blue-600 dark:text-blue-400 font-medium mb-3 flex items-center gap-1.5">
              <CheckCircle2 className="w-3.5 h-3.5" /> {inputHint}
            </div>
          )}

          {error && (
            <div className="p-3 rounded-xl bg-rose-500/10 border border-rose-500/25 text-rose-700 dark:text-rose-300 text-xs flex items-center gap-2 mb-3">
              <AlertTriangle className="w-4 h-4 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {/* Quick Scenario Fillers (Only Fills Inputs, DOES NOT SPOIL SCORES) */}
          <div className="text-[11px] font-semibold uppercase tracking-wider text-slate-400 mb-2">
            Load Test Scenarios (Click to Fill Inputs, then Click Verify):
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-2">
            {PRESETS.map((p, idx) => (
              <button
                key={idx}
                type="button"
                onClick={() => handleSelectPreset(p)}
                className="text-left p-2.5 rounded-xl border border-slate-200 dark:border-slate-800 hover:border-slate-400 dark:hover:border-slate-600 bg-white/50 dark:bg-slate-950/50 hover:bg-slate-50 dark:hover:bg-slate-900 transition group cursor-pointer"
              >
                <div className="flex items-center justify-between mb-1">
                  <span className="text-xs font-bold text-slate-800 dark:text-slate-200 truncate">
                    {p.name}
                  </span>
                  <span className="text-[9px] px-1.5 py-0.5 rounded font-semibold bg-slate-200 dark:bg-slate-800 text-slate-600 dark:text-slate-400">
                    {p.badge}
                  </span>
                </div>
                <div className="text-[10px] text-slate-500 dark:text-slate-400 truncate">
                  ₹{p.amount.toLocaleString()} · {p.counterparty}
                </div>
              </button>
            ))}
          </div>
        </div>

        {/* Results Presentation (Only Shows When Verification Has Actually Run) */}
        {result ? (
          <div className="p-5 rounded-2xl bg-white/90 dark:bg-slate-900/90 border border-slate-200 dark:border-slate-800 space-y-4">
            {/* Verdict Top Bar */}
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-4 border-b border-slate-200 dark:border-slate-800">
              <div className="flex items-center gap-3">
                <div
                  className={`p-3 rounded-2xl ${
                    result.verdict.includes("REJECT")
                      ? "bg-rose-500/20 text-rose-600 dark:text-rose-400"
                      : result.verdict.includes("BLOCKED") || result.verdict.includes("SUSPECT")
                      ? "bg-amber-500/20 text-amber-600 dark:text-amber-400"
                      : "bg-emerald-500/20 text-emerald-600 dark:text-emerald-400"
                  }`}
                >
                  {result.verdict.includes("REJECT") ? (
                    <ShieldX className="w-8 h-8" />
                  ) : result.verdict.includes("BLOCKED") || result.verdict.includes("SUSPECT") ? (
                    <AlertTriangle className="w-8 h-8" />
                  ) : (
                    <ShieldCheck className="w-8 h-8" />
                  )}
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-bold uppercase tracking-wider text-slate-500">
                      Exasol Live Decision
                    </span>
                    <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-slate-200 dark:bg-slate-800 text-slate-700 dark:text-slate-300">
                      {result.execution_ms} ms
                    </span>
                  </div>
                  <h3 className="text-lg font-extrabold text-slate-900 dark:text-white tracking-tight">
                    {result.action.replaceAll("_", " ")}
                  </h3>
                  <div className="text-xs font-medium text-slate-500">
                    Target: <span className="font-mono font-bold text-slate-700 dark:text-slate-300">{result.counterparty}</span> · Amount: <span className="font-bold text-slate-700 dark:text-slate-300">₹{result.amount_inr?.toLocaleString()}</span>
                  </div>
                </div>
              </div>

              {/* Hazard Gauge */}
              <div className="flex items-center gap-4 bg-slate-100 dark:bg-slate-800/80 px-4 py-3 rounded-2xl">
                <div className="text-right">
                  <div className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
                    Lien Hazard Score
                  </div>
                  <div className="text-xl font-extrabold font-mono text-slate-900 dark:text-white">
                    {result.lien_hazard_score}
                    <span className="text-xs font-normal text-slate-400">/100</span>
                  </div>
                </div>
                <div
                  className={`w-3.5 h-12 rounded-full ${
                    result.lien_hazard_score >= 80
                      ? "bg-rose-500"
                      : result.lien_hazard_score >= 50
                      ? "bg-amber-500"
                      : "bg-emerald-500"
                  }`}
                />
              </div>
            </div>

            {/* Contagion Graph Path Visualization */}
            <div>
              <div className="text-[11px] font-bold uppercase tracking-wider text-slate-400 mb-2">
                Exasol Topological Proximity Path
              </div>
              <div className="flex flex-wrap items-center gap-2 p-3 rounded-xl bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 text-xs font-mono">
                <span className="px-2.5 py-1 rounded-lg bg-blue-500/10 text-blue-600 dark:text-blue-400 font-semibold">
                  🏪 {result.merchant_id}
                </span>
                <ChevronRight className="w-4 h-4 text-slate-400 shrink-0" />
                {result.contagion_path.map((node, i) => (
                  <div key={i} className="flex items-center gap-2">
                    <span
                      className={`px-2.5 py-1 rounded-lg font-semibold ${
                        node.includes("MULE") || node.includes("RING")
                          ? "bg-rose-500/20 text-rose-600 dark:text-rose-400 border border-rose-500/30"
                          : node.includes("CLEAN")
                          ? "bg-emerald-500/20 text-emerald-600 dark:text-emerald-400 border border-emerald-500/30"
                          : "bg-amber-500/20 text-amber-600 dark:text-amber-400 border border-amber-500/30"
                      }`}
                    >
                      {node}
                    </span>
                    {i < result.contagion_path.length - 1 && (
                      <ChevronRight className="w-4 h-4 text-slate-400 shrink-0" />
                    )}
                  </div>
                ))}
              </div>
            </div>

            {/* Advisory Box */}
            <div
              className={`p-4 rounded-xl text-xs leading-relaxed border ${
                result.lien_hazard_score >= 80
                  ? "bg-rose-500/10 border-rose-500/25 text-rose-900 dark:text-rose-200"
                  : result.lien_hazard_score >= 50
                  ? "bg-amber-500/10 border-amber-500/25 text-amber-900 dark:text-amber-200"
                  : "bg-emerald-500/10 border-emerald-500/25 text-emerald-900 dark:text-emerald-200"
              }`}
            >
              <div className="font-bold mb-1 flex items-center gap-1.5">
                <Sparkles className="w-4 h-4" /> Advisory & Recommended Action:
              </div>
              <p>{result.advisory}</p>
            </div>

            {/* Safe-Pay Certificate & Export */}
            <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 pt-3 border-t border-slate-200 dark:border-slate-800">
              <div className="flex items-center gap-2 text-xs text-slate-500 dark:text-slate-400">
                <FileBadge className="w-4 h-4 text-emerald-500" />
                <span>
                  Certificate ID:{" "}
                  <strong className="font-mono text-slate-800 dark:text-slate-200">
                    {result.shield_certificate?.cert_id}
                  </strong>{" "}
                  · Standard:{" "}
                  <span className="font-mono text-[10px]">RBI-SOP-CYBER-2026</span>
                </span>
              </div>
              <button
                onClick={downloadCert}
                className="px-4 py-2 rounded-xl bg-slate-900 hover:bg-slate-800 text-white dark:bg-white dark:text-slate-900 dark:hover:bg-slate-100 text-xs font-semibold flex items-center gap-2 shadow-sm transition cursor-pointer"
              >
                <Download className="w-3.5 h-3.5" /> Download Safe-Pay Certificate (JSON)
              </button>
            </div>
          </div>
        ) : (
          <div className="p-8 rounded-2xl bg-white/40 dark:bg-slate-900/40 border border-dashed border-slate-300 dark:border-slate-800 text-center text-slate-400 text-xs">
            <Scan className="w-8 h-8 mx-auto mb-2 text-slate-400 opacity-60" />
            <div className="font-semibold text-slate-600 dark:text-slate-300 mb-1">
              No Verification Run Yet
            </div>
            <div>
              Enter any counterparty UPI handle above or pick a scenario, then click{" "}
              <strong>Run Pre-Flight Exasol Verification</strong> to query live graph distance.
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
