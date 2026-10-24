import type { Metadata } from "next";
import React from "react";
import "./globals.css";
import { LenisProvider } from "@/components/LenisProvider";

export const metadata: Metadata = {
  title: "STING — Autonomous Cyber Threat Intelligence & Takedown Platform",
  description: "Automated scam funnel detonation, mule payee extraction, and cartel correlation pipeline.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600;700&family=Outfit:wght@500;600;700;800;900&display=swap"
          rel="stylesheet"
        />
      </head>
      <body>
        <div className="cyber-bg" aria-hidden="true" />
        <div className="cyber-grid-dots" aria-hidden="true" />
        <LenisProvider>
          <div style={{ position: "relative", zIndex: 1, minHeight: "100vh" }}>
            {children}
          </div>
        </LenisProvider>
      </body>
    </html>
  );
}
