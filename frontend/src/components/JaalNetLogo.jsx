import { useState } from "react";

/**
 * JaalNetLogo: A bespoke, non-generic brand mark designed around the concept of
 * "Jaal" (Hindi: जाल — The Interwoven Graph Net / Trap Matrix) that catches money mules.
 * Features an isometric neural graph lattice with 3 glowing vertex nodes and multi-hop paths.
 */
export default function JaalNetLogo({ className = "" }) {
  const [isHovered, setIsHovered] = useState(false);

  return (
    <div
      className={`flex items-center gap-3.5 select-none cursor-pointer group ${className}`}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
    >
      {/* Bespoke Geometric Isometric Neural Lattice Emblem */}
      <div className="relative w-10 h-10 flex-shrink-0 flex items-center justify-center">
        {/* Soft Ambient Dynamic Underglow */}
        <div
          className="absolute inset-0 rounded-xl bg-gradient-to-tr from-[#2E69FF] via-[#79F7C6] to-[#FF0055] opacity-40 blur-md transition-all duration-500 group-hover:opacity-85 group-hover:blur-lg"
        />

        {/* Handcrafted Vector Graph Neural Matrix Mark */}
        <div className="relative z-10 w-10 h-10 rounded-xl bg-[#030718] border border-white/20 p-1.5 shadow-2xl flex items-center justify-center overflow-hidden transition-all duration-300 group-hover:border-white/40 group-hover:scale-105">
          {/* Subtle Cyber Grid Texture */}
          <div className="absolute inset-0 bg-[radial-gradient(#2E69FF_1px,transparent_1px)] [background-size:6px_6px] opacity-25" />

          <svg
            viewBox="0 0 44 44"
            className="w-full h-full relative z-10 transition-transform duration-500 group-hover:rotate-6"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
          >
            <defs>
              <linearGradient id="edgeGrad1" x1="8" y1="22" x2="22" y2="8" gradientUnits="userSpaceOnUse">
                <stop stopColor="#2E69FF" />
                <stop offset="1" stopColor="#79F7C6" />
              </linearGradient>
              <linearGradient id="edgeGrad2" x1="22" y1="8" x2="36" y2="22" gradientUnits="userSpaceOnUse">
                <stop stopColor="#79F7C6" />
                <stop offset="1" stopColor="#FF0055" />
              </linearGradient>
              <linearGradient id="edgeGrad3" x1="8" y1="22" x2="22" y2="36" gradientUnits="userSpaceOnUse">
                <stop stopColor="#2E69FF" />
                <stop offset="1" stopColor="#FFCA36" />
              </linearGradient>
              <linearGradient id="edgeGrad4" x1="22" y1="36" x2="36" y2="22" gradientUnits="userSpaceOnUse">
                <stop stopColor="#FFCA36" />
                <stop offset="1" stopColor="#FF0055" />
              </linearGradient>
              <linearGradient id="coreGlow" x1="22" y1="14" x2="22" y2="30" gradientUnits="userSpaceOnUse">
                <stop stopColor="#79F7C6" stopOpacity="0.8" />
                <stop offset="1" stopColor="#2E69FF" stopOpacity="0.2" />
              </linearGradient>
              <filter id="neonBloom" x="-20%" y="-20%" width="140%" height="140%">
                <feGaussianBlur stdDeviation="2" result="blur" />
                <feComposite in="SourceGraphic" in2="blur" operator="over" />
              </filter>
            </defs>

            {/* Neural Lattice Diamond Mesh Struts */}
            <path
              d="M22 6 L38 22 L22 38 L6 22 Z"
              stroke="url(#edgeGrad1)"
              strokeWidth="2"
              strokeLinejoin="round"
              className="opacity-70 group-hover:opacity-100 transition-opacity"
            />

            {/* Inner Multi-Hop Cross Lattice ("Jaal" Web Topology) */}
            <path
              d="M6 22 L38 22"
              stroke="url(#edgeGrad2)"
              strokeWidth="1.5"
              strokeDasharray="2 2"
              className="opacity-80"
            />
            <path
              d="M22 6 L22 38"
              stroke="url(#edgeGrad3)"
              strokeWidth="1.5"
              strokeDasharray="2 2"
              className="opacity-80"
            />

            {/* Central GNN In-Memory Core Hexagon */}
            <polygon
              points="22,15 28,18.5 28,25.5 22,29 16,25.5 16,18.5"
              fill="url(#coreGlow)"
              stroke="#79F7C6"
              strokeWidth="1.5"
              className="transition-transform duration-500 origin-center group-hover:scale-110"
            />

            {/* Kinetic Vertex Nodes with Glowing Halos */}
            {/* Top Node */}
            <circle cx="22" cy="6" r="3" fill="#79F7C6" filter="url(#neonBloom)" />
            {/* Left Node */}
            <circle cx="6" cy="22" r="3" fill="#2E69FF" filter="url(#neonBloom)" />
            {/* Right Node (Interception/Shield) */}
            <circle cx="38" cy="22" r="3" fill="#FF0055" filter="url(#neonBloom)" />
            {/* Bottom Node */}
            <circle cx="22" cy="38" r="3" fill="#FFCA36" filter="url(#neonBloom)" />
            {/* Central Core Pulse */}
            <circle cx="22" cy="22" r="2" fill="#FFFFFF" />
          </svg>
        </div>
      </div>

      {/* Bespoke Wordmark with Technical Typography */}
      <div className="flex flex-col">
        <div className="flex items-center">
          {/* Custom Stylized "jaal" with glowing node over 'j' */}
          <span className="font-sans font-black text-[22px] tracking-tight leading-none text-white flex items-center">
            <span className="relative">
              j
              <span className="absolute top-[1.5px] left-[3.2px] w-1.5 h-1.5 rounded-full bg-[#79F7C6] shadow-[0_0_8px_#79F7C6] animate-pulse" />
            </span>
            <span>aal</span>
          </span>

          {/* Connected Matrix Badge "net" with glowing laser accent */}
          <span className="ml-1 font-mono2 font-extrabold text-[13px] tracking-wider uppercase px-1.5 py-0.5 rounded-md bg-gradient-to-r from-[#2E69FF]/20 to-[#79F7C6]/20 border border-[#79F7C6]/50 text-[#79F7C6] shadow-[0_0_12px_rgba(121,247,198,0.25)] group-hover:border-[#79F7C6] transition-colors">
            NET
          </span>
        </div>

        {/* Micro Subtitle with Real-time GNN Heartbeat */}
        <div className="flex items-center gap-1.5 mt-0.5 text-[8.5px] font-mono2 uppercase tracking-[0.2em] text-slate-400 font-semibold">
          <span className="w-1.5 h-1.5 rounded-full bg-[#10B981] animate-pulse shadow-[0_0_6px_#10B981]" />
          <span>GNN MATRIX · EXASOL</span>
        </div>
      </div>
    </div>
  );
}
