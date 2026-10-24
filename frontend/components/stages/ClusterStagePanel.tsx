"use client";

import React, { useEffect, useRef, useState } from "react";
import { 
  Network, 
  ShieldAlert, 
  DollarSign, 
  ZoomIn, 
  ZoomOut, 
  Maximize2, 
  Layers, 
  Sparkles, 
  Lock, 
  AlertTriangle,
  Info,
  CheckCircle2,
  Share2
} from "lucide-react";
import cytoscape from "cytoscape";
import { CaseSummary, GraphData } from "@/lib/types";
import { api } from "@/lib/api";

interface ClusterStagePanelProps {
  caseData: CaseSummary;
}

export function ClusterStagePanel({ caseData }: ClusterStagePanelProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const cyRef = useRef<cytoscape.Core | null>(null);
  const [graphData, setGraphData] = useState<GraphData | null>(null);
  const [selectedNode, setSelectedNode] = useState<any>(null);
  const [disruptionMetrics, setDisruptionMetrics] = useState({
    domainsNeutralized: 5,
    estimatedInr: 4200000,
    mulesFlagged: 1
  });

  // Load graph data
  useEffect(() => {
    async function loadGraph() {
      try {
        const data = await api.getGraph(caseData.result?.payee.upi_vpa);
        setGraphData(data);
      } catch (err) {
        console.error("Failed to load graph data:", err);
      }
    }
    loadGraph();
  }, [caseData]);

  // Initialize Cytoscape
  useEffect(() => {
    if (!containerRef.current || !graphData) return;

    // Destroy existing instance before re-initializing
    if (cyRef.current) {
      cyRef.current.destroy();
    }

    try {
      const cy = cytoscape({
        container: containerRef.current,
        elements: {
          nodes: graphData.nodes.map(n => ({
            data: {
              ...n.data,
              nodeColor: n.data.type === 'payee' ? '#ff2a55' :
                         n.data.type === 'domain' ? '#00f0ff' :
                         n.data.type === 'phone' ? '#9d4edd' :
                         n.data.type === 'ip' ? '#ffaa00' : '#ffffff'
            }
          })),
          edges: graphData.edges.map(e => ({
            data: {
              ...e.data,
              edgeColor: e.data.relationship === 'funnel_destination' ? 'rgba(255, 42, 85, 0.6)' : 'rgba(0, 240, 255, 0.4)'
            }
          }))
        },
        style: [
          {
            selector: 'node',
            style: {
              'background-color': 'data(nodeColor)',
              'label': 'data(label)',
              'color': '#f0f2f8',
              'font-family': 'JetBrains Mono, monospace',
              'font-size': '10px',
              'text-valign': 'bottom',
              'text-margin-y': 6,
              'width': 26,
              'height': 26,
              'border-width': 2,
              'border-color': 'rgba(255, 255, 255, 0.3)',
              'text-outline-color': '#07070b',
              'text-outline-width': 2,
              'text-max-width': '140px',
              'text-wrap': 'ellipsis'
            }
          },
          {
            selector: 'node[type = "payee"]',
            style: {
              'width': 44,
              'height': 44,
              'font-size': '11px',
              'font-weight': 'bold',
              'border-width': 3,
              'border-color': '#ffffff',
              'overlay-color': '#ff2a55',
              'overlay-opacity': 0.35,
              'overlay-padding': 6
            }
          },
          {
            selector: 'node[type = "domain"]',
            style: {
              'width': 30,
              'height': 30,
              'shape': 'diamond',
              'border-width': 2,
              'border-color': 'rgba(0, 240, 255, 0.6)',
              'overlay-color': '#00f0ff',
              'overlay-opacity': 0.25,
              'overlay-padding': 4
            }
          },
          {
            selector: 'edge',
            style: {
              'width': 2,
              'line-color': 'data(edgeColor)',
              'target-arrow-color': 'data(edgeColor)',
              'target-arrow-shape': 'triangle',
              'curve-style': 'bezier',
              'arrow-scale': 1.1,
              'opacity': 0.7
            }
          },
          {
            selector: ':selected',
            style: {
              'border-width': 4,
              'border-color': '#ffffff',
              'overlay-color': '#00ff9d',
              'overlay-opacity': 0.5,
              'overlay-padding': 8
            }
          }
        ] as any,
        layout: {
          name: 'cose',
          animate: true,
          animationDuration: 800,
          padding: 40,
          nodeRepulsion: () => 450000,
          idealEdgeLength: () => 100
        }
      });

      // Node Click Interaction
      cy.on('tap', 'node', (evt) => {
        const node = evt.target;
        setSelectedNode(node.data());

        // Highlight connected edges & neighbors
        cy.elements().removeClass('highlighted');
        node.neighborhood().add(node).addClass('highlighted');
      });

      cy.on('tap', (evt) => {
        if (evt.target === cy) {
          setSelectedNode(null);
          cy.elements().removeClass('highlighted');
        }
      });

      cyRef.current = cy;
    } catch (e) {
      console.error("Error setting up cytoscape:", e);
    }

    return () => {
      if (cyRef.current) {
        cyRef.current.destroy();
      }
    };
  }, [graphData]);

  const handleZoomIn = () => cyRef.current?.zoom(cyRef.current.zoom() * 1.25);
  const handleZoomOut = () => cyRef.current?.zoom(cyRef.current.zoom() * 0.8);
  const handleFit = () => cyRef.current?.fit();

  return (
    <section 
      id="stage-cluster" 
      className="glass-panel" 
      style={{ padding: "32px", position: "relative", overflow: "hidden" }}
    >
      {/* Top Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "20px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "14px" }}>
          <div style={{
            width: "44px",
            height: "44px",
            borderRadius: "10px",
            background: "var(--accent-purple-dim)",
            border: "1px solid rgba(157, 78, 221, 0.4)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            boxShadow: "0 0 20px rgba(157, 78, 221, 0.3)"
          }}>
            <Network size={22} color="var(--accent-purple)" />
          </div>
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
              <h3 className="font-display" style={{ fontSize: "20px" }}>
                Stage 05: Payee Syndicate Correlation Graph
              </h3>
              <span className="cyber-badge cyber-badge-red">
                <ShieldAlert size={12} />
                5 SCAM DOMAINS CORRELATED
              </span>
            </div>
            <p className="text-secondary font-mono" style={{ fontSize: "12px" }}>
              Interactive NetworkX/Cytoscape Knowledge Graph &bull; Trace the Money to Dismantle Cartel
            </p>
          </div>
        </div>

        {/* Live Disruption Score Pill */}
        <div style={{
          padding: "8px 16px",
          background: "rgba(0, 240, 255, 0.08)",
          border: "1px solid var(--border-cyan)",
          borderRadius: "8px",
          textAlign: "right"
        }}>
          <span className="font-mono text-muted" style={{ fontSize: "10px" }}>ESTIMATED LOSS PREVENTED</span>
          <p className="font-display text-cyan" style={{ fontSize: "20px", fontWeight: 800 }}>
            ₹42.00 LAKHS
          </p>
        </div>
      </div>

      {/* Interactive Cytoscape Viewport */}
      <div style={{ position: "relative", height: "480px", borderRadius: "12px", border: "1px solid var(--border-cyan)", overflow: "hidden", background: "#05060b" }}>
        {/* Cytoscape Canvas Container */}
        <div ref={containerRef} style={{ width: "100%", height: "100%" }} />

        {/* Floating HUD Graph Controls */}
        <div style={{
          position: "absolute",
          top: "16px",
          right: "16px",
          display: "flex",
          flexDirection: "column",
          gap: "8px",
          zIndex: 10
        }}>
          <button 
            onClick={handleZoomIn} 
            title="Zoom In"
            className="glass-panel" 
            style={{ width: "34px", height: "34px", display: "flex", alignItems: "center", justifyContent: "center", cursor: "pointer", color: "var(--accent-cyan)", border: "1px solid rgba(0, 240, 255, 0.2)" }}
          >
            <ZoomIn size={16} />
          </button>
          <button 
            onClick={handleZoomOut} 
            title="Zoom Out"
            className="glass-panel" 
            style={{ width: "34px", height: "34px", display: "flex", alignItems: "center", justifyContent: "center", cursor: "pointer", color: "var(--accent-cyan)", border: "1px solid rgba(0, 240, 255, 0.2)" }}
          >
            <ZoomOut size={16} />
          </button>
          <button 
            onClick={handleFit} 
            title="Fit to Screen"
            className="glass-panel" 
            style={{ width: "34px", height: "34px", display: "flex", alignItems: "center", justifyContent: "center", cursor: "pointer", color: "var(--accent-cyan)", border: "1px solid rgba(0, 240, 255, 0.2)" }}
          >
            <Maximize2 size={16} />
          </button>
        </div>

        {/* Legend */}
        <div style={{
          position: "absolute",
          bottom: "16px",
          left: "16px",
          padding: "8px 14px",
          background: "rgba(10, 11, 20, 0.85)",
          backdropFilter: "blur(8px)",
          borderRadius: "8px",
          border: "1px solid rgba(255, 255, 255, 0.08)",
          display: "flex",
          gap: "14px",
          fontSize: "11px",
          fontFamily: "var(--font-mono)",
          zIndex: 10
        }}>
          <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
            <span style={{ width: "10px", height: "10px", borderRadius: "50%", background: "#ff2a55", display: "inline-block" }} />
            <span className="text-muted">Rogue Payee VPA</span>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
            <span style={{ width: "10px", height: "10px", transform: "rotate(45deg)", background: "#00f0ff", display: "inline-block" }} />
            <span className="text-muted">Phishing Domain</span>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
            <span style={{ width: "10px", height: "10px", borderRadius: "50%", background: "#9d4edd", display: "inline-block" }} />
            <span className="text-muted">Shared Contact / IP</span>
          </div>
        </div>

        {/* Selected Node Details Drawer */}
        {selectedNode && (
          <div style={{
            position: "absolute",
            top: "16px",
            left: "16px",
            maxWidth: "320px",
            padding: "16px",
            background: "rgba(12, 14, 25, 0.95)",
            backdropFilter: "blur(12px)",
            borderRadius: "10px",
            border: "1px solid var(--border-cyan)",
            boxShadow: "0 8px 30px rgba(0,0,0,0.8)",
            zIndex: 10,
            fontSize: "12px",
            fontFamily: "var(--font-mono)"
          }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" }}>
              <span className="cyber-badge cyber-badge-cyan" style={{ fontSize: "9px" }}>
                NODE: {selectedNode.type?.toUpperCase()}
              </span>
              <button 
                onClick={() => setSelectedNode(null)} 
                style={{ background: "transparent", border: "none", color: "var(--text-muted)", cursor: "pointer" }}
              >
                &times;
              </button>
            </div>

            <p className="font-display text-primary" style={{ fontSize: "14px", fontWeight: 700, wordBreak: "break-all" }}>
              {selectedNode.label}
            </p>

            {selectedNode.metadata && (
              <div style={{ marginTop: "10px", display: "flex", flexDirection: "column", gap: "4px", color: "var(--text-secondary)" }}>
                <div>Bank: <span className="text-cyan">{selectedNode.metadata.bank}</span></div>
                <div>Account: <span className="text-primary">{selectedNode.metadata.account}</span></div>
                <div>Volume: <span className="text-green">₹{(selectedNode.metadata.total_revenue_est_inr / 100000).toFixed(1)} Lakhs</span></div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Disruption Metrics Action Bar */}
      <div style={{
        marginTop: "18px",
        display: "grid",
        gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))",
        gap: "14px"
      }}>
        <div className="glass-panel" style={{ padding: "14px", display: "flex", alignItems: "center", gap: "12px" }}>
          <div style={{ width: "36px", height: "36px", borderRadius: "8px", background: "var(--accent-red-dim)", border: "1px solid var(--border-red)", display: "flex", alignItems: "center", justifyContent: "center" }}>
            <ShieldAlert size={18} color="var(--accent-red)" />
          </div>
          <div>
            <span className="font-mono text-muted" style={{ fontSize: "11px" }}>DOMAINS SHUTDOWN</span>
            <p className="font-display text-primary" style={{ fontSize: "18px", fontWeight: 700 }}>
              5 Infiltration Funnels
            </p>
          </div>
        </div>

        <div className="glass-panel" style={{ padding: "14px", display: "flex", alignItems: "center", gap: "12px" }}>
          <div style={{ width: "36px", height: "36px", borderRadius: "8px", background: "var(--accent-green-dim)", border: "1px solid var(--border-green)", display: "flex", alignItems: "center", justifyContent: "center" }}>
            <DollarSign size={18} color="var(--accent-green)" />
          </div>
          <div>
            <span className="font-mono text-muted" style={{ fontSize: "11px" }}>SINGLE-POINT SYNDICATE FREEZE</span>
            <p className="font-display text-green" style={{ fontSize: "18px", fontWeight: 700 }}>
              1 VPA Freezes Whole Ring
            </p>
          </div>
        </div>

        <div className="glass-panel" style={{ padding: "14px", display: "flex", alignItems: "center", gap: "12px" }}>
          <div style={{ width: "36px", height: "36px", borderRadius: "8px", background: "var(--accent-cyan-dim)", border: "1px solid var(--border-cyan)", display: "flex", alignItems: "center", justifyContent: "center" }}>
            <Share2 size={18} color="var(--accent-cyan)" />
          </div>
          <div>
            <span className="font-mono text-muted" style={{ fontSize: "11px" }}>CORRELATION CONFIDENCE</span>
            <p className="font-display text-cyan" style={{ fontSize: "18px", fontWeight: 700 }}>
              100% Deterministic Match
            </p>
          </div>
        </div>
      </div>
    </section>
  );
}
