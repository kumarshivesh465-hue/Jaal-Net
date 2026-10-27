import { useEffect, useRef, useState } from "react";
import { bandOf } from "../lib/mock.js";

export function CountUp({ value, format = (v) => v.toFixed(0), className = "" }) {
  const [display, setDisplay] = useState(value);
  const from = useRef(value);
  useEffect(() => {
    const start = performance.now();
    const dur = 700;
    const a = from.current;
    const b = value;
    const step = (now) => {
      const p = Math.min(1, (now - start) / dur);
      setDisplay(a + (b - a) * (1 - Math.pow(1 - p, 3)));
      if (p < 1) requestAnimationFrame(step);
      else from.current = b;
    };
    requestAnimationFrame(step);
    return () => {};
  }, [value]);
  return <span className={className}>{format(display)}</span>;
}

export function KpiCard({ label, value, delta, neg = false, className = "" }) {
  return (
    <div className={`glass kpi ${className}`}>
      <div className="kpi-label">{label}</div>
      <div className="kpi-value">{value}</div>
      <div className={`kpi-delta ${neg ? "neg" : ""}`}>{delta}</div>
    </div>
  );
}

export function ScoreBadge({ score }) {
  return <span className={`badge badge-${bandOf(score)}`}>{String(score).padStart(2, "0")}</span>;
}

export function SectionHeader({ children, extra }) {
  return (
    <div className="flex items-center justify-between">
      <div className="section-header">{children}</div>
      {extra}
    </div>
  );
}
