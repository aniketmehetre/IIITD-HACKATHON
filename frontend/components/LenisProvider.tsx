"use client";

import React, { useEffect, useRef } from "react";
import Lenis from "lenis";

export function LenisProvider({ children }: { children: React.ReactNode }) {
  const lenisRef = useRef<Lenis | null>(null);

  useEffect(() => {
    // Only initialize smooth scroll on desktop screens for optimal performance
    if (typeof window !== "undefined") {
      const lenis = new Lenis({
        duration: 1.2,
        easing: (t) => Math.min(1, 1.001 - Math.pow(2, -10 * t)),
        orientation: "vertical",
        gestureOrientation: "vertical",
        smoothWheel: true,
        wheelMultiplier: 1.0,
        touchMultiplier: 2.0,
      });

      lenisRef.current = lenis;

      function raf(time: number) {
        lenis.raf(time);
        requestAnimationFrame(raf);
      }

      const rafId = requestAnimationFrame(raf);

      return () => {
        cancelAnimationFrame(rafId);
        lenis.destroy();
      };
    }
  }, []);

  return <>{children}</>;
}
