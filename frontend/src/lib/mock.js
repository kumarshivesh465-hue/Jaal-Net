// Mock UPI transaction stream + ring graph generator.
// Faithful port of data.py (same distributions, same thresholds) so the UI
// behaves identically when the FastAPI backend is unreachable.

export const THRESHOLDS = { monitor: 30, stepup: 70, block: 90 };
export const ACTIONS = ["ALLOW", "MONITOR", "STEP_UP", "BLOCK"];
export const INDIAN_STATES = ["MH", "KA", "TN", "DL", "UP", "GJ", "WB", "RJ", "KL", "TS"];
export const MAX_STREAM_SIZE = 200;
export const STREAM_BATCH_SIZE = 3;
export const REFRESH_INTERVAL_MS = 2000;

export const EDGE_COLORS = {
  normal: "#374151",
  ring: "#EC4899",
  layering: "#A855F7",
  circular: "#06B6D4",
};

const risk = () => Math.random();
const pick = (arr) => arr[Math.floor(Math.random() * arr.length)];
const between = (a, b) => a + Math.random() * (b - a);
const rint = (a, b) => Math.floor(between(a, b + 1));

const acct = () => `${pick([..."ABCDEFGH"])}***${rint(1000, 9999)}`;
const makeRing = (n) => Array.from({ length: n }, () => acct());

// Rings generated once at module load so the graph stays stable within a
// session (same rule as data.py's import-time generation).
export const RINGS = {
  "RING-001": makeRing(8),
  "RING-002": makeRing(5),
  "RING-003": makeRing(12),
};

export function actionFromScore(score) {
  if (score < THRESHOLDS.monitor) return "ALLOW";
  if (score < THRESHOLDS.stepup) return "MONITOR";
  if (score < THRESHOLDS.block) return "STEP_UP";
  return "BLOCK";
}

const scoreFromFeatures = (ringId, deviceChange, ipRisk, amount) => {
  let score = 15;
  if (ringId) score += rint(55, 75);
  if (deviceChange) score += rint(8, 16);
  score += Math.trunc(ipRisk * 20);
  if (amount > 40000) score += rint(4, 10);
  return Math.min(100, Math.max(0, score));
};

export function generateTransaction(i) {
  const inRing = Math.random() < 0.02;
  let ringId = null;
  let sender, receiver;
  if (inRing) {
    ringId = pick(Object.keys(RINGS));
    const accounts = RINGS[ringId];
    sender = pick(accounts);
    receiver = pick(accounts.filter((a) => a !== sender));
  } else {
    sender = acct();
    receiver = acct();
  }
  const amount = Math.round(pick([between(50, 2000), between(2000, 20000), between(20000, 100000)]) * 100) / 100;
  const deviceChange = Math.random() < 0.15;
  const ipRisk = risk() * (inRing ? 0.9 : 0.35);
  const score = scoreFromFeatures(ringId, deviceChange, ipRisk, amount);
  return {
    txnId: `UPI-${Math.floor(Date.now() / 1000)}-${String(i).padStart(5, "0")}`,
    ts: Date.now() - rint(0, 5) * 1000,
    sender,
    receiver,
    amount,
    score,
    action: actionFromScore(score),
    state: pick(INDIAN_STATES),
    deviceChange,
    ipRisk: Math.round(ipRisk * 1000) / 1000,
    ringId,
    model: "TGAT+SAGE-v1.2",
  };
}

export function explanationFor(t) {
  const base = [
    ["2-hop cycle detected", 0.34],
    ["Sender velocity spike", 0.28],
    ["New device + IP change", 0.19],
    ["Receiver mule-flagged", 0.12],
    ["Amount > 95th percentile", 0.07],
  ];
  const scale = Math.max(0.05, t.score / 100);
  return base
    .map(([label, w]) => [label, Math.round(w * scale * 1000) / 1000])
    .sort((a, b) => b[1] - a[1]);
}

export function initialStream(n = 30) {
  return Array.from({ length: n }, (_, i) => generateTransaction(i)).sort((a, b) => b.ts - a.ts);
}

export function ringGraphData(ringId) {
  const accounts = RINGS[ringId];
  if (!accounts) throw new Error(`Unknown ring_id: ${ringId}`);
  const nodes = accounts.map((a) => ({ id: a, score: rint(60, 95), ring: ringId }));
  const edges = [];
  accounts.forEach((a, i) => {
    const b = accounts[(i + 1) % accounts.length];
    edges.push({ source: a, target: b, amount: between(5000, 45000), type: "ring" });
  });
  for (let k = 0; k < Math.floor(accounts.length / 2); k++) {
    const a = pick(accounts);
    let b = pick(accounts);
    while (b === a) b = pick(accounts);
    if (!edges.some((e) => e.source === a && e.target === b)) {
      edges.push({ source: a, target: b, amount: between(2000, 30000), type: "layering" });
    }
  }
  return { nodes, edges };
}

export function neighborhoodGraphData(txn, hops = 2) {
  const nodes = new Map([
    [txn.sender, { id: txn.sender, score: txn.score, focus: "source" }],
    [txn.receiver, { id: txn.receiver, score: rint(10, 95), focus: "target" }],
  ]);
  const edges = [
    {
      source: txn.sender,
      target: txn.receiver,
      amount: txn.amount,
      type: txn.ringId ? "ring" : "normal",
      focus: true,
    },
  ];
  const neighborCount = Math.min(50, rint(4, 9) * hops);
  for (let k = 0; k < neighborCount; k++) {
    const a = pick([txn.sender, txn.receiver]);
    let b = acct();
    if (b === txn.sender || b === txn.receiver) continue;
    if (nodes.has(b) || edges.some((e) => e.source === a && e.target === b)) continue;
    nodes.set(b, { id: b, score: rint(10, 95) });
    edges.push({ source: a, target: b, amount: between(500, 25000), type: "normal" });
  }
  return { nodes: [...nodes.values()], edges };
}

export const scoreColor = (score) => {
  if (score < 30) return "#10B981"; // Safe Green
  if (score < 70) return "#FFCA36"; // Monitor Amber
  if (score < 90) return "#FF9500"; // Step-Up Orange
  return "#FF0055"; // Block Hot Pink
};

export const bandOf = (score) => {
  if (score < 30) return "safe";
  if (score < 70) return "monitor";
  if (score < 90) return "stepup";
  return "block";
};

export const inr = (v) => {
  if (v >= 1e7) return `₹${(v / 1e7).toFixed(1)}Cr`;
  if (v >= 1e5) return `₹${(v / 1e5).toFixed(1)}L`;
  return `₹${Math.round(v / 1000)}K`;
};
