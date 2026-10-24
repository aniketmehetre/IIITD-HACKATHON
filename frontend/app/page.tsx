"use client";

import React from "react";
import { 
  ShieldAlert, 
  Radar, 
  Terminal, 
  Network, 
  FileCheck2, 
  Zap, 
  ArrowRight,
  ExternalLink,
  Lock,
  Cpu
} from "lucide-react";

export default function Home() {
  const stages = [
    { num: "01", name: "Intake", icon: Terminal, desc: "Multimodal ingestion (links, QR, SMS)", color: "cyan" },
    { num: "02", name: "Triage", icon: Radar, desc: "RDAP, WHOIS & brand fingerprinting", color: "cyan" },
    { num: "03", name: "Detonate", icon: Zap, desc: "TinyFish synthetic victim funnel traversal", color: "red" },
    { num: "04", name: "Enrich", icon: Cpu, desc: "UPI/PSP resolve & QR payload decoding", color: "purple" },
    { num: "05", name: "Cluster", icon: Network, desc: "Syndicate graph & mule cartel correlation", color: "purple" },
    { num: "06", name: "Act", icon: FileCheck2, desc: "SHA-256 evidence PDF & I4C takedown", color: "green" },
  ];

  return (
    <div style={{ maxWidth: "1280px", margin: "0 auto", padding: "40px 24px" }}>
      {/* Top HUD Header */}
      <header style={{ 
        display: "flex", 
        justifyContent: "space-between", 
        alignItems: "center",
        paddingBottom: "32px",
        borderBottom: "1px solid var(--border-subtle)" 
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: "14px" }}>
          <div style={{
            width: "42px",
            height: "42px",
            borderRadius: "10px",
            background: "linear-gradient(135deg, rgba(0, 240, 255, 0.2), rgba(255, 42, 85, 0.2))",
            border: "1px solid var(--border-cyan)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            boxShadow: "0 0 20px rgba(0, 240, 255, 0.25)"
          }}>
            <ShieldAlert size={22} color="var(--accent-cyan)" />
          </div>
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
              <h1 className="font-display" style={{ fontSize: "24px", letterSpacing: "0.08em" }}>
                STING <span className="text-cyan font-mono" style={{ fontSize: "14px", fontWeight: 400 }}>// OPS-CORE</span>
              </h1>
              <span className="cyber-badge cyber-badge-cyan">
                v1.0.0-PROD
              </span>
            </div>
            <p className="text-muted" style={{ fontSize: "12px", fontFamily: "var(--font-mono)" }}>
              SYNTHETIC THREAT INFILTRATION & NETWORK GRAPHING
            </p>
          </div>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: "16px" }}>
          <div className="glass-panel" style={{ padding: "8px 14px", display: "flex", alignItems: "center", gap: "10px" }}>
            <span className="pulsing-dot pulsing-dot-green" />
            <span className="font-mono text-green" style={{ fontSize: "12px", fontWeight: 600 }}>
              DEFENSE GRID ONLINE
            </span>
          </div>
          <div className="glass-panel" style={{ padding: "8px 14px", display: "flex", alignItems: "center", gap: "8px" }}>
            <Lock size={14} color="var(--accent-cyan)" />
            <span className="font-mono text-muted" style={{ fontSize: "12px" }}>
              SANDBOX ISOLATED
            </span>
          </div>
        </div>
      </header>

      {/* Hero Section */}
      <section style={{ padding: "64px 0 48px", textAlign: "center" }}>
        <div style={{ display: "inline-flex", marginBottom: "20px" }}>
          <span className="cyber-badge cyber-badge-cyan" style={{ padding: "6px 14px", fontSize: "12px" }}>
            <Radar size={14} style={{ animation: "spin 4s linear infinite" }} />
            AUTONOMOUS CYBER DEFENSE PIPELINE
          </span>
        </div>
        <h2 className="font-display text-gradient-cyan" style={{ fontSize: "48px", lineHeight: "1.15", marginBottom: "18px", maxWidth: "900px", margin: "0 auto 18px" }}>
          From Phishing Link to Syndicate Payee in Seconds
        </h2>
        <p className="text-secondary" style={{ fontSize: "17px", maxWidth: "680px", margin: "0 auto 36px", lineHeight: "1.6" }}>
          STING deploys autonomous synthetic victims to traverse deceptive funnels, uncover hidden UPI & bank payees, and dismantle entire cybercrime cartels.
        </p>

        {/* Action Bar Preview */}
        <div className="glass-panel-cyan" style={{ maxWidth: "780px", margin: "0 auto", padding: "8px 10px", display: "flex", alignItems: "center", gap: "12px" }}>
          <div style={{ paddingLeft: "12px", display: "flex", alignItems: "center" }}>
            <Terminal size={18} color="var(--accent-cyan)" />
          </div>
          <input 
            type="text" 
            readOnly
            value="https://pmcares-relief-claim.sbi-update.fake.in/kyc-verify" 
            className="font-mono"
            style={{
              flex: 1,
              background: "transparent",
              border: "none",
              outline: "none",
              color: "var(--text-primary)",
              fontSize: "14px",
              letterSpacing: "0.02em"
            }}
          />
          <button className="cyber-button-primary">
            <span>DETONATE TARGET</span>
            <ArrowRight size={16} />
          </button>
        </div>
      </section>

      {/* 6 Pipeline Stages Verification Grid */}
      <section style={{ marginTop: "32px" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end", marginBottom: "24px" }}>
          <div>
            <h3 className="font-display" style={{ fontSize: "20px" }}>
              Autonomous Investigation Architecture
            </h3>
            <p className="text-muted" style={{ fontSize: "13px" }}>
              Six-stage coordinated multi-agent execution pipeline
            </p>
          </div>
          <span className="font-mono text-cyan" style={{ fontSize: "12px" }}>
            STAGE VERIFICATION: READY
          </span>
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))", gap: "18px" }}>
          {stages.map((stage) => {
            const Icon = stage.icon;
            return (
              <div 
                key={stage.num} 
                className="glass-panel" 
                style={{ 
                  padding: "24px",
                  position: "relative",
                  overflow: "hidden"
                }}
              >
                <div style={{ 
                  display: "flex", 
                  justifyContent: "space-between", 
                  alignItems: "flex-start",
                  marginBottom: "16px" 
                }}>
                  <div style={{
                    width: "38px",
                    height: "38px",
                    borderRadius: "8px",
                    background: stage.color === "red" 
                      ? "var(--accent-red-dim)" 
                      : stage.color === "purple" 
                      ? "var(--accent-purple-dim)" 
                      : stage.color === "green" 
                      ? "var(--accent-green-dim)" 
                      : "var(--accent-cyan-dim)",
                    border: `1px solid ${
                      stage.color === "red" 
                        ? "var(--border-red)" 
                        : stage.color === "purple" 
                        ? "rgba(157, 78, 221, 0.3)" 
                        : stage.color === "green" 
                        ? "var(--border-green)" 
                        : "var(--border-cyan)"
                    }`,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center"
                  }}>
                    <Icon size={20} color={
                      stage.color === "red" 
                        ? "var(--accent-red)" 
                        : stage.color === "purple" 
                        ? "var(--accent-purple)" 
                        : stage.color === "green" 
                        ? "var(--accent-green)" 
                        : "var(--accent-cyan)"
                    } />
                  </div>
                  <span className="font-mono text-muted" style={{ fontSize: "13px", fontWeight: 700 }}>
                    STAGE {stage.num}
                  </span>
                </div>

                <h4 className="font-display" style={{ fontSize: "18px", marginBottom: "6px" }}>
                  {stage.name} Agent
                </h4>
                <p className="text-secondary" style={{ fontSize: "13px", lineHeight: "1.5" }}>
                  {stage.desc}
                </p>

                <div style={{ 
                  marginTop: "20px", 
                  paddingTop: "14px", 
                  borderTop: "1px solid var(--border-subtle)", 
                  display: "flex", 
                  alignItems: "center", 
                  justifyContent: "space-between" 
                }}>
                  <span className="font-mono text-muted" style={{ fontSize: "11px" }}>
                    STATUS
                  </span>
                  <span className="font-mono text-cyan" style={{ fontSize: "11px", fontWeight: 600 }}>
                    CONFIGURED &bull; READY
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      </section>

      {/* Footer Info */}
      <footer style={{ 
        marginTop: "80px", 
        paddingTop: "24px", 
        borderTop: "1px solid var(--border-subtle)",
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center",
        fontSize: "12px",
        color: "var(--text-muted)"
      }}>
        <div className="font-mono">
          STING PLATFORM &bull; TEAM VOID MAIN &bull; IIITD HACKATHON
        </div>
        <div style={{ display: "flex", gap: "20px" }}>
          <span>Contract: shared/api-schema.json</span>
          <span>Engine: Next.js 16 + Lenis + Motion</span>
        </div>
      </footer>
    </div>
  );
}
