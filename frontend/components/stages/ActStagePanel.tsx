"use client";

import React, { useState } from "react";
import { 
  FileCheck2, 
  ShieldCheck, 
  Lock, 
  Download, 
  CheckCircle2, 
  Building, 
  FileText, 
  Send, 
  AlertOctagon, 
  Clock, 
  Hash,
  ExternalLink,
  ChevronDown,
  ChevronUp,
  Sparkles
} from "lucide-react";
import confetti from "canvas-confetti";
import { CaseSummary } from "@/lib/types";
import { api } from "@/lib/api";

interface ActStagePanelProps {
  caseData: CaseSummary;
}

export function ActStagePanel({ caseData }: ActStagePanelProps) {
  const [isVerifying, setIsVerifying] = useState(false);
  const [isSealVerified, setIsSealVerified] = useState(false);
  const [activeDossierTab, setActiveDossierTab] = useState<'i4c' | 'bank' | 'certin'>('i4c');
  const [isApproving, setIsApproving] = useState(false);
  const [approvalStatus, setApprovalStatus] = useState<string | null>(
    caseData.result?.approved ? "DISPATCHED_TO_NODAL_DESKS" : null
  );

  const drafts = caseData.result?.drafts;
  const evidenceHash = caseData.result?.evidence_hash || "e4a781b290dfc102a9918734bcfe1239aa81230491823bcda987102938471209";

  const handleVerifySeal = async () => {
    setIsVerifying(true);
    try {
      await api.verifyEvidenceSeal(evidenceHash);
      setIsSealVerified(true);
    } catch (e) {
      console.error(e);
    } finally {
      setIsVerifying(false);
    }
  };

  const handleApprove = async () => {
    setIsApproving(true);
    try {
      const res = await api.approveReport(caseData.id, true);
      setApprovalStatus(res.message);

      // Cyber celebration effect with emerald/cyan confetti
      confetti({
        particleCount: 80,
        spread: 70,
        origin: { y: 0.7 },
        colors: ['#00ff9d', '#00f0ff', '#ffffff']
      });
    } catch (e) {
      console.error(e);
    } finally {
      setIsApproving(false);
    }
  };

  return (
    <section 
      id="stage-act" 
      className="glass-panel-verified" 
      style={{ padding: "32px", position: "relative", overflow: "hidden" }}
    >
      {/* Header Accent */}
      <div style={{
        position: "absolute",
        top: 0,
        left: 0,
        width: "120px",
        height: "2px",
        background: "linear-gradient(90deg, var(--accent-green), transparent)"
      }} />

      {/* Top Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "24px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "14px" }}>
          <div style={{
            width: "44px",
            height: "44px",
            borderRadius: "10px",
            background: "var(--accent-green-dim)",
            border: "1px solid var(--border-green)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            boxShadow: "var(--glow-green-box)"
          }}>
            <FileCheck2 size={22} color="var(--accent-green)" />
          </div>
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
              <h3 className="font-display" style={{ fontSize: "20px" }}>
                Stage 06: Evidence Vault & Automated Takedown Dispatch
              </h3>
              <span className="cyber-badge cyber-badge-green">
                <ShieldCheck size={12} />
                SECTION 65B CERTIFIED
              </span>
            </div>
            <p className="text-secondary font-mono" style={{ fontSize: "12px" }}>
              Pre-filled Law Enforcement Dossiers &bull; Human-in-the-Loop Sign-off Gate
            </p>
          </div>
        </div>

        {/* Approval State Badge */}
        <div>
          {approvalStatus ? (
            <span className="cyber-badge cyber-badge-green" style={{ fontSize: "11px", padding: "6px 12px" }}>
              <CheckCircle2 size={13} />
              DISPATCH AUTHORIZED
            </span>
          ) : (
            <span className="cyber-badge cyber-badge-cyan" style={{ fontSize: "11px", padding: "6px 12px" }}>
              <Lock size={13} />
              AWAITING ANALYST APPROVAL
            </span>
          )}
        </div>
      </div>

      {/* Cryptographic Proof & Hash Verification Card */}
      <div style={{
        padding: "20px",
        background: "rgba(6, 7, 12, 0.85)",
        border: "1px solid var(--border-green)",
        borderRadius: "10px",
        marginBottom: "24px"
      }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "12px" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <Hash size={16} color="var(--accent-green)" />
            <span className="font-mono text-green" style={{ fontSize: "12px", fontWeight: 700 }}>
              IMMUTABLE CHAIN-OF-CUSTODY DIGITAL SEAL
            </span>
          </div>

          <button
            onClick={handleVerifySeal}
            disabled={isVerifying || isSealVerified}
            className={isSealVerified ? "cyber-badge cyber-badge-green" : "cyber-button-primary"}
            style={{ padding: "6px 14px", fontSize: "11px" }}
          >
            {isVerifying ? (
              <span>COMPUTING CHECKSUM...</span>
            ) : isSealVerified ? (
              <>
                <CheckCircle2 size={13} />
                <span>SEAL CRYPTOGRAPHICALLY VERIFIED</span>
              </>
            ) : (
              <>
                <Sparkles size={13} />
                <span>VERIFY TAMPER-PROOF SEAL</span>
              </>
            )}
          </button>
        </div>

        <div style={{
          padding: "10px 14px",
          background: "rgba(0, 255, 157, 0.04)",
          border: "1px solid rgba(0, 255, 157, 0.15)",
          borderRadius: "6px",
          wordBreak: "break-all",
          fontFamily: "var(--font-mono)",
          fontSize: "13px",
          color: isSealVerified ? "var(--accent-green)" : "#e0e4ef"
        }}>
          {evidenceHash}
        </div>

        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: "10px", fontSize: "11px", color: "var(--text-muted)", fontFamily: "var(--font-mono)" }}>
          <span>ALGORITHM: SHA-256 (FIPS PUB 180-4)</span>
          <span>COMPLIANCE: Indian Evidence Act 65B Admissible</span>
        </div>
      </div>

      {/* Pre-Filled Dispatch Dossier Tabs */}
      <div style={{
        background: "rgba(6, 7, 12, 0.75)",
        borderRadius: "10px",
        border: "1px solid rgba(255, 255, 255, 0.08)",
        overflow: "hidden",
        marginBottom: "24px"
      }}>
        {/* Tab Headers */}
        <div style={{ display: "flex", borderBottom: "1px solid rgba(255, 255, 255, 0.06)", background: "#0a0c16" }}>
          <button
            onClick={() => setActiveDossierTab('i4c')}
            style={{
              flex: 1,
              padding: "12px",
              background: activeDossierTab === 'i4c' ? "rgba(0, 255, 157, 0.1)" : "transparent",
              color: activeDossierTab === 'i4c' ? "var(--accent-green)" : "var(--text-secondary)",
              border: "none",
              borderBottom: activeDossierTab === 'i4c' ? "2px solid var(--accent-green)" : "none",
              fontFamily: "var(--font-mono)",
              fontSize: "12px",
              fontWeight: 600,
              cursor: "pointer"
            }}
          >
            I4C CYBER CRIME COMPLAINT
          </button>

          <button
            onClick={() => setActiveDossierTab('bank')}
            style={{
              flex: 1,
              padding: "12px",
              background: activeDossierTab === 'bank' ? "rgba(0, 240, 255, 0.1)" : "transparent",
              color: activeDossierTab === 'bank' ? "var(--accent-cyan)" : "var(--text-secondary)",
              border: "none",
              borderBottom: activeDossierTab === 'bank' ? "2px solid var(--accent-cyan)" : "none",
              fontFamily: "var(--font-mono)",
              fontSize: "12px",
              fontWeight: 600,
              cursor: "pointer"
            }}
          >
            BANK LIEN & FREEZE ORDER
          </button>

          <button
            onClick={() => setActiveDossierTab('certin')}
            style={{
              flex: 1,
              padding: "12px",
              background: activeDossierTab === 'certin' ? "rgba(255, 42, 85, 0.1)" : "transparent",
              color: activeDossierTab === 'certin' ? "var(--accent-red)" : "var(--text-secondary)",
              border: "none",
              borderBottom: activeDossierTab === 'certin' ? "2px solid var(--accent-red)" : "none",
              fontFamily: "var(--font-mono)",
              fontSize: "12px",
              fontWeight: 600,
              cursor: "pointer"
            }}
          >
            CERT-IN TAKEDOWN ADVISORY
          </button>
        </div>

        {/* Tab Body */}
        <div style={{ padding: "20px" }}>
          {activeDossierTab === 'i4c' && (
            <div>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "10px" }}>
                <span className="font-mono text-muted" style={{ fontSize: "11px" }}>
                  FORMAT: Plain-text compliant with National Cyber Crime Reporting Portal (cybercrime.gov.in)
                </span>
                <span className="cyber-badge cyber-badge-green" style={{ fontSize: "9px" }}>READY TO SUBMIT</span>
              </div>
              <div className="terminal-window">
                <div className="terminal-body" style={{ maxHeight: "200px" }}>
                  <pre style={{ color: "#a0e0b0", whiteSpace: "pre-wrap" }}>
                    {drafts?.i4c_complaint || "National Cyber Crime Complaint generating..."}
                  </pre>
                </div>
              </div>
            </div>
          )}

          {activeDossierTab === 'bank' && (
            <div>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "10px" }}>
                <span className="font-mono text-muted" style={{ fontSize: "11px" }}>
                  FORMAT: Structured JSON Webhook payload for Bank Nodal Fraud Desk
                </span>
                <span className="cyber-badge cyber-badge-cyan" style={{ fontSize: "9px" }}>PAYEE TARGETED</span>
              </div>
              <div className="terminal-window">
                <div className="terminal-body" style={{ maxHeight: "200px" }}>
                  <pre style={{ color: "#00f0ff" }}>
                    {JSON.stringify(drafts?.bank_alert || {
                      target_bank: "Axis Bank Ltd",
                      risk_rating: "CRITICAL",
                      recommended_action: "FREEZE_INWARD_CREDITS",
                      vpa: caseData.result?.payee.upi_vpa || "pmcares-relief@okaxis",
                      account_number: caseData.result?.payee.bank_account || "91802004819201"
                    }, null, 2)}
                  </pre>
                </div>
              </div>
            </div>
          )}

          {activeDossierTab === 'certin' && (
            <div>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "10px" }}>
                <span className="font-mono text-muted" style={{ fontSize: "11px" }}>
                  FORMAT: Computer Emergency Response Team (CERT-In) Infrastructure Suspension Notice
                </span>
                <span className="cyber-badge cyber-badge-red" style={{ fontSize: "9px" }}>DNS SEIZURE</span>
              </div>
              <div className="terminal-window">
                <div className="terminal-body" style={{ maxHeight: "200px" }}>
                  <pre style={{ color: "#ff8da1" }}>
                    {JSON.stringify(drafts?.cert_in_advisory || {
                      incident_type: "Active Phishing & Payment Interception",
                      malicious_fqdn: caseData.result?.triage.domain || "pmcares-relief-claim.sbi-update.fake.in",
                      takedown_action: "EMERGENCY_DNS_TAKEDOWN_REQUEST"
                    }, null, 2)}
                  </pre>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Human-in-the-Loop Final Sign-off Bar */}
      <div style={{
        padding: "20px",
        background: "rgba(0, 0, 0, 0.6)",
        borderRadius: "10px",
        border: "1px solid rgba(255, 255, 255, 0.1)",
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center"
      }}>
        <div>
          <span className="font-mono text-cyan" style={{ fontSize: "13px", fontWeight: 700 }}>
            HUMAN-IN-THE-LOOP APPROVAL PROTOCOL
          </span>
          <p className="text-secondary font-mono" style={{ fontSize: "11px", marginTop: "2px" }}>
            Per STING legal guardrails, zero takedown or freeze orders are transmitted without verified human sign-off.
          </p>
        </div>

        <button
          onClick={handleApprove}
          disabled={isApproving || !!approvalStatus}
          className="cyber-button-primary"
          style={{
            background: approvalStatus ? "var(--accent-green)" : "var(--accent-cyan)",
            color: "#07070b",
            padding: "12px 24px",
            fontSize: "13px",
            boxShadow: approvalStatus ? "var(--glow-green-box)" : "var(--glow-cyan-box)"
          }}
        >
          {isApproving ? (
            <span>DISPATCHING...</span>
          ) : approvalStatus ? (
            <>
              <CheckCircle2 size={16} />
              <span>TAKEDOWN ORDERS DISPATCHED</span>
            </>
          ) : (
            <>
              <Send size={16} />
              <span>APPROVE & DISPATCH TAKEDOWN</span>
            </>
          )}
        </button>
      </div>
    </section>
  );
}
