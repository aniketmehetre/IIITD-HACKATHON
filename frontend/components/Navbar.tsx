"use client";

import React from "react";
import { 
  ShieldAlert, 
  Sparkles, 
  LayoutDashboard, 
  ChevronDown, 
  Radio, 
  Terminal,
  Activity
} from "lucide-react";

export type ViewMode = 'story' | 'warroom';

interface NavbarProps {
  mode: ViewMode;
  onModeChange: (mode: ViewMode) => void;
  selectedCaseId: string;
  onCaseSelect: (id: string) => void;
  onRunGuidedDemo?: () => void;
}

export function Navbar({
  mode,
  onModeChange,
  selectedCaseId,
  onCaseSelect,
  onRunGuidedDemo
}: NavbarProps) {
  const caseOptions = [
    { id: "c-pmcares-9281", label: "PM CARES Scam Lure", badge: "CRITICAL", color: "red" },
    { id: "c-sbikyc-7714", label: "SBI Card Lure (Known Payee)", badge: "GRAPH SKIP", color: "cyan" },
    { id: "c-hdfc-0021", label: "HDFC Official Portal", badge: "BENIGN EXIT", color: "green" },
  ];

  return (
    <nav style={{
      position: "sticky",
      top: 0,
      zIndex: 100,
      backdropFilter: "blur(18px)",
      WebkitBackdropFilter: "blur(18px)",
      backgroundColor: "rgba(7, 8, 14, 0.82)",
      borderBottom: "1px solid rgba(0, 240, 255, 0.12)",
      padding: "12px 24px",
      transition: "all 0.3s ease"
    }}>
      <div style={{
        maxWidth: "1400px",
        margin: "0 auto",
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        gap: "16px"
      }}>
        {/* Left: Brand & Status */}
        <div style={{ display: "flex", alignItems: "center", gap: "16px" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
            <div style={{
              width: "38px",
              height: "38px",
              borderRadius: "9px",
              background: "linear-gradient(135deg, rgba(0, 240, 255, 0.25), rgba(255, 42, 85, 0.25))",
              border: "1px solid var(--border-cyan)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              boxShadow: "0 0 16px rgba(0, 240, 255, 0.3)"
            }}>
              <ShieldAlert size={20} color="var(--accent-cyan)" />
            </div>
            <div>
              <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                <span className="font-display" style={{ fontSize: "20px", fontWeight: 800, letterSpacing: "0.05em" }}>
                  STING
                </span>
                <span className="cyber-badge cyber-badge-cyan" style={{ fontSize: "10px", padding: "2px 6px" }}>
                  TACTICAL
                </span>
              </div>
              <p className="text-muted font-mono" style={{ fontSize: "10px", letterSpacing: "0.04em" }}>
                SYNTHETIC THREAT INVESTIGATION
              </p>
            </div>
          </div>

          <div style={{ height: "24px", width: "1px", background: "rgba(255,255,255,0.08)" }} />

          {/* Quick Case Switcher */}
          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <span className="text-muted font-mono" style={{ fontSize: "11px" }}>CASE:</span>
            <div style={{ position: "relative" }}>
              <select
                value={selectedCaseId}
                onChange={(e) => onCaseSelect(e.target.value)}
                className="font-mono"
                style={{
                  appearance: "none",
                  backgroundColor: "rgba(17, 18, 29, 0.9)",
                  color: "var(--text-primary)",
                  border: "1px solid var(--border-cyan)",
                  borderRadius: "6px",
                  padding: "6px 28px 6px 12px",
                  fontSize: "12px",
                  fontWeight: 500,
                  outline: "none",
                  cursor: "pointer",
                  boxShadow: "0 0 10px rgba(0, 240, 255, 0.1)"
                }}
              >
                {caseOptions.map((opt) => (
                  <option key={opt.id} value={opt.id} style={{ background: "#0b0c13", color: "#f0f2f8" }}>
                    {opt.label} ({opt.badge})
                  </option>
                ))}
              </select>
              <ChevronDown 
                size={14} 
                color="var(--accent-cyan)" 
                style={{ position: "absolute", right: "8px", top: "50%", transform: "translateY(-50%)", pointerEvents: "none" }} 
              />
            </div>
          </div>
        </div>

        {/* Right: Mode Toggle + Live Telemetry */}
        <div style={{ display: "flex", alignItems: "center", gap: "16px" }}>
          {/* Dual Mode Switcher */}
          <div style={{
            display: "flex",
            alignItems: "center",
            padding: "3px",
            background: "rgba(17, 18, 29, 0.9)",
            border: "1px solid rgba(255, 255, 255, 0.08)",
            borderRadius: "8px",
            gap: "2px"
          }}>
            <button
              onClick={() => onModeChange('story')}
              style={{
                display: "flex",
                alignItems: "center",
                gap: "6px",
                padding: "6px 12px",
                borderRadius: "6px",
                border: "none",
                background: mode === 'story' ? "var(--accent-cyan)" : "transparent",
                color: mode === 'story' ? "#07070b" : "var(--text-secondary)",
                fontFamily: "var(--font-mono)",
                fontSize: "12px",
                fontWeight: mode === 'story' ? 700 : 500,
                cursor: "pointer",
                transition: "all 0.2s ease",
                boxShadow: mode === 'story' ? "0 0 12px rgba(0, 240, 255, 0.4)" : "none"
              }}
            >
              <Sparkles size={14} />
              <span>STORY MODE</span>
            </button>

            <button
              onClick={() => onModeChange('warroom')}
              style={{
                display: "flex",
                alignItems: "center",
                gap: "6px",
                padding: "6px 12px",
                borderRadius: "6px",
                border: "none",
                background: mode === 'warroom' ? "var(--accent-red)" : "transparent",
                color: mode === 'warroom' ? "#ffffff" : "var(--text-secondary)",
                fontFamily: "var(--font-mono)",
                fontSize: "12px",
                fontWeight: mode === 'warroom' ? 700 : 500,
                cursor: "pointer",
                transition: "all 0.2s ease",
                boxShadow: mode === 'warroom' ? "0 0 12px rgba(255, 42, 85, 0.4)" : "none"
              }}
            >
              <LayoutDashboard size={14} />
              <span>WAR ROOM</span>
            </button>
          </div>

          {/* Guided Demo Auto-Run Trigger */}
          {onRunGuidedDemo && (
            <button
              onClick={onRunGuidedDemo}
              className="cyber-button-primary"
              style={{
                padding: "6px 14px",
                fontSize: "11px",
                background: "linear-gradient(135deg, var(--accent-cyan), #00a2ff)",
                boxShadow: "0 0 16px rgba(0, 240, 255, 0.45)"
              }}
            >
              <Sparkles size={13} />
              <span>RUN GUIDED DEMO</span>
            </button>
          )}

          {/* Grid Status Beacon */}
          <div className="glass-panel" style={{ padding: "6px 12px", display: "flex", alignItems: "center", gap: "8px" }}>
            <span className="pulsing-dot pulsing-dot-green" />
            <span className="font-mono text-green" style={{ fontSize: "11px", fontWeight: 600 }}>
              GRID ONLINE
            </span>
          </div>
        </div>
      </div>
    </nav>
  );
}
