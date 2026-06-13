"use client";

import { useEffect, useRef, useState } from "react";

const DURATION_MS = 650;

function easeOutCubic(t: number): number {
  return 1 - (1 - t) ** 3;
}

export function useCountUp(target: number, from = 0): number {
  const [value, setValue] = useState(from);
  const currentRef = useRef(from);
  const frameRef = useRef(0);

  useEffect(() => {
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const origin = currentRef.current;
    const start = performance.now();
    const tick = (now: number) => {
      const t = reduce ? 1 : Math.min(1, (now - start) / DURATION_MS);
      const next = origin + (target - origin) * easeOutCubic(t);
      currentRef.current = next;
      setValue(next);
      if (t < 1) frameRef.current = requestAnimationFrame(tick);
    };
    frameRef.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frameRef.current);
  }, [target]);

  return value;
}
