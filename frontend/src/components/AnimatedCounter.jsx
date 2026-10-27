import { useState, useEffect, useRef } from "react";

/**
 * AnimatedCounter: Smoothly interpolates from 0 to target value on scroll into view.
 * Supports prefixes (like "₹"), suffixes (like "+", "B", "%", "/s"), and decimal precision.
 */
export default function AnimatedCounter({
  value,
  prefix = "",
  suffix = "",
  decimals = 0,
  duration = 1600,
  className = "",
  repeatOnScroll = true,
}) {
  const [displayValue, setDisplayValue] = useState(0);
  const elementRef = useRef(null);
  const animFrameRef = useRef(null);

  useEffect(() => {
    // Parse numeric target from value string or number
    let numericTarget = 0;
    if (typeof value === "number") {
      numericTarget = value;
    } else if (typeof value === "string") {
      const cleaned = value.replace(/[^0-9.-]/g, "");
      numericTarget = parseFloat(cleaned) || 0;
    }

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          if (animFrameRef.current) cancelAnimationFrame(animFrameRef.current);

          const startTime = performance.now();
          const startVal = 0;

          const step = (currentTime) => {
            const elapsed = currentTime - startTime;
            const progress = Math.min(elapsed / duration, 1);

            // Quintic smooth ease-out: 1 - pow(1 - t, 4)
            const easeOut = 1 - Math.pow(1 - progress, 4);
            const current = startVal + (numericTarget - startVal) * easeOut;

            setDisplayValue(current);

            if (progress < 1) {
              animFrameRef.current = requestAnimationFrame(step);
            } else {
              setDisplayValue(numericTarget);
            }
          };

          animFrameRef.current = requestAnimationFrame(step);
        } else if (repeatOnScroll) {
          // Reset to 0 when scrolled away so it replays fresh on return!
          if (animFrameRef.current) cancelAnimationFrame(animFrameRef.current);
          setDisplayValue(0);
        }
      },
      { threshold: 0.15 }
    );

    if (elementRef.current) {
      observer.observe(elementRef.current);
    }

    return () => {
      observer.disconnect();
      if (animFrameRef.current) cancelAnimationFrame(animFrameRef.current);
    };
  }, [value, duration, repeatOnScroll]);

  const formatted = decimals > 0
    ? displayValue.toFixed(decimals)
    : Math.round(displayValue).toLocaleString("en-IN");

  return (
    <span ref={elementRef} className={`inline-block tabular-nums ${className}`}>
      {prefix}
      {formatted}
      {suffix}
    </span>
  );
}
