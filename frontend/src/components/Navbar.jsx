import { useEffect, useRef, useState, useMemo } from "react";
import {
  Shield,
  ShieldCheck,
  Search,
  ArrowRight,
  X,
  Activity,
  Radar,
  Network,
  Cpu,
  FileCheck,
  Volume2,
  VolumeX,
  Pause,
  Play,
  Command,
  Sparkles,
  Database,
  Menu,
  Radio,
  Layers,
  Zap,
  CheckCircle2,
  AlertTriangle,
  History,
} from "lucide-react";
import JaalNetLogo from "./JaalNetLogo.jsx";

const NAV_TABS = [
  {
    id: "command",
    label: "Command Center",
    icon: Activity,
    badge: null,
    sub: "Live Ingest & 3D Matrix",
  },
  {
    id: "investigate",
    label: "Investigation",
    icon: Radar,
    badge: "alertCount",
    sub: "2-Hop Dossier & AI Agent",
  },
  {
    id: "network",
    label: "Syndicate Explorer",
    icon: Network,
    badge: "60 RINGS",
    badgeColor: "bg-pink-500/20 text-[#FF0055] border-pink-500/30",
    sub: "In-DB Louvain Topologies",
  },
  {
    id: "model",
    label: "Model Intelligence",
    icon: Cpu,
    badge: "< 2ms",
    badgeColor: "bg-emerald-500/20 text-[#10B981] border-emerald-500/30",
    sub: "TGAT+SAGE & PSI Drift",
  },
  {
    id: "audit",
    label: "Audit & Governance",
    icon: History,
    badge: "SHA-256",
    badgeColor: "bg-blue-500/20 text-[#2E69FF] border-blue-500/30",
    sub: "Statutory RBI Ledger",
  },
];

export default function Navbar({
  tab,
  setTab,
  stream = [],
  health = { online: true },
  isStreaming = true,
  toggleStreaming = () => {},
  onOpenMerchantShield = () => {},
  scrollProgress = 0,
  playNavClick = () => {},
  soundOn = true,
  setSoundOn = () => {},
  onSelectTxn = () => {},
}) {
  const [mousePos, setMousePos] = useState({ x: -1000, y: -1000 });
  const [hoverIndex, setHoverIndex] = useState(null);
  const [isHudOpen, setIsHudOpen] = useState(false);
  const [isPaletteOpen, setIsPaletteOpen] = useState(false);
  const [paletteQuery, setPaletteQuery] = useState("");
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  // Tab Indicator geometry
  const navContainerRef = useRef(null);
  const tabsRef = useRef([]);
  const [indicatorStyle, setIndicatorStyle] = useState({ left: 0, width: 0 });
  const [ghostStyle, setGhostStyle] = useState({ left: 0, width: 0 });

  // Calculate alert count for the Investigation tab badge
  const alertCount = useMemo(() => {
    return stream.filter((t) => ["BLOCK", "STEP_UP"].includes(t.action)).length;
  }, [stream]);

  // Update magnetic sliding capsule indicator position
  const activeIndex = useMemo(() => {
    return NAV_TABS.findIndex((t) => t.id === tab);
  }, [tab]);

  useEffect(() => {
    const updateIndicator = () => {
      if (tabsRef.current[activeIndex]) {
        const el = tabsRef.current[activeIndex];
        setIndicatorStyle({
          left: el.offsetLeft,
          width: el.offsetWidth,
        });
      }
    };
    updateIndicator();
    window.addEventListener("resize", updateIndicator);
    return () => window.removeEventListener("resize", updateIndicator);
  }, [activeIndex]);

  // Update ghost hover highlight pill
  useEffect(() => {
    if (hoverIndex !== null && tabsRef.current[hoverIndex]) {
      const el = tabsRef.current[hoverIndex];
      setGhostStyle({
        left: el.offsetLeft,
        width: el.offsetWidth,
      });
    }
  }, [hoverIndex]);

  // Mouse spotlight tracker
  const handleMouseMove = (e) => {
    const rect = e.currentTarget.getBoundingClientRect();
    setMousePos({ x: e.clientX - rect.left, y: e.clientY - rect.top });
  };

  const handleMouseLeave = () => {
    setMousePos({ x: -1000, y: -1000 });
    setHoverIndex(null);
  };

  // Keyboard shortcut for Command Palette (Ctrl+K or Cmd+K)
  useEffect(() => {
    const handleKeyDown = (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setIsPaletteOpen((prev) => !prev);
        if (soundOn) playNavClick(800);
      } else if (e.key === "Escape") {
        setIsPaletteOpen(false);
        setIsHudOpen(false);
        setMobileMenuOpen(false);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [soundOn, playNavClick]);

  // Palette Actions list
  const PALETTE_ACTIONS = useMemo(() => [
    {
      id: "action-shield",
      title: "Launch MerchantShield™ Verification",
      subtitle: "Kirana pre-flight counterparty graph check",
      icon: ShieldCheck,
      color: "text-emerald-400 bg-emerald-500/20",
      action: () => {
        setIsPaletteOpen(false);
        onOpenMerchantShield();
      },
    },
    {
      id: "action-command",
      title: "Switch to Command Center",
      subtitle: "Live matrix stream, 3D interactive globe, state hotspots",
      icon: Activity,
      color: "text-[#2E69FF] bg-[#2E69FF]/20",
      action: () => {
        setIsPaletteOpen(false);
        setTab("command");
      },
    },
    {
      id: "action-mule",
      title: "Investigate Critical Mule Account L***7350",
      subtitle: "Ring hub linked to 22 transactions & ₹1,24,000+ laundering",
      icon: Radar,
      color: "text-[#FF0055] bg-[#FF0055]/20",
      action: () => {
        setIsPaletteOpen(false);
        const muleTxn = stream.find((t) => t.sender === "L***7350" || t.receiver === "L***7350");
        if (muleTxn) onSelectTxn(muleTxn);
        setTab("investigate");
      },
    },
    {
      id: "action-network",
      title: "Inspect Mule Syndicate Explorer",
      subtitle: "Exasol MPP In-DB Louvain community detection across 60 rings",
      icon: Network,
      color: "text-purple-400 bg-purple-500/20",
      action: () => {
        setIsPaletteOpen(false);
        setTab("network");
      },
    },
    {
      id: "action-model",
      title: "Inspect Model Telemetry & Drift",
      subtitle: "TGAT+GraphSAGE inference SLA & PSI population stability",
      icon: Cpu,
      color: "text-amber-400 bg-amber-500/20",
      action: () => {
        setIsPaletteOpen(false);
        setTab("model");
      },
    },
    {
      id: "action-audit",
      title: "View Statutory Audit Ledger",
      subtitle: "Exasol DECISION_LOG table & RBI compliance threshold history",
      icon: History,
      color: "text-cyan-400 bg-cyan-500/20",
      action: () => {
        setIsPaletteOpen(false);
        setTab("audit");
      },
    },
    {
      id: "action-stream",
      title: isStreaming ? "Pause Live Transaction Ingest" : "Resume Live Transaction Ingest",
      subtitle: isStreaming ? "Freeze the live feed to examine transactions" : "Resume real-time GNN scoring feed",
      icon: isStreaming ? Pause : Play,
      color: "text-amber-300 bg-amber-500/20",
      action: () => {
        setIsPaletteOpen(false);
        toggleStreaming();
      },
    },
  ], [isStreaming, onOpenMerchantShield, setTab, stream, onSelectTxn, toggleStreaming]);

  const filteredPaletteActions = useMemo(() => {
    if (!paletteQuery.trim()) return PALETTE_ACTIONS;
    const q = paletteQuery.toLowerCase();
    return PALETTE_ACTIONS.filter(
      (a) => a.title.toLowerCase().includes(q) || a.subtitle.toLowerCase().includes(q)
    );
  }, [paletteQuery, PALETTE_ACTIONS]);

  return (
    <>
      {/* Enhanced Liquid Glass Sticky Header */}
      <header
        className="sift-nav sticky top-0 z-50 transition-all select-none"
        onMouseMove={handleMouseMove}
        onMouseLeave={handleMouseLeave}
      >
        {/* Dynamic Interactive Mouse Spotlight Ambient Glow */}
        <div
          className="pointer-events-none absolute inset-0 -z-10 transition-opacity duration-300 opacity-100"
          style={{
            background: `radial-gradient(550px circle at ${mousePos.x}px ${mousePos.y}px, rgba(46, 105, 255, 0.18), transparent 60%)`,
          }}
        />

        {/* Ambient Top Micro Glow Wire */}
        <div className="absolute top-0 left-0 right-0 h-[1px] bg-gradient-to-r from-transparent via-white/30 to-transparent pointer-events-none" />

        <div className="max-w-[1680px] mx-auto px-4 sm:px-6 py-2.5 flex items-center justify-between gap-3">
          {/* Brand Logo with Interactive Physics */}
          <div
            onClick={() => {
              if (soundOn) playNavClick(640);
              setTab("command");
            }}
            className="flex-shrink-0"
          >
            <JaalNetLogo />
          </div>

          {/* Magnetic Sliding Capsule Navigation Track (Desktop) */}
          <nav
            ref={navContainerRef}
            className="hidden lg:flex items-center relative bg-white/[0.04] p-1.5 rounded-full border border-white/10 backdrop-blur-xl shadow-[inset_0_1px_2px_rgba(255,255,255,0.08),0_8px_24px_rgba(0,0,0,0.4)]"
          >
            {/* 1. Ghost Hover Highlight Pill (Follows cursor smoothly) */}
            <div
              className="absolute top-1.5 bottom-1.5 rounded-full pointer-events-none transition-all duration-200 ease-out"
              style={{
                left: `${ghostStyle.left}px`,
                width: `${ghostStyle.width}px`,
                background: "rgba(255, 255, 255, 0.08)",
                opacity: hoverIndex !== null && hoverIndex !== activeIndex ? 1 : 0,
              }}
            />

            {/* 2. Magnetic Active Pill (Slides with spring fluid ease) */}
            <div
              className="absolute top-1.5 bottom-1.5 rounded-full pointer-events-none transition-all duration-300 ease-[cubic-bezier(0.16,1,0.3,1)]"
              style={{
                left: `${indicatorStyle.left}px`,
                width: `${indicatorStyle.width}px`,
                background: "linear-gradient(135deg, #2E69FF 0%, #1D4ED8 100%)",
                boxShadow:
                  "0 4px 18px rgba(46, 105, 255, 0.55), inset 0 1px 1px rgba(255, 255, 255, 0.45), inset 0 -1px 2px rgba(0, 0, 0, 0.3)",
                opacity: indicatorStyle.width > 0 ? 1 : 0,
              }}
            >
              {/* Neon Mint Center Laser Bar */}
              <div className="absolute -bottom-[1px] left-1/4 right-1/4 h-[2px] bg-[#79F7C6] rounded-full shadow-[0_0_8px_#79F7C6]" />
            </div>

            {/* Tab Buttons */}
            {NAV_TABS.map((t, idx) => {
              const Icon = t.icon;
              const isActive = tab === t.id;

              return (
                <button
                  key={t.id}
                  ref={(el) => (tabsRef.current[idx] = el)}
                  onClick={() => {
                    if (soundOn) playNavClick(580 + idx * 70);
                    setTab(t.id);
                  }}
                  onMouseEnter={() => setHoverIndex(idx)}
                  className={`relative z-10 flex items-center gap-2 px-4 py-2 rounded-full text-[13px] font-semibold transition-all duration-200 cursor-pointer ${
                    isActive
                      ? "text-white font-bold drop-shadow-sm"
                      : "text-slate-300 hover:text-white"
                  }`}
                >
                  <Icon
                    size={15}
                    className={`transition-transform duration-200 ${
                      isActive ? "scale-110 text-white" : "text-slate-400 group-hover:text-slate-200"
                    }`}
                  />
                  <span>{t.label}</span>

                  {/* Dynamic Alert Count Badge on Investigation */}
                  {t.badge === "alertCount" && alertCount > 0 && (
                    <span className="flex items-center justify-center min-w-[18px] h-[18px] px-1 text-[10px] font-mono2 font-extrabold rounded-full bg-[#FF0055] text-white shadow-[0_0_8px_rgba(255,0,85,0.7)] animate-pulse">
                      {alertCount}
                    </span>
                  )}

                  {/* Static Chip Badges */}
                  {t.badge && t.badge !== "alertCount" && (
                    <span
                      className={`text-[9.5px] font-mono2 font-bold px-1.5 py-0.5 rounded-full border transition-all ${
                        isActive
                          ? "bg-white/20 text-white border-white/30"
                          : t.badgeColor || "bg-white/10 text-slate-300 border-white/15"
                      }`}
                    >
                      {t.badge}
                    </span>
                  )}
                </button>
              );
            })}
          </nav>

          {/* Right Action Controls: Search, HUD, Stream, Sound & MerchantShield */}
          <div className="flex items-center gap-2 sm:gap-2.5">
            {/* Quick Command Palette Button (`Ctrl+K`) */}
            <button
              onClick={() => {
                if (soundOn) playNavClick(800);
                setIsPaletteOpen(true);
              }}
              className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-white/[0.05] hover:bg-white/[0.1] text-slate-300 hover:text-white border border-white/10 transition-all text-xs cursor-pointer shadow-sm group"
              title="Quick Search & Navigation (Ctrl+K)"
            >
              <Search size={13} className="text-slate-400 group-hover:text-[#2E69FF] transition-colors" />
              <span className="hidden xl:inline text-xs text-slate-400 group-hover:text-slate-200">
                Jump to…
              </span>
              <kbd className="hidden sm:inline-flex items-center gap-0.5 px-1.5 py-0.5 text-[9px] font-mono2 font-bold bg-white/10 rounded border border-white/15 text-slate-400">
                <Command size={10} />K
              </kbd>
            </button>

            {/* Exasol In-Memory Cluster HUD Pill (With Interactive Telemetry Popover) */}
            <div className="relative">
              <button
                onClick={() => {
                  if (soundOn) playNavClick(700);
                  setIsHudOpen((v) => !v);
                }}
                className={`flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-mono2 border transition-all cursor-pointer shadow-sm ${
                  health.online
                    ? "bg-emerald-500/[0.08] hover:bg-emerald-500/[0.14] border-emerald-500/30 text-emerald-300"
                    : "bg-amber-500/[0.08] hover:bg-amber-500/[0.14] border-amber-500/30 text-amber-300"
                }`}
                title="Click to view Exasol RAM Engine telemetry"
              >
                <span className="relative flex h-2 w-2">
                  <span
                    className={`animate-ping absolute inline-flex h-full w-full rounded-full opacity-75 ${
                      health.online ? "bg-emerald-400" : "bg-amber-400"
                    }`}
                  />
                  <span
                    className={`relative inline-flex rounded-full h-2 w-2 ${
                      health.online ? "bg-emerald-500" : "bg-amber-500"
                    }`}
                  />
                </span>
                <span className="hidden md:inline font-bold">
                  {health.online ? "EXASOL RAM: 102K" : "SYNTH ENGINE"}
                </span>
              </button>

              {/* Exasol Cluster Telemetry Popover HUD */}
              {isHudOpen && (
                <div className="absolute right-0 top-full mt-2 w-72 rounded-2xl bg-[#020617]/95 border border-white/15 p-4 shadow-[0_20px_50px_rgba(0,0,0,0.8)] backdrop-blur-2xl z-50 animate-in fade-in zoom-in-95 duration-150">
                  <div className="flex items-center justify-between pb-3 border-b border-white/10 mb-3">
                    <div className="flex items-center gap-2 text-white font-bold text-xs">
                      <Database size={15} className="text-[#2E69FF]" />
                      <span>Exasol In-Memory Grid</span>
                    </div>
                    <span className="text-[10px] font-mono2 font-bold px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
                      LIVE MPP
                    </span>
                  </div>

                  <div className="space-y-2.5 text-[11px] font-mono2">
                    <div className="flex items-center justify-between text-slate-300">
                      <span className="text-slate-400">Memory Residency:</span>
                      <span className="text-white font-bold">102,514 Txns (100%)</span>
                    </div>
                    <div className="flex items-center justify-between text-slate-300">
                      <span className="text-slate-400">Ring Registry:</span>
                      <span className="text-[#FF0055] font-bold">60 Syndicates Loaded</span>
                    </div>
                    <div className="flex items-center justify-between text-slate-300">
                      <span className="text-slate-400">In-DB Engine:</span>
                      <span className="text-[#79F7C6] font-bold">Python 3 SET UDF</span>
                    </div>
                    <div className="flex items-center justify-between text-slate-300">
                      <span className="text-slate-400">Inference Latency:</span>
                      <span className="text-[#10B981] font-bold">
                        {health.p99_ms ? `${Math.round(health.p99_ms)}ms P99` : "< 2ms local"}
                      </span>
                    </div>
                  </div>

                  <div className="mt-3 pt-3 border-t border-white/10 flex items-center justify-between text-[10px] text-slate-400">
                    <span>Host: localhost:8563</span>
                    <button
                      onClick={() => {
                        setTab("network");
                        setIsHudOpen(false);
                      }}
                      className="text-[#2E69FF] hover:underline font-bold"
                    >
                      Open Explorer →
                    </button>
                  </div>
                </div>
              )}
            </div>

            {/* Live Streaming Engine Toggle Button */}
            <button
              onClick={() => {
                if (soundOn) playNavClick(isStreaming ? 500 : 750);
                toggleStreaming();
              }}
              className={`hidden sm:flex items-center gap-1.5 px-2.5 py-1.5 rounded-full text-xs font-mono2 border transition-all cursor-pointer ${
                isStreaming
                  ? "bg-blue-500/10 hover:bg-blue-500/20 text-blue-300 border-blue-500/30"
                  : "bg-amber-500/15 hover:bg-amber-500/25 text-amber-300 border-amber-500/40"
              }`}
              title={isStreaming ? "Pause incoming live transactions" : "Resume incoming live transactions"}
            >
              {isStreaming ? (
                <>
                  <Pause size={12} className="text-blue-400" />
                  <span className="text-[11px] font-bold">LIVE STREAM</span>
                </>
              ) : (
                <>
                  <Play size={12} className="text-amber-400" />
                  <span className="text-[11px] font-bold">PAUSED</span>
                </>
              )}
            </button>

            {/* Tactile Audio Equalizer Toggle */}
            <button
              onClick={() => {
                const next = !soundOn;
                setSoundOn(next);
                if (next) playNavClick(880);
              }}
              className={`p-2 rounded-full border transition-all cursor-pointer ${
                soundOn
                  ? "bg-white/[0.08] hover:bg-white/[0.14] text-[#79F7C6] border-white/20"
                  : "bg-white/[0.04] text-slate-500 border-white/10"
              }`}
              title={soundOn ? "Mute audio feedback" : "Enable tactile sound chimes"}
            >
              {soundOn ? (
                <div className="flex items-end gap-0.5 h-3.5 w-3.5 justify-center">
                  <div className="w-[2px] h-full bg-[#79F7C6] rounded-full animate-[pulse_1s_ease-in-out_infinite]" />
                  <div className="w-[2px] h-2/3 bg-[#79F7C6] rounded-full animate-[pulse_1.2s_ease-in-out_infinite_0.2s]" />
                  <div className="w-[2px] h-4/5 bg-[#79F7C6] rounded-full animate-[pulse_0.8s_ease-in-out_infinite_0.4s]" />
                </div>
              ) : (
                <VolumeX size={14} />
              )}
            </button>

            {/* MerchantShield™ Pre-Flight Action Button */}
            <button
              onClick={() => {
                if (soundOn) playNavClick(940);
                onOpenMerchantShield();
              }}
              className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-full text-xs font-bold bg-gradient-to-r from-emerald-500/20 to-teal-500/20 text-emerald-300 border border-emerald-500/40 hover:border-emerald-400 hover:from-emerald-500/30 hover:to-teal-500/30 active:scale-95 transition-all shadow-[0_0_15px_rgba(16,185,129,0.2)] cursor-pointer group"
              title="Pre-flight counterparty protection for kiranas and merchants"
            >
              <ShieldCheck
                size={14}
                className="text-emerald-400 group-hover:rotate-12 transition-transform duration-200"
              />
              <span className="tracking-wide">MERCHANT SHIELD</span>
            </button>

            {/* Mobile Hamburger Menu Toggle */}
            <button
              onClick={() => {
                if (soundOn) playNavClick(660);
                setMobileMenuOpen((v) => !v);
              }}
              className="lg:hidden p-2 rounded-xl bg-white/[0.06] text-white border border-white/15 cursor-pointer"
              aria-label="Toggle navigation menu"
            >
              {mobileMenuOpen ? <X size={18} /> : <Menu size={18} />}
            </button>
          </div>
        </div>

        {/* Mobile / Tablet Dropdown Drawer with Smooth Glass Blur */}
        {mobileMenuOpen && (
          <div className="lg:hidden px-4 pt-2 pb-6 border-t border-white/10 bg-[#000926]/95 backdrop-blur-2xl animate-in slide-in-from-top-2 duration-200">
            <div className="grid grid-cols-1 gap-1.5 pt-2">
              {NAV_TABS.map((t, idx) => {
                const Icon = t.icon;
                const isActive = tab === t.id;

                return (
                  <button
                    key={t.id}
                    onClick={() => {
                      if (soundOn) playNavClick(580 + idx * 70);
                      setTab(t.id);
                      setMobileMenuOpen(false);
                    }}
                    className={`flex items-center justify-between p-3 rounded-2xl border text-left transition-all ${
                      isActive
                        ? "bg-[#2E69FF] text-white border-[#2E69FF] shadow-lg font-bold"
                        : "bg-white/[0.03] text-slate-300 border-white/5 hover:bg-white/[0.08]"
                    }`}
                  >
                    <div className="flex items-center gap-3">
                      <Icon size={18} className={isActive ? "text-white" : "text-slate-400"} />
                      <div>
                        <div className="text-sm font-semibold">{t.label}</div>
                        <div className="text-[11px] text-slate-400 font-normal">{t.sub}</div>
                      </div>
                    </div>
                    {t.badge === "alertCount" && alertCount > 0 ? (
                      <span className="px-2 py-0.5 text-xs font-mono2 font-bold rounded-full bg-[#FF0055] text-white">
                        {alertCount} alerts
                      </span>
                    ) : (
                      t.badge && (
                        <span className="px-2 py-0.5 text-[10px] font-mono2 font-bold rounded-full bg-white/10 text-slate-300 border border-white/15">
                          {t.badge}
                        </span>
                      )
                    )}
                  </button>
                );
              })}
            </div>
          </div>
        )}

        {/* Dynamic Quantum Laser Scroll Progress Indicator */}
        <div className="w-full h-[2.5px] bg-white/[0.04] relative overflow-hidden">
          <div
            className="h-full bg-gradient-to-r from-[#2E69FF] via-[#79F7C6] to-[#FF0055] transition-all duration-150 ease-out relative"
            style={{ width: `${scrollProgress}%` }}
          >
            {/* Pulsing Energy Comet Head */}
            <div className="absolute right-0 top-1/2 -translate-y-1/2 w-3.5 h-3.5 rounded-full bg-white shadow-[0_0_12px_#79F7C6,0_0_24px_#FF0055] animate-pulse" />
          </div>
        </div>
      </header>

      {/* Quick Jump Command Palette Modal (`Ctrl+K`) */}
      {isPaletteOpen && (
        <div
          className="fixed inset-0 z-50 flex items-start justify-center pt-24 px-4 bg-black/60 backdrop-blur-md animate-in fade-in duration-150"
          onClick={() => setIsPaletteOpen(false)}
        >
          <div
            className="w-full max-w-xl rounded-3xl bg-[#000E33] border border-white/20 p-4 shadow-[0_25px_60px_rgba(0,0,0,0.85)] text-white overflow-hidden animate-in zoom-in-95 duration-200"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Search Input Box */}
            <div className="flex items-center gap-3 px-3 py-3 rounded-2xl bg-white/[0.06] border border-white/15">
              <Search size={18} className="text-[#2E69FF]" />
              <input
                type="text"
                autoFocus
                placeholder="Type a command, page, or account (e.g., L***7350, RING-001)..."
                value={paletteQuery}
                onChange={(e) => setPaletteQuery(e.target.value)}
                className="w-full bg-transparent border-none outline-none text-sm text-white placeholder-slate-400 font-sans"
              />
              <kbd className="px-2 py-0.5 text-[10px] font-mono2 font-bold bg-white/10 rounded-md border border-white/15 text-slate-400">
                ESC
              </kbd>
            </div>

            {/* Filtered Action Shortcuts List */}
            <div className="mt-3 max-h-80 overflow-y-auto space-y-1 pr-1 font-sans">
              <div className="text-[10px] font-mono2 uppercase tracking-widest text-slate-400 px-3 py-1 font-bold">
                Quick Actions & Direct Jumps
              </div>

              {filteredPaletteActions.length === 0 ? (
                <div className="text-center py-8 text-slate-400 text-xs">
                  No matching commands or entities found for "{paletteQuery}".
                </div>
              ) : (
                filteredPaletteActions.map((item) => {
                  const ItemIcon = item.icon;
                  return (
                    <button
                      key={item.id}
                      onClick={() => {
                        if (soundOn) playNavClick(780);
                        item.action();
                      }}
                      className="w-full flex items-center justify-between p-2.5 px-3 rounded-xl hover:bg-white/[0.08] transition-all text-left cursor-pointer group"
                    >
                      <div className="flex items-center gap-3">
                        <div className={`w-8 h-8 rounded-lg grid place-items-center ${item.color}`}>
                          <ItemIcon size={16} />
                        </div>
                        <div>
                          <div className="text-xs font-bold text-white group-hover:text-[#79F7C6] transition-colors">
                            {item.title}
                          </div>
                          <div className="text-[11px] text-slate-400">{item.subtitle}</div>
                        </div>
                      </div>
                      <ArrowRight size={14} className="text-slate-500 group-hover:text-white group-hover:translate-x-1 transition-all" />
                    </button>
                  );
                })
              )}
            </div>

            {/* Footer Navigation Tip */}
            <div className="mt-3 pt-3 border-t border-white/10 flex items-center justify-between text-[11px] font-mono2 text-slate-400 px-2">
              <span>Tip: Press ESC to dismiss</span>
              <span className="text-[#79F7C6]">JaalNet Real-Time Defense</span>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
