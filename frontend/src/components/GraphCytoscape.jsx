import { useEffect, useRef } from "react";
import cytoscape from "cytoscape";
import { EDGE_COLORS, bandOf } from "../lib/mock.js";

const BAND_COLOR = { safe: "#10B981", monitor: "#F59E0B", stepup: "#F97316", block: "#EF4444" };

export default function GraphCytoscape({ graph, height = 460, scrubTimeSec }) {
  const ref = useRef(null);
  const cyRef = useRef(null);

  const safeNodes = Array.isArray(graph?.nodes) ? graph.nodes : [];
  const safeEdges = Array.isArray(graph?.edges) ? graph.edges : [];

  useEffect(() => {
    if (!ref.current || safeNodes.length === 0) return;

    // 1. Build authoritative node set and ensure defensive edge endpoint matching
    const nodeMap = new Map();
    safeNodes.forEach((n) => {
      if (n && n.id != null) {
        const id = String(n.id);
        nodeMap.set(id, {
          id,
          score: Number(n.score ?? 50),
          is_core: Boolean(n.is_core || (n.score != null && n.score >= 75) || n.role === "hub"),
          degree: 0,
          focus: n.focus || null,
        });
      }
    });

    // 2. Discover any peripheral edge endpoints and auto-synthesize nodes to prevent Cytoscape orphan edge throws
    safeEdges.forEach((e) => {
      if (!e) return;
      const s = e.source != null ? String(e.source) : null;
      const t = e.target != null ? String(e.target) : null;
      if (!s || !t) return;
      if (!nodeMap.has(s)) {
        nodeMap.set(s, { id: s, score: 50, is_core: false, degree: 0 });
      }
      if (!nodeMap.has(t)) {
        nodeMap.set(t, { id: t, score: 50, is_core: false, degree: 0 });
      }
      nodeMap.get(s).degree += 1;
      nodeMap.get(t).degree += 1;
    });

    // 3. Consolidate and aggregate parallel edges to eliminate overlapping visual clutter
    const edgeMap = new Map();
    safeEdges.forEach((e) => {
      if (!e || e.source == null || e.target == null) return;
      const s = String(e.source);
      const t = String(e.target);
      if (!nodeMap.has(s) || !nodeMap.has(t)) return;
      const key = `${s}->${t}`;
      if (edgeMap.has(key)) {
        const existing = edgeMap.get(key);
        existing.amount += Number(e.amount || 0);
        if (e.type === "ring") existing.type = "ring";
        existing.count += 1;
      } else {
        edgeMap.set(key, {
          id: e.id || key,
          source: s,
          target: t,
          amount: Number(e.amount || 1000),
          type: e.type || "normal",
          focus: !!e.focus,
          count: 1,
        });
      }
    });

    const aggregatedEdges = Array.from(edgeMap.values());
    const totalEdges = aggregatedEdges.length;

    const elements = [
      ...Array.from(nodeMap.values()).map((n) => ({
        data: {
          id: n.id,
          score: n.score,
          degree: n.degree,
          is_core: n.is_core,
          focus: n.focus,
        },
      })),
      ...aggregatedEdges.map((e, i) => {
        // Deterministic chronological appearance window (10s to 175s)
        const appearanceTime = Math.round((i / Math.max(1, totalEdges - 1)) * 165) + 10;
        return {
          data: {
            id: e.id || `e${i}`,
            source: e.source,
            target: e.target,
            amount: e.amount,
            type: e.type,
            appearanceTime,
            focus: e.focus,
          },
          classes: e.type === "ring" ? "ring-ed" : "",
        };
      }),
    ];

    let cy = null;
    try {
      cy = cytoscape({
        container: ref.current,
        elements,
        minZoom: 0.25,
        maxZoom: 2.5,
        wheelSensitivity: 0.25,
        style: [
          {
            selector: "node",
            style: {
              "background-color": (ele) => BAND_COLOR[bandOf(ele.data("score"))],
              width: (ele) => (ele.data("is_core") ? 52 : 44),
              height: (ele) => (ele.data("is_core") ? 52 : 44),
              label: (ele) => ele.id(),
              color: "#FFFFFF",
              "text-background-color": "#070E22",
              "text-background-opacity": 0.94,
              "text-background-padding": 5,
              "text-background-radius": 6,
              "text-border-width": 1,
              "text-border-color": "rgba(255,255,255,0.22)",
              "text-valign": "bottom",
              "text-margin-y": 8,
              "font-size": 12,
              "font-family": "JetBrains Mono, monospace",
              "font-weight": 700,
              "border-width": 2,
              "border-color": "rgba(255,255,255,0.75)",
              transition: "all 0.25s ease",
            },
          },
          {
            selector: "node[focus = 'source']",
            style: {
              width: 58,
              height: 58,
              "border-width": 4,
              "border-color": "#FF0055",
              "text-border-color": "#FF0055",
              "text-border-width": 2,
              "z-index": 999,
            },
          },
          {
            selector: "node[focus = 'target']",
            style: {
              width: 52,
              height: 52,
              "border-width": 3,
              "border-color": "#2E69FF",
              "text-border-color": "#2E69FF",
              "text-border-width": 1.5,
              "z-index": 998,
            },
          },
          {
            selector: "edge",
            style: {
              width: (ele) => Math.max(2.5, Math.min(8, (ele.data("amount") || 1000) / 4500)),
              "line-color": (ele) =>
                ele.data("type") === "ring" ? EDGE_COLORS.ring : ele.data("type") === "layering" ? EDGE_COLORS.layering : EDGE_COLORS.normal,
              "curve-style": "bezier",
              "control-point-step-size": 36,
              "target-arrow-shape": "triangle",
              "arrow-scale": 1.35,
              "target-arrow-color": (ele) =>
                ele.data("type") === "ring" ? EDGE_COLORS.ring : ele.data("type") === "layering" ? EDGE_COLORS.layering : EDGE_COLORS.normal,
              "line-opacity": (ele) => (ele.data("type") === "ring" ? 0.95 : 0.75),
              transition: "all 0.2s ease",
            },
          },
          {
            selector: ".ring-ed.focused",
            style: { "line-opacity": 1, width: 7 },
          },
          {
            selector: ".scrub-hidden",
            style: { opacity: 0.06, width: 1 },
          },
          {
            selector: ".scrub-active-pulse",
            style: { "line-color": "#FF0055", "target-arrow-color": "#FF0055", width: 7, "line-opacity": 1 },
          },
        ],
        layout: {
          name: "cose",
          animate: true,
          animationDuration: 450,
          padding: 45,
          nodeRepulsion: (safeNodes.length <= 4 ? 500000 : 1600000),
          idealEdgeLength: (safeNodes.length <= 4 ? 120 : 160),
          edgeElasticity: 100,
          componentSpacing: 100,
          randomize: false,
        },
      });

      // Adaptive zoom & viewport fitting
      const adjustZoomAndFit = () => {
        try {
          if (!cy || (typeof cy.destroyed === "function" && cy.destroyed())) return;
          if (safeNodes.length <= 2) {
            // For 1 or 2 nodes (e.g. single alert investigation), clamp zoom so it never balloons into giant circles
            if (cy.zoom() > 1.0) {
              cy.zoom(1.0);
              cy.center();
            }
          } else {
            // For multi-node syndicates, fit comfortably across the canvas
            cy.fit(undefined, 45);
            if (cy.zoom() > 1.8) {
              cy.zoom(1.5);
              cy.center();
            } else if (cy.zoom() < 0.65) {
              cy.zoom(0.75);
              cy.center();
            }
          }
        } catch (_) {}
      };

      cy.ready(adjustZoomAndFit);
      cy.on("layoutstop", adjustZoomAndFit);

      cyRef.current = cy;
    } catch (cyErr) {
      console.error("Cytoscape initialization caught error:", cyErr);
    }

    return () => {
      if (cyRef.current) {
        try {
          cyRef.current.destroy();
        } catch (_) {}
        cyRef.current = null;
      }
    };
  }, [graph]);

  // Update dynamic visibility when scrubTimeSec changes
  useEffect(() => {
    const cy = cyRef.current;
    if (!cy || scrubTimeSec === undefined) return;

    try {
      if (typeof cy.destroyed === "function" && cy.destroyed()) return;
      cy.batch(() => {
        cy.edges().forEach((edge) => {
          const appTime = edge.data("appearanceTime") || 0;
          if (appTime <= scrubTimeSec) {
            edge.removeClass("scrub-hidden");
            if (Math.abs(appTime - scrubTimeSec) <= 15) {
              edge.addClass("scrub-active-pulse");
            } else {
              edge.removeClass("scrub-active-pulse");
            }
          } else {
            edge.addClass("scrub-hidden");
            edge.removeClass("scrub-active-pulse");
          }
        });
      });
    } catch (_) {}
  }, [scrubTimeSec]);

  return (
    <div className="relative rounded-2xl overflow-hidden border border-white/10 bg-slate-950/60">
      <div ref={ref} style={{ height }} />

      {/* Interactive Canvas Controls */}
      <div className="absolute top-3 right-3 flex items-center gap-1.5 bg-slate-900/90 backdrop-blur-md p-1 rounded-xl border border-white/10 shadow-lg z-10">
        <button
          onClick={() => {
            const cy = cyRef.current;
            if (cy && !cy.destroyed()) {
              cy.zoom(cy.zoom() * 1.25);
              cy.center();
            }
          }}
          className="w-7 h-7 rounded-lg bg-white/5 hover:bg-white/15 text-slate-200 grid place-items-center font-bold text-sm cursor-pointer transition-colors"
          title="Zoom In"
        >
          +
        </button>
        <button
          onClick={() => {
            const cy = cyRef.current;
            if (cy && !cy.destroyed()) {
              cy.zoom(cy.zoom() / 1.25);
              cy.center();
            }
          }}
          className="w-7 h-7 rounded-lg bg-white/5 hover:bg-white/15 text-slate-200 grid place-items-center font-bold text-sm cursor-pointer transition-colors"
          title="Zoom Out"
        >
          -
        </button>
        <button
          onClick={() => {
            const cy = cyRef.current;
            if (cy && !cy.destroyed()) {
              if (safeNodes.length <= 2) {
                cy.zoom(1.0);
                cy.center();
              } else {
                cy.fit(undefined, 45);
              }
            }
          }}
          className="px-2 h-7 rounded-lg bg-white/5 hover:bg-white/15 text-slate-300 font-mono2 text-[10px] font-bold cursor-pointer transition-colors flex items-center"
          title="Reset Fit"
        >
          FIT
        </button>
      </div>

      {safeNodes.length === 0 && (
        <div className="absolute inset-0 flex items-center justify-center text-slate-400 font-mono2 text-xs bg-slate-950/80">
          <div className="flex flex-col items-center gap-2">
            <div className="w-5 h-5 border-2 border-[#2E69FF] border-t-transparent rounded-full animate-spin" />
            <span>Tracing Exasol graph topology…</span>
          </div>
        </div>
      )}
      <div className="absolute bottom-3 left-3 flex gap-3 text-[10px] text-slate-400">
        <span className="flex items-center gap-1"><i className="w-2 h-2 rounded-full inline-block" style={{ background: EDGE_COLORS.normal }} />Normal</span>
        <span className="flex items-center gap-1"><i className="w-2 h-2 rounded-full inline-block" style={{ background: EDGE_COLORS.ring }} />Mule ring</span>
        <span className="flex items-center gap-1"><i className="w-2 h-2 rounded-full inline-block" style={{ background: EDGE_COLORS.layering }} />Layering</span>
      </div>
    </div>
  );
}
