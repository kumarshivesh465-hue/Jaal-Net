import { useState, useEffect } from "react";
import { Play, Pause, RotateCcw, FastForward, Clock, Zap, TrendingUp } from "lucide-react";

export default function TemporalScrubber({
  durationSec = 180,
  currentTime,
  onTimeChange,
  totalLaundered = 240000,
}) {
  const [isPlaying, setIsPlaying] = useState(false);
  const [speed, setSpeed] = useState(1); // 1x, 2x, 4x

  // Auto-advance loop when playing
  useEffect(() => {
    let interval = null;
    if (isPlaying) {
      interval = setInterval(() => {
        onTimeChange((prev) => {
          if (prev >= durationSec) {
            setIsPlaying(false);
            return durationSec;
          }
          return Math.min(durationSec, prev + 1 * speed);
        });
      }, 100);
    }
    return () => clearInterval(interval);
  }, [isPlaying, speed, durationSec, onTimeChange]);

  const progressPct = (currentTime / durationSec) * 100;

  // Determine active dynamic phase and instantaneous velocity (dV/dt)
  let phaseText = "Phase 0: Dormant Account State";
  let velocityRate = 0;
  let phaseColor = "#10B981";

  if (currentTime > 0 && currentTime <= 35) {
    phaseText = "Phase 1: Victim Inflow & L1 Account Compromise";
    velocityRate = Math.round((totalLaundered * 0.4) / 35);
    phaseColor = "#F59E0B";
  } else if (currentTime > 35 && currentTime <= 110) {
    phaseText = "Phase 2: Layer-2 Cyclic Smurfing & Multi-Hop Fan-Out";
    velocityRate = Math.round((totalLaundered * 0.5) / 45);
    phaseColor = "#FF0055";
  } else if (currentTime > 110) {
    phaseText = "Phase 3: Collusive QR Soundbox Merchant Cashout";
    velocityRate = Math.round((totalLaundered * 0.1) / 30);
    phaseColor = "#EF4444";
  }

  const formatSec = (s) => {
    const mins = Math.floor(s / 60);
    const secs = Math.floor(s % 60);
    return `T+${String(mins).padStart(2, "0")}:${String(secs).padStart(2, "0")}`;
  };

  return (
    <div className="bg-[#000B29] border border-white/10 rounded-2xl p-4 shadow-xl space-y-3 font-mono2">
      {/* Top Header: Timeline Meta & Real-Time Velocity Indicator */}
      <div className="flex flex-wrap items-center justify-between gap-3 text-xs border-b border-white/5 pb-2.5">
        <div className="flex items-center gap-2">
          <span className="w-2.5 h-2.5 rounded-full animate-ping" style={{ background: phaseColor }} />
          <span className="font-bold text-white flex items-center gap-1.5">
            <Clock size={13} className="text-[#2E69FF]" />
            4D Temporal Graph Time-Machine
          </span>
          <span className="px-2 py-0.5 rounded-full bg-white/10 text-slate-300 text-[10px]">
            {formatSec(currentTime)} / {formatSec(durationSec)}
          </span>
        </div>

        {/* Real-time money velocity readout (dV/dt) */}
        <div className="flex items-center gap-3">
          <div className="text-right">
            <span className="text-[10px] text-slate-400 uppercase tracking-wider block">
              INSTANTANEOUS VELOCITY (dV/dt)
            </span>
            <span className="font-bold text-sm" style={{ color: phaseColor }}>
              ₹{velocityRate.toLocaleString("en-IN")}/sec
            </span>
          </div>
        </div>
      </div>

      {/* Main Timeline Slider Bar */}
      <div className="space-y-1.5">
        <div className="flex items-center justify-between text-[10px] text-slate-400">
          <span style={{ color: phaseColor }} className="font-bold">
            ● {phaseText}
          </span>
          <span>{Math.round(progressPct)}% Cycle Elapsed</span>
        </div>

        <div className="relative flex items-center">
          <input
            type="range"
            min={0}
            max={durationSec}
            step={1}
            value={currentTime}
            onChange={(e) => onTimeChange(Number(e.target.value))}
            className="w-full h-2 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-[#2E69FF]"
          />
        </div>
      </div>

      {/* Controls Bar: Play, Pause, Speeds, Reset */}
      <div className="flex items-center justify-between pt-1">
        <div className="flex items-center gap-2">
          <button
            onClick={() => setIsPlaying(!isPlaying)}
            className="w-8 h-8 rounded-full bg-[#2E69FF] hover:bg-blue-600 text-white grid place-items-center transition-colors shadow-md cursor-pointer"
            title={isPlaying ? "Pause Simulation" : "Replay Laundering Cycle"}
          >
            {isPlaying ? <Pause size={14} /> : <Play size={14} className="ml-0.5" />}
          </button>

          <button
            onClick={() => {
              setIsPlaying(false);
              onTimeChange(0);
            }}
            className="w-8 h-8 rounded-full bg-white/5 hover:bg-white/10 text-slate-400 hover:text-white grid place-items-center transition-colors cursor-pointer"
            title="Reset to T+00:00"
          >
            <RotateCcw size={13} />
          </button>

          {/* Speed Multiplier */}
          <div className="flex items-center rounded-lg bg-white/5 p-0.5 border border-white/5 text-[10px]">
            {[1, 2, 4].map((s) => (
              <button
                key={s}
                onClick={() => setSpeed(s)}
                className={`px-2 py-0.5 rounded cursor-pointer transition-colors ${
                  speed === s ? "bg-[#2E69FF] text-white font-bold" : "text-slate-400 hover:text-white"
                }`}
              >
                {s}x
              </button>
            ))}
          </div>
        </div>

        <div className="text-[10px] text-slate-400">
          Drag slider or press Play to watch multi-hop layering fan out in real time
        </div>
      </div>
    </div>
  );
}
