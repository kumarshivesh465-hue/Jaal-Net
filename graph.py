"""Cytoscape.js HTML builder for Streamlit embedding. Implements CONTRACTS.md section 6.
Enhanced with Liquid Glass Tooltips, Glowing Neon Node Halos, Cyber Edges, and HUD controls.
"""

import json

import networkx as nx

import config
from styles import score_color

_EDGE_COLORS = {
    config.EDGE_RING: config.COLOR_MULE_RING,
    config.EDGE_LAYERING: config.COLOR_LAYERING,
    config.EDGE_CIRCULAR: config.COLOR_CIRCULAR,
    config.EDGE_NORMAL: config.COLOR_EDGE_NORMAL,
}


def cytoscape_html(
    G: nx.DiGraph,
    height: int = 480,
    highlight_rings: bool = True,
) -> str:
    """Return a self-contained HTML string that renders a Cytoscape graph.

    Preconditions:
      - G is a networkx.DiGraph
      - Every node has attribute `score: int`
      - Every edge has attributes `amount: float` and `edge_type: str`
      - 200 <= height <= 1200

    Raises ValueError if preconditions are violated.
    """
    if not isinstance(G, nx.DiGraph):
        raise ValueError(f"G must be a networkx.DiGraph, got {type(G).__name__}")
    if not (200 <= height <= 1200):
        raise ValueError(f"height must be in [200, 1200], got {height}")

    for node, attrs in G.nodes(data=True):
        if "score" not in attrs:
            raise ValueError(f"node {node!r} missing required attribute 'score'")

    for u, v, attrs in G.edges(data=True):
        if "amount" not in attrs:
            raise ValueError(f"edge ({u!r}, {v!r}) missing required attribute 'amount'")
        if "edge_type" not in attrs:
            raise ValueError(f"edge ({u!r}, {v!r}) missing required attribute 'edge_type'")

    nodes = []
    for n, attrs in G.nodes(data=True):
        score = int(attrs.get("score", 20))
        nodes.append({
            "data": {
                "id": n,
                "label": n,
                "score": score,
                "color": score_color(max(0, min(100, score))),
                "size": 26 + min(22, G.degree(n) * 3),
            }
        })

    edges = []
    for u, v, attrs in G.edges(data=True):
        et = attrs.get("edge_type", config.EDGE_NORMAL)
        color = _EDGE_COLORS.get(et, config.COLOR_EDGE_NORMAL)
        edges.append({
            "data": {
                "source": u,
                "target": v,
                "amount": attrs.get("amount", 0),
                "edge_type": et,
                "color": color,
                "width": 2.0 + min(5, attrs.get("amount", 0) / 20000),
            }
        })

    elements = {"nodes": nodes, "edges": edges}

    # must start exactly with the doctype or the graph renders blank
    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<script src="https://unpkg.com/cytoscape@3.28.1/dist/cytoscape.min.js"></script>
<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@500;700&family=Space+Grotesk:wght@500;700&family=Outfit:wght@500;600&display=swap" rel="stylesheet">
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  html, body {{
    margin: 0; padding: 0;
    background: {config.COLOR_BG_PRIMARY};
    overflow: hidden;
    font-family: 'Outfit', 'Space Grotesk', -apple-system, sans-serif;
  }}
  #graph-wrapper {{
    position: relative;
    width: 100%;
    height: {height}px;
    background: radial-gradient(circle at 50% 50%, #0F172A 0%, {config.COLOR_BG_PRIMARY} 100%);
    border-radius: 14px;
    border: 1px solid rgba(255, 255, 255, 0.1);
    box-shadow: 0 16px 36px rgba(0, 0, 0, 0.5), inset 0 1px 1px rgba(255, 255, 255, 0.15);
    overflow: hidden;
  }}
  #cy {{
    width: 100%;
    height: 100%;
    background: transparent;
  }}
  /* Liquid Glass HUD Tooltip */
  #tooltip {{
    position: absolute;
    background: rgba(15, 23, 42, 0.85);
    backdrop-filter: blur(20px) saturate(200%);
    -webkit-backdrop-filter: blur(20px) saturate(200%);
    border: 1px solid rgba(255, 255, 255, 0.18);
    border-radius: 12px;
    padding: 12px 16px;
    color: #F8FAFC;
    font-size: 12px;
    pointer-events: none;
    display: none;
    z-index: 100;
    min-width: 190px;
    box-shadow: 0 12px 32px rgba(0,0,0,0.65), 0 0 20px rgba(139, 92, 246, 0.25);
    transition: transform 0.1s ease-out;
  }}
  #tooltip .t-head {{
    font-family: 'Space Grotesk', sans-serif;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: #94A3B8;
    margin-bottom: 6px;
    padding-bottom: 4px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  }}
  #tooltip .t-row {{ display: flex; justify-content: space-between; gap: 16px; margin: 4px 0; font-size: 12px; }}
  #tooltip .t-key {{ color: {config.COLOR_TEXT_MUTED}; font-weight: 500; }}
  #tooltip .t-val {{ color: #F8FAFC; font-family: 'JetBrains Mono', monospace; font-weight: 700; }}

  /* Graph Floating HUD Controls */
  .cy-hud {{
    position: absolute;
    top: 12px; right: 12px;
    display: flex; gap: 6px;
    z-index: 20;
  }}
  .cy-hud-btn {{
    background: rgba(15, 23, 42, 0.7);
    backdrop-filter: blur(14px);
    border: 1px solid rgba(255, 255, 255, 0.15);
    color: #E2E8F0;
    padding: 6px 12px;
    border-radius: 8px;
    font-size: 11px;
    font-weight: 600;
    font-family: 'Space Grotesk', sans-serif;
    cursor: pointer;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
    transition: all 0.2s ease;
  }}
  .cy-hud-btn:hover {{
    background: rgba(139, 92, 246, 0.35);
    border-color: #8B5CF6;
    color: #FFF;
    transform: translateY(-1px);
    box-shadow: 0 0 12px rgba(139, 92, 246, 0.4);
  }}
</style>
</head>
<body>
<div id="graph-wrapper">
  <div id="cy"></div>
  <div class="cy-hud">
    <button class="cy-hud-btn" onclick="cy.fit(40)">⛶ Fit</button>
    <button class="cy-hud-btn" onclick="cy.zoom(cy.zoom()*1.25); cy.center();">➕</button>
    <button class="cy-hud-btn" onclick="cy.zoom(cy.zoom()*0.8); cy.center();">➖</button>
  </div>
  <div id="tooltip"></div>
</div>

<script>
  const elements = {json.dumps(elements)};
  const highlightRings = {str(highlight_rings).lower()};

  const cy = cytoscape({{
    container: document.getElementById('cy'),
    elements: elements,
    style: [
      {{
        selector: 'node',
        style: {{
          'background-color': 'data(color)',
          'label': 'data(label)',
          'color': '#CBD5E1',
          'font-size': 11,
          'font-family': 'Space Grotesk, Inter, sans-serif',
          'font-weight': 600,
          'text-valign': 'bottom',
          'text-margin-y': 7,
          'width': 'data(size)',
          'height': 'data(size)',
          'border-width': 2.5,
          'border-color': 'rgba(255, 255, 255, 0.2)',
          'shadow-blur': 12,
          'shadow-color': 'data(color)',
          'shadow-opacity': 0.65,
          'transition-property': 'transform, border-color, shadow-blur',
          'transition-duration': '0.2s',
        }}
      }},
      {{
        selector: 'edge',
        style: {{
          'width': 'data(width)',
          'line-color': 'data(color)',
          'target-arrow-color': 'data(color)',
          'target-arrow-shape': 'triangle',
          'curve-style': 'bezier',
          'arrow-scale': 0.9,
          'opacity': 0.85,
        }}
      }},
      {{
        selector: 'edge[edge_type = "ring"]',
        style: {{
          'line-style': 'solid',
          'line-color': '{config.COLOR_MULE_RING}',
          'target-arrow-color': '{config.COLOR_MULE_RING}',
          'opacity': 0.95,
          'width': 3.5,
          'shadow-blur': 10,
          'shadow-color': '{config.COLOR_MULE_RING}',
          'shadow-opacity': 0.7,
        }}
      }},
      {{
        selector: 'node:selected',
        style: {{
          'border-width': 4,
          'border-color': '#FFFFFF',
          'shadow-blur': 25,
          'shadow-color': '{config.COLOR_ACCENT}',
          'shadow-opacity': 0.9,
        }}
      }}
    ],
    layout: {{
      name: 'cose',
      animate: true,
      animationDuration: 700,
      nodeRepulsion: 9000,
      idealEdgeLength: 100,
      padding: 40,
    }},
    wheelSensitivity: 0.25,
  }});

  // Ring pulse animation
  if (highlightRings) {{
    let t = 0;
    setInterval(() => {{
      t = (t + 1) % 2;
      cy.edges('[edge_type = "ring"]').style('opacity', t === 0 ? 0.6 : 1.0);
    }}, 900);
  }}

  // Tooltip with liquid glass styling
  const tooltip = document.getElementById('tooltip');
  cy.on('mouseover', 'node', (e) => {{
    const n = e.target;
    tooltip.innerHTML = `
      <div class="t-head">Account Intelligence</div>
      <div class="t-row"><span class="t-key">Account</span><span class="t-val">${{n.data('label')}}</span></div>
      <div class="t-row"><span class="t-key">Risk Score</span><span class="t-val" style="color:${{n.data('color')}}">${{n.data('score')}} / 100</span></div>
      <div class="t-row"><span class="t-key">Degree</span><span class="t-val">${{n.degree()}} connections</span></div>
    `;
    tooltip.style.display = 'block';
    const pos = e.renderedPosition || {{x: 0, y: 0}};
    tooltip.style.left = (pos.x + 18) + 'px';
    tooltip.style.top  = (pos.y + 18) + 'px';
  }});
  cy.on('mouseout', 'node', () => {{ tooltip.style.display = 'none'; }});
  cy.on('mousemove', 'node', (e) => {{
    const pos = e.renderedPosition || {{x: 0, y: 0}};
    tooltip.style.left = (pos.x + 18) + 'px';
    tooltip.style.top  = (pos.y + 18) + 'px';
  }});

  cy.on('mouseover', 'edge', (e) => {{
    const d = e.target.data();
    tooltip.innerHTML = `
      <div class="t-head">Transaction Arc</div>
      <div class="t-row"><span class="t-key">Amount</span><span class="t-val">₹${{d.amount.toLocaleString('en-IN')}}</span></div>
      <div class="t-row"><span class="t-key">Pattern</span><span class="t-val" style="color:${{d.color}}">${{d.edge_type.toUpperCase()}}</span></div>
    `;
    tooltip.style.display = 'block';
    const pos = e.renderedPosition || {{x: 0, y: 0}};
    tooltip.style.left = (pos.x + 18) + 'px';
    tooltip.style.top  = (pos.y + 18) + 'px';
  }});
  cy.on('mouseout', 'edge', () => {{ tooltip.style.display = 'none'; }});
</script>
</body>
</html>
"""
