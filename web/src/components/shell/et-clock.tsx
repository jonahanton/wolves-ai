"use client";

import { Clock } from "lucide-react";
import { useEffect, useState } from "react";

function nowInEt(): string {
  return new Date().toLocaleTimeString("en-GB", {
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "America/New_York",
  });
}

export function EtClock() {
  const [time, setTime] = useState<string | null>(null);

  useEffect(() => {
    const tick = () => setTime(nowInEt());
    const id = window.setInterval(tick, 15_000);
    tick();
    return () => window.clearInterval(id);
  }, []);

  return (
    <span
      className="flex items-center gap-1.5 font-mono text-[11px] font-semibold text-cream-dim tabular-nums"
      suppressHydrationWarning
    >
      {time && (
        <>
          <Clock size={12} className="shrink-0 text-cream-faint" />
          Current time {time} ET
        </>
      )}
    </span>
  );
}
