import { useEffect, useRef, useState } from "react";
import { Shield, ShieldCheck, Search, ArrowRight, X } from "lucide-react";
import CommandCenter from "./pages/CommandCenter.jsx";
import Investigation from "./pages/Investigation.jsx";
import NetworkExplorer from "./pages/NetworkExplorer.jsx";
import ModelDrift from "./pages/ModelDrift.jsx";
import Audit from "./pages/Audit.jsx";
import ScrollRadarHUD from "./components/ScrollRadarHUD.jsx";
import JaalNetLogo from "./components/JaalNetLogo.jsx";
import Navbar from "./components/Navbar.jsx";
import ErrorBoundary from "./components/ErrorBoundary.jsx";
import MerchantShieldModal from "./components/MerchantShieldModal.jsx";
import { useStream } from "./hooks/useStream.js";
import { scoreTxn } from "./lib/api.js";

const TABS = [
  { id: "command", label: "Command Center" },
  { id: "investigate", label: "Investigation" },
  { id: "network", label: "Syndicate Explorer" },
  { id: "model", label: "Model Intelligence" },
  { id: "audit", label: "Audit & Governance" },
];

export default function App() {
  const { stream, health, analystAct, injectTxn, isStreaming, toggleStreaming } = useStream();
  const [tab, setTab] = useState("command");
  const [selected, setSelected] = useState(null);
  const [showBanner, setShowBanner] = useState(true);
  const [scrollProgress, setScrollProgress] = useState(0);
  const [isMerchantShieldOpen, setIsMerchantShieldOpen] = useState(false);
  const [soundOn, setSoundOn] = useState(true);
  const lastLatency = useRef(null);
  const [latency, setLatency] = useState(null);

  // measure end-to-end latency when backend is online
  useEffect(() => {
    if (health.online && latency === null && stream[0]) {
      scoreTxn(stream[0]).then((res) => {
        if (res?.latencyMs) {
          lastLatency.current = res.latencyMs;
          setLatency(res.latencyMs);
        }
      });
    }
  }, [health.online, latency, stream]);

  // Track scroll progress for the top laser progress bar
  useEffect(() => {
    const handleScroll = () => {
      const totalScroll = document.documentElement.scrollHeight - window.innerHeight;
      if (totalScroll > 0) {
        const currentProgress = (window.scrollY / totalScroll) * 100;
        setScrollProgress(Math.min(100, Math.max(0, currentProgress)));
      }
    };
    window.addEventListener("scroll", handleScroll, { passive: true });
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  const openTxn = (t) => {
    setSelected(t);
    setTab("investigate");
  };

  const investigationTxn =
    (selected && (stream.find((t) => t.txnId === selected.txnId) || selected)) ||
    (stream && stream.length > 0 ? [...stream].sort((a, b) => b.score - a.score)[0] : null);

  // Tactile micro-chirp synthesizer on navigation tab clicks
  const playNavClick = (freq = 720) => {
    if (!soundOn) return;
    try {
      const ctx = new (window.AudioContext || window.webkitAudioContext)();
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = "sine";
      osc.frequency.setValueAtTime(freq, ctx.currentTime);
      osc.frequency.exponentialRampToValueAtTime(freq + 180, ctx.currentTime + 0.07);
      gain.gain.setValueAtTime(0.035, ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + 0.08);
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.start();
      osc.stop(ctx.currentTime + 0.085);
    } catch {
      // Audio context silently bypassed if restricted
    }
  };

  return (
    <div className="relative min-h-screen bg-[#EEF2F9] text-[#0A122C] flex flex-col font-sans selection:bg-[#2E69FF] selection:text-white overflow-x-hidden">
      {/* Background Liquid Ambient Auroras (Gives depth and liquid refraction behind glass) */}
      <div className="pointer-events-none fixed inset-0 overflow-hidden -z-10 opacity-70">
        <div
          className="absolute top-10 left-[15%] w-[600px] h-[600px] rounded-full bg-[#2E69FF]/8 blur-[120px] transition-transform duration-300 ease-out"
          style={{ transform: `translate3d(0, ${(scrollProgress * -0.6).toFixed(1)}px, 0)` }}
        />
        <div
          className="absolute top-[40%] right-[10%] w-[650px] h-[650px] rounded-full bg-[#79F7C6]/12 blur-[130px] transition-transform duration-300 ease-out"
          style={{ transform: `translate3d(0, ${(scrollProgress * 0.4).toFixed(1)}px, 0)` }}
        />
        <div
          className="absolute top-[75%] left-[20%] w-[700px] h-[700px] rounded-full bg-[#FF0055]/6 blur-[140px] transition-transform duration-300 ease-out"
          style={{ transform: `translate3d(0, ${(scrollProgress * -0.3).toFixed(1)}px, 0)` }}
        />
      </div>

      {/* Top Announcement Banner */}
      {showBanner && (
        <div className="sift-top-banner flex items-center justify-center gap-3">
          <span className="font-extrabold tracking-wide">
            NEW: AI AGENTS BUILT FOR FRAUD TEAMS // TGAT+SAGE v1.2 LIVE ON EXASOL
          </span>
          <button
            onClick={() => setShowBanner(false)}
            className="hover:opacity-75 p-0.5 ml-2 cursor-pointer"
            title="Dismiss announcement"
          >
            <X size={14} className="stroke-[3]" />
          </button>
        </div>
      )}

      {/* High-Performance Animated Liquid Glass Navigation Bar */}
      <Navbar
        tab={tab}
        setTab={setTab}
        stream={stream}
        health={health}
        isStreaming={isStreaming}
        toggleStreaming={toggleStreaming}
        onOpenMerchantShield={() => setIsMerchantShieldOpen(true)}
        scrollProgress={scrollProgress}
        playNavClick={playNavClick}
        soundOn={soundOn}
        setSoundOn={setSoundOn}
        onSelectTxn={openTxn}
      />

      {/* Main Content Area in Light Periwinkle Theme */}
      <main className="flex-1 w-full max-w-[1600px] mx-auto px-4 sm:px-6 py-8">
        <ErrorBoundary resetKey={tab} onReset={() => setTab("command")}>
          {tab === "command" && (
            <CommandCenter
              stream={stream}
              health={health}
              onOpenTxn={openTxn}
              onInjectTxn={injectTxn}
              isStreaming={isStreaming}
              onToggleStream={toggleStreaming}
            />
          )}
          {tab === "investigate" && (
            <Investigation
              txn={investigationTxn}
              analystAct={analystAct}
              onViewRing={(ring) => {
                setSelected((prev) => (prev ? { ...prev, ringId: ring } : { ringId: ring }));
                setTab("network");
              }}
            />
          )}
          {tab === "network" && (
            <NetworkExplorer
              activeRingId={investigationTxn?.ringId}
              selectedTxn={investigationTxn}
            />
          )}
          {tab === "model" && <ModelDrift health={health} latencyMs={latency} />}
          {tab === "audit" && <Audit stream={stream} />}
        </ErrorBoundary>
      </main>

      {/* Global Console Footer */}
      <footer className="border-t border-slate-200 bg-white py-10 text-xs text-slate-500 mt-16">
        <div className="max-w-[1600px] mx-auto px-6 flex flex-col md:flex-row items-center justify-between gap-6">
          <div className="flex items-center gap-3">
            <div className="w-6 h-6 rounded-lg bg-[#0A122C] text-[#79F7C6] font-black grid place-items-center text-xs">
              J
            </div>
            <span className="font-heading font-black text-[#0A122C] text-base">jaalnet</span>
            <span>· Enterprise UPI Mule Detection & Topological Graph Defense Engine</span>
          </div>
          <div className="flex items-center gap-6 font-mono2 text-[11px] text-slate-600">
            <span>Model: TGAT+GraphSAGE v1.2</span>
            <span>Vector Grid: Exasol Personal 64-dim</span>
            <span>Latency SLA: &lt; 2ms CPU</span>
            <span className="text-[#10B981] font-bold">● RBI KYC/AML Compliant</span>
          </div>
        </div>
      </footer>

      {/* Floating 3D Telemetry Radar Navigator for Command Center */}
      {tab === "command" && <ScrollRadarHUD />}

      {/* Pre-Flight Counterparty Defense Modal */}
      <MerchantShieldModal
        isOpen={isMerchantShieldOpen}
        onClose={() => setIsMerchantShieldOpen(false)}
      />
    </div>
  );
}
