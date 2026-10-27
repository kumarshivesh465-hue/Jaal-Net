import { useState, useEffect, useRef } from "react";
import {
  Zap,
  Database,
  Cpu,
  Network,
  ShieldCheck,
  CheckCircle2,
  RotateCcw,
  Sparkles,
} from "lucide-react";

const STAGES = [
  {
    id: "ingest",
    step: "01",
    label: "UPI INGESTION",
    sub: "NPCI Buffer · 1,200/s",
    desc: "Real-time webhook and queue ingestion parsing VPA, masked device fingerprint, and IP geolocation.",
    metric: "Sub-2ms buffer queue",
    color: "#79F7C6",
    nextGrad: "linear-gradient(90deg, #79F7C6, #2E69FF)",
    Icon: Zap,
  },
  {
    id: "memory",
    step: "02",
    label: "EXASOL MEMORY",
    sub: "64-dim Node Store",
    desc: "In-memory database lookup of structural graph embeddings across 100,000 accounts.",
    metric: "100k verified accounts",
    color: "#2E69FF",
    nextGrad: "linear-gradient(90deg, #2E69FF, #FFCA36)",
    Icon: Database,
  },
  {
    id: "gnn",
    step: "03",
    label: "GNN INFERENCE",
    sub: "TGAT+GraphSAGE 2-Hop",
    desc: "Temporal Graph Attention edge evaluation aggregating 2-hop topological mule patterns.",
    metric: "P99: 1.2 ms · AUC-PR: 0.870",
    color: "#FFCA36",
    nextGrad: "linear-gradient(90deg, #FFCA36, #FF3B84)",
    Icon: Cpu,
  },
  {
    id: "radar",
    step: "04",
    label: "SYNDICATE RADAR",
    sub: "Circular Mule Smurf",
    desc: "Graph cycle detection identifying multi-hop funnels, layering chains, and planted rings.",
    metric: "3 detected mule syndicates",
    color: "#FF3B84",
    nextGrad: "linear-gradient(90deg, #FF3B84, #00F5A0)",
    Icon: Network,
  },
  {
    id: "shield",
    step: "05",
    label: "AUTONOMOUS SHIELD",
    sub: "Instant AI Interception",
    desc: "Policy engine immediately returns BLOCK, STEP_UP challenge, or ALLOW to the UPI switch.",
    metric: "Policy v3 (RBI Guidelines)",
    color: "#00F5A0",
    Icon: ShieldCheck,
  },
];

export default function ConnectedPipeline() {
  const [selected, setSelected] = useState(STAGES[2]); // Default GNN
  const [animStage, setAnimStage] = useState(0); // 0 to 5 nodes revealed
  const [lineStage, setLineStage] = useState(0); // 0 to 4 lines drawn
  const [isChainActive, setIsChainActive] = useState(false);
  const containerRef = useRef(null);
  const hasTriggered = useRef(false);

  // Subtle Web Audio tone synthesis for high-tech tactile feedback
  const playPulseTone = (freq = 440) => {
    try {
      const ctx = new (window.AudioContext || window.webkitAudioContext)();
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = "sine";
      osc.frequency.setValueAtTime(freq, ctx.currentTime);
      gain.gain.setValueAtTime(0.04, ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + 0.14);
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.start();
      osc.stop(ctx.currentTime + 0.15);
    } catch {
      // Audio context silently bypassed if blocked by autoplay policy
    }
  };

  const startChainSequence = () => {
    setIsChainActive(true);
    setAnimStage(0);
    setLineStage(0);

    // Step 1: Ingest
    setTimeout(() => {
      setAnimStage(1);
      playPulseTone(520);
    }, 150);
    setTimeout(() => setLineStage(1), 600);

    // Step 2: Memory
    setTimeout(() => {
      setAnimStage(2);
      playPulseTone(640);
    }, 1100);
    setTimeout(() => setLineStage(2), 1550);

    // Step 3: GNN
    setTimeout(() => {
      setAnimStage(3);
      playPulseTone(780);
    }, 2050);
    setTimeout(() => setLineStage(3), 2500);

    // Step 4: Radar
    setTimeout(() => {
      setAnimStage(4);
      playPulseTone(920);
    }, 3000);
    setTimeout(() => setLineStage(4), 3450);

    // Step 5: Shield
    setTimeout(() => {
      setAnimStage(5);
      playPulseTone(1100);
    }, 3950);
  };

  // Trigger on scroll into view via IntersectionObserver (replays every time you scroll to it)
  useEffect(() => {
    let timerIds = [];

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          if (!hasTriggered.current) {
            hasTriggered.current = true;
            startChainSequence();
          }
        } else {
          // Reset when scrolled out of view so it re-forms the chain next time you scroll here!
          hasTriggered.current = false;
        }
      },
      { threshold: 0.25 }
    );

    if (containerRef.current) {
      observer.observe(containerRef.current);
    }

    return () => observer.disconnect();
  }, []);

  return (
    <div
      ref={containerRef}
      className="relative rounded-3xl bg-[#000B29] p-8 sm:p-10 border border-white/15 overflow-hidden shadow-2xl space-y-8"
    >
      {/* Liquid Glass Highlight Sheen */}
      <div className="absolute top-0 left-0 right-0 h-32 bg-gradient-to-b from-white/10 to-transparent pointer-events-none" />
      <div className="absolute -bottom-20 -left-20 w-80 h-80 rounded-full bg-[#2E69FF]/20 blur-3xl pointer-events-none" />
      <div className="absolute -top-20 -right-20 w-80 h-80 rounded-full bg-[#79F7C6]/15 blur-3xl pointer-events-none" />

      {/* Sift Header with Replay Action */}
      <div className="relative z-10 flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="text-[10px] font-bold text-[#79F7C6] uppercase tracking-widest flex items-center gap-1.5 mb-1">
            <Sparkles size={13} />
            Sequential Graph Lifecycle
          </div>
          <h2 className="font-heading font-black text-2xl sm:text-3xl text-white">
            Deliver Trust Across the{" "}
            <span className="font-marker text-[#79F7C6]">UPI DEFENSE</span>{" "}
            Journey
          </h2>
          <p className="text-xs text-slate-300 mt-1">
            Watch the real-time topological pipeline spring into action from UPI ingestion to autonomous shield.
          </p>
        </div>

        <button
          onClick={startChainSequence}
          className="btn-sift-outline self-start md:self-auto text-xs !py-2 !px-4 flex items-center gap-2 cursor-pointer"
        >
          <RotateCcw size={13} className={isChainActive && animStage < 5 ? "animate-spin" : ""} />
          <span>REPLAY CHAIN SEQUENCE</span>
        </button>
      </div>

      {/* Main Chain Row with Sift's Left Graphic + Right 5 Nodes */}
      <div className="relative z-10 grid grid-cols-1 lg:grid-cols-12 gap-8 items-center py-4">
        {/* Left: Sift Liquid Organic Blob Framing */}
        <div className="lg:col-span-3 flex justify-center lg:justify-start">
          <div className="relative w-48 h-44 flex items-center justify-center">
            {/* Organic liquid color blobs */}
            <div className="absolute w-36 h-36 rounded-[40%_60%_70%_30%/40%_50%_60%_50%] bg-[#FF0055] opacity-80 blur-md transform -rotate-12 animate-pulse" />
            <div className="absolute w-32 h-32 rounded-[60%_40%_30%_70%/50%_30%_70%_40%] bg-[#2E69FF] opacity-90 blur-md transform translate-x-4 translate-y-3" />
            <div className="absolute w-14 h-14 rounded-full bg-[#FFCA36] top-1 left-1 blur-sm opacity-90" />
            <div className="absolute w-8 h-8 rounded-full border-2 border-[#79F7C6] bottom-2 right-4" />

            {/* Inner Shield Illustration with Liquid Glass Frosting */}
            <div className="relative z-10 w-26 h-26 rounded-2xl bg-[#000B29]/80 border border-white/30 backdrop-blur-xl grid place-items-center shadow-2xl p-4">
              <ShieldCheck size={48} className="text-[#79F7C6] drop-shadow-[0_0_12px_#79F7C6]" />
              <div className="text-[9px] font-mono2 font-bold text-white uppercase tracking-widest mt-1 text-center">
                AUTONOMOUS
              </div>
            </div>
          </div>
        </div>

        {/* Right: The 5 Connected Nodes Forming the Chain One by One */}
        <div className="lg:col-span-9 overflow-x-auto pb-4 pt-2 relative">
          <div className="min-w-[700px] flowSteps-wrapper relative">
            {/* Real-time neon energy packet shoots across the circuit once chain is formed */}
            {animStage >= 5 && <div className="chain-energy-packet" />}

            {STAGES.map((s, idx) => {
              const nodeNum = idx + 1;
              const isVisible = animStage >= nodeNum;
              const isLineVisible = lineStage >= nodeNum;
              const isLast = idx === STAGES.length - 1;
              const isSelected = selected.id === s.id;
              const { Icon } = s;

              return (
                <div key={s.id} className="contents">
                  {/* Node */}
                  <div
                    className="flowSteps-item group"
                    onClick={() => {
                      setSelected(s);
                      playPulseTone(400 + idx * 160);
                    }}
                    style={{ "--c": s.color }}
                  >
                    <div
                      className={`flowSteps-node transition-all relative ${
                        isVisible ? "chain-node-enter opacity-100 scale-100" : "opacity-0 scale-50"
                      }`}
                      style={{
                        background: isSelected ? "#0A173D" : "#000B29",
                        borderColor: s.color,
                        boxShadow: isSelected
                          ? `0 0 28px ${s.color}, 0 0 0 2px white`
                          : `0 0 16px -2px ${s.color}`,
                        borderWidth: isSelected ? "3px" : "2px",
                      }}
                    >
                      {/* Ultrasonic radar wave ripple when selected */}
                      {isSelected && (
                        <div
                          className="radar-ring"
                          style={{ borderColor: s.color }}
                        />
                      )}

                      <Icon
                        size={24}
                        className="flowSteps-node-icon"
                        style={{ color: s.color }}
                      />
                    </div>

                    <div
                      className={`text-center mt-3 transition-opacity duration-500 ${
                        isVisible ? "opacity-100" : "opacity-0"
                      }`}
                    >
                      <div
                        className="font-heading font-black text-xs tracking-wider uppercase transition-colors"
                        style={{ color: isSelected ? s.color : "#FFFFFF" }}
                      >
                        {s.label}
                      </div>
                      <div className="text-[10px] font-mono2 text-slate-400 mt-0.5">
                        {s.sub}
                      </div>
                    </div>
                  </div>

                  {/* Connecting Line that Draws from Left to Right */}
                  {!isLast && (
                    <div
                      className={`flowSteps-conn transition-all ${
                        isLineVisible ? "chain-line-enter opacity-100" : "opacity-0 scale-x-0"
                      }`}
                      style={{
                        "--g": s.nextGrad,
                      }}
                    />
                  )}
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* Selected Stage Detail Box with Liquid Glass Polish */}
      <div
        className="relative z-10 p-5 rounded-2xl bg-[#00124D]/80 backdrop-blur-xl border border-white/15 flex flex-col md:flex-row items-start md:items-center justify-between gap-4 transition-all shadow-lg"
        style={{ borderLeft: `5px solid ${selected.color}` }}
      >
        <div className="flex items-center gap-4">
          <div
            className="w-10 h-10 rounded-xl flex items-center justify-center font-heading font-black text-base text-[#000B29] shadow-md flex-shrink-0"
            style={{ background: selected.color }}
          >
            {selected.step}
          </div>
          <div>
            <div className="font-heading font-bold text-white text-sm sm:text-base flex items-center gap-2">
              <span>{selected.label}</span>
              <span className="text-slate-400 font-mono2 text-xs font-normal">— {selected.sub}</span>
            </div>
            <div className="text-xs text-slate-300 mt-1">
              {selected.desc}
            </div>
          </div>
        </div>

        <div className="flex items-center gap-3 self-end md:self-center flex-shrink-0">
          <div className="text-right">
            <div className="text-[9px] font-bold text-slate-400 uppercase tracking-widest">
              BENCHMARK
            </div>
            <div className="font-mono2 font-bold text-xs" style={{ color: selected.color }}>
              {selected.metric}
            </div>
          </div>
          <span className="w-8 h-8 rounded-full bg-white/10 border border-white/20 grid place-items-center">
            <CheckCircle2 size={16} style={{ color: selected.color }} />
          </span>
        </div>
      </div>
    </div>
  );
}
