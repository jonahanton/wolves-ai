"use client";

import { useEffect, useRef, useState } from "react";
import type { Impact } from "@/lib/impact";

const POLL_MS = 60_000;

// A cold engine can outlast the server fetch; the client fills the gap once,
// then polls only while matches are in play (the estimate moves on goals).
export function useImpact(initial: Impact | null): Impact | null {
  const [impact, setImpact] = useState(initial);
  const recoveredRef = useRef(false);
  const live = (impact?.fixtures.length ?? 0) > 0;
  const recover = impact === null && !recoveredRef.current;

  useEffect(() => {
    if (!live && !recover) return;
    let timer: ReturnType<typeof setTimeout>;
    let cancelled = false;

    const poll = async () => {
      if (document.visibilityState === "visible") {
        try {
          const response = await fetch("/api/impact", { cache: "no-store" });
          if (response.ok && !cancelled) setImpact((await response.json()) as Impact);
        } catch {
          // keep the previous estimate; it is already labelled as such
        }
        recoveredRef.current = true;
      }
      if (!cancelled && live) timer = setTimeout(poll, POLL_MS);
    };

    timer = setTimeout(poll, recover ? 0 : POLL_MS);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [live, recover]);

  return impact;
}
