"use client";

import { useEffect, useState } from "react";

const DURATION_MS = 280;

export function useRollingValue(target: number, from: number | null): number {
  const [animated, setAnimated] = useState<number | null>(null);

  useEffect(() => {
    if (from === null || from === target) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    let raf = 0;
    const start = performance.now();
    const tick = (now: number) => {
      const t = Math.min((now - start) / DURATION_MS, 1);
      const eased = 1 - (1 - t) ** 3;
      setAnimated(t < 1 ? from + (target - from) * eased : null);
      if (t < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [target, from]);

  return animated ?? target;
}
