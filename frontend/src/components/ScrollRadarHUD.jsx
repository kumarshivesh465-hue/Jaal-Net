import { useState, useEffect } from "react";
import { Compass, ChevronUp, ChevronDown } from "lucide-react";

const SECTIONS = [
  { id: "hero-section", label: "Overview", tag: "HERO" },
  { id: "g2-marquee-section", label: "Trust Badges", tag: "G2" },
  { id: "difference-section", label: "Difference", tag: "CLEARBOX" },
  { id: "intelligence-section", label: "Network Intelligence", tag: "NETWORK" },
  { id: "efficiency-section", label: "Rule Automation", tag: "RULES" },
  { id: "pipeline-section", label: "Connected Pipeline", tag: "GNN PIPELINE" },
  { id: "simulator-section", label: "Live Simulator", tag: "INJECTOR" },
  { id: "globe-section", label: "Spatial Matrix", tag: "3D TOPOLOGY" },
  { id: "stream-section", label: "Stream & Hotspots", tag: "RADAR" },
];

export default function ScrollRadarHUD() {
  const [activeSection, setActiveSection] = useState(SECTIONS[0].id);
  const [scrollPercent, setScrollPercent] = useState(0);
  const [isExpanded, setIsExpanded] = useState(false);

  useEffect(() => {
    const handleScroll = () => {
      const scrollY = window.scrollY;
      const totalHeight = document.documentElement.scrollHeight - window.innerHeight;
      if (totalHeight > 0) {
        setScrollPercent(Math.round((scrollY / totalHeight) * 100));
      }

      // Detect active section based on proximity to viewport center
      const viewportCenter = scrollY + window.innerHeight * 0.35;
      for (let i = SECTIONS.length - 1; i >= 0; i--) {
        const el = document.getElementById(SECTIONS[i].id);
        if (el && el.offsetTop <= viewportCenter) {
          setActiveSection(SECTIONS[i].id);
          break;
        }
      }
    };

    window.addEventListener("scroll", handleScroll, { passive: true });
    handleScroll();
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  const scrollTo = (id) => {
    const el = document.getElementById(id);
    if (el) {
      el.scrollIntoView({ behavior: "smooth" });
    }
  };

  const scrollToTop = () => {
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const currentSec = SECTIONS.find((s) => s.id === activeSection) || SECTIONS[0];

  return (
    <div className="fixed bottom-6 right-6 z-40 flex items-end gap-3 select-none">
      {/* Expanded Menu Panel */}
      {isExpanded && (
        <div className="liquid-glass p-3 shadow-2xl border border-white/80 space-y-1.5 min-w-[200px] mb-1 animate-in fade-in slide-in-from-bottom-2 duration-200">
          <div className="flex items-center justify-between pb-2 border-b border-slate-200 px-2">
            <span className="text-[10px] font-mono2 font-bold text-slate-500 uppercase tracking-widest">
              TELEMETRY RADAR
            </span>
            <span className="text-[10px] font-mono2 font-bold text-[#2E69FF]">
              {scrollPercent}% SCROLL
            </span>
          </div>

          <div className="space-y-0.5">
            {SECTIONS.map((sec) => {
              const isActive = activeSection === sec.id;
              return (
                <button
                  key={sec.id}
                  onClick={() => {
                    scrollTo(sec.id);
                    setIsExpanded(false);
                  }}
                  className={`w-full flex items-center justify-between px-2.5 py-1.5 rounded-lg text-xs font-semibold text-left transition-all ${
                    isActive
                      ? "bg-[#2E69FF] text-white shadow-sm"
                      : "text-slate-700 hover:bg-slate-100/80"
                  }`}
                >
                  <span className="truncate">{sec.label}</span>
                  <span
                    className={`text-[9px] font-mono2 uppercase ml-2 ${
                      isActive ? "text-white/80" : "text-slate-400"
                    }`}
                  >
                    {sec.tag}
                  </span>
                </button>
              );
            })}
          </div>
        </div>
      )}

      {/* Floating Pill Trigger */}
      <div className="liquid-glass p-1.5 shadow-2xl border border-white/90 flex items-center gap-2 rounded-full">
        {/* Clickable section indicator button */}
        <button
          onClick={() => setIsExpanded(!isExpanded)}
          className="flex items-center gap-2 pl-3 pr-2 py-1.5 rounded-full hover:bg-white/80 transition-all text-left"
          title="Toggle telemetry navigator"
        >
          <div className="relative flex items-center justify-center">
            <div className="w-2.5 h-2.5 rounded-full bg-[#2E69FF] animate-pulse" />
            <div className="absolute w-4 h-4 rounded-full border border-[#2E69FF]/50 animate-ping pointer-events-none" />
          </div>

          <div className="flex flex-col">
            <span className="text-[10px] font-mono2 font-extrabold text-slate-900 leading-none">
              {currentSec.tag}
            </span>
            <span className="text-[8.5px] font-mono2 text-slate-500 leading-tight">
              {scrollPercent}%
            </span>
          </div>

          <Compass size={14} className="text-slate-500 ml-1" />
        </button>

        {/* Quick Scroll To Top Button */}
        <button
          onClick={scrollToTop}
          className="w-8 h-8 rounded-full bg-[#00124D] text-white hover:bg-[#2E69FF] transition-colors grid place-items-center shadow-sm cursor-pointer"
          title="Scroll to top"
        >
          <ChevronUp size={16} />
        </button>
      </div>
    </div>
  );
}
