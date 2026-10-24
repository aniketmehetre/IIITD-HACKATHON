"use client";

import React from "react";
import { 
  Terminal, 
  ShieldCheck, 
  Clock, 
  Globe, 
  Hash, 
  Radio, 
  CheckCircle2, 
  ExternalLink,
  Lock,
  Layers
} from "lucide-react";
import { CaseSummary } from "@/lib/types";

interface IntakeStagePanelProps {
  caseData: CaseSummary;
}

export function IntakeStagePanel({ caseData }: IntakeStagePanelProps) {
  const events = caseData.events.filter(e => e.stage === 'intake');

  return (
    <section id="stage-intake" className="glass-panel" style={{ padding: "32px", position: "relative", overflow: "hidden" }}>
      {/* Decorative Cyber Header Accents */}
      <div style={{
        position: "absolute",
        top: 0,
        left: 0,
        width: "120px",
        height: "2px",
        background: "linear-gradient(90deg, var(--accent-cyan), transparent)"
      }} />

      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "24px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "14px" }}>
          <div style={{
            width: "44px",
            height: "44px",
            borderRadius: "10px",
            background: "var(--accent-cyan-dim)",
            border: "1px solid var(--border-cyan)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            boxShadow: "0 0 16px rgba(0, 240, 255, 0.2)"
          }}>
            <Terminal size={22} color="var(--accent-cyan)" />
          </div>
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
              <h3 className="font-display" style={{ fontSize: "20px" }}>
                Stage 01: Case Intake & Multimodal Ingestion
              </h3>
              <span className="cyber-badge cyber-badge-green">
                <CheckCircle2 size={12} />
                INGESTION VALIDATED
              </span>
            </div>
            <p className="text-secondary font-mono" style={{ fontSize: "12px" }}>
              Autonomous Ingestion Agent &bull; Protocol Verification & Isolation
            </p>
          </div>
        </div>

        <div className="font-mono text-muted" style={{ fontSize: "12px", textAlign: "right" }}>
          <div>INGESTION ID: <span className="text-cyan">{caseData.id}</span></div>
          <div>TIMESTAMP: {caseData.created_at}</div>
        </div>
      </div>

      {/* Main Target Ingestion Card */}
      <div 
        className="glass-panel" 
        style={{ 
          padding: "20px", 
          backgroundColor: "rgba(6, 7, 12, 0.85)", 
          border: "1px solid var(--border-cyan)",
          borderRadius: "10px",
          position: "relative",
          marginBottom: "24px"
        }}
      >
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "12px" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <span className="pulsing-dot pulsing-dot-green" />
            <span className="font-mono text-cyan" style={{ fontSize: "12px", fontWeight: 600 }}>
              INGESTED ARTIFACT [{caseData.type.toUpperCase()}]
            </span>
          </div>
          <span className="cyber-badge cyber-badge-cyan" style={{ fontSize: "10px" }}>
            <Lock size={11} />
            SANDBOX ROUTED
          </span>
        </div>

        {/* Target Display */}
        <div style={{
          display: "flex",
          alignItems: "center",
          gap: "12px",
          padding: "12px 16px",
          background: "rgba(0, 240, 255, 0.04)",
          border: "1px solid rgba(0, 240, 255, 0.15)",
          borderRadius: "8px",
          wordBreak: "break-all"
        }}>
          <Globe size={18} color="var(--accent-cyan)" style={{ flexShrink: 0 }} />
          <span className="font-mono" style={{ fontSize: "15px", color: "#ffffff", fontWeight: 600 }}>
            {caseData.target}
          </span>
        </div>

        {/* Extracted Ingestion Metadata Pills */}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: "12px", marginTop: "16px" }}>
          <div style={{ padding: "10px 14px", background: "rgba(255,255,255,0.02)", borderRadius: "6px", border: "1px solid rgba(255,255,255,0.05)" }}>
            <span className="text-muted font-mono" style={{ fontSize: "11px" }}>INGESTION METHOD</span>
            <p className="font-mono text-cyan" style={{ fontSize: "13px", fontWeight: 600, marginTop: "2px" }}>
              Citizen Telemetry Feed
            </p>
          </div>

          <div style={{ padding: "10px 14px", background: "rgba(255,255,255,0.02)", borderRadius: "6px", border: "1px solid rgba(255,255,255,0.05)" }}>
            <span className="text-muted font-mono" style={{ fontSize: "11px" }}>PROTOCOL INTEGRITY</span>
            <p className="font-mono text-green" style={{ fontSize: "13px", fontWeight: 600, marginTop: "2px" }}>
              TLS Encrypted (Port 443)
            </p>
          </div>

          <div style={{ padding: "10px 14px", background: "rgba(255,255,255,0.02)", borderRadius: "6px", border: "1px solid rgba(255,255,255,0.05)" }}>
            <span className="text-muted font-mono" style={{ fontSize: "11px" }}>QUEUE STATUS</span>
            <p className="font-mono text-secondary" style={{ fontSize: "13px", fontWeight: 600, marginTop: "2px" }}>
              Dispatched to Triage Engine
            </p>
          </div>
        </div>
      </div>

      {/* Stage 1 Real-time Events Log */}
      <div>
        <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "10px" }}>
          <Radio size={14} color="var(--accent-cyan)" />
          <span className="font-mono text-muted" style={{ fontSize: "11px", fontWeight: 600 }}>
            STAGE 01 AUDIT TRAIL
          </span>
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
          {events.length > 0 ? (
            events.map((evt) => (
              <div 
                key={evt.id} 
                style={{ 
                  display: "flex", 
                  alignItems: "center", 
                  gap: "12px", 
                  padding: "8px 12px", 
                  background: "rgba(255, 255, 255, 0.02)", 
                  borderRadius: "6px", 
                  border: "1px solid rgba(255, 255, 255, 0.04)",
                  fontSize: "12px",
                  fontFamily: "var(--font-mono)"
                }}
              >
                <span className="text-cyan">[{evt.timestamp}]</span>
                <span className="text-green font-bold">VERIFIED:</span>
                <span style={{ color: "var(--text-secondary)" }}>{evt.message}</span>
              </div>
            ))
          ) : (
            <div style={{ padding: "10px", fontSize: "12px", color: "var(--text-muted)", fontFamily: "var(--font-mono)" }}>
              Target ingested into STING intake pipeline. Isolation token generated.
            </div>
          )}
        </div>
      </div>
    </section>
  );
}
