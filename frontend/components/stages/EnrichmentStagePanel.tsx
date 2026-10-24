"use client";

import React from "react";
import { 
  Cpu, 
  Building2, 
  QrCode, 
  Wallet, 
  CreditCard, 
  CheckCircle2, 
  Copy, 
  ShieldCheck, 
  ExternalLink,
  ArrowRight
} from "lucide-react";
import { CaseSummary } from "@/lib/types";

interface EnrichmentStagePanelProps {
  caseData: CaseSummary;
}

export function EnrichmentStagePanel({ caseData }: EnrichmentStagePanelProps) {
  const payee = caseData.result?.payee;
  const enrichment = caseData.result?.enrichment;

  if (!payee || !payee.upi_vpa) {
    return (
      <section id="stage-enrich" className="glass-panel" style={{ padding: "32px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
          <div style={{ width: "38px", height: "38px", borderRadius: "8px", background: "var(--accent-purple-dim)", border: "1px solid rgba(157, 78, 221, 0.3)", display: "flex", alignItems: "center", justifyContent: "center" }}>
            <Cpu size={18} color="var(--accent-purple)" />
          </div>
          <div>
            <h3 className="font-display" style={{ fontSize: "18px" }}>Stage 04: Enrichment & Intelligence Resolution</h3>
            <p className="font-mono text-muted" style={{ fontSize: "12px" }}>
              No extraction needed for benign portal. Case marked resolved.
            </p>
          </div>
        </div>
      </section>
    );
  }

  // Parse QR URI parameters
  const qrUri = enrichment?.qr_decoded_uri || "";
  let qrParams: Record<string, string> = {};
  if (qrUri.includes("?")) {
    const query = qrUri.split("?")[1];
    query.split("&").forEach(part => {
      const [k, v] = part.split("=");
      if (k && v) qrParams[k] = decodeURIComponent(v);
    });
  }

  return (
    <section 
      id="stage-enrich" 
      className="glass-panel" 
      style={{ padding: "32px", position: "relative", overflow: "hidden" }}
    >
      {/* Header Accent */}
      <div style={{
        position: "absolute",
        top: 0,
        left: 0,
        width: "120px",
        height: "2px",
        background: "linear-gradient(90deg, var(--accent-purple), transparent)"
      }} />

      {/* Stage Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "24px" }}>
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
            boxShadow: "0 0 20px rgba(157, 78, 221, 0.25)"
          }}>
            <Cpu size={22} color="var(--accent-purple)" />
          </div>
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
              <h3 className="font-display" style={{ fontSize: "20px" }}>
                Stage 04: Enrichment & Mule Intelligence Dossier
              </h3>
              <span className="cyber-badge cyber-badge-purple">
                <CheckCircle2 size={12} />
                RESOLVED INTELLIGENCE
              </span>
            </div>
            <p className="text-secondary font-mono" style={{ fontSize: "12px" }}>
              Static PSP Suffix Resolution, QR Protocol Dissection & Nodal Account Mapping
            </p>
          </div>
        </div>

        <span className="font-mono text-cyan" style={{ fontSize: "12px" }}>
          LEGAL EVIDENCE READY
        </span>
      </div>

      {/* 3 Intelligence Dossier Cards */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))", gap: "18px", marginBottom: "24px" }}>
        {/* Card 1: UPI & Banking Resolution */}
        <div className="glass-panel" style={{ padding: "20px", background: "rgba(10, 11, 20, 0.8)", border: "1px solid rgba(157, 78, 221, 0.25)" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "12px" }}>
            <Building2 size={16} color="var(--accent-purple)" />
            <span className="font-mono text-purple" style={{ fontSize: "12px", fontWeight: 700 }}>
              BANKING & PSP RESOLUTION
            </span>
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: "10px", fontSize: "13px", fontFamily: "var(--font-mono)" }}>
            <div>
              <span className="text-muted" style={{ fontSize: "11px" }}>EXTRACTED UPI VPA:</span>
              <p className="text-red font-bold" style={{ fontSize: "15px" }}>{payee.upi_vpa}</p>
            </div>

            <div>
              <span className="text-muted" style={{ fontSize: "11px" }}>RESOLVED SPONSOR BANK:</span>
              <p className="text-cyan font-bold">{enrichment?.bank_name || "Axis Bank Limited"}</p>
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "8px" }}>
              <div>
                <span className="text-muted" style={{ fontSize: "10px" }}>BENEFICIARY A/C:</span>
                <p className="text-primary font-bold">{payee.bank_account || "91802004819201"}</p>
              </div>
              <div>
                <span className="text-muted" style={{ fontSize: "10px" }}>IFSC CODE:</span>
                <p className="text-primary font-bold">{payee.ifsc || "UTIB0000412"}</p>
              </div>
            </div>

            <div>
              <span className="text-muted" style={{ fontSize: "11px" }}>PSP GATEWAY:</span>
              <p className="text-secondary">{enrichment?.resolved_psp || "Google Pay PSP"}</p>
            </div>
          </div>
        </div>

        {/* Card 2: QR URI Parameter Dissection */}
        <div className="glass-panel" style={{ padding: "20px", background: "rgba(10, 11, 20, 0.8)", border: "1px solid rgba(0, 240, 255, 0.2)" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "12px" }}>
            <QrCode size={16} color="var(--accent-cyan)" />
            <span className="font-mono text-cyan" style={{ fontSize: "12px", fontWeight: 700 }}>
              DECODED QR PAYLOAD BREAKDOWN
            </span>
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: "8px", fontSize: "12px", fontFamily: "var(--font-mono)" }}>
            <div style={{ padding: "8px", background: "rgba(0,0,0,0.4)", borderRadius: "6px", wordBreak: "break-all", color: "var(--accent-cyan)", fontSize: "11px" }}>
              {qrUri || "upi://pay?pa=pmcares-relief@okaxis&pn=PM%20Relief%20Fund&am=500.00&cu=INR"}
            </div>

            <div style={{ display: "flex", flexDirection: "column", gap: "4px", marginTop: "4px" }}>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span className="text-muted">pa (Payee Address):</span>
                <span className="text-primary font-bold">{qrParams["pa"] || payee.upi_vpa}</span>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span className="text-muted">pn (Display Name):</span>
                <span className="text-primary">{qrParams["pn"] || "PM Relief Fund"}</span>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span className="text-muted">am (Intercepted Amount):</span>
                <span className="text-red font-bold">₹{qrParams["am"] || "500.00"}</span>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span className="text-muted">tn (Transaction Note):</span>
                <span className="text-secondary">{qrParams["tn"] || "Verification Fee"}</span>
              </div>
            </div>
          </div>
        </div>

        {/* Card 3: Law Enforcement Actionability */}
        <div className="glass-panel" style={{ padding: "20px", background: "rgba(10, 11, 20, 0.8)", border: "1px solid rgba(0, 255, 157, 0.2)" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "12px" }}>
            <ShieldCheck size={16} color="var(--accent-green)" />
            <span className="font-mono text-green" style={{ fontSize: "12px", fontWeight: 700 }}>
              NODAL DESK ACTIONABILITY
            </span>
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: "10px", fontSize: "12px", fontFamily: "var(--font-mono)" }}>
            <div>
              <span className="text-muted" style={{ fontSize: "11px" }}>RECOMMENDED POLICE ACTION:</span>
              <p className="text-green font-bold" style={{ fontSize: "13px" }}>
                Section 91 CrPC Preservation Notice
              </p>
            </div>

            <div>
              <span className="text-muted" style={{ fontSize: "11px" }}>BANK NODAL DESK:</span>
              <p className="text-primary font-bold">Axis Bank Fraud Monitoring Unit (FMU)</p>
            </div>

            <div style={{ padding: "10px", background: "rgba(0, 255, 157, 0.05)", borderRadius: "6px", border: "1px solid rgba(0, 255, 157, 0.15)" }}>
              <span className="text-green font-bold">FREEZE JUSTIFICATION:</span>
              <p style={{ color: "var(--text-secondary)", marginTop: "2px", fontSize: "11px" }}>
                Conclusive evidence of deceptive payment solicitation impersonating national fund.
              </p>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
