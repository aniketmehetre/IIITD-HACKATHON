"use client";

import React, { useState } from "react";
import { 
  Zap, 
  ShieldCheck, 
  ShieldAlert, 
  Play, 
  Pause, 
  RotateCcw, 
  Lock, 
  Smartphone, 
  Globe, 
  ArrowRight, 
  QrCode, 
  ExternalLink,
  ChevronRight,
  Sparkles,
  MousePointer,
  CheckCircle2,
  AlertTriangle,
  Flame
} from "lucide-react";
import { CaseSummary, DetonationStep } from "@/lib/types";

interface DetonationStagePanelProps {
  caseData: CaseSummary;
}

export function DetonationStagePanel({ caseData }: DetonationStagePanelProps) {
  const detonation = caseData.result?.detonation;
  const steps: DetonationStep[] = detonation?.steps || [];
  const [activeStepIdx, setActiveStepIdx] = useState<number>(steps.length > 0 ? steps.length - 1 : 0);
  const [isPlaying, setIsPlaying] = useState<boolean>(false);

  if (!detonation || steps.length === 0) {
    return (
      <section id="stage-detonate" className="glass-panel" style={{ padding: "32px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
          <div style={{ width: "38px", height: "38px", borderRadius: "8px", background: "var(--accent-cyan-dim)", border: "1px solid var(--border-cyan)", display: "flex", alignItems: "center", justifyContent: "center" }}>
            <Zap size={18} color="var(--accent-cyan)" />
          </div>
          <div>
            <h3 className="font-display" style={{ fontSize: "18px" }}>Stage 03: Autonomous Agent Detonation</h3>
            <p className="font-mono text-muted" style={{ fontSize: "12px" }}>
              {detonation?.halt_reason || "Pre-detonation skip: Target already known or classified benign."}
            </p>
          </div>
        </div>
      </section>
    );
  }

  const currentStep = steps[activeStepIdx] || steps[0];

  const handleNext = () => {
    setActiveStepIdx((prev) => (prev < steps.length - 1 ? prev + 1 : 0));
  };

  const handlePrev = () => {
    setActiveStepIdx((prev) => (prev > 0 ? prev - 1 : steps.length - 1));
  };

  return (
    <section 
      id="stage-detonate" 
      className="glass-panel-threat" 
      style={{ padding: "32px", position: "relative", overflow: "hidden" }}
    >
      {/* Decorative Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "20px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "14px" }}>
          <div style={{
            width: "44px",
            height: "44px",
            borderRadius: "10px",
            background: "var(--accent-red-dim)",
            border: "1px solid var(--border-red)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            boxShadow: "var(--glow-red-box)"
          }}>
            <Zap size={22} color="var(--accent-red)" />
          </div>
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
              <h3 className="font-display" style={{ fontSize: "20px" }}>
                Stage 03: Synthetic Victim Detonation Viewport
              </h3>
              <span className="cyber-badge cyber-badge-red">
                <Flame size={12} />
                LIVE INFILTRATION
              </span>
            </div>
            <p className="text-secondary font-mono" style={{ fontSize: "12px" }}>
              Manus-Style Autonomous Traversal &bull; Intercepts Payee Before Financial Movement
            </p>
          </div>
        </div>

        {/* Persona Pill */}
        <div style={{ textAlign: "right" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "6px", justifyContent: "flex-end" }}>
            <Smartphone size={13} color="var(--accent-cyan)" />
            <span className="font-mono text-cyan" style={{ fontSize: "11px", fontWeight: 600 }}>
              SYNTHETIC PERSONA // MOBILE 4G
            </span>
          </div>
          <p className="font-mono text-muted" style={{ fontSize: "10px", marginTop: "2px" }}>
            {detonation.synthetic_persona.ip_proxy} &bull; {detonation.synthetic_persona.geo}
          </p>
        </div>
      </div>

      {/* Redirect Chain Hop Ribbon */}
      <div style={{ 
        padding: "10px 16px", 
        background: "rgba(0, 0, 0, 0.5)", 
        borderRadius: "8px", 
        border: "1px solid rgba(255, 255, 255, 0.06)",
        marginBottom: "20px"
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "6px" }}>
          <Globe size={13} color="var(--accent-cyan)" />
          <span className="font-mono text-muted" style={{ fontSize: "11px", fontWeight: 700 }}>
            RECORDED REDIRECTION HOPS ({detonation.redirect_chain.length} STAGES):
          </span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: "8px", overflowX: "auto", scrollbarWidth: "none" }}>
          {detonation.redirect_chain.map((url, idx) => (
            <React.Fragment key={idx}>
              <div style={{
                display: "flex",
                alignItems: "center",
                gap: "6px",
                padding: "4px 10px",
                borderRadius: "5px",
                background: idx === detonation.redirect_chain.length - 1 ? "rgba(255, 42, 85, 0.15)" : "rgba(255, 255, 255, 0.03)",
                border: `1px solid ${idx === detonation.redirect_chain.length - 1 ? "var(--border-red)" : "rgba(255, 255, 255, 0.05)"}`,
                fontSize: "11px",
                fontFamily: "var(--font-mono)",
                color: idx === detonation.redirect_chain.length - 1 ? "var(--accent-red)" : "var(--text-secondary)",
                whiteSpace: "nowrap"
              }}>
                <span className="text-muted">#{idx + 1}</span>
                <span>{url.replace("https://", "").slice(0, 32)}...</span>
              </div>
              {idx < detonation.redirect_chain.length - 1 && (
                <ChevronRight size={13} color="var(--accent-cyan)" style={{ opacity: 0.5, flexShrink: 0 }} />
              )}
            </React.Fragment>
          ))}
        </div>
      </div>

      {/* Floating Agent Simulated Browser Chrome */}
      <div style={{
        background: "#080911",
        borderRadius: "12px",
        border: "1px solid var(--border-cyan)",
        boxShadow: "0 0 35px rgba(0, 240, 255, 0.15)",
        overflow: "hidden",
        marginBottom: "20px"
      }}>
        {/* Browser Top Bar */}
        <div style={{
          background: "#11121e",
          padding: "10px 16px",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          borderBottom: "1px solid rgba(255, 255, 255, 0.06)"
        }}>
          {/* Window Buttons */}
          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <span style={{ width: "10px", height: "10px", borderRadius: "50%", background: "#ff5f56", display: "inline-block" }} />
            <span style={{ width: "10px", height: "10px", borderRadius: "50%", background: "#ffbd2e", display: "inline-block" }} />
            <span style={{ width: "10px", height: "10px", borderRadius: "50%", background: "#27c93f", display: "inline-block" }} />
          </div>

          {/* URL Address Bar */}
          <div style={{
            flex: 1,
            maxWidth: "600px",
            margin: "0 16px",
            background: "rgba(0, 0, 0, 0.6)",
            borderRadius: "6px",
            padding: "5px 12px",
            display: "flex",
            alignItems: "center",
            gap: "8px",
            border: "1px solid rgba(0, 240, 255, 0.15)"
          }}>
            <Lock size={12} color="var(--accent-red)" />
            <span className="font-mono text-red" style={{ fontSize: "12px", fontWeight: 600 }}>
              SUSPICIOUS //
            </span>
            <span className="font-mono" style={{ fontSize: "12px", color: "var(--text-primary)" }}>
              {detonation.final_url}
            </span>
          </div>

          {/* Persona Egress Badge */}
          <span className="cyber-badge cyber-badge-cyan" style={{ fontSize: "10px" }}>
            EMULATED HEADLESS
          </span>
        </div>

        {/* Viewport Content Rendering */}
        <div style={{ padding: "28px", minHeight: "360px", position: "relative", backgroundColor: "#06070c" }}>
          {/* Simulated Webpage DOM Card */}
          <div style={{
            maxWidth: "520px",
            margin: "0 auto",
            background: "rgba(18, 20, 32, 0.95)",
            border: "1px solid rgba(255, 255, 255, 0.1)",
            borderRadius: "10px",
            padding: "24px",
            boxShadow: "0 10px 30px rgba(0,0,0,0.8)"
          }}>
            {/* Phishing Header Mockup */}
            <div style={{ textAlign: "center", paddingBottom: "16px", borderBottom: "1px solid rgba(255, 255, 255, 0.08)" }}>
              <div style={{ display: "inline-block", padding: "4px 8px", background: "rgba(255, 42, 85, 0.2)", borderRadius: "4px", color: "var(--accent-red)", fontSize: "11px", fontWeight: 700, fontFamily: "var(--font-mono)", marginBottom: "6px" }}>
                OFFICIAL RELIEF DISBURSEMENT PORTAL
              </div>
              <h4 className="font-display" style={{ fontSize: "18px", color: "#ffffff" }}>
                Prime Minister Citizen Assistance Scheme
              </h4>
              <p style={{ fontSize: "12px", color: "#8a90a6", marginTop: "2px" }}>
                Claim Immediate Financial Relief of ₹5,000/- Directly to Bank
              </p>
            </div>

            {/* Step-by-Step Simulated Screen */}
            <div style={{ padding: "20px 0" }}>
              {activeStepIdx < 3 ? (
                /* Form Filling State */
                <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
                  <div>
                    <label style={{ display: "block", fontSize: "11px", color: "#8a90a6", marginBottom: "4px" }}>
                      Beneficiary Full Name
                    </label>
                    <div style={{ padding: "8px 12px", background: "rgba(0,0,0,0.5)", border: "1px solid rgba(0, 240, 255, 0.3)", borderRadius: "6px", fontSize: "13px", color: "var(--accent-cyan)", fontFamily: "var(--font-mono)" }}>
                      Rohan Sharma <span style={{ fontSize: "10px", color: "#6a708a" }}>(Synthetic Dummy Profile)</span>
                    </div>
                  </div>

                  <div>
                    <label style={{ display: "block", fontSize: "11px", color: "#8a90a6", marginBottom: "4px" }}>
                      Aadhaar Identity Number
                    </label>
                    <div style={{ padding: "8px 12px", background: "rgba(0,0,0,0.5)", border: "1px solid rgba(0, 240, 255, 0.3)", borderRadius: "6px", fontSize: "13px", color: "var(--accent-cyan)", fontFamily: "var(--font-mono)" }}>
                      4129-8821-0091 <span style={{ fontSize: "10px", color: "#6a708a" }}>(Synthetic Checksum)</span>
                    </div>
                  </div>

                  <div style={{ marginTop: "10px" }}>
                    <button style={{ width: "100%", padding: "10px", background: "#ff3b3b", color: "#fff", border: "none", borderRadius: "6px", fontWeight: 700, fontSize: "13px" }}>
                      VERIFY & PROCEED TO DISBURSEMENT
                    </button>
                  </div>
                </div>
              ) : (
                /* Payment Trap Screen State */
                <div style={{ textAlign: "center" }}>
                  <div style={{ display: "inline-flex", padding: "6px 12px", background: "rgba(255, 42, 85, 0.15)", border: "1px solid var(--border-red)", borderRadius: "20px", marginBottom: "12px" }}>
                    <span className="font-mono text-red" style={{ fontSize: "11px", fontWeight: 700 }}>
                      ⚠️ VERIFICATION FEE REQUIRED: ₹500
                    </span>
                  </div>

                  {/* QR Code Graphic Mockup */}
                  <div style={{
                    width: "160px",
                    height: "160px",
                    margin: "0 auto 14px",
                    background: "#ffffff",
                    borderRadius: "10px",
                    padding: "10px",
                    display: "flex",
                    flexDirection: "column",
                    alignItems: "center",
                    justifyContent: "center",
                    boxShadow: "0 0 25px rgba(255, 42, 85, 0.3)"
                  }}>
                    <QrCode size={130} color="#000000" />
                  </div>

                  {/* Intercepted UPI ID Spotlight */}
                  <div style={{
                    padding: "10px 14px",
                    background: "rgba(255, 42, 85, 0.1)",
                    border: "1px solid var(--accent-red)",
                    borderRadius: "8px"
                  }}>
                    <span className="font-mono text-muted" style={{ fontSize: "10px" }}>INTERCEPTED ROGUE PAYEE VPA:</span>
                    <p className="font-mono text-red" style={{ fontSize: "16px", fontWeight: 800 }}>
                      {detonation.extracted_payee.upi_vpa}
                    </p>
                    <span className="font-mono text-secondary" style={{ fontSize: "11px" }}>
                      PSP: {detonation.extracted_payee.psp_name} &bull; Account: {detonation.extracted_payee.bank_account || "91802004819201"}
                    </span>
                  </div>
                </div>
              )}
            </div>

            {/* Synthetic Cursor Floating Indicator */}
            <div style={{
              display: "flex",
              alignItems: "center",
              gap: "8px",
              padding: "8px 12px",
              background: "rgba(0, 240, 255, 0.15)",
              border: "1px solid var(--accent-cyan)",
              borderRadius: "6px",
              marginTop: "10px"
            }}>
              <MousePointer size={14} color="var(--accent-cyan)" />
              <span className="font-mono text-cyan" style={{ fontSize: "11px", fontWeight: 600 }}>
                [AGENT TELEMETRY]: {currentStep.telemetry}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Flight Recorder Timeline Scrubber */}
      <div style={{
        background: "rgba(0, 0, 0, 0.6)",
        borderRadius: "10px",
        padding: "16px 20px",
        border: "1px solid rgba(255, 255, 255, 0.08)"
      }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "12px" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <Sparkles size={14} color="var(--accent-cyan)" />
            <span className="font-mono text-cyan" style={{ fontSize: "12px", fontWeight: 700 }}>
              FLIGHT RECORDER: STEP {activeStepIdx + 1} OF {steps.length}
            </span>
          </div>

          <div style={{ display: "flex", gap: "8px" }}>
            <button
              onClick={handlePrev}
              className="cyber-button-secondary"
              style={{ padding: "4px 10px", fontSize: "11px" }}
            >
              PREV
            </button>
            <button
              onClick={handleNext}
              className="cyber-button-secondary"
              style={{ padding: "4px 10px", fontSize: "11px" }}
            >
              NEXT
            </button>
          </div>
        </div>

        {/* Step Buttons Row */}
        <div style={{ display: "grid", gridTemplateColumns: `repeat(${steps.length}, 1fr)`, gap: "8px" }}>
          {steps.map((st, idx) => (
            <button
              key={st.step_number}
              onClick={() => setActiveStepIdx(idx)}
              style={{
                padding: "8px 10px",
                borderRadius: "6px",
                border: "1px solid",
                borderColor: idx === activeStepIdx ? "var(--border-cyan)" : "rgba(255, 255, 255, 0.06)",
                background: idx === activeStepIdx ? "var(--accent-cyan-dim)" : "rgba(255, 255, 255, 0.02)",
                cursor: "pointer",
                textAlign: "left",
                transition: "all 0.2s ease"
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <span className="font-mono text-cyan" style={{ fontSize: "11px", fontWeight: 700 }}>
                  {st.timestamp_offset}
                </span>
                {idx === steps.length - 1 && (
                  <span style={{ width: "6px", height: "6px", borderRadius: "50%", background: "var(--accent-red)" }} />
                )}
              </div>
              <p className="font-display" style={{ fontSize: "11px", color: idx === activeStepIdx ? "#fff" : "var(--text-muted)", marginTop: "4px", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                {st.action}
              </p>
            </button>
          ))}
        </div>
      </div>

      {/* Safety Guardrail Legal Certificate */}
      <div style={{
        marginTop: "16px",
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        padding: "10px 16px",
        background: "rgba(0, 255, 157, 0.05)",
        border: "1px solid var(--border-green)",
        borderRadius: "8px"
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
          <ShieldCheck size={18} color="var(--accent-green)" />
          <span className="font-mono text-green" style={{ fontSize: "12px", fontWeight: 600 }}>
            LEGAL SAFEGUARD ACTIVE: Zero real currency or credentials transmitted. Synthetic victim halt enforced.
          </span>
        </div>
        <span className="cyber-badge cyber-badge-green" style={{ fontSize: "10px" }}>
          COMPLIANT
        </span>
      </div>
    </section>
  );
}
