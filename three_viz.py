"""
Three.js 3D WebGL Visualizations for UPI Mule Fraud Detection Dashboard.
Provides holographic 3D network globe, nodal matrix, and 3D risk core gauges.

Contract (CONTRACTS.md, three_viz section):
- three_globe_html: self-contained HTML that loads Three.js + OrbitControls
  from CDN; HUD ring count and shielded volume come from rings_data and
  stream_txns, not made-up constants.
- three_risk_gauge_html: score bands follow config.THRESHOLD_* exactly;
  raises ValueError outside [0, 100].
"""

import json
from typing import Any, Dict, List, Optional

import config


def _fmt_amount(v: float) -> str:
    """Indian-convention rupee label: Cr (crore, 1e7) and L (lakh, 1e5).

    Below one lakh it shows whole thousands; zero shows ₹0 exactly.
    """
    if v <= 0:
        return "₹0"
    if v >= 1e7:
        return f"₹{v / 1e7:.1f}Cr"
    if v >= 1e5:
        return f"₹{v / 1e5:.1f}L"
    return f"₹{v / 1e3:.0f}K"


def _shielded_volume(stream_txns: Optional[List[Dict[str, Any]]]) -> float:
    """Sum amount of BLOCK/STEP_UP rows from the session stream.

    Accepts dict rows or attribute-bearing objects (app.py passes dict
    projections of data.Transaction). Unknown shapes contribute nothing.
    """
    if not stream_txns:
        return 0.0
    total = 0.0
    for t in stream_txns:
        if isinstance(t, dict):
            action = t.get("action")
            amount = t.get("amount")
        else:
            action = getattr(t, "action", None)
            amount = getattr(t, "amount", None)
        if action in ("BLOCK", "STEP_UP") and amount is not None:
            try:
                total += float(amount)
            except (TypeError, ValueError):
                continue
    return total


def three_globe_html(
    height: int = 540,
    active_ring: Optional[str] = "RING-001",
    rings_data: Optional[Dict[str, List[str]]] = None,
    stream_txns: Optional[List[Dict[str, Any]]] = None,
) -> str:
    """
    Renders an interactive 3D WebGL Cyber Globe and UPI Mule Defense Matrix
    using Three.js. Supports orbit rotation, interactive nodal pulsing,
    animated 3D bezier transaction arcs, and holographic HUD controls.

    rings_data drives the "Detected Syndicates" HUD count (None -> the
    illustrative default of 3).    stream_txns drives the "Shielded Volume"
    HUD stat, summed over BLOCK/STEP_UP rows; there is no hard-coded ₹9.8M.
    """
    if not isinstance(height, int) or isinstance(height, bool) or not (200 <= height <= 1200):
        raise ValueError(f"height must be an int in [200, 1200], got {height!r}")
    # Sample nodes representing major Indian UPI financial hubs
    hubs = [
        {"id": "MUMBAI", "name": "Mumbai Core", "lat": 18.97, "lon": 72.82, "risk": "high"},
        {"id": "DELHI", "name": "Delhi NCR", "lat": 28.61, "lon": 77.20, "risk": "high"},
        {"id": "BLR", "name": "Bengaluru Tech", "lat": 12.97, "lon": 77.59, "risk": "low"},
        {"id": "HYD", "name": "Hyderabad Cyber", "lat": 17.38, "lon": 78.48, "risk": "medium"},
        {"id": "MAA", "name": "Chennai Port", "lat": 13.08, "lon": 80.27, "risk": "low"},
        {"id": "CCU", "name": "Kolkata Hub", "lat": 22.57, "lon": 88.36, "risk": "high"},
        {"id": "PNQ", "name": "Pune Fintech", "lat": 18.52, "lon": 73.85, "risk": "low"},
        {"id": "AMD", "name": "Ahmedabad Ex", "lat": 23.02, "lon": 72.57, "risk": "medium"},
        {"id": "JAI", "name": "Jaipur Node", "lat": 26.91, "lon": 75.78, "risk": "medium"},
        {"id": "COK", "name": "Kochi Gateway", "lat": 9.93, "lon": 76.26, "risk": "low"},
        {"id": "LKO", "name": "Lucknow Metro", "lat": 26.84, "lon": 80.94, "risk": "high"},
        {"id": "GAU", "name": "Guwahati North", "lat": 26.14, "lon": 91.73, "risk": "medium"},
    ]

    # Sample dynamic arcs representing money flow between hubs
    flows = [
        {"from": "MUMBAI", "to": "DELHI", "amt": 245000, "type": "ring", "speed": 0.015, "color": "#EC4899"},
        {"from": "DELHI", "to": "LKO", "amt": 180000, "type": "ring", "speed": 0.018, "color": "#EC4899"},
        {"from": "LKO", "to": "CCU", "amt": 140000, "type": "ring", "speed": 0.016, "color": "#EC4899"},
        {"from": "CCU", "to": "MUMBAI", "amt": 220000, "type": "circular", "speed": 0.02, "color": "#06B6D4"},
        {"from": "BLR", "to": "HYD", "amt": 45000, "type": "normal", "speed": 0.01, "color": "#10B981"},
        {"from": "PNQ", "to": "BLR", "amt": 32000, "type": "normal", "speed": 0.012, "color": "#10B981"},
        {"from": "AMD", "to": "MUMBAI", "amt": 95000, "type": "layering", "speed": 0.017, "color": "#A855F7"},
        {"from": "JAI", "to": "DELHI", "amt": 75000, "type": "layering", "speed": 0.014, "color": "#A855F7"},
        {"from": "HYD", "to": "MAA", "amt": 28000, "type": "normal", "speed": 0.009, "color": "#10B981"},
        {"from": "MAA", "to": "COK", "amt": 15000, "type": "normal", "speed": 0.008, "color": "#10B981"},
    ]

    # Live HUD stats: ring count from RINGS, shielded volume from the stream.
    ring_count = len(rings_data) if rings_data else 3
    shielded_label = _fmt_amount(_shielded_volume(stream_txns))
    hubs_label = f"{len(hubs)} HUBS"
    # Server-side inference latency is the measured 1-2 ms (see README
    # Performance); the claims panel must not invent a decimal.

    hubs_json = json.dumps(hubs)
    flows_json = json.dumps(flows)

    html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; user-select: none; }}
  html, body {{
    width: 100%; height: {height}px;
    background: transparent;
    overflow: hidden;
    font-family: 'Space Grotesk', 'Inter', -apple-system, sans-serif;
    color: #F9FAFB;
  }}
  #canvas-container {{
    position: relative;
    width: 100%; height: {height}px;
    border-radius: 16px;
    background: radial-gradient(circle at 50% 50%, rgba(17, 24, 39, 0.7) 0%, rgba(10, 14, 23, 0.95) 100%);
    border: 1px solid rgba(255, 255, 255, 0.1);
    box-shadow: 0 20px 50px rgba(0, 0, 0, 0.6), inset 0 1px 1px rgba(255, 255, 255, 0.2);
    overflow: hidden;
  }}
  #three-canvas {{
    width: 100%; height: 100%;
    display: block;
    cursor: grab;
  }}
  #three-canvas:active {{
    cursor: grabbing;
  }}

  /* Liquid Glass HUD Overlay */
  .hud-panel {{
    position: absolute;
    pointer-events: auto;
    background: rgba(15, 23, 42, 0.65);
    backdrop-filter: blur(20px) saturate(190%);
    -webkit-backdrop-filter: blur(20px) saturate(190%);
    border: 1px solid rgba(255, 255, 255, 0.12);
    box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.4), inset 0 1px 0 rgba(255, 255, 255, 0.18);
    border-radius: 12px;
    padding: 10px 14px;
    color: #E2E8F0;
    font-size: 11px;
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  }}
  .hud-top-left {{
    top: 14px; left: 14px;
    display: flex; flex-direction: column; gap: 4px;
  }}
  .hud-top-right {{
    top: 14px; right: 14px;
    display: flex; gap: 8px;
  }}
  .hud-bottom {{
    bottom: 14px; left: 14px; right: 14px;
    display: flex; justify-content: space-between; align-items: center;
  }}
  .hud-title {{
    font-size: 13px; font-weight: 700;
    letter-spacing: 0.08em;
    background: linear-gradient(135deg, #FFF 0%, #A78BFA 50%, #38BDF8 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    display: flex; align-items: center; gap: 6px;
  }}
  .hud-tag {{
    display: inline-flex; align-items: center; gap: 5px;
    font-size: 10px; font-weight: 600;
    color: #38BDF8;
    background: rgba(56, 189, 248, 0.12);
    border: 1px solid rgba(56, 189, 248, 0.3);
    padding: 2px 8px; border-radius: 999px;
    letter-spacing: 0.05em;
  }}
  .hud-pulse {{
    width: 6px; height: 6px; border-radius: 50%;
    background: #10B981;
    box-shadow: 0 0 8px #10B981;
    animation: pulseDot 1.6s infinite ease-in-out;
  }}
  @keyframes pulseDot {{
    0%, 100% {{ transform: scale(1); opacity: 1; }}
    50% {{ transform: scale(1.4); opacity: 0.4; }}
  }}
  .hud-btn {{
    background: rgba(30, 41, 59, 0.7);
    border: 1px solid rgba(255, 255, 255, 0.15);
    color: #CBD5E1;
    padding: 5px 10px;
    border-radius: 8px;
    cursor: pointer;
    font-size: 11px; font-weight: 600;
    display: flex; align-items: center; gap: 5px;
    transition: all 0.2s ease;
  }}
  .hud-btn:hover {{
    background: rgba(139, 92, 246, 0.3);
    border-color: #8B5CF6;
    color: #FFF;
    transform: translateY(-1px);
    box-shadow: 0 0 15px rgba(139, 92, 246, 0.4);
  }}
  .hud-btn.active {{
    background: linear-gradient(135deg, rgba(139, 92, 246, 0.4), rgba(6, 182, 212, 0.3));
    border-color: #A78BFA;
    color: #FFF;
  }}
  .hud-stat {{
    display: flex; flex-direction: column;
    padding: 0 8px;
    border-right: 1px solid rgba(255, 255, 255, 0.1);
  }}
  .hud-stat:last-child {{ border-right: none; }}
  .hud-stat-num {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 13px; font-weight: 700; color: #FFF;
  }}
  .hud-stat-lbl {{
    font-size: 9px; text-transform: uppercase; color: #94A3B8; letter-spacing: 0.05em;
  }}
  .legend-item {{
    display: inline-flex; align-items: center; gap: 6px;
    font-size: 10px; margin-right: 12px;
  }}
  .legend-dot {{
    width: 8px; height: 8px; border-radius: 50%;
  }}
</style>
<script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/controls/OrbitControls.js"></script>
</head>
<body>
<div id="canvas-container">
  <div id="three-canvas"></div>

  <!-- HUD Top Left -->
  <div class="hud-panel hud-top-left">
    <div class="hud-title">
      <span>🛡️ 3D UPI NEURAL DEFENSE MATRIX</span>
    </div>
    <div style="display:flex; align-items:center; gap:8px; margin-top:2px;">
      <span class="hud-tag"><span class="hud-pulse"></span> GNN TGAT+SAGE LIVE</span>
      <span style="color:#94A3B8; font-size:10px;">EXASOL INTERCEPT ACTIVE</span>
    </div>
  </div>

  <!-- HUD Top Right Controls -->
  <div class="hud-panel hud-top-right">
    <button class="hud-btn active" id="btn-spin" onclick="toggleSpin()">🌀 Auto-Rotate</button>
    <button class="hud-btn" id="btn-focus" onclick="focusIndia()">🇮🇳 Focus India</button>
    <button class="hud-btn" id="btn-pulse" onclick="triggerScan()">⚡ Radar Scan</button>
  </div>

  <!-- HUD Bottom Stats & Legend -->
  <div class="hud-panel hud-bottom">
    <div style="display:flex; align-items:center;">
      <div class="hud-stat">
        <span class="hud-stat-num" id="stat-nodes">{hubs_label}</span>
        <span class="hud-stat-lbl">Active Vertices</span>
      </div>
      <div class="hud-stat">
        <span class="hud-stat-num" style="color:#EC4899;">{ring_count} RINGS</span>
        <span class="hud-stat-lbl">Detected Syndicates</span>
      </div>
      <div class="hud-stat">
        <span class="hud-stat-num" style="color:#10B981;">{shielded_label}</span>
        <span class="hud-stat-lbl">Shielded Volume</span>
      </div>
      <div class="hud-stat">
        <span class="hud-stat-num" style="color:#38BDF8;">1-2 ms</span>
        <span class="hud-stat-lbl">Inference (server)</span>
      </div>
    </div>
    <div>
      <span class="legend-item"><span class="legend-dot" style="background:#10B981; box-shadow:0 0 6px #10B981;"></span>Benign P2P</span>
      <span class="legend-item"><span class="legend-dot" style="background:#A855F7; box-shadow:0 0 6px #A855F7;"></span>Layering Hop</span>
      <span class="legend-item"><span class="legend-dot" style="background:#EC4899; box-shadow:0 0 6px #EC4899;"></span>Mule Ring Flow</span>
      <span class="legend-item"><span class="legend-dot" style="background:#06B6D4; box-shadow:0 0 6px #06B6D4;"></span>Circular Loop</span>
    </div>
  </div>
</div>

<script>
  const container = document.getElementById('three-canvas');
  const width = container.clientWidth || {height} * 1.6;
  const height = {height};

  // Scene, Camera, Renderer
  const scene = new THREE.Scene();
  scene.fog = new THREE.FogExp2(0x0a0e17, 0.0025);

  const camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 1000);
  camera.position.set(0, 35, 175);

  const renderer = new THREE.WebGLRenderer({{ antialias: true, alpha: true }});
  renderer.setSize(width, height);
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.2;
  container.appendChild(renderer.domElement);

  // Orbit Controls
  const controls = new THREE.OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  controls.dampingFactor = 0.05;
  controls.rotateSpeed = 0.8;
  controls.enableZoom = true;
  controls.minDistance = 90;
  controls.maxDistance = 280;
  controls.autoRotate = true;
  controls.autoRotateSpeed = 1.2;

  // Globe Mesh Group
  const globeGroup = new THREE.Group();
  scene.add(globeGroup);

  const GLOBE_RADIUS = 50;

  // 1. Dark Hologram Base Sphere
  const sphereGeo = new THREE.SphereGeometry(GLOBE_RADIUS, 48, 48);
  const sphereMat = new THREE.MeshBasicMaterial({{
    color: 0x0c1322,
    transparent: true,
    opacity: 0.85,
    wireframe: false,
  }});
  const sphereMesh = new THREE.Mesh(sphereGeo, sphereMat);
  globeGroup.add(sphereMesh);

  // 2. Wireframe Cyber Grid Rings
  const wireGeo = new THREE.SphereGeometry(GLOBE_RADIUS + 0.1, 28, 28);
  const wireMat = new THREE.MeshBasicMaterial({{
    color: 0x223554,
    wireframe: true,
    transparent: true,
    opacity: 0.35,
  }});
  const wireMesh = new THREE.Mesh(wireGeo, wireMat);
  globeGroup.add(wireMesh);

  // 3. Glowing Outer Atmosphere Halo
  const haloGeo = new THREE.SphereGeometry(GLOBE_RADIUS * 1.15, 32, 32);
  const haloMat = new THREE.ShaderMaterial({{
    uniforms: {{}},
    vertexShader: `
      varying vec3 vNormal;
      void main() {{
        vNormal = normalize(normalMatrix * normal);
        gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
      }}
    `,
    fragmentShader: `
      varying vec3 vNormal;
      void main() {{
        float intensity = pow(0.65 - dot(vNormal, vec3(0, 0, 1.0)), 2.0);
        gl_FragColor = vec4(0.55, 0.36, 0.96, 0.35) * intensity;
      }}
    `,
    blending: THREE.AdditiveBlending,
    side: THREE.BackSide,
    transparent: true
  }});
  const haloMesh = new THREE.Mesh(haloGeo, haloMat);
  globeGroup.add(haloMesh);

  // 4. Floating Equatorial & Polar Hologram Rings
  function createHoloRing(radius, color, tiltX, tiltY) {{
    const ringGeo = new THREE.RingGeometry(radius - 0.4, radius + 0.4, 64);
    const ringMat = new THREE.MeshBasicMaterial({{
      color: color,
      side: THREE.DoubleSide,
      transparent: true,
      opacity: 0.4,
      blending: THREE.AdditiveBlending,
    }});
    const ringMesh = new THREE.Mesh(ringGeo, ringMat);
    ringMesh.rotation.x = tiltX;
    ringMesh.rotation.y = tiltY;
    return ringMesh;
  }}
  const ring1 = createHoloRing(GLOBE_RADIUS * 1.35, 0x8b5cf6, Math.PI / 2.3, 0.2);
  const ring2 = createHoloRing(GLOBE_RADIUS * 1.48, 0x06b6d4, Math.PI / 3.1, -0.4);
  scene.add(ring1);
  scene.add(ring2);

  // 5. Starfield / Floating Data Dust Particles
  const starsGeo = new THREE.BufferGeometry();
  const starCount = 1200;
  const starPositions = new Float32Array(starCount * 3);
  const starColors = new Float32Array(starCount * 3);

  for (let i = 0; i < starCount * 3; i += 3) {{
    starPositions[i] = (Math.random() - 0.5) * 500;
    starPositions[i + 1] = (Math.random() - 0.5) * 500;
    starPositions[i + 2] = (Math.random() - 0.5) * 500;

    const r = 0.5 + Math.random() * 0.5;
    const g = 0.5 + Math.random() * 0.5;
    const b = 0.9 + Math.random() * 0.1;
    starColors[i] = r; starColors[i + 1] = g; starColors[i + 2] = b;
  }}
  starsGeo.setAttribute('position', new THREE.BufferAttribute(starPositions, 3));
  starsGeo.setAttribute('color', new THREE.BufferAttribute(starColors, 3));
  const starsMat = new THREE.PointsMaterial({{
    size: 1.6,
    vertexColors: true,
    transparent: true,
    opacity: 0.65,
    blending: THREE.AdditiveBlending,
  }});
  const starField = new THREE.Points(starsGeo, starsMat);
  scene.add(starField);

  // Helper: Lat/Lon to 3D Cartesian Coordinate
  function latLonToVec3(lat, lon, radius) {{
    const phi = (90 - lat) * (Math.PI / 180);
    const theta = (lon + 180) * (Math.PI / 180);
    const x = -(radius * Math.sin(phi) * Math.cos(theta));
    const z = (radius * Math.sin(phi) * Math.sin(theta));
    const y = (radius * Math.cos(phi));
    return new THREE.Vector3(x, y, z);
  }}

  // 6. Hub Nodes
  const hubs = {hubs_json};
  const hubVectors = {{}};
  const hubMeshes = [];

  hubs.forEach(h => {{
    const pos = latLonToVec3(h.lat, h.lon, GLOBE_RADIUS);
    hubVectors[h.id] = pos;

    // Node Sphere
    const colorHex = h.risk === 'high' ? 0xec4899 : (h.risk === 'medium' ? 0xf59e0b : 0x10b981);
    const nodeGeo = new THREE.SphereGeometry(1.4, 16, 16);
    const nodeMat = new THREE.MeshBasicMaterial({{
      color: colorHex,
      blending: THREE.AdditiveBlending,
    }});
    const nodeMesh = new THREE.Mesh(nodeGeo, nodeMat);
    nodeMesh.position.copy(pos);
    globeGroup.add(nodeMesh);

    // Node Beacon Wave Ring
    const waveGeo = new THREE.RingGeometry(1.5, 2.2, 16);
    const waveMat = new THREE.MeshBasicMaterial({{
      color: colorHex,
      side: THREE.DoubleSide,
      transparent: true,
      opacity: 0.8,
      blending: THREE.AdditiveBlending,
    }});
    const waveMesh = new THREE.Mesh(waveGeo, waveMat);
    waveMesh.position.copy(pos);
    waveMesh.lookAt(new THREE.Vector3(0, 0, 0));
    globeGroup.add(waveMesh);

    hubMeshes.push({{ mesh: nodeMesh, wave: waveMesh, baseScale: 1.0, colorHex: colorHex }});
  }});

  // 7. Dynamic Bezier Arcs with Flowing Light Pulses
  const flows = {flows_json};
  const pulseBeams = [];

  flows.forEach(f => {{
    const p1 = hubVectors[f.from];
    const p2 = hubVectors[f.to];
    if (!p1 || !p2) return;

    // Calculate midpoint lifted outwards in 3D for dramatic arch
    const mid = new THREE.Vector3().addVectors(p1, p2).multiplyScalar(0.5);
    const dist = p1.distanceTo(p2);
    mid.normalize().multiplyScalar(GLOBE_RADIUS + dist * 0.45);

    const curve = new THREE.QuadraticBezierCurve3(p1, mid, p2);
    const points = curve.getPoints(36);
    const curveGeo = new THREE.BufferGeometry().setFromPoints(points);

    const col = new THREE.Color(f.color);
    const curveMat = new THREE.LineBasicMaterial({{
      color: col,
      transparent: true,
      opacity: f.type === 'ring' ? 0.85 : 0.45,
      blending: THREE.AdditiveBlending,
    }});
    const curveLine = new THREE.Line(curveGeo, curveMat);
    globeGroup.add(curveLine);

    // Glowing travelling pulse bead
    const pulseGeo = new THREE.SphereGeometry(1.2, 12, 12);
    const pulseMat = new THREE.MeshBasicMaterial({{
      color: 0xffffff,
      blending: THREE.AdditiveBlending,
    }});
    const pulseMesh = new THREE.Mesh(pulseGeo, pulseMat);
    globeGroup.add(pulseMesh);

    pulseBeams.push({{
      curve: curve,
      mesh: pulseMesh,
      t: Math.random(),
      speed: f.speed || 0.015,
      color: col,
    }});
  }});

  // Position Globe to highlight India by default
  globeGroup.rotation.y = 4.2;
  globeGroup.rotation.x = 0.35;

  // Interactivity Functions
  let isSpinning = true;
  window.toggleSpin = function() {{
    isSpinning = !isSpinning;
    controls.autoRotate = isSpinning;
    const btn = document.getElementById('btn-spin');
    if (isSpinning) {{
      btn.classList.add('active');
    }} else {{
      btn.classList.remove('active');
    }}
  }};

  window.focusIndia = function() {{
    globeGroup.rotation.y = 4.2;
    globeGroup.rotation.x = 0.35;
    camera.position.set(0, 30, 160);
    controls.update();
  }};

  let scanActive = false;
  let scanProgress = 0;
  window.triggerScan = function() {{
    scanActive = true;
    scanProgress = 0;
  }};

  // Animation Loop
  let clock = new THREE.Clock();

  function animate() {{
    requestAnimationFrame(animate);
    const delta = clock.getDelta();
    const time = clock.getElapsedTime();

    // Pulse node rings
    hubMeshes.forEach((item, idx) => {{
      const scale = 1.0 + 0.4 * Math.sin(time * 3 + idx);
      item.wave.scale.set(scale, scale, 1.0);
      item.wave.material.opacity = 0.9 - (scale - 1.0) * 1.5;
    }});

    // Move traveling transaction pulses along bezier arcs
    pulseBeams.forEach(p => {{
      p.t = (p.t + p.speed) % 1.0;
      const pt = p.curve.getPoint(p.t);
      p.mesh.position.copy(pt);
      const pulseScale = 1.0 + 0.5 * Math.sin(p.t * Math.PI);
      p.mesh.scale.set(pulseScale, pulseScale, pulseScale);
    }});

    // Rotate holographic rings
    ring1.rotation.z += 0.003;
    ring2.rotation.z -= 0.0025;
    starField.rotation.y += 0.0004;

    // Scanwave effect if triggered
    if (scanActive) {{
      scanProgress += delta * 1.8;
      sphereMat.color.setHex(scanProgress % 0.4 < 0.2 ? 0x1e1b4b : 0x0c1322);
      if (scanProgress > 2.0) {{
        scanActive = false;
        sphereMat.color.setHex(0x0c1322);
      }}
    }}

    controls.update();
    renderer.render(scene, camera);
  }}

  animate();

  // Responsive resize
  window.addEventListener('resize', () => {{
    const w = container.clientWidth || width;
    camera.aspect = w / height;
    camera.updateProjectionMatrix();
    renderer.setSize(w, height);
  }});
</script>
</body>
</html>
"""
    return html


def three_risk_gauge_html(score: int, action: str, height: int = 240) -> str:
    """
    Renders an interactive 3D WebGL Holographic Risk Reactor / Gauge.
    Concentric glowing plasma rings rotate in 3D around an illuminated
    numerical core that reflects the exact GNN fraud classification.

    Score bands come from config.THRESHOLD_* (same mapping as
    data.action_from_score): <MONITOR safe, <STEPUP monitor, <BLOCK step-up,
    otherwise block. Raises ValueError for a non-int or out-of-range score,
    matching styles.score_class.
    """
    if not isinstance(score, int) or isinstance(score, bool):
        raise ValueError(f"score must be an int in [0, 100], got {score!r}")
    if not (0 <= score <= 100):
        raise ValueError(f"score out of range [0, 100]: {score}")

    if score < config.THRESHOLD_MONITOR:
        color_hex = 0x10B981
        css_color = "#10B981"
        status_label = "SAFE MERCHANT"
    elif score < config.THRESHOLD_STEPUP:
        color_hex = 0xF59E0B
        css_color = "#F59E0B"
        status_label = "WATCHLIST MONITOR"
    elif score < config.THRESHOLD_BLOCK:
        color_hex = 0xF97316
        css_color = "#F97316"
        status_label = "STEP-UP AUTH REQ"
    else:
        color_hex = 0xEF4444
        css_color = "#EF4444"
        status_label = "CRITICAL MULE BLOCK"

    html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    background: transparent;
    overflow: hidden;
    font-family: 'Space Grotesk', 'Inter', monospace;
    color: #FFF;
    display: flex; justify-content: center; align-items: center;
    height: {height}px;
  }}
  #reactor-wrap {{
    position: relative;
    width: 100%; height: {height}px;
    display: flex; justify-content: center; align-items: center;
  }}
  #center-readout {{
    position: absolute;
    pointer-events: none;
    text-align: center;
    z-index: 10;
  }}
  .core-score {{
    font-size: 46px; font-weight: 800; line-height: 1;
    color: {css_color};
    text-shadow: 0 0 24px {css_color}, 0 0 45px rgba(255,255,255,0.4);
    letter-spacing: -0.04em;
  }}
  .core-max {{
    font-size: 14px; color: #94A3B8; font-weight: 600;
  }}
  .core-label {{
    margin-top: 4px;
    font-size: 11px; font-weight: 700;
    letter-spacing: 0.12em; text-transform: uppercase;
    color: #E2E8F0;
    background: rgba(15, 23, 42, 0.7);
    padding: 3px 10px; border-radius: 999px;
    border: 1px solid rgba(255, 255, 255, 0.15);
    display: inline-block;
  }}
</style>
<script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
</head>
<body>
<div id="reactor-wrap">
  <div id="three-reactor" style="width:100%; height:100%;"></div>
  <div id="center-readout">
    <div class="core-score">{score:02d}</div>
    <div class="core-max">/ 100</div>
    <div class="core-label">{action} · {status_label}</div>
  </div>
</div>

<script>
  const wrap = document.getElementById('three-reactor');
  const w = wrap.clientWidth || 380;
  const h = {height};

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(45, w / h, 0.1, 1000);
  camera.position.z = 85;

  const renderer = new THREE.WebGLRenderer({{ antialias: true, alpha: true }});
  renderer.setSize(w, h);
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  wrap.appendChild(renderer.domElement);

  const mainColor = {color_hex};

  // Concentric Spinning Reactor Rings
  function createRing(rIn, rOut, tiltX, tiltY, col, opacity) {{
    const geo = new THREE.RingGeometry(rIn, rOut, 48);
    const mat = new THREE.MeshBasicMaterial({{
      color: col,
      side: THREE.DoubleSide,
      transparent: true,
      opacity: opacity,
      blending: THREE.AdditiveBlending,
    }});
    const mesh = new THREE.Mesh(geo, mat);
    mesh.rotation.x = tiltX;
    mesh.rotation.y = tiltY;
    scene.add(mesh);
    return mesh;
  }}

  const r1 = createRing(28, 29.5, 0.3, 0.2, mainColor, 0.7);
  const r2 = createRing(32, 33, -0.4, 0.5, 0x8b5cf6, 0.5);
  const r3 = createRing(35, 35.8, 0.6, -0.3, mainColor, 0.4);

  // Sparkle particles
  const particleCount = 70;
  const pGeo = new THREE.BufferGeometry();
  const pPos = new Float32Array(particleCount * 3);
  for(let i=0; i<particleCount*3; i+=3) {{
    const theta = Math.random() * Math.PI * 2;
    const rad = 24 + Math.random() * 16;
    pPos[i] = Math.cos(theta) * rad;
    pPos[i+1] = Math.sin(theta) * rad;
    pPos[i+2] = (Math.random() - 0.5) * 20;
  }}
  pGeo.setAttribute('position', new THREE.BufferAttribute(pPos, 3));
  const pMat = new THREE.PointsMaterial({{
    size: 2.0,
    color: mainColor,
    transparent: true,
    opacity: 0.8,
    blending: THREE.AdditiveBlending,
  }});
  const particles = new THREE.Points(pGeo, pMat);
  scene.add(particles);

  let angle = 0;
  function animate() {{
    requestAnimationFrame(animate);
    angle += 0.02;

    r1.rotation.z += 0.015;
    r2.rotation.z -= 0.02;
    r3.rotation.z += 0.01;

    r1.rotation.x = 0.3 + 0.1 * Math.sin(angle);
    r2.rotation.y = 0.4 + 0.15 * Math.cos(angle * 0.8);

    particles.rotation.z += 0.005;

    renderer.render(scene, camera);
  }}
  animate();
</script>
</body>
</html>
"""
    return html
