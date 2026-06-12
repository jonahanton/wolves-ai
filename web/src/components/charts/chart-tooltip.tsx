"use client";

import { useLayoutEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";

interface ChartTooltipProps {
  x: number;
  y: number;
  children: React.ReactNode;
}

const EDGE = 12;
const OFFSET = 14;

export function ChartTooltip({ x, y, children }: ChartTooltipProps) {
  const ref = useRef<HTMLDivElement>(null);
  const [pos, setPos] = useState<{ left: number; top: number } | null>(null);

  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    const { width, height } = el.getBoundingClientRect();
    let left = x + OFFSET;
    if (left + width > window.innerWidth - EDGE) left = x - width - OFFSET;
    left = Math.max(EDGE, left);
    let top = y - height / 2;
    top = Math.min(Math.max(EDGE, top), window.innerHeight - height - EDGE);
    setPos({ left, top });
  }, [x, y, children]);

  return createPortal(
    <div
      ref={ref}
      role="presentation"
      className="pointer-events-none fixed z-[60] min-w-[180px] max-w-[300px] border border-hairline bg-night-2/95 px-3.5 py-3 shadow-none backdrop-blur-sm"
      style={{ left: pos?.left ?? -9999, top: pos?.top ?? -9999, visibility: pos ? "visible" : "hidden" }}
    >
      {children}
    </div>,
    document.body,
  );
}
