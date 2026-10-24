"use client";

import React, { useState, useEffect } from "react";
import { Navbar, ViewMode } from "@/components/Navbar";
import { StageProgressRail } from "@/components/StageProgressRail";
import { CaseSubmissionBar } from "@/components/CaseSubmissionBar";
import { IntakeStagePanel } from "@/components/stages/IntakeStagePanel";
import { TriageStagePanel } from "@/components/stages/TriageStagePanel";
import { DetonationStagePanel } from "@/components/stages/DetonationStagePanel";
import { EnrichmentStagePanel } from "@/components/stages/EnrichmentStagePanel";
import { ClusterStagePanel } from "@/components/stages/ClusterStagePanel";
import { ActStagePanel } from "@/components/stages/ActStagePanel";
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

  const handleRunGuidedDemo = async () => {
    setMode("story");
    setSelectedCaseId("c-pmcares-9281");
    const stages = ["stage-intake", "stage-triage", "stage-detonate", "stage-enrich", "stage-cluster", "stage-act"];
    for (const st of stages) {
      const elem = document.getElementById(st);
      if (elem) {
        elem.scrollIntoView({ behavior: "smooth" });
      }
      await new Promise(r => setTimeout(r, 1600));
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
        onRunGuidedDemo={handleRunGuidedDemo}
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
              {activeCase && <TriageStagePanel caseData={activeCase} />}

              {/* STAGE 3: DETONATE */}
              {activeCase && <DetonationStagePanel caseData={activeCase} />}

              {/* STAGE 4: ENRICH */}
              {activeCase && <EnrichmentStagePanel caseData={activeCase} />}

              {/* STAGE 5: CLUSTER */}
              {activeCase && <ClusterStagePanel caseData={activeCase} />}

              {/* STAGE 6: ACT */}
              {activeCase && <ActStagePanel caseData={activeCase} />}
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
