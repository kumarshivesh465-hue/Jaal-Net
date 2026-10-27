import { useMemo, useState, useEffect, useRef } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  ArrowRight,
  ShieldCheck,
  AlertTriangle,
  TrendingUp,
  Shield,
  Zap,
  Quote,
  CheckCircle2,
  XOctagon,
  Sparkles,
} from "lucide-react";
import Globe3D from "../components/Globe3D.jsx";
import ConnectedPipeline from "../components/ConnectedPipeline.jsx";
import UpiSimulator from "../components/UpiSimulator.jsx";
import AnimatedCounter from "../components/AnimatedCounter.jsx";
import TiltCard from "../components/TiltCard.jsx";
import ParallaxBadge from "../components/ParallaxBadge.jsx";
import { INDIAN_STATES, inr, scoreColor, bandOf } from "../lib/mock.js";

// Velocity spike timeline telemetry
const VELOCITY_CHART_DATA = [
  { time: "12 am", txns: 120, threshold: 450 },
  { time: "4 am", txns: 80, threshold: 450 },
  { time: "8 am", txns: 240, threshold: 450 },
  { time: "12 pm", txns: 640, threshold: 450 },
  { time: "4 pm", txns: 310, threshold: 450 },
  { time: "8 pm", txns: 190, threshold: 450 },
  { time: "12 am", txns: 140, threshold: 450 },
];

// Compliance and benchmark badges
const G2_BADGES = [
  { season: "FALL 2026", title: "Leader", sub: "MULE DEFENSE", color: "#FF492C" },
  { season: "FALL 2026", title: "Leader", sub: "SMALL BUSINESS", color: "#FF492C" },
  { season: "FALL 2026", title: "Momentum Leader", sub: "SUB-2MS ONNX", color: "#FF9A00" },
  { season: "FALL 2026", title: "Most Implementable", sub: "ENTERPRISE", color: "#00B8D9" },
  { season: "FALL 2026", title: "Best Results", sub: "EXASOL GRID", color: "#6554C0" },
  { season: "FALL 2026", title: "Best Usability", sub: "RBI DIRECTIVE", color: "#FFAB00" },
  { season: "FALL 2026", title: "Leader", sub: "ENTERPRISE", color: "#FF492C" },
];

// Distinctive Multicolor Palette for Indian States (NO BLACK BARS)
const STATE_MULTICOLORS = {
  MH: "#2E69FF", // Electric Blue (Maharashtra)
  DL: "#FF0055", // Hot Pink / Crimson (Delhi)
  KA: "#00F5A0", // Mint (Karnataka)
  WB: "#FFCA36", // Vivid Gold (West Bengal)
  TN: "#8B5CF6", // Electric Purple (Tamil Nadu)
  GJ: "#FF7849", // Vivid Coral Orange (Gujarat)
  UP: "#06B6D4", // Bright Cyan (Uttar Pradesh)
  TG: "#EC4899", // Neon Magenta (Telangana)
  TS: "#EC4899", // Telangana
  RJ: "#3B82F6", // Royal Blue (Rajasthan)
  KL: "#10B981", // Sea Green (Kerala)
};

// Reusable Scroll-Reveal Wrapper for Smooth Side-Gliding Scroll Animations
// Triggers reliably on every scroll down OR up by reacting directly to entry.isIntersecting
function ScrollRevealSection({
  children,
  className = "",
  id = "",
  direction = "center", // "left" | "right" | "center"
}) {
  const ref = useRef(null);
  const [isVisible, setIsVisible] = useState(false);

  useEffect(() => {
    const observer = new IntersectionObserver(
      ([entry]) => {
        // Re-triggers smoothly every time user scrolls past in either direction
        setIsVisible(entry.isIntersecting);
      },
      { threshold: 0.12, rootMargin: "0px 0px -40px 0px" }
    );

    if (ref.current) observer.observe(ref.current);
    return () => observer.disconnect();
  }, []);

  let animClass = "scroll-reveal";
  if (direction === "left") animClass = "scroll-glide-left";
  else if (direction === "right") animClass = "scroll-glide-right";
  else if (direction === "center") animClass = "scroll-reveal-3d";

  return (
    <div
      id={id}
      ref={ref}
      className={`${animClass} ${isVisible ? "is-visible" : ""} ${className}`}
    >
      {children}
    </div>
  );
}

// Authentic Sift Large G2 Shield Badge Component
function BigSiftG2Shield({ season, title, sub, color }) {
  return (
    <div className="relative group transition-all duration-300 hover:-translate-y-2 flex-shrink-0 cursor-default select-none mx-3">
      {/* Main White Rectangular Card Body (Enlarged) */}
      <div className="w-[185px] bg-white rounded-t-xl pt-4 px-4 pb-3 shadow-lg border-t border-l border-r border-slate-200/90 text-center flex flex-col justify-between h-[126px]">
        {/* Header: Season + G2 Red Logo */}
        <div className="flex items-center justify-between">
          <span className="text-[9.5px] font-extrabold text-slate-400 uppercase tracking-wider">
            {season}
          </span>
          <div className="w-5 h-5 rounded-md bg-[#FF492C] text-white flex items-center justify-center font-black text-[10.5px] shadow-sm">
            G
          </div>
        </div>

        {/* Center Title & Subtitle */}
        <div className="my-auto py-1">
          <div className="font-sans font-bold text-[15px] text-slate-900 leading-snug">
            {title}
          </div>
          {sub && (
            <div className="text-[9px] font-bold text-slate-400 uppercase tracking-wider mt-1">
              {sub}
            </div>
          )}
        </div>
      </div>

      {/* Pointed Shield Bottom with SVG and Colored Chevron Border (Enlarged) */}
      <svg
        viewBox="0 0 185 28"
        className="w-[185px] h-[28px] block -mt-[1px] filter drop-shadow(0 4px 6px rgba(0, 0, 0, 0.08))"
      >
        <polygon points="0,0 185,0 92.5,26" fill="#FFFFFF" />
        <polyline
          points="0,1 92.5,25 185,1"
          fill="none"
          stroke={color}
          strokeWidth="4"
          strokeLinejoin="round"
        />
      </svg>
    </div>
  );
}

export default function CommandCenter({
  stream,
  health,
  onOpenTxn,
  onInjectTxn,
  isStreaming,
  onToggleStream,
}) {
  const [activeAlertTab, setActiveAlertTab] = useState("active");
  const [exasolHotspots, setExasolHotspots] = useState({});
  const [ringCount, setRingCount] = useState(60);

  useEffect(() => {
    fetch("/api/rings")
      .then((res) => (res.ok ? res.json() : []))
      .then((data) => {
        if (Array.isArray(data) && data.length > 0) setRingCount(data.length);
      })
      .catch((err) => console.warn("Could not fetch Exasol rings count:", err));
  }, []);

  useEffect(() => {
    let alive = true;
    const fetchHotspots = () => {
      fetch("/api/stats/state-hotspots")
        .then((res) => (res.ok ? res.json() : []))
        .then((data) => {
          if (alive && Array.isArray(data) && data.length > 0) {
            const map = {};
            data.forEach((d) => {
              map[d.state_code] = d.alerts;
            });
            setExasolHotspots(map);
          }
        })
        .catch((err) => console.warn("Could not fetch Exasol state hotspots:", err));
    };
    fetchHotspots();
    const interval = setInterval(fetchHotspots, 20000);
    return () => {
      alive = false;
      clearInterval(interval);
    };
  }, []);

  const blocked = useMemo(
    () =>
      stream.reduce(
        (s, t) => (t.action === "BLOCK" && !t.overridden ? s + t.amount : s),
        0
      ),
    [stream]
  );

  const hotspots = useMemo(() => {
    const streamCounts = {};
    stream.forEach((t) => {
      if (["BLOCK", "STEP_UP"].includes(t.action))
        streamCounts[t.state] = (streamCounts[t.state] || 0) + 1;
    });
    return INDIAN_STATES.map((s) => ({
      state: s,
      alerts: (exasolHotspots[s] || 0) + (streamCounts[s] || 0),
    }));
  }, [stream, exasolHotspots]);

  return (
    <div className="space-y-24">
      {/* =====================================================================
          1. Hero Telemetry & Ingestion Overview
          ===================================================================== */}
      <ScrollRevealSection id="hero-section">
        <section className="relative rounded-3xl bg-[#00124D] text-white overflow-hidden p-8 sm:p-12 shadow-2xl border border-white/10">
          {/* Sift Signature Angled Golden/Mint Glow Backdrop */}
          <div className="absolute top-0 right-0 w-[55%] h-full bg-gradient-to-bl from-[#FFCA36]/20 via-[#2E69FF]/15 to-transparent pointer-events-none transform -skew-x-12 translate-x-20" />
          <div className="absolute -top-24 right-16 w-96 h-96 rounded-full bg-[#FFCA36]/25 blur-3xl pointer-events-none" />

          <div className="relative z-10 grid grid-cols-1 lg:grid-cols-12 gap-10 items-center">
            {/* Left Column: Sift Headline & Story (Glides smoothly from Left) */}
            <div className="lg:col-span-7 space-y-6 glide-child-left">
              <h1 className="font-heading font-black text-4xl sm:text-5xl xl:text-6xl text-white leading-[1.08] tracking-tight">
                The Modern Way <br />
                to Build{" "}
                <span className="font-marker text-[#79F7C6] inline-block -rotate-1">
                  CUSTOMER TRUST
                </span>
              </h1>

              <p className="text-slate-200 text-sm sm:text-base leading-relaxed max-w-xl font-normal">
                JaalNet is a fraud prevention platform that uses machine learning to tell
                legitimate customers from fraudsters in real time. Powered by an Exasol
                in-memory graph grid of 100,000+ accounts across India's UPI matrix, JaalNet
                gives businesses continuous visibility into payment fraud, account takeover,
                and money mule rings, so they can approve more customers and grow securely.
              </p>

              <p className="text-slate-400 text-xs sm:text-sm leading-relaxed max-w-xl font-normal">
                Industry leaders like State Bank of India, HDFC Bank, and NPCI partner desks
                rely on JaalNet to protect customers, prevent fraud losses, and build sustainable
                competitive advantage through smarter risk management.
              </p>

              <div className="flex flex-wrap items-center gap-4 pt-2">
                <button
                  onClick={() => {
                    const el = document.getElementById("pipeline-section");
                    el?.scrollIntoView({ behavior: "smooth" });
                  }}
                  className="btn-sift-pink"
                >
                  EXPLORE GNN DEFENSE
                </button>

                <button
                  onClick={() => {
                    const el = document.getElementById("simulator-section");
                    el?.scrollIntoView({ behavior: "smooth" });
                  }}
                  className="btn-sift-outline"
                >
                  LAUNCH SIMULATOR
                </button>
              </div>
            </div>

            {/* Right Column: Desktop Monitor Frame (Glides smoothly from Right) */}
            <div className="lg:col-span-5 glide-child-right">
              <TiltCard maxTilt={6} scale={1.015} className="mx-auto max-w-[500px]">
                {/* Monitor Screen Frame with Liquid Border */}
                <div className="rounded-2xl bg-[#000B29] p-3 border-4 border-slate-700 shadow-2xl">
                  {/* Browser/Window Header */}
                  <div className="flex items-center justify-between pb-2 mb-2 border-b border-white/10 px-1">
                    <div className="flex items-center gap-2">
                      <div className="w-2.5 h-2.5 rounded-full bg-red-500" />
                      <div className="w-2.5 h-2.5 rounded-full bg-yellow-500" />
                      <div className="w-2.5 h-2.5 rounded-full bg-green-500" />
                      <span className="text-[10px] text-slate-400 font-mono2 ml-2">
                        jaalnet.internal/insights
                      </span>
                    </div>
                    <span className="px-2 py-0.5 rounded-full bg-[#79F7C6]/20 text-[#79F7C6] text-[9px] font-bold font-mono2">
                      LIVE STREAM
                    </span>
                  </div>

                  {/* Inner Dashboard View inside Monitor with Liquid Glass Frosting */}
                  <div className="space-y-3 bg-white text-[#0A122C] rounded-xl p-4 shadow-inner">
                    <div className="flex items-center justify-between">
                      <div>
                        <div className="text-[10px] text-slate-500 font-bold uppercase tracking-wider">
                          Logins by Decision
                        </div>
                        <div className="font-sans font-bold text-lg text-slate-900">
                          <AnimatedCounter value={5067942} duration={2000} />{" "}
                          <span className="text-xs font-normal text-slate-500">Total</span>
                        </div>
                      </div>
                      <div className="text-right">
                        <div className="text-[10px] text-slate-500 font-bold uppercase tracking-wider">
                          Real-Time Block Rate
                        </div>
                        <div className="font-sans font-bold text-lg text-[#2E69FF]">
                          <AnimatedCounter value={1.59} decimals={2} suffix="%" duration={1600} />
                        </div>
                      </div>
                    </div>

                    {/* Velocity Spike Line Chart */}
                    <div className="h-[125px] w-full pt-1">
                      <ResponsiveContainer width="100%" height="100%">
                        <LineChart data={VELOCITY_CHART_DATA} margin={{ top: 5, right: 10, left: -25, bottom: 0 }}>
                          <CartesianGrid stroke="#E2E8F0" strokeDasharray="3 3" vertical={false} />
                          <XAxis dataKey="time" tick={{ fontSize: 9, fill: "#94A3B8" }} axisLine={false} tickLine={false} />
                          <YAxis tick={{ fontSize: 9, fill: "#94A3B8" }} axisLine={false} tickLine={false} domain={[0, 700]} />
                          <Line
                            type="monotone"
                            dataKey="txns"
                            stroke="#2E69FF"
                            strokeWidth={2.5}
                            dot={{ r: 3, fill: "#2E69FF" }}
                          />
                          <Line
                            type="monotone"
                            dataKey="threshold"
                            stroke="#FF0055"
                            strokeWidth={1.5}
                            strokeDasharray="3 3"
                            dot={false}
                          />
                        </LineChart>
                      </ResponsiveContainer>
                    </div>

                    {/* Summary Bar */}
                    <div className="grid grid-cols-3 gap-2 pt-2 border-t border-slate-100 text-center">
                      <div>
                        <div className="text-[9px] text-slate-400 font-bold">BURST VELOCITY</div>
                        <div className="font-sans font-bold text-xs text-[#FF0055]">640 tx/hr</div>
                      </div>
                      <div>
                        <div className="text-[9px] text-slate-400 font-bold">PEAK WINDOW</div>
                        <div className="font-sans font-bold text-xs text-slate-800">12:00 PM</div>
                      </div>
                      <div>
                        <div className="text-[9px] text-slate-400 font-bold">STATUS</div>
                        <div className="font-sans font-bold text-xs text-[#15803D]">Shield Active</div>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Monitor Stand Base */}
                <div className="w-20 h-6 bg-slate-700 mx-auto rounded-b-md" />
                <div className="w-40 h-2.5 bg-slate-600 mx-auto rounded-full shadow-lg" />
              </TiltCard>
            </div>
          </div>

          {/* Telemetry Summary Counters */}
          <div className="relative z-10 pt-10 mt-10 border-t border-white/10 grid grid-cols-1 sm:grid-cols-3 gap-6 text-center sm:text-left">
            <div>
              <AnimatedCounter
                value={100}
                suffix="K+"
                duration={1800}
                className="font-heading font-black text-4xl sm:text-5xl text-[#FFCA36] tracking-tight"
              />
              <div className="text-xs text-slate-300 font-bold uppercase tracking-wider mt-1">
                Exasol In-Memory Graph Entities
              </div>
            </div>

            <div>
              <AnimatedCounter
                value={2.1}
                decimals={1}
                suffix="B"
                duration={1800}
                className="font-heading font-black text-4xl sm:text-5xl text-[#FFCA36] tracking-tight"
              />
              <div className="text-xs text-slate-300 font-bold uppercase tracking-wider mt-1">
                Annual Events Evaluated
              </div>
            </div>

            <div>
              <AnimatedCounter
                value={4.2}
                decimals={1}
                prefix="₹"
                suffix="M*"
                duration={1800}
                className="font-heading font-black text-4xl sm:text-5xl text-[#FFCA36] tracking-tight"
              />
              <div className="text-xs text-slate-300 font-bold uppercase tracking-wider mt-1">
                Real-Time Shielded Funds Today
              </div>
            </div>
          </div>
        </section>
      </ScrollRevealSection>

      {/* =====================================================================
          2. SIFT TRUST BADGES ROW (BIG SIZES + INFINITE MARQUEE LOOP)
          ===================================================================== */}
      <ScrollRevealSection id="g2-marquee-section" className="py-2">
        <div className="relative w-full overflow-hidden py-4">
          {/* Left and Right Edge Fade Gradients for Seamless Marquee Entrance */}
          <div className="pointer-events-none absolute left-0 top-0 bottom-0 w-28 bg-gradient-to-r from-[#EEF2F9] to-transparent z-20" />
          <div className="pointer-events-none absolute right-0 top-0 bottom-0 w-28 bg-gradient-to-l from-[#EEF2F9] to-transparent z-20" />

          {/* Continuous Infinite Marquee Track (Repeated for Seamless Endless Flow) */}
          <div className="animate-marquee-infinite flex items-center">
            {/* Set 1 */}
            {G2_BADGES.map((b, i) => (
              <BigSiftG2Shield
                key={`g2-set1-${i}`}
                season={b.season}
                title={b.title}
                sub={b.sub}
                color={b.color}
              />
            ))}
            {/* Set 2 (for seamless loop) */}
            {G2_BADGES.map((b, i) => (
              <BigSiftG2Shield
                key={`g2-set2-${i}`}
                season={b.season}
                title={b.title}
                sub={b.sub}
                color={b.color}
              />
            ))}
            {/* Set 3 */}
            {G2_BADGES.map((b, i) => (
              <BigSiftG2Shield
                key={`g2-set3-${i}`}
                season={b.season}
                title={b.title}
                sub={b.sub}
                color={b.color}
              />
            ))}
          </div>
        </div>
        <hr className="border-slate-200 mt-6 max-w-6xl mx-auto" />
      </ScrollRevealSection>

      {/* =====================================================================
          2. Platform Architectural Differentiators
          ===================================================================== */}
      <ScrollRevealSection id="difference-section" className="py-4">
        <h2 className="font-sans font-bold text-3xl sm:text-4xl text-slate-900 mb-8 tracking-tight">
          The JaalNet{" "}
          <span className="font-marker text-slate-900 font-normal">DIFFERENCE</span>
        </h2>

        <div className="grid grid-cols-1 lg:grid-cols-12 gap-10 lg:gap-14 items-center">
          {/* Left Column: Visual Container (Glides smoothly from Left) */}
          <div className="lg:col-span-6 relative pt-6 pr-6 glide-child-left">
            {/* The Main Dark Container with Interactive 3D Tilt */}
            <TiltCard maxTilt={5} scale={1.01}>
              <div className="relative rounded-3xl bg-[#000B29] p-6 sm:p-8 shadow-2xl border border-slate-800">
                {/* Inner Glow Confined Safely */}
                <div className="absolute inset-0 rounded-3xl overflow-hidden pointer-events-none">
                  <div className="absolute -bottom-10 -right-10 w-72 h-72 rounded-full bg-[#2E69FF]/40 blur-2xl" />
                </div>

                {/* Main White Orders Report Card with Liquid Glass Finish */}
                <div className="relative z-10 liquid-glass-card p-5 shadow-lg space-y-4">
                  <div className="flex items-center justify-between border-b border-slate-100 pb-2">
                    <span className="font-bold text-xs text-slate-700">Orders & Inferences Report</span>
                    <span className="text-[10px] text-slate-400 font-mono2">Live Stream</span>
                  </div>

                  <div className="space-y-2 text-xs">
                    <div className="flex items-center justify-between p-2 rounded-lg bg-slate-50 border border-slate-100">
                      <span className="font-mono2 text-slate-600">rahul.k@oksbi</span>
                      <span className="font-bold text-[#15803D]">₹4,500 · ALLOWED</span>
                    </div>
                    <div className="flex items-center justify-between p-2 rounded-lg bg-slate-50 border border-slate-100">
                      <span className="font-mono2 text-slate-600">priya.m@hdfc</span>
                      <span className="font-bold text-[#15803D]">₹1,200 · ALLOWED</span>
                    </div>
                    <div className="flex items-center justify-between p-2 rounded-lg bg-red-50 border border-red-100">
                      <span className="font-mono2 text-[#FF0055]">mule.acc.01@icici</span>
                      <span className="font-bold text-[#FF0055]">₹1,84,000 · BLOCKED</span>
                    </div>
                  </div>

                  <div className="grid grid-cols-4 gap-2 pt-1 text-center font-mono2 text-xs">
                    <div>
                      <div className="text-[9px] text-slate-400">Total</div>
                      <div className="font-bold text-slate-800">
                        <AnimatedCounter value={96101} duration={2000} />
                      </div>
                    </div>
                    <div>
                      <div className="text-[9px] text-slate-400">Mules</div>
                      <div className="font-bold text-[#FF0055]">
                        <AnimatedCounter value={2915} duration={1800} />
                      </div>
                    </div>
                    <div>
                      <div className="text-[9px] text-slate-400">Reviews</div>
                      <div className="font-bold text-[#FFCA36]">
                        <AnimatedCounter value={69205} duration={1900} />
                      </div>
                    </div>
                    <div>
                      <div className="text-[9px] text-slate-400">Shielded</div>
                      <div className="font-bold text-[#2E69FF]">₹3.31M</div>
                    </div>
                  </div>
                </div>
              </div>
            </TiltCard>

            {/* SIFT SIGNATURE FLOATING POP-UP CARD 1 (SCROLL PARALLAX + 3D TILT + LIQUID GLASS) */}
            <ParallaxBadge speed={-0.08} className="absolute -top-4 -right-2 sm:-top-6 sm:-right-4 z-30">
              <TiltCard maxTilt={8} scale={1.03}>
                <div className="liquid-glass p-4 sm:p-5 shadow-2xl min-w-[210px] border border-white/90">
                  <div className="text-[11px] font-bold text-slate-500 uppercase tracking-wider">
                    Accepted Orders
                  </div>
                  <div className="font-sans font-bold text-2xl sm:text-3xl text-[#2E69FF] my-0.5">
                    <AnimatedCounter value={7414703} prefix="₹" duration={2200} />
                  </div>
                  <div className="text-[11px] text-slate-500 font-normal">
                    Value of accepted orders
                  </div>
                </div>
              </TiltCard>
            </ParallaxBadge>
          </div>

          {/* Right Column: Copy (Glides smoothly from Right) */}
          <div className="lg:col-span-6 space-y-4 glide-child-right">
            <h3 className="font-sans font-bold text-2xl sm:text-3xl text-slate-900 tracking-tight">
              Clearbox Control over Risk & Revenue
            </h3>
            <p className="text-slate-600 text-sm sm:text-base leading-relaxed font-normal">
              Gain visibility into the signals, models, and workflows behind every decision
              so teams can tune automation with confidence instead of relying on a black box.
            </p>
            <div className="pt-2 space-y-3">
              <div className="flex items-start gap-3">
                <div className="w-5 h-5 rounded-full bg-[#2E69FF]/10 text-[#2E69FF] grid place-items-center mt-0.5 flex-shrink-0">
                  <CheckCircle2 size={14} />
                </div>
                <div>
                  <div className="text-sm font-bold text-slate-900">
                    Multi-Hop Topological Tracing
                  </div>
                  <div className="text-xs text-slate-500">
                    Traces smurfing and money mules 3 hops deep in Exasol in sub-2ms.
                  </div>
                </div>
              </div>

              <div className="flex items-start gap-3">
                <div className="w-5 h-5 rounded-full bg-[#2E69FF]/10 text-[#2E69FF] grid place-items-center mt-0.5 flex-shrink-0">
                  <CheckCircle2 size={14} />
                </div>
                <div>
                  <div className="text-sm font-bold text-slate-900">
                    Transparent SHAP Feature Attribution
                  </div>
                  <div className="text-xs text-slate-500">
                    Audit log explains why every score was assigned before freezing funds.
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </ScrollRevealSection>

      {/* =====================================================================
          3. Cross-Network Signal Aggregation
          ===================================================================== */}
      <ScrollRevealSection id="intelligence-section" className="py-4">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-10 lg:gap-14 items-center">
          {/* Left Column: Heading, Copy, Testimonial Quote (Glides smoothly from Left) */}
          <div className="lg:col-span-6 space-y-6 glide-child-left">
            <h3 className="font-sans font-bold text-3xl sm:text-4xl text-slate-900 tracking-tight">
              Intelligence Beyond Your Own Data
            </h3>
            <p className="text-slate-600 text-sm sm:text-base leading-relaxed font-normal">
              Benefit from a global data network processing more than 1 trillion events
              annually. New-to-you users are often not new to JaalNet, which means your
              team starts with more context before making a decision.
            </p>

            <hr className="border-slate-200" />

            {/* Fraud Operations Testimonial */}
            <div className="flex items-start gap-4 pt-2">
              <div className="w-8 h-8 rounded-full bg-[#2E69FF] text-white flex-shrink-0 grid place-items-center mt-1">
                <Quote size={16} className="fill-white" />
              </div>
              <div className="space-y-3">
                <p className="font-bold text-sm sm:text-base text-slate-900 leading-snug">
                  “JaalNet consistently offers valuable expertise on various fraud trends
                  and provides insightful recommendations to achieve better results.”
                </p>
                <div className="flex items-center justify-between">
                  <div>
                    <div className="font-bold text-xs text-slate-900">Rick Hiltbrunner</div>
                    <div className="text-[11px] text-slate-500">Director of Fraud Operations, Patreon</div>
                  </div>
                  <span className="font-sans font-bold text-xs tracking-widest text-slate-800">
                    PATREON
                  </span>
                </div>
              </div>
            </div>
          </div>

          {/* Right Column: Mint Container + Free-Floating Pop-Ups (Glides smoothly from Right) */}
          <div className="lg:col-span-6 relative pt-6 pr-6 pl-4 pb-6 glide-child-right">
            {/* The Mint Backdrop Container with Interactive 3D Tilt */}
            <TiltCard maxTilt={5} scale={1.01}>
              <div className="relative rounded-3xl bg-[#79F7C6] p-6 sm:p-8 shadow-xl">
                {/* Inner Curve Blur Confined Safely */}
                <div className="absolute inset-0 rounded-3xl overflow-hidden pointer-events-none">
                  <div className="absolute -top-12 -right-12 w-56 h-56 rounded-full bg-[#00F5A0]/50 blur-2xl" />
                </div>

                {/* Entity Risk Matrix */}
                <div className="relative z-10 liquid-glass-card p-5 shadow-lg space-y-3">
                  <div className="flex items-center justify-between border-b border-slate-100 pb-2">
                    <span className="font-bold text-xs text-slate-900">Account Takeover</span>
                    <div className="flex gap-2 text-[10px] font-bold">
                      <span className="text-[#2E69FF] border-b-2 border-[#2E69FF] pb-0.5">Explore</span>
                      <span className="text-slate-400">Review</span>
                    </div>
                  </div>

                  <div className="space-y-2 text-xs">
                    <div className="flex items-center justify-between p-1.5 rounded hover:bg-slate-50">
                      <span className="font-mono2 text-slate-500">brett_*****@hotmail.com</span>
                      <span className="px-2 py-0.5 rounded-full bg-yellow-100 text-yellow-800 font-bold font-mono2 text-[10px]">
                        🛡️ 36
                      </span>
                    </div>
                    <div className="flex items-center justify-between p-1.5 rounded hover:bg-slate-50">
                      <span className="font-mono2 text-slate-500">rob*****@gmail.com</span>
                      <span className="px-2 py-0.5 rounded-full bg-red-100 text-[#FF0055] font-bold font-mono2 text-[10px]">
                        🛡️ 99
                      </span>
                    </div>
                    <div className="flex items-center justify-between p-1.5 rounded hover:bg-slate-50">
                      <span className="font-mono2 text-slate-500">abdul_kar*****@gmail.com</span>
                      <span className="px-2 py-0.5 rounded-full bg-green-100 text-[#15803D] font-bold font-mono2 text-[10px]">
                        🛡️ 27
                      </span>
                    </div>
                    <div className="flex items-center justify-between p-1.5 rounded hover:bg-slate-50">
                      <span className="font-mono2 text-slate-500">ciarra.san*****@yahoo.com</span>
                      <span className="px-2 py-0.5 rounded-full bg-yellow-100 text-yellow-800 font-bold font-mono2 text-[10px]">
                        🛡️ 34
                      </span>
                    </div>
                    <div className="flex items-center justify-between p-1.5 rounded hover:bg-slate-50">
                      <span className="font-mono2 text-slate-500">camryn.m*****@yahoo.com</span>
                      <span className="px-2 py-0.5 rounded-full bg-green-100 text-[#15803D] font-bold font-mono2 text-[10px]">
                        🛡️ 20
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            </TiltCard>

            {/* SIFT SIGNATURE POP-UP 1: Risk Level 12 (SCROLL PARALLAX + 3D TILT + LIQUID GLASS) */}
            <ParallaxBadge speed={-0.09} className="absolute -top-4 -right-2 sm:-top-6 sm:-right-4 z-30">
              <TiltCard maxTilt={8} scale={1.03}>
                <div className="liquid-glass p-4 sm:p-5 shadow-2xl flex items-center gap-3 border border-white/90">
                  <div>
                    <div className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">
                      Risk Level
                    </div>
                    <div className="flex items-center gap-2 mt-0.5">
                      <div className="w-6 h-6 rounded-lg bg-[#10B981] text-white flex items-center justify-center shadow-sm">
                        <Shield size={14} className="fill-white" />
                      </div>
                      <span className="font-sans font-bold text-2xl text-slate-900">
                        <AnimatedCounter value={12} duration={1400} />
                      </span>
                    </div>
                  </div>
                </div>
              </TiltCard>
            </ParallaxBadge>

            {/* SIFT SIGNATURE POP-UP 2: Real Fraud Analyst Avatar Photo with Pink Ring (SCROLL PARALLAX) */}
            <ParallaxBadge speed={0.06} floatAnim="sift-floating-avatar" className="absolute -bottom-4 -left-2 sm:-bottom-6 sm:-left-4 z-30">
              <div className="w-22 h-22 sm:w-26 sm:h-26 rounded-full border-4 border-[#FF0055] overflow-hidden shadow-2xl bg-white hover:scale-105 transition-transform duration-300">
                <img
                  src="https://images.unsplash.com/photo-1573496359142-b8d87734a5a2?auto=format&fit=crop&w=300&q=80"
                  alt="Fraud Analyst Rick Hiltbrunner"
                  className="w-full h-full object-cover"
                />
              </div>
            </ParallaxBadge>
          </div>
        </div>
      </ScrollRevealSection>

      {/* =====================================================================
          4. Automated Workflow & Interception Engine
          ===================================================================== */}
      <ScrollRevealSection id="efficiency-section" className="py-4">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-10 lg:gap-14 items-center">
          {/* Left Column: Blue Container (Glides smoothly from Left) */}
          <div className="lg:col-span-6 relative pt-6 pr-6 pb-6 glide-child-left">
            {/* The Blue Container with Interactive 3D Tilt */}
            <TiltCard maxTilt={5} scale={1.01}>
              <div className="relative rounded-3xl bg-gradient-to-tr from-[#1E3A8A] via-[#2E69FF] to-[#1D4ED8] p-6 sm:p-8 shadow-2xl">
                {/* Inner Curve Blur Confined Safely */}
                <div className="absolute inset-0 rounded-3xl overflow-hidden pointer-events-none">
                  <div className="absolute -bottom-10 -left-10 w-64 h-64 rounded-full bg-[#FFCA36]/35 blur-xl" />
                </div>

                {/* Workflow Configuration Card */}
                <div className="relative z-10 liquid-glass-card p-5 shadow-lg space-y-3">
                  <div className="flex items-center justify-between border-b border-slate-100 pb-2">
                    <span className="font-bold text-xs text-slate-900">Create Order Rules</span>
                    <div className="flex gap-2 text-[10px] font-bold">
                      <span className="text-slate-400">Automate</span>
                      <span className="text-[#2E69FF] border-b-2 border-[#2E69FF] pb-0.5">Workflows</span>
                      <span className="text-slate-400">Decisions</span>
                    </div>
                  </div>

                  <div className="grid grid-cols-3 gap-2 py-1 text-center font-mono2 text-xs bg-slate-50 p-2 rounded-xl">
                    <div>
                      <div className="text-[9px] text-slate-400">Runs Started</div>
                      <div className="font-bold text-slate-800">
                        <AnimatedCounter value={76381} duration={2000} />
                      </div>
                    </div>
                    <div>
                      <div className="text-[9px] text-slate-400">Unique Users</div>
                      <div className="font-bold text-slate-800">
                        <AnimatedCounter value={48509} duration={2000} />
                      </div>
                    </div>
                    <div>
                      <div className="text-[9px] text-slate-400">Auto Intercept</div>
                      <div className="font-bold text-[#15803D]">
                        <AnimatedCounter value={99.2} decimals={1} suffix="%" duration={1600} />
                      </div>
                    </div>
                  </div>

                  <div className="space-y-2 text-xs">
                    <div className="p-2 rounded-lg border border-slate-200 space-y-1">
                      <div className="font-bold text-[11px] text-slate-800">High Score Block</div>
                      <div className="flex items-center justify-between text-[10px] text-slate-500">
                        <span>IF GNN SCORE &gt; 90</span>
                        <span className="font-bold text-[#FF0055]">● Auto Block</span>
                      </div>
                    </div>

                    <div className="p-2 rounded-lg border border-slate-200 space-y-1">
                      <div className="font-bold text-[11px] text-slate-800">MCC High Risk Smurf</div>
                      <div className="flex items-center justify-between text-[10px] text-slate-500">
                        <span>IF MULTI-HOP CYCLE</span>
                        <span className="font-bold text-[#FFCA36]">● Verify in 3DS</span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </TiltCard>

            {/* SIFT SIGNATURE POP-UP CARD 1: Block Rate 0.98% (SCROLL PARALLAX + 3D TILT + LIQUID GLASS) */}
            <ParallaxBadge speed={-0.08} className="absolute -top-4 -right-2 sm:-top-6 sm:-right-4 z-30">
              <TiltCard maxTilt={8} scale={1.03}>
                <div className="liquid-glass p-4 sm:p-5 shadow-2xl min-w-[180px] border border-white/90">
                  <div className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">
                    Block Rate
                  </div>
                  <div className="font-sans font-bold text-3xl sm:text-4xl text-[#2E69FF] my-0.5">
                    <AnimatedCounter value={0.98} decimals={2} suffix="%" duration={1800} />
                  </div>
                  <div className="flex items-center gap-1 text-[10px] font-bold text-[#FF0055]">
                    <span>↓ 11%</span>
                    <span className="text-slate-400 font-normal">from prior 30 days</span>
                  </div>
                </div>
              </TiltCard>
            </ParallaxBadge>

            {/* SIFT SIGNATURE POP-UP 2: Black Pill "Watch this order" (SCROLL PARALLAX) */}
            <ParallaxBadge speed={0.07} floatAnim="sift-floating-avatar" className="absolute -bottom-4 left-4 sm:-bottom-5 sm:left-6 z-30">
              <div className="bg-[#0A122C] text-white px-5 py-2.5 rounded-full font-bold shadow-2xl border border-yellow-400/50 flex items-center gap-2 text-xs sm:text-sm hover:scale-105 transition-transform duration-300">
                <span className="text-[#FFCA36]">⚠️</span>
                <span className="font-sans font-bold">Watch this order</span>
              </div>
            </ParallaxBadge>
          </div>

          {/* Right Column: Heading, Copy, Testimonial Quote (Glides smoothly from Right) */}
          <div className="lg:col-span-6 space-y-6 glide-child-right">
            <h3 className="font-sans font-bold text-3xl sm:text-4xl text-slate-900 tracking-tight">
              Efficiency That Improves Accuracy
            </h3>
            <p className="text-slate-600 text-sm sm:text-base leading-relaxed font-normal">
              Reduce manual review by automating low-risk decisions and giving analysts the
              context, visibility, and control they need to investigate high-priority cases
              faster. Built for analyst-driven teams that need speed without sacrificing accuracy.
            </p>

            <hr className="border-slate-200" />

            {/* Trust and Safety Operations Callout */}
            <div className="flex items-start gap-4 pt-2">
              <div className="w-8 h-8 rounded-full bg-[#2E69FF] text-white flex-shrink-0 grid place-items-center mt-1">
                <Quote size={16} className="fill-white" />
              </div>
              <div className="space-y-3">
                <p className="font-bold text-sm sm:text-base text-slate-900 leading-snug">
                  “JaalNet couldn't be easier to use, and the automation has helped me
                  immensely as a team of one.”
                </p>
                <div className="flex items-center justify-between">
                  <div>
                    <div className="font-bold text-xs text-slate-900">Susannah Page-Katz</div>
                    <div className="text-[11px] text-slate-500">Trust and Safety Manager, Skill Share</div>
                  </div>
                  <span className="font-sans font-bold text-xs tracking-widest text-slate-800">
                    SKILLSHARE.
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </ScrollRevealSection>

      {/* =====================================================================
          6. SIFT CONNECTED DEFENSE PIPELINE (Chain Animation + Liquid Glass)
          ===================================================================== */}
      <ScrollRevealSection id="pipeline-section">
        <section>
          <ConnectedPipeline />
        </section>
      </ScrollRevealSection>

      {/* =====================================================================
          7. INTERACTIVE SIMULATOR (One-Click Scenario Testing + Liquid Glass)
          ===================================================================== */}
      <ScrollRevealSection id="simulator-section">
        <section>
          <UpiSimulator
            onInject={onInjectTxn}
            onSelectTxn={onOpenTxn}
            isStreaming={isStreaming}
            onToggleStream={onToggleStream}
          />
        </section>
      </ScrollRevealSection>

      {/* =====================================================================
          8. 3D SPATIAL GLOBE & REAL-TIME STREAM
          ===================================================================== */}
      <ScrollRevealSection id="globe-section" className="space-y-6">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 glide-child-left">
          <div>
            <h2 className="font-sans font-bold text-2xl text-slate-900 tracking-tight">
              Spatial Graph Intelligence // India UPI Matrix
            </h2>
            <p className="text-xs text-slate-500 font-normal">
              Interactive 3D WebGL node topology linking real-time inter-state transaction funnels
            </p>
          </div>
          <div className="text-xs font-mono2 text-slate-500">
            DRAG TO ROTATE · SCROLL TO ZOOM
          </div>
        </div>

        {/* 3D Globe Container in High-Contrast Navy Showcase Frame with 3D Tilt */}
        <div className="glide-child-right">
          <TiltCard maxTilt={3} scale={1.008} glare={false}>
            <div className="bg-[#000B29] rounded-3xl p-4 border border-slate-800 shadow-2xl">
              <Globe3D
                height={460}
                ringCount={ringCount}
                shielded={blocked}
                backendUp={health.online}
              />
            </div>
          </TiltCard>
        </div>
      </ScrollRevealSection>

      {/* =====================================================================
          9. LIVE TRANSACTION STREAM & STATE HOTSPOTS (MULTICOLOR BARS)
          ===================================================================== */}
      <ScrollRevealSection id="stream-section" className="grid grid-cols-1 xl:grid-cols-5 gap-6">
        {/* Stream Column in Liquid Glass Card (Glides from Left) */}
        <div className="xl:col-span-3 liquid-glass p-6 sm:p-7 space-y-4 glide-child-left">
          <div className="flex items-center justify-between pb-3 border-b border-slate-100">
            <div className="flex items-center gap-2">
              <span className="live-dot" />
              <h3 className="font-sans font-bold text-lg text-slate-900">
                Live Transaction Stream
              </h3>
            </div>
            <span className="text-xs text-slate-400 font-mono2">
              STREAMING · CLICK ANY ROW TO INVESTIGATE
            </span>
          </div>

          <div className="max-h-[460px] overflow-y-auto pr-2 space-y-2">
            {stream.slice(0, 25).map((t) => {
              const band = bandOf(t.score);
              const cls =
                band === "block"
                  ? "sift-tx-row-light blk"
                  : band === "stepup"
                  ? "sift-tx-row-light stp"
                  : "sift-tx-row-light";

              const badgeCls =
                band === "block"
                  ? "score-pill-block"
                  : band === "stepup"
                  ? "score-pill-stepup"
                  : band === "monitor"
                  ? "score-pill-monitor"
                  : "score-pill-safe";

              return (
                <div
                  key={t.txnId}
                  className={`${cls} cursor-pointer`}
                  onClick={() => onOpenTxn(t)}
                >
                  <span className="font-mono2 text-xs text-slate-500 w-16">
                    {new Date(t.ts).toLocaleTimeString("en-IN", {
                      hour12: false,
                    })}
                  </span>

                  <span className="font-mono2 text-xs text-slate-700 truncate flex-1">
                    <span className="text-slate-900 font-bold">{t.sender}</span>
                    <span className="text-[#2E69FF] mx-1.5 font-bold">➔</span>
                    <span className="text-slate-900 font-bold">{t.receiver}</span>
                    {t.ringId && (
                      <span className="ml-2 px-1.5 py-0.5 rounded bg-pink-100 text-[#FF0055] text-[10px] font-bold">
                        {t.ringId}
                      </span>
                    )}
                  </span>

                  <span className="font-mono2 text-sm font-bold text-slate-900 w-24 text-right">
                    ₹{t.amount.toLocaleString("en-IN", { maximumFractionDigits: 0 })}
                  </span>

                  <span className={`score-pill ${badgeCls}`}>
                    {String(t.score).padStart(2, "0")}
                  </span>

                  <span
                    className="font-bold text-xs uppercase w-20 text-right"
                    style={{ color: scoreColor(t.score) }}
                  >
                    {t.action}
                  </span>
                </div>
              );
            })}
          </div>
        </div>

        {/* Hotspots Column: 100% VIVID MULTICOLOR BARS (Glides from Right) */}
        <div className="xl:col-span-2 liquid-glass p-6 sm:p-7 space-y-4 glide-child-right">
          <div className="flex items-center justify-between pb-3 border-b border-slate-100">
            <div>
              <h3 className="font-sans font-bold text-lg text-slate-900">
                State-Level Mule Hotspots
              </h3>
              <p className="text-xs text-slate-500 font-normal">
                Vibrant real-time jurisdictional interception matrix
              </p>
            </div>
            <span className="text-xs text-[#2E69FF] font-mono2 font-bold px-2 py-0.5 rounded-full bg-blue-50 border border-blue-100">
              INDIA RADAR
            </span>
          </div>

          <ResponsiveContainer width="100%" height={440}>
            <BarChart
              data={hotspots}
              layout="vertical"
              margin={{ top: 10, right: 30, left: -5, bottom: 0 }}
            >
              <CartesianGrid stroke="#F1F5F9" horizontal={false} />
              <XAxis
                type="number"
                tick={{ fill: "#64748B", fontSize: 11 }}
                axisLine={false}
                tickLine={false}
              />
              <YAxis
                type="category"
                dataKey="state"
                tick={{ fill: "#0A122C", fontSize: 12, fontWeight: "bold" }}
                axisLine={false}
                tickLine={false}
              />
              <Tooltip
                cursor={{ fill: "rgba(46,105,255,0.06)" }}
                content={({ active, payload }) => {
                  if (active && payload && payload.length) {
                    const data = payload[0].payload;
                    const barColor = STATE_MULTICOLORS[data.state] || "#2E69FF";
                    return (
                      <div className="liquid-glass p-3 shadow-xl border border-slate-200 text-xs">
                        <div className="flex items-center gap-2">
                          <span className="w-3 h-3 rounded-full" style={{ background: barColor }} />
                          <span className="font-bold text-slate-900">{data.state} Interceptions</span>
                        </div>
                        <div className="font-mono2 text-sm font-bold text-slate-900 mt-1">
                          {data.alerts} Mule Alerts Flagged
                        </div>
                      </div>
                    );
                  }
                  return null;
                }}
              />
              {/* Multicolor Bar Cells */}
              <Bar dataKey="alerts" radius={[0, 8, 8, 0]}>
                {hotspots.map((h) => (
                  <Cell
                    key={h.state}
                    fill={STATE_MULTICOLORS[h.state] || "#2E69FF"}
                  />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </ScrollRevealSection>
    </div>
  );
}
