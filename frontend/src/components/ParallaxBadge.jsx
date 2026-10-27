import { useState, useEffect, useRef } from "react";

/**
 * ParallaxBadge: A floating badge that glides along the Y-axis at a differential
 * scroll speed (optical parallax depth) and maintains continuous organic levitation.
 */
export default function ParallaxBadge({
  children,
  className = "",
  speed = -0.07, // Parallax multiplier (-0.05 to -0.15 gives subtle optical depth)
  floatAnim = "sift-floating-badge",
}) {
  const badgeRef = useRef(null);
  const [offsetY, setOffsetY] = useState(0);

  useEffect(() => {
    let ticking = false;

    const handleScroll = () => {
      if (!ticking) {
        requestAnimationFrame(() => {
          if (badgeRef.current) {
            const rect = badgeRef.current.getBoundingClientRect();
            const viewportCenter = window.innerHeight / 2;
            const elementCenter = rect.top + rect.height / 2;
            const distance = elementCenter - viewportCenter;
            setOffsetY(distance * speed);
          }
          ticking = false;
        });
        ticking = true;
      }
    };

    window.addEventListener("scroll", handleScroll, { passive: true });
    handleScroll();

    return () => window.removeEventListener("scroll", handleScroll);
  }, [speed]);

  return (
    <div
      ref={badgeRef}
      className={`will-change-transform ${floatAnim} ${className}`}
      style={{
        transform: `translate3d(0, ${offsetY.toFixed(1)}px, 0)`,
        transition: "transform 0.1s cubic-bezier(0.16, 1, 0.3, 1)",
      }}
    >
      {children}
    </div>
  );
}
