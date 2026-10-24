"use client";

import React, { useState } from "react";
import { 
  Terminal, 
  ArrowRight, 
  UploadCloud, 
  MessageSquare, 
  Link2,
  Sparkles,
  Loader2
} from "lucide-react";
import { InputType } from "@/lib/types";

interface CaseSubmissionBarProps {
  onAnalyze: (type: InputType, content: string) => Promise<void>;
  isLoading: boolean;
}

export function CaseSubmissionBar({
  onAnalyze,
  isLoading
}: CaseSubmissionBarProps) {
  const [inputType, setInputType] = useState<InputType>('url');
  const [content, setContent] = useState('https://pmcares-relief-claim.sbi-update.fake.in/kyc-verify');

  const presetLures = [
    {
      label: "PM CARES Scam Lure",
      type: "url" as InputType,
      value: "https://pmcares-relief-claim.sbi-update.fake.in/kyc-verify",
      badge: "Full Detonation"
    },
    {
      label: "SBI KYC Phish",
      type: "url" as InputType,
      value: "https://sbi-card-reward-redeem.online/login",
      badge: "Cartel Skip"
    },
    {
      label: "HDFC Authentic",
      type: "url" as InputType,
      value: "https://netbanking.hdfcbank.com/netbanking",
      badge: "Benign Exit"
    }
  ];

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!content.trim() || isLoading) return;
    onAnalyze(inputType, content.trim());
  };

  const handleSelectPreset = (preset: typeof presetLures[0]) => {
    setInputType(preset.type);
    setContent(preset.value);
    onAnalyze(preset.type, preset.value);
  };

  return (
    <div style={{ maxWidth: "1000px", margin: "0 auto", padding: "0 24px" }}>
      {/* Type Selector Tabs */}
      <div style={{ display: "flex", gap: "8px", marginBottom: "10px", justifyContent: "space-between", alignItems: "center" }}>
        <div style={{ display: "flex", gap: "8px" }}>
          <button
            type="button"
            onClick={() => setInputType('url')}
            style={{
              display: "flex",
              alignItems: "center",
              gap: "6px",
              padding: "6px 12px",
              borderRadius: "6px",
              border: "1px solid",
              borderColor: inputType === 'url' ? "var(--border-cyan)" : "rgba(255,255,255,0.06)",
              background: inputType === 'url' ? "var(--accent-cyan-dim)" : "rgba(17, 18, 29, 0.6)",
              color: inputType === 'url' ? "var(--accent-cyan)" : "var(--text-muted)",
              fontFamily: "var(--font-mono)",
              fontSize: "12px",
              cursor: "pointer"
            }}
          >
            <Link2 size={13} />
            <span>Target URL</span>
          </button>

          <button
            type="button"
            onClick={() => setInputType('message')}
            style={{
              display: "flex",
              alignItems: "center",
              gap: "6px",
              padding: "6px 12px",
              borderRadius: "6px",
              border: "1px solid",
              borderColor: inputType === 'message' ? "var(--border-cyan)" : "rgba(255,255,255,0.06)",
              background: inputType === 'message' ? "var(--accent-cyan-dim)" : "rgba(17, 18, 29, 0.6)",
              color: inputType === 'message' ? "var(--accent-cyan)" : "var(--text-muted)",
              fontFamily: "var(--font-mono)",
              fontSize: "12px",
              cursor: "pointer"
            }}
          >
            <MessageSquare size={13} />
            <span>SMS / WhatsApp Text</span>
          </button>

          <button
            type="button"
            onClick={() => setInputType('qr')}
            style={{
              display: "flex",
              alignItems: "center",
              gap: "6px",
              padding: "6px 12px",
              borderRadius: "6px",
              border: "1px solid",
              borderColor: inputType === 'qr' ? "var(--border-cyan)" : "rgba(255,255,255,0.06)",
              background: inputType === 'qr' ? "var(--accent-cyan-dim)" : "rgba(17, 18, 29, 0.6)",
              color: inputType === 'qr' ? "var(--accent-cyan)" : "var(--text-muted)",
              fontFamily: "var(--font-mono)",
              fontSize: "12px",
              cursor: "pointer"
            }}
          >
            <UploadCloud size={13} />
            <span>QR Image Ingest</span>
          </button>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
          <Sparkles size={13} color="var(--accent-cyan)" />
          <span className="font-mono text-muted" style={{ fontSize: "11px" }}>QUICK DEMO PRESETS:</span>
        </div>
      </div>

      {/* Main Submission Input Form */}
      <form onSubmit={handleSubmit}>
        <div 
          className="glass-panel-cyan" 
          style={{ 
            padding: "8px 12px", 
            display: "flex", 
            alignItems: "center", 
            gap: "12px",
            boxShadow: "0 0 25px rgba(0, 240, 255, 0.2)"
          }}
        >
          <div style={{ paddingLeft: "8px", display: "flex", alignItems: "center" }}>
            <Terminal size={20} color="var(--accent-cyan)" />
          </div>

          <input
            type="text"
            value={content}
            onChange={(e) => setContent(e.target.value)}
            placeholder={
              inputType === 'url' 
                ? "Enter suspicious scam URL (e.g. https://...)" 
                : inputType === 'message'
                ? "Paste SMS or WhatsApp phishing message..."
                : "Upload or paste base64 QR payload..."
            }
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

          <button
            type="submit"
            disabled={isLoading}
            className="cyber-button-primary"
            style={{ opacity: isLoading ? 0.7 : 1 }}
          >
            {isLoading ? (
              <>
                <Loader2 size={16} className="animate-spin" />
                <span>INFILTRATING...</span>
              </>
            ) : (
              <>
                <span>DEPLOY STING</span>
                <ArrowRight size={16} />
              </>
            )}
          </button>
        </div>
      </form>

      {/* Quick Preset Buttons */}
      <div style={{ display: "flex", gap: "8px", marginTop: "12px", flexWrap: "wrap", justifyContent: "flex-end" }}>
        {presetLures.map((preset) => (
          <button
            key={preset.label}
            type="button"
            onClick={() => handleSelectPreset(preset)}
            className="glass-panel"
            style={{
              padding: "4px 10px",
              display: "flex",
              alignItems: "center",
              gap: "6px",
              fontSize: "11px",
              fontFamily: "var(--font-mono)",
              color: "var(--text-secondary)",
              cursor: "pointer",
              border: "1px solid rgba(255,255,255,0.06)"
            }}
          >
            <span>{preset.label}</span>
            <span style={{ 
              fontSize: "9px", 
              padding: "1px 5px", 
              borderRadius: "4px", 
              background: "rgba(0, 240, 255, 0.15)", 
              color: "var(--accent-cyan)" 
            }}>
              {preset.badge}
            </span>
          </button>
        ))}
      </div>
    </div>
  );
}
