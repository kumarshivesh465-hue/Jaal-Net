import { useEffect, useRef } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { inr } from "../lib/mock.js";

const HUBS = [
  { id: "MUMBAI", lat: 18.97, lon: 72.82, risk: "high" },
  { id: "DELHI", lat: 28.61, lon: 77.2, risk: "high" },
  { id: "BLR", lat: 12.97, lon: 77.59, risk: "low" },
  { id: "HYD", lat: 17.38, lon: 78.48, risk: "medium" },
  { id: "MAA", lat: 13.08, lon: 80.27, risk: "low" },
  { id: "CCU", lat: 22.57, lon: 88.36, risk: "high" },
  { id: "PNQ", lat: 18.52, lon: 73.85, risk: "low" },
  { id: "AMD", lat: 23.02, lon: 72.57, risk: "medium" },
  { id: "JAI", lat: 26.91, lon: 75.78, risk: "medium" },
  { id: "COK", lat: 9.93, lon: 76.26, risk: "low" },
  { id: "LKO", lat: 26.84, lon: 80.94, risk: "high" },
  { id: "GAU", lat: 26.14, lon: 91.73, risk: "medium" },
];

const FLOWS = [
  { from: "MUMBAI", to: "DELHI", type: "ring", speed: 0.015, color: "#EC4899" },
  { from: "DELHI", to: "LKO", type: "ring", speed: 0.018, color: "#EC4899" },
  { from: "LKO", to: "CCU", type: "ring", speed: 0.016, color: "#EC4899" },
  { from: "CCU", to: "MUMBAI", type: "circular", speed: 0.02, color: "#06B6D4" },
  { from: "BLR", to: "HYD", type: "normal", speed: 0.01, color: "#10B981" },
  { from: "PNQ", to: "BLR", type: "normal", speed: 0.012, color: "#10B981" },
  { from: "AMD", to: "MUMBAI", type: "layering", speed: 0.017, color: "#A855F7" },
  { from: "JAI", to: "DELHI", type: "layering", speed: 0.014, color: "#A855F7" },
  { from: "HYD", to: "MAA", type: "normal", speed: 0.009, color: "#10B981" },
  { from: "MAA", to: "COK", type: "normal", speed: 0.008, color: "#10B981" },
];

// Hub layout is illustrative (same 12 UPI corridors as three_viz.py).
// Live stats are props: ringCount from data.RINGS, shielded from the stream.
export default function Globe3D({ height = 500, ringCount = 3, shielded = 0, backendUp = false }) {
  const mountRef = useRef(null);
  const statsRef = useRef(null);

  useEffect(() => {
    const mount = mountRef.current;
    const width = mount.clientWidth || 800;

    const scene = new THREE.Scene();
    scene.fog = new THREE.FogExp2(0x000b29, 0.0025);
    const camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 1000);
    camera.position.set(0, 35, 175);

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setSize(width, height);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    mount.appendChild(renderer.domElement);
    renderer.domElement.style.cssText = "width:100%;height:100%;display:block;cursor:grab;";

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.05;
    controls.minDistance = 90;
    controls.maxDistance = 280;
    controls.autoRotate = true;
    controls.autoRotateSpeed = 1.2;

    const globeGroup = new THREE.Group();
    scene.add(globeGroup);
    const R = 50;

    const sphereMat = new THREE.MeshBasicMaterial({ color: 0x00124d, transparent: true, opacity: 0.9 });
    globeGroup.add(new THREE.Mesh(new THREE.SphereGeometry(R, 48, 48), sphereMat));

    const wireMat = new THREE.MeshBasicMaterial({ color: 0x223554, wireframe: true, transparent: true, opacity: 0.35 });
    globeGroup.add(new THREE.Mesh(new THREE.SphereGeometry(R + 0.1, 28, 28), wireMat));

    const halo = new THREE.Mesh(
      new THREE.SphereGeometry(R * 1.15, 32, 32),
      new THREE.ShaderMaterial({
        vertexShader:
          "varying vec3 vNormal; void main(){ vNormal = normalize(normalMatrix * normal); gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }",
        fragmentShader:
          "varying vec3 vNormal; void main(){ float i = pow(0.65 - dot(vNormal, vec3(0,0,1.0)), 2.0); gl_FragColor = vec4(0.55,0.36,0.96,0.35) * i; }",
        blending: THREE.AdditiveBlending,
        side: THREE.BackSide,
        transparent: true,
      })
    );
    globeGroup.add(halo);

    const holoRing = (rad, color, tx, ty) => {
      const m = new THREE.Mesh(
        new THREE.RingGeometry(rad - 0.4, rad + 0.4, 64),
        new THREE.MeshBasicMaterial({ color, side: THREE.DoubleSide, transparent: true, opacity: 0.4, blending: THREE.AdditiveBlending })
      );
      m.rotation.x = tx;
      m.rotation.y = ty;
      return m;
    };
    const ring1 = holoRing(R * 1.35, 0x8b5cf6, Math.PI / 2.3, 0.2);
    const ring2 = holoRing(R * 1.48, 0x06b6d4, Math.PI / 3.1, -0.4);
    scene.add(ring1, ring2);

    // starfield
    const starCount = 1200;
    const pos = new Float32Array(starCount * 3);
    for (let i = 0; i < starCount; i++) {
      pos[i * 3] = (Math.random() - 0.5) * 500;
      pos[i * 3 + 1] = (Math.random() - 0.5) * 500;
      pos[i * 3 + 2] = (Math.random() - 0.5) * 500;
    }
    const starGeo = new THREE.BufferGeometry();
    starGeo.setAttribute("position", new THREE.BufferAttribute(pos, 3));
    const starField = new THREE.Points(
      starGeo,
      new THREE.PointsMaterial({ size: 1.6, color: 0xaabbff, transparent: true, opacity: 0.65, blending: THREE.AdditiveBlending })
    );
    scene.add(starField);

    const latLon = (lat, lon, r) => {
      const phi = ((90 - lat) * Math.PI) / 180;
      const theta = ((lon + 180) * Math.PI) / 180;
      return new THREE.Vector3(
        -(r * Math.sin(phi) * Math.cos(theta)),
        r * Math.cos(phi),
        r * Math.sin(phi) * Math.sin(theta)
      );
    };

    const vectors = {};
    const waves = [];
    HUBS.forEach((h, idx) => {
      const p = latLon(h.lat, h.lon, R);
      vectors[h.id] = p;
      const colorHex = h.risk === "high" ? 0xec4899 : h.risk === "medium" ? 0xf59e0b : 0x10b981;
      const node = new THREE.Mesh(
        new THREE.SphereGeometry(1.4, 16, 16),
        new THREE.MeshBasicMaterial({ color: colorHex, blending: THREE.AdditiveBlending })
      );
      node.position.copy(p);
      globeGroup.add(node);

      const wave = new THREE.Mesh(
        new THREE.RingGeometry(1.5, 2.2, 16),
        new THREE.MeshBasicMaterial({ color: colorHex, side: THREE.DoubleSide, transparent: true, opacity: 0.8, blending: THREE.AdditiveBlending })
      );
      wave.position.copy(p);
      wave.lookAt(0, 0, 0);
      globeGroup.add(wave);
      waves.push(wave);
    });

    const beams = [];
    FLOWS.forEach((f) => {
      const p1 = vectors[f.from];
      const p2 = vectors[f.to];
      if (!p1 || !p2) return;
      const mid = new THREE.Vector3().addVectors(p1, p2).multiplyScalar(0.5);
      mid.normalize().multiplyScalar(R + p1.distanceTo(p2) * 0.45);
      const curve = new THREE.QuadraticBezierCurve3(p1, mid, p2);
      const line = new THREE.Line(
        new THREE.BufferGeometry().setFromPoints(curve.getPoints(36)),
        new THREE.LineBasicMaterial({ color: new THREE.Color(f.color), transparent: true, opacity: f.type === "ring" ? 0.85 : 0.45, blending: THREE.AdditiveBlending })
      );
      globeGroup.add(line);

      const pulse = new THREE.Mesh(
        new THREE.SphereGeometry(1.2, 12, 12),
        new THREE.MeshBasicMaterial({ color: 0xffffff, blending: THREE.AdditiveBlending })
      );
      globeGroup.add(pulse);
      beams.push({ curve, pulse, t: Math.random(), speed: f.speed });
    });

    globeGroup.rotation.y = 4.2;
    globeGroup.rotation.x = 0.35;

    let raf;
    const clock = new THREE.Clock();
    let scan = 0;
    const onScan = () => {
      scan = 0.0001;
    };
    window.addEventListener("jaalnet:scan", onScan);
    const onSpin = () => {
      controls.autoRotate = !controls.autoRotate;
    };
    window.addEventListener("jaalnet:spin", onSpin);
    const onFocus = () => {
      globeGroup.rotation.y = 4.2;
      globeGroup.rotation.x = 0.35;
      camera.position.set(0, 30, 160);
    };
    window.addEventListener("jaalnet:focus", onFocus);

    const animate = () => {
      raf = requestAnimationFrame(animate);
      const dt = clock.getDelta();
      const t = clock.getElapsedTime();
      waves.forEach((w, i) => {
        const s = 1 + 0.4 * Math.sin(t * 3 + i);
        w.scale.set(s, s, 1);
        w.material.opacity = 0.9 - (s - 1) * 1.5;
      });
      beams.forEach((b) => {
        b.t = (b.t + b.speed) % 1;
        b.pulse.position.copy(b.curve.getPoint(b.t));
        const s = 1 + 0.5 * Math.sin(b.t * Math.PI);
        b.pulse.scale.set(s, s, s);
      });
      ring1.rotation.z += 0.003;
      ring2.rotation.z -= 0.0025;
      starField.rotation.y += 0.0004;
      if (scan > 0) {
        scan += dt * 1.8;
        sphereMat.color.setHex(scan % 0.4 < 0.2 ? 0x1e1b4b : 0x0c1322);
        if (scan > 2) {
          scan = 0;
          sphereMat.color.setHex(0x0c1322);
        }
      }
      controls.update();
      renderer.render(scene, camera);
    };
    animate();

    const onResize = () => {
      const w = mount.clientWidth || width;
      camera.aspect = w / height;
      camera.updateProjectionMatrix();
      renderer.setSize(w, height);
    };
    window.addEventListener("resize", onResize);

    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("resize", onResize);
      window.removeEventListener("jaalnet:scan", onScan);
      window.removeEventListener("jaalnet:spin", onSpin);
      window.removeEventListener("jaalnet:focus", onFocus);
      controls.dispose();
      renderer.dispose();
      mount.removeChild(renderer.domElement);
      scene.traverse((o) => o.geometry?.dispose?.());
    };
  }, [height]);

  const triggerScan = () => window.dispatchEvent(new Event("jaalnet:scan"));
  const focusIndia = () => window.dispatchEvent(new Event("jaalnet:focus"));

  return (
    <div
      style={{ height }}
      className="relative rounded-2xl overflow-hidden border border-white/10"
    >
      <div ref={mountRef} style={{ background: "radial-gradient(circle at 50% 50%, rgba(17,24,39,.7) 0%, rgba(10,14,23,.95) 100%)" }} className="absolute inset-0" />

      {/* HUD top-left */}
      <div className="glass absolute top-3.5 left-3.5 !rounded-xl px-4 py-2.5 text-[11px] pointer-events-none" style={{ background: "rgba(15,23,42,.65)" }}>
        <div className="font-display font-bold text-[13px] tracking-widest bg-gradient-to-r from-white via-purple-300 to-sky-400 bg-clip-text text-transparent">
          🛡️ 3D UPI NEURAL DEFENSE MATRIX
        </div>
        <div className="flex items-center gap-2 mt-1">
          <span className="text-[10px] font-semibold text-sky-300 bg-sky-400/10 border border-sky-400/30 rounded-full px-2 py-0.5 flex items-center gap-1.5">
            <span className="live-dot" style={{ background: backendUp ? "#10B981" : "#F59E0B", boxShadow: `0 0 8px ${backendUp ? "#10B981" : "#F59E0B"}` }} />
            {backendUp ? "GNN TGAT+SAGE LIVE" : "SYNTHETIC FALLBACK"}
          </span>
          <span className="text-[10px] text-slate-400">FASTAPI INTERCEPT ACTIVE</span>
        </div>
      </div>

      {/* HUD controls */}
      <div className="absolute top-3.5 right-3.5 flex gap-2">
        <button className="glass !rounded-lg px-3 py-1.5 text-[11px] font-semibold hover:!bg-purple-500/30 hover:border-purple-400/60 transition-all" onClick={() => window.dispatchEvent(new Event("jaalnet:spin"))}>
          🌀 Auto-Rotate
        </button>
        <button className="glass !rounded-lg px-3 py-1.5 text-[11px] font-semibold hover:!bg-purple-500/30 hover:border-purple-400/60 transition-all" onClick={focusIndia}>
          🇮🇳 Focus India
        </button>
        <button className="glass !rounded-lg px-3 py-1.5 text-[11px] font-semibold hover:!bg-purple-500/30 hover:border-purple-400/60 transition-all" onClick={triggerScan}>
          ⚡ Radar Scan
        </button>
      </div>

      {/* HUD bottom stats */}
      <div ref={statsRef} className="glass absolute bottom-3.5 left-3.5 right-3.5 !rounded-xl px-4 py-2.5 flex flex-wrap items-center justify-between gap-3 text-[11px]" style={{ background: "rgba(15,23,42,.65)" }}>
        <div className="flex items-center">
          <div className="px-2 border-r border-white/10">
            <span className="block font-mono2 text-[13px] font-bold text-white">{HUBS.length} HUBS</span>
            <span className="block text-[9px] uppercase tracking-wider text-slate-400">Active Vertices</span>
          </div>
          <div className="px-2 border-r border-white/10">
            <span className="block font-mono2 text-[13px] font-bold text-pink-400">{ringCount} RINGS</span>
            <span className="block text-[9px] uppercase tracking-wider text-slate-400">Detected Syndicates</span>
          </div>
          <div className="px-2 border-r border-white/10">
            <span className="block font-mono2 text-[13px] font-bold text-emerald-400">{inr(shielded)}</span>
            <span className="block text-[9px] uppercase tracking-wider text-slate-400">Shielded Volume</span>
          </div>
          <div className="px-2">
            <span className="block font-mono2 text-[13px] font-bold text-sky-300">1-2 ms</span>
            <span className="block text-[9px] uppercase tracking-wider text-slate-400">Inference (server)</span>
          </div>
        </div>
        <div className="hidden md:flex items-center gap-4">
          {[
            ["#10B981", "Benign P2P"],
            ["#A855F7", "Layering Hop"],
            ["#EC4899", "Mule Ring Flow"],
            ["#06B6D4", "Circular Loop"],
          ].map(([c, l]) => (
            <span key={l} className="flex items-center gap-1.5 text-[10px]">
              <span style={{ background: c, boxShadow: `0 0 6px ${c}` }} className="w-2 h-2 rounded-full" />
              {l}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}
