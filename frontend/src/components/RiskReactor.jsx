import { useEffect, useRef } from "react";
import * as THREE from "three";
import { THRESHOLDS } from "../lib/mock.js";

// React port of three_viz.three_risk_gauge_html. Bands follow the same
// config thresholds as everything else; React owns the text readout, three
// owns the spinning rings, so score changes repaint live.

const BAND = (score) => {
  if (score < THRESHOLDS.monitor) return { css: "#10B981", label: "SAFE MERCHANT" };
  if (score < THRESHOLDS.stepup) return { css: "#F59E0B", label: "WATCHLIST MONITOR" };
  if (score < THRESHOLDS.block) return { css: "#F97316", label: "STEP-UP AUTH REQ" };
  return { css: "#EF4444", label: "CRITICAL MULE BLOCK" };
};

export default function RiskReactor({ score, action, height = 220 }) {
  const mountRef = useRef(null);
  const ringsRef = useRef([]);

  useEffect(() => {
    const mount = mountRef.current;
    const w = mount.clientWidth || 380;

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(45, w / height, 0.1, 1000);
    camera.position.z = 85;

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setSize(w, height);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    mount.appendChild(renderer.domElement);

    const ring = (rIn, rOut, tx, ty, col, opacity) => {
      const m = new THREE.Mesh(
        new THREE.RingGeometry(rIn, rOut, 48),
        new THREE.MeshBasicMaterial({ color: col, side: THREE.DoubleSide, transparent: true, opacity, blending: THREE.AdditiveBlending })
      );
      m.rotation.x = tx;
      m.rotation.y = ty;
      scene.add(m);
      return m;
    };
    const r1 = ring(28, 29.5, 0.3, 0.2, 0x8b5cf6, 0.6);
    const r2 = ring(32, 33, -0.4, 0.5, 0x8b5cf6, 0.4);
    const r3 = ring(35, 35.8, 0.6, -0.3, 0x8b5cf6, 0.3);
    ringsRef.current = [r1, r2, r3];

    // sparkle particles
    const N = 70;
    const pos = new Float32Array(N * 3);
    for (let i = 0; i < N; i++) {
      const theta = Math.random() * Math.PI * 2;
      const rad = 24 + Math.random() * 16;
      pos[i * 3] = Math.cos(theta) * rad;
      pos[i * 3 + 1] = Math.sin(theta) * rad;
      pos[i * 3 + 2] = (Math.random() - 0.5) * 20;
    }
    const pGeo = new THREE.BufferGeometry();
    pGeo.setAttribute("position", new THREE.BufferAttribute(pos, 3));
    const particles = new THREE.Points(
      pGeo,
      new THREE.PointsMaterial({ size: 2.0, color: 0x8b5cf6, transparent: true, opacity: 0.8, blending: THREE.AdditiveBlending })
    );
    scene.add(particles);

    let raf;
    let angle = 0;
    const animate = () => {
      raf = requestAnimationFrame(animate);
      angle += 0.02;
      const [a, b, c] = ringsRef.current;
      a.rotation.z += 0.015;
      b.rotation.z -= 0.02;
      c.rotation.z += 0.01;
      a.rotation.x = 0.3 + 0.1 * Math.sin(angle);
      b.rotation.y = 0.4 + 0.15 * Math.cos(angle * 0.8);
      particles.rotation.z += 0.005;
      renderer.render(scene, camera);
    };
    animate();

    const onResize = () => {
      const nw = mount.clientWidth || w;
      camera.aspect = nw / height;
      camera.updateProjectionMatrix();
      renderer.setSize(nw, height);
    };
    window.addEventListener("resize", onResize);

    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("resize", onResize);
      renderer.dispose();
      mount.removeChild(renderer.domElement);
      scene.traverse((o) => o.geometry?.dispose?.());
    };
  }, [height]);

  const band = BAND(score);

  // tint the reactor by band without rebuilding the scene
  useEffect(() => {
    const col = new THREE.Color(band.css);
    if (ringsRef.current[0]) {
      ringsRef.current[0].material.color.copy(col);
      ringsRef.current[1].material.color.copy(new THREE.Color("#8B5CF6"));
      ringsRef.current[2].material.color.copy(col);
    }
  }, [band.css]);

  return (
    <div className="relative" style={{ height }}>
      <div ref={mountRef} className="absolute inset-0" />
      <div className="absolute inset-0 pointer-events-none flex flex-col items-center justify-center text-center">
        <div style={{ color: band.css, textShadow: `0 0 24px ${band.css}, 0 0 45px rgba(255,255,255,.4)` }} className="font-display text-5xl font-extrabold leading-none tracking-tight">
          {String(score).padStart(2, "0")}
        </div>
        <div className="text-sm text-slate-400 font-semibold mt-0.5">/ 100</div>
        <div className="mt-1.5 text-[11px] font-bold tracking-[0.12em] uppercase text-slate-200 bg-slate-900/70 border border-white/15 rounded-full px-3 py-1">
          {action} · {band.label}
        </div>
      </div>
    </div>
  );
}
