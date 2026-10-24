"use client";

import React, { useState, useEffect } from "react";
import { Navbar, ViewMode } from "@/components/Navbar";
import { StageProgressRail } from "@/components/StageProgressRail";
import { CaseSubmissionBar } from "@/components/CaseSubmissionBar";
import { IntakeStagePanel } from "@/components/stages/IntakeStagePanel";
import { api } from "@/lib/api";
import { CaseSummary, InputType, PipelineStage } from "@/lib/types";
import { 
  ShieldAlert, 
  Terminal, 
  Radar, 
  Zap, 
  Cpu, 
  Network, 
  FileCheck2,
  AlertTriangle,
  ArrowRight,
  ExternalLink,
  Flame,
  CheckCircle2,
  Lock
} from "lucide-react";

export default function Home() {
  const [mode, setMode] = useState<ViewMode>("story");
  const [selectedCaseId, setSelectedCaseId] = useState<string>("c-pmcares-9281");
  const [activeCase, setActiveCase] = useState<CaseSummary | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);

  useEffect(() => {
    async function loadInitial() {
      try {
        const c = await api.getCaseStatus(selectedCaseId);
        setActiveCase(c);
      } catch (err) {
        console.error("Error loading case:", err);
      }
    }
    loadInitial();
  }, [selectedCaseId]);

  const handleAnalyze = async (type: InputType, content: string) => {
    setIsLoading(true);
    try {
      const created = await api.createCase(type, content);
      setActiveCase(created);
      setSelectedCaseId(created.id);
    } catch (err) {
      console.error("Error analyzing target:", err);
    } finally {
      setIsLoading(false);
    }
  };

  const currentStage: PipelineStage = activeCase?.current_stage || "intake";

  return (
    <div style={{ minHeight: "100vh", display: "flex", flexDirection: "column" }}>
      {/* Top Navbar */}
      <Navbar
        mode={mode}
        onModeChange={setMode}
        selectedCaseId={selectedCaseId}
        onCaseSelect={setSelectedCaseId}
      />

      {/* Stage Progress Rail */}
      <StageProgressRail currentStage={currentStage} />

      {/* Main Content Area */}
      <main style={{ flex: 1, padding: "32px 0 64px" }}>
        {/* Case Ingestion Bar */}
        <section style={{ marginBottom: "48px" }}>
          <CaseSubmissionBar onAnalyze={handleAnalyze} isLoading={isLoading} />
        </section>

        {/* Dynamic Display based on Mode */}
        {mode === "story" ? (
          /* STORY MODE: Narrative Stage Walkthrough */
          <div style={{ maxWidth: "1280px", margin: "0 auto", padding: "0 24px" }}>
            {/* Mission Hero Header */}
            <div style={{ textAlign: "center", marginBottom: "48px" }}>
              <div style={{ display: "inline-flex", marginBottom: "12px" }}>
                <span className="cyber-badge cyber-badge-cyan">
                  <ShieldAlert size={13} />
                  LIVE CASE FILE: #{activeCase?.id.toUpperCase()}
                </span>
              </div>
              <h2 className="font-display text-gradient-cyan" style={{ fontSize: "36px", marginBottom: "8px" }}>
                {activeCase?.target}
              </h2>
              <p className="text-secondary font-mono" style={{ fontSize: "14px" }}>
                STATUS: <span className="text-cyan font-bold">{activeCase?.status.toUpperCase()}</span> &bull; 
                ATTRIBUTION: <span className="text-red font-bold">{activeCase?.result?.attribution.toUpperCase() || "PENDING"}</span> &bull; 
                STAGE: <span className="text-green font-bold">{activeCase?.current_stage.toUpperCase()}</span>
              </p>
            </div>

            {/* Stage Anchor Panels */}
            <div style={{ display: "flex", flexDirection: "column", gap: "32px" }}>
              {/* STAGE 1: INTAKE */}
              {activeCase && <IntakeStagePanel caseData={activeCase} />}

              {/* STAGE 2: TRIAGE */}
              <section id="stage-triage" className="glass-panel" style={{ padding: "28px" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
                    <div style={{ width: "36px", height: "36px", borderRadius: "8px", background: "var(--accent-cyan-dim)", border: "1px solid var(--border-cyan)", display: "flex", alignItems: "center", justifyContent: "center" }}>
                      <Radar size={18} color="var(--accent-cyan)" />
                    </div>
                    <div>
                      <h3 className="font-display" style={{ fontSize: "18px" }}>Stage 02: Triage & Fingerprinting</h3>
                      <p className="text-muted font-mono" style={{ fontSize: "12px" }}>RDAP, WHOIS and Brand Collision Check</p>
                    </div>
                  </div>
                  <span className={`cyber-badge ${activeCase?.result?.triage.verdict === 'HIGH_RISK' ? 'cyber-badge-red' : 'cyber-badge-green'}`}>
                    {activeCase?.result?.triage.verdict || "ANALYZED"}
                  </span>
                </div>
                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))", gap: "14px" }}>
                  <div className="glass-panel" style={{ padding: "14px" }}>
                    <span className="text-muted font-mono" style={{ fontSize: "11px" }}>DOMAIN AGE</span>
                    <p className="font-display" style={{ fontSize: "20px", color: (activeCase?.result?.triage.domain_age_days ?? 0) < 30 ? "var(--accent-red)" : "var(--accent-green)" }}>
                      {activeCase?.result?.triage.domain_age_days ?? "--"} Days
                    </p>
                  </div>
                  <div className="glass-panel" style={{ padding: "14px" }}>
                    <span className="text-muted font-mono" style={{ fontSize: "11px" }}>REGISTRAR</span>
                    <p className="font-mono" style={{ fontSize: "14px", color: "var(--text-primary)" }}>
                      {activeCase?.result?.triage.registrar || "NameCheap"}
                    </p>
                  </div>
                  <div className="glass-panel" style={{ padding: "14px" }}>
                    <span className="text-muted font-mono" style={{ fontSize: "11px" }}>CLAIMED BRAND</span>
                    <p className="font-mono text-cyan" style={{ fontSize: "14px" }}>
                      {activeCase?.result?.triage.claimed_brand || "N/A"}
                    </p>
                  </div>
                  <div className="glass-panel" style={{ padding: "14px" }}>
                    <span className="text-muted font-mono" style={{ fontSize: "11px" }}>DETONATION GATE</span>
                    <p className="font-mono font-bold" style={{ fontSize: "14px", color: activeCase?.result?.triage.should_detonate ? "var(--accent-red)" : "var(--accent-green)" }}>
                      {activeCase?.result?.triage.should_detonate ? "DETONATE (HIGH RISK)" : "SKIP (BENIGN/KNOWN)"}
                    </p>
                  </div>
                </div>
              </section>

              {/* STAGE 3: DETONATE (Preview for Section 6) */}
              <section id="stage-detonate" className="glass-panel-cyan" style={{ padding: "28px" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
                    <div style={{ width: "36px", height: "36px", borderRadius: "8px", background: "var(--accent-red-dim)", border: "1px solid var(--border-red)", display: "flex", alignItems: "center", justifyContent: "center" }}>
                      <Zap size={18} color="var(--accent-red)" />
                    </div>
                    <div>
                      <h3 className="font-display" style={{ fontSize: "18px" }}>Stage 03: Autonomous Agent Detonation</h3>
                      <p className="text-muted font-mono" style={{ fontSize: "12px" }}>Synthetic victim navigation & intercept</p>
                    </div>
                  </div>
                  <span className="cyber-badge cyber-badge-cyan">EXTRACTED PAYEE</span>
                </div>
                <div style={{ background: "#06070c", borderRadius: "8px", padding: "18px", border: "1px solid var(--border-cyan)" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                    <div>
                      <span className="text-muted font-mono" style={{ fontSize: "11px" }}>INTERCEPTED UPI VPA</span>
                      <p className="font-mono text-cyan" style={{ fontSize: "22px", fontWeight: 700 }}>
                        {activeCase?.result?.payee.upi_vpa || "None (Benign Exit)"}
                      </p>
                      <p className="text-secondary font-mono" style={{ fontSize: "12px" }}>
                        PSP: {activeCase?.result?.payee.psp_name || "N/A"} &bull; Account: {activeCase?.result?.payee.bank_account || "N/A"}
                      </p>
                    </div>
                    <div style={{ textAlign: "right" }}>
                      <span className="cyber-badge cyber-badge-green" style={{ fontSize: "11px" }}>
                        <Lock size={12} />
                        0 INR EXPENDED
                      </span>
                    </div>
                  </div>
                </div>
              </section>

              {/* STAGE 4: ENRICH */}
              <section id="stage-enrich" className="glass-panel" style={{ padding: "28px" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
                    <div style={{ width: "36px", height: "36px", borderRadius: "8px", background: "var(--accent-purple-dim)", border: "1px solid rgba(157, 78, 221, 0.3)", display: "flex", alignItems: "center", justifyContent: "center" }}>
                      <Cpu size={18} color="var(--accent-purple)" />
                    </div>
                    <div>
                      <h3 className="font-display" style={{ fontSize: "18px" }}>Stage 04: Enrichment & Intelligence Resolution</h3>
                      <p className="text-muted font-mono" style={{ fontSize: "12px" }}>PSP identification and QR code payload dissection</p>
                    </div>
                  </div>
                  <span className="cyber-badge cyber-badge-purple">RESOLVED</span>
                </div>
                <p className="font-mono text-secondary" style={{ fontSize: "13px" }}>
                  Resolved Bank: <span className="text-cyan font-bold">{activeCase?.result?.enrichment.bank_name || "N/A"}</span> ({activeCase?.result?.enrichment.resolved_psp})
                </p>
              </section>

              {/* STAGE 5: CLUSTER (Syndicate Graph Preview) */}
              <section id="stage-cluster" className="glass-panel" style={{ padding: "28px" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
                    <div style={{ width: "36px", height: "36px", borderRadius: "8px", background: "var(--accent-purple-dim)", border: "1px solid rgba(157, 78, 221, 0.3)", display: "flex", alignItems: "center", justifyContent: "center" }}>
                      <Network size={18} color="var(--accent-purple)" />
                    </div>
                    <div>
                      <h3 className="font-display" style={{ fontSize: "18px" }}>Stage 05: Syndicate Correlation Network</h3>
                      <p className="text-muted font-mono" style={{ fontSize: "12px" }}>Graph correlation across shared mule infrastructure</p>
                    </div>
                  </div>
                  <span className="cyber-badge cyber-badge-red">
                    {activeCase?.result?.cluster.size ? `${activeCase?.result?.cluster.size} DOMAINS LINKED` : "0 LINKED"}
                  </span>
                </div>
                <p className="font-mono text-muted" style={{ fontSize: "13px" }}>
                  Cluster ID: <span className="text-cyan">{activeCase?.result?.cluster.cluster_id || "none"}</span> &bull; 
                  Shared Identifiers: {activeCase?.result?.cluster.shared_identifiers.join(", ") || "None"}
                </p>
              </section>

              {/* STAGE 6: ACT */}
              <section id="stage-act" className="glass-panel-verified" style={{ padding: "28px" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
                    <div style={{ width: "36px", height: "36px", borderRadius: "8px", background: "var(--accent-green-dim)", border: "1px solid var(--border-green)", display: "flex", alignItems: "center", justifyContent: "center" }}>
                      <FileCheck2 size={18} color="var(--accent-green)" />
                    </div>
                    <div>
                      <h3 className="font-display" style={{ fontSize: "18px" }}>Stage 06: Evidence Vault & Takedown Dispatch</h3>
                      <p className="text-muted font-mono" style={{ fontSize: "12px" }}>Pre-filled I4C, Bank Lien & CERT-In dossiers</p>
                    </div>
                  </div>
                  <span className="cyber-badge cyber-badge-green">READY FOR SIGN-OFF</span>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <div>
                    <span className="font-mono text-muted" style={{ fontSize: "11px" }}>EVIDENCE SHA-256 HASH</span>
                    <p className="font-mono text-green" style={{ fontSize: "13px" }}>
                      {activeCase?.result?.evidence_hash || "N/A"}
                    </p>
                  </div>
                  <button className="cyber-button-primary">
                    <span>APPROVE TAKEDOWN</span>
                    <ArrowRight size={15} />
                  </button>
                </div>
              </section>
            </div>
          </div>
        ) : (
          /* WAR ROOM MODE: Live Ops Terminal & Matrix */
          <div style={{ maxWidth: "1400px", margin: "0 auto", padding: "0 24px" }}>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 380px", gap: "24px" }}>
              {/* Left: Intelligence Console */}
              <div className="terminal-window">
                <div className="terminal-header">
                  <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                    <span className="pulsing-dot pulsing-dot-red" />
                    <span className="font-mono text-red" style={{ fontSize: "12px", fontWeight: 700 }}>
                      WAR ROOM // LIVE OPS DISPATCH
                    </span>
                  </div>
                  <span className="font-mono text-muted" style={{ fontSize: "11px" }}>
                    FEED_RATE: 200ms
                  </span>
                </div>
                <div className="terminal-body">
                  {activeCase?.events.map((evt) => (
                    <div key={evt.id} style={{ marginBottom: "10px", display: "flex", gap: "10px" }}>
                      <span className="text-muted" style={{ minWidth: "65px" }}>[{evt.timestamp}]</span>
                      <span className={`cyber-badge ${
                        evt.level === 'error' ? 'cyber-badge-red' : 
                        evt.level === 'warning' ? 'cyber-badge-purple' : 
                        evt.level === 'success' ? 'cyber-badge-green' : 'cyber-badge-cyan'
                      }`} style={{ fontSize: "9px", padding: "1px 6px" }}>
                        {evt.stage.toUpperCase()}
                      </span>
                      <span style={{ color: "var(--text-primary)" }}>{evt.message}</span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Right: Telemetry Metrics */}
              <div style={{ display: "flex", flexDirection: "column", gap: "18px" }}>
                <div className="glass-panel" style={{ padding: "20px" }}>
                  <span className="text-muted font-mono" style={{ fontSize: "11px" }}>CAMPAIGN DISRUPTION SCORE</span>
                  <p className="font-display text-cyan" style={{ fontSize: "32px", fontWeight: 800 }}>
                    ₹42,00,000
                  </p>
                  <p className="text-secondary font-mono" style={{ fontSize: "12px", marginTop: "4px" }}>
                    Estimated scam volume neutralized by freezing 1 mule VPA.
                  </p>
                </div>

                <div className="glass-panel" style={{ padding: "20px" }}>
                  <span className="text-muted font-mono" style={{ fontSize: "11px" }}>ACTIVE MULE ACCOUNT</span>
                  <p className="font-mono text-red" style={{ fontSize: "15px", fontWeight: 700, marginTop: "4px" }}>
                    {activeCase?.result?.payee.upi_vpa || "Benign Portal"}
                  </p>
                  <p className="text-muted font-mono" style={{ fontSize: "11px", marginTop: "2px" }}>
                    PSP: {activeCase?.result?.payee.psp_name || "N/A"}
                  </p>
                </div>

                <div className="glass-panel" style={{ padding: "20px" }}>
                  <span className="text-muted font-mono" style={{ fontSize: "11px" }}>DEFENSE TELEMETRY</span>
                  <div style={{ marginTop: "8px", display: "flex", flexDirection: "column", gap: "6px", fontSize: "12px", fontFamily: "var(--font-mono)" }}>
                    <div style={{ display: "flex", justifyContent: "space-between" }}>
                      <span className="text-muted">Proxy Egress:</span>
                      <span className="text-cyan">Reliance Jio (New Delhi)</span>
                    </div>
                    <div style={{ display: "flex", justifyContent: "space-between" }}>
                      <span className="text-muted">Synthetic Device:</span>
                      <span className="text-secondary">Galaxy S24 Ultra (Android 14)</span>
                    </div>
                    <div style={{ display: "flex", justifyContent: "space-between" }}>
                      <span className="text-muted">Integrity Standard:</span>
                      <span className="text-green">Section 65B Certified</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}
      </main>

      {/* Footer */}
      <footer style={{
        padding: "20px 24px",
        borderTop: "1px solid rgba(255, 255, 255, 0.05)",
        backgroundColor: "rgba(7, 8, 14, 0.9)",
        fontSize: "12px",
        color: "var(--text-muted)"
      }}>
        <div style={{ maxWidth: "1400px", margin: "0 auto", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <span className="font-mono">STING PLATFORM // TEAM VOID MAIN (IIITD HACKATHON)</span>
          <div style={{ display: "flex", gap: "18px" }}>
            <span>Contract: shared/api-schema.json</span>
            <span>Mock Client: Active</span>
          </div>
        </div>
      </footer>
    </div>
  );
}
