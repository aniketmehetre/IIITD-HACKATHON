"use client";

import React from "react";
import { 
  Terminal, 
  Radar, 
  Zap, 
  Cpu, 
  Network, 
  FileCheck2, 
  CheckCircle2,
  ChevronRight
} from "lucide-react";
import { PipelineStage } from "@/lib/types";

interface StageProgressRailProps {
  currentStage: PipelineStage;
  onStageClick?: (stage: PipelineStage) => void;
}

export function StageProgressRail({
  currentStage,
  onStageClick
}: StageProgressRailProps) {
  const stages: { id: PipelineStage; num: string; name: string; icon: React.ElementType }[] = [
    { id: "intake", num: "01", name: "Intake", icon: Terminal },
    { id: "triage", num: "02", name: "Triage", icon: Radar },
    { id: "detonate", num: "03", name: "Detonate", icon: Zap },
    { id: "enrich", num: "04", name: "Enrich", icon: Cpu },
    { id: "cluster", num: "05", name: "Cluster", icon: Network },
    { id: "act", num: "06", name: "Takedown", icon: FileCheck2 },
  ];

  const stageOrder: PipelineStage[] = ["intake", "triage", "detonate", "enrich", "cluster", "act", "complete"];
  const currentIndex = stageOrder.indexOf(currentStage);

  const scrollToStage = (stageId: PipelineStage) => {
    if (onStageClick) {
      onStageClick(stageId);
    }
    const elem = document.getElementById(`stage-${stageId}`);
    if (elem) {
      elem.scrollIntoView({ behavior: "smooth" });
    }
  };

  return (
    <div style={{
      position: "sticky",
      top: "70px",
      zIndex: 90,
      backdropFilter: "blur(12px)",
      WebkitBackdropFilter: "blur(12px)",
      backgroundColor: "rgba(10, 11, 19, 0.75)",
      borderBottom: "1px solid rgba(255, 255, 255, 0.05)",
      padding: "10px 24px"
    }}>
      <div style={{
        maxWidth: "1400px",
        margin: "0 auto",
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        overflowX: "auto",
        gap: "8px",
        scrollbarWidth: "none"
      }}>
        {stages.map((stage, idx) => {
          const Icon = stage.icon;
          const isPassed = currentIndex > idx || currentStage === 'complete';
          const isCurrent = currentStage === stage.id;

          let badgeColor = "rgba(255, 255, 255, 0.04)";
          let borderColor = "rgba(255, 255, 255, 0.08)";
          let textColor = "var(--text-muted)";
          let iconColor = "var(--text-muted)";

          if (isCurrent) {
            badgeColor = "var(--accent-cyan-dim)";
            borderColor = "var(--border-cyan)";
            textColor = "var(--accent-cyan)";
            iconColor = "var(--accent-cyan)";
          } else if (isPassed) {
            badgeColor = "var(--accent-green-dim)";
            borderColor = "var(--border-green)";
            textColor = "var(--accent-green)";
            iconColor = "var(--accent-green)";
          }

          return (
            <React.Fragment key={stage.id}>
              <button
                onClick={() => scrollToStage(stage.id)}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "8px",
                  padding: "6px 14px",
                  borderRadius: "8px",
                  background: badgeColor,
                  border: `1px solid ${borderColor}`,
                  cursor: "pointer",
                  transition: "all 0.2s ease",
                  whiteSpace: "nowrap",
                  boxShadow: isCurrent ? "0 0 14px rgba(0, 240, 255, 0.25)" : "none"
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                  {isPassed ? (
                    <CheckCircle2 size={15} color="var(--accent-green)" />
                  ) : (
                    <Icon size={15} color={iconColor} />
                  )}
                  <span className="font-mono" style={{ fontSize: "11px", fontWeight: 700, color: textColor }}>
                    {stage.num}
                  </span>
                </div>

                <span className="font-display" style={{ fontSize: "12px", fontWeight: 600, color: isCurrent ? "#fff" : textColor }}>
                  {stage.name}
                </span>

                {isCurrent && (
                  <span className="pulsing-dot pulsing-dot-green" style={{ width: "6px", height: "6px" }} />
                )}
              </button>

              {idx < stages.length - 1 && (
                <div style={{ display: "flex", alignItems: "center", opacity: 0.35 }}>
                  <ChevronRight size={14} color="var(--accent-cyan)" />
                </div>
              )}
            </React.Fragment>
          );
        })}
      </div>
    </div>
  );
}
