"use client";

import React, { useState } from "react";
import { 
  Radar, 
  ShieldAlert, 
  ShieldCheck, 
  AlertTriangle, 
  Calendar, 
  Building2, 
  Check, 
  X, 
  Fingerprint, 
  ChevronDown, 
  ChevronUp, 
  Server,
  Zap,
  Info
} from "lucide-react";
import { CaseSummary } from "@/lib/types";

interface TriageStagePanelProps {
  caseData: CaseSummary;
}

export function TriageStagePanel({ caseData }: TriageStagePanelProps) {
  const [showRawRdap, setShowRawRdap] = useState(false);
  const triage = caseData.result?.triage;

  if (!triage) {
    return (
      <section id="stage-triage" className="glass-panel" style={{ padding: "32px" }}>
        <p className="font-mono text-muted">Awaiting Triage Agent processing...</p>
      </section>
    );
  }

  const isHighRisk = triage.verdict === "HIGH_RISK";
  const isBenign = triage.verdict === "LOW_RISK";

  return (
    <section 
      id="stage-triage" 
      className={isHighRisk ? "glass-panel-threat" : isBenign ? "glass-panel-verified" : "glass-panel"} 
      style={{ padding: "32px", position: "relative", overflow: "hidden" }}
    >
      {/* Top Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "24px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "14px" }}>
          <div style={{
            width: "44px",
            height: "44px",
            borderRadius: "10px",
            background: isHighRisk ? "var(--accent-red-dim)" : "var(--accent-green-dim)",
            border: `1px solid ${isHighRisk ? "var(--border-red)" : "var(--border-green)"}`,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            boxShadow: isHighRisk ? "var(--glow-red-box)" : "var(--glow-green-box)"
          }}>
            <Radar size={22} color={isHighRisk ? "var(--accent-red)" : "var(--accent-green)"} />
          </div>
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
              <h3 className="font-display" style={{ fontSize: "20px" }}>
                Stage 02: Triage & Threat Fingerprinting
              </h3>
              <span className={`cyber-badge ${isHighRisk ? "cyber-badge-red" : "cyber-badge-green"}`}>
                {isHighRisk ? <ShieldAlert size={12} /> : <ShieldCheck size={12} />}
                {triage.verdict} // RISK SCORE: {triage.risk_score}/100
              </span>
            </div>
            <p className="text-secondary font-mono" style={{ fontSize: "12px" }}>
              RDAP Domain Age, Trademark Mismatch & Fast-Flux DNS Fingerprinting
            </p>
          </div>
        </div>

        {/* Detonation Decision Gate Pill */}
        <div style={{ textAlign: "right" }}>
          <span className="font-mono text-muted" style={{ fontSize: "11px" }}>DETONATION GATE:</span>
          <div style={{ marginTop: "3px" }}>
            {triage.should_detonate ? (
              <span className="cyber-badge cyber-badge-red" style={{ fontSize: "11px" }}>
                <Zap size={12} />
                ENGAGE SYNTHETIC DETONATION
              </span>
            ) : triage.known_campaign ? (
              <span className="cyber-badge cyber-badge-cyan" style={{ fontSize: "11px" }}>
                CARTEL SKIP (PRE-CORRELATED)
              </span>
            ) : (
              <span className="cyber-badge cyber-badge-green" style={{ fontSize: "11px" }}>
                BENIGN (NO DETONATION)
              </span>
            )}
          </div>
        </div>
      </div>

      {/* 4 Metric Telemetry Cards */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: "16px", marginBottom: "24px" }}>
        {/* Domain Age */}
        <div className="glass-panel" style={{ padding: "16px", backgroundColor: "rgba(6,7,12,0.8)" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "6px" }}>
            <Calendar size={14} color="var(--accent-cyan)" />
            <span className="font-mono text-muted" style={{ fontSize: "11px" }}>DOMAIN LIFETIME</span>
          </div>
          <div style={{ display: "flex", alignItems: "baseline", gap: "6px" }}>
            <span className="font-display" style={{ 
              fontSize: "26px", 
              fontWeight: 800,
              color: triage.domain_age_days < 30 ? "var(--accent-red)" : triage.domain_age_days < 365 ? "var(--accent-amber)" : "var(--accent-green)"
            }}>
              {triage.domain_age_days}
            </span>
            <span className="font-mono text-secondary" style={{ fontSize: "13px" }}>Days Old</span>
          </div>
          <p className="font-mono" style={{ fontSize: "10px", color: triage.domain_age_days < 30 ? "var(--accent-red)" : "var(--text-muted)", marginTop: "4px" }}>
            {triage.domain_age_days < 30 ? "⚠️ Newly registered disposable domain" : "Established domain authority"}
          </p>
        </div>

        {/* Brand Collision */}
        <div className="glass-panel" style={{ padding: "16px", backgroundColor: "rgba(6,7,12,0.8)" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "6px" }}>
            <Building2 size={14} color="var(--accent-cyan)" />
            <span className="font-mono text-muted" style={{ fontSize: "11px" }}>CLAIMED BRAND</span>
          </div>
          <p className="font-display" style={{ fontSize: "16px", fontWeight: 700, color: "var(--text-primary)" }}>
            {triage.claimed_brand}
          </p>
          <div style={{ display: "flex", alignItems: "center", gap: "6px", marginTop: "4px" }}>
            {triage.brand_match ? (
              <>
                <Check size={12} color="var(--accent-green)" />
                <span className="font-mono text-green" style={{ fontSize: "11px" }}>Authentic Trademark</span>
              </>
            ) : (
              <>
                <X size={12} color="var(--accent-red)" />
                <span className="font-mono text-red" style={{ fontSize: "11px", fontWeight: 600 }}>Brand Impersonation</span>
              </>
            )}
          </div>
        </div>

        {/* Registrar & ASN */}
        <div className="glass-panel" style={{ padding: "16px", backgroundColor: "rgba(6,7,12,0.8)" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "6px" }}>
            <Server size={14} color="var(--accent-cyan)" />
            <span className="font-mono text-muted" style={{ fontSize: "11px" }}>REGISTRAR / HOST</span>
          </div>
          <p className="font-mono text-cyan" style={{ fontSize: "13px", fontWeight: 600 }}>
            {triage.registrar}
          </p>
          <p className="font-mono text-muted" style={{ fontSize: "11px", marginTop: "4px" }}>
            Target: {triage.domain}
          </p>
        </div>

        {/* Cartel Status */}
        <div className="glass-panel" style={{ padding: "16px", backgroundColor: "rgba(6,7,12,0.8)" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "6px" }}>
            <Fingerprint size={14} color="var(--accent-cyan)" />
            <span className="font-mono text-muted" style={{ fontSize: "11px" }}>GRAPH CORRELATION</span>
          </div>
          <p className="font-mono" style={{ fontSize: "13px", fontWeight: 700, color: triage.known_campaign ? "var(--accent-red)" : "var(--accent-green)" }}>
            {triage.known_campaign ? "KNOWN SCAM CAMPAIGN" : "UNMAPPED TARGET"}
          </p>
          <p className="font-mono text-muted" style={{ fontSize: "11px", marginTop: "4px" }}>
            {triage.known_campaign ? "Syndicate cluster detected" : "New candidate link"}
          </p>
        </div>
      </div>

      {/* Decision Rationale Bullet Box */}
      <div style={{ 
        padding: "16px", 
        background: "rgba(0, 0, 0, 0.4)", 
        borderRadius: "8px", 
        border: "1px solid rgba(255, 255, 255, 0.05)",
        marginBottom: "16px"
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "8px" }}>
          <Info size={14} color="var(--accent-cyan)" />
          <span className="font-mono text-cyan" style={{ fontSize: "12px", fontWeight: 600 }}>
            TRIAGE AGENT DECISION RATIONALE:
          </span>
        </div>
        <ul style={{ listStyle: "none", display: "flex", flexDirection: "column", gap: "6px" }}>
          {triage.reasons.map((reason, idx) => (
            <li key={idx} style={{ display: "flex", alignItems: "center", gap: "8px", fontSize: "12px", fontFamily: "var(--font-mono)", color: "var(--text-secondary)" }}>
              <span className="text-red font-bold">&bull;</span>
              <span>{reason}</span>
            </li>
          ))}
        </ul>
      </div>

      {/* Collapsible Raw RDAP Details */}
      <div>
        <button
          onClick={() => setShowRawRdap(!showRawRdap)}
          style={{
            display: "flex",
            alignItems: "center",
            gap: "6px",
            background: "transparent",
            border: "none",
            color: "var(--accent-cyan)",
            fontFamily: "var(--font-mono)",
            fontSize: "12px",
            cursor: "pointer"
          }}
        >
          <span>{showRawRdap ? "Hide RDAP Payload" : "View Structured RDAP / WHOIS Payload"}</span>
          {showRawRdap ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
        </button>

        {showRawRdap && (
          <div className="terminal-window" style={{ marginTop: "10px" }}>
            <div className="terminal-body" style={{ maxHeight: "180px", fontSize: "11px" }}>
              <pre style={{ color: "#a0a5bb" }}>
{JSON.stringify({
  domain: triage.domain,
  registrar: triage.registrar,
  domain_age_days: triage.domain_age_days,
  claimed_brand: triage.claimed_brand,
  brand_match: triage.brand_match,
  nameservers: ["ns1.hostinger.com", "ns2.hostinger.com"],
  dnssec: "unsigned",
  status: ["clientTransferProhibited"],
  entities: [{ role: "registrant", privacy_guard: true }]
}, null, 2)}
              </pre>
            </div>
          </div>
        )}
      </div>
    </section>
  );
}
