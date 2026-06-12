"use client";

import { useEffect, useState } from "react";
import type { Impact } from "@/lib/impact";

const POLL_MS = 60_000;

// Polls only while matches are in play; the estimate moves on goals, not seconds.
export function useImpact(initial: Impact | null): Impact | null {
  const [impact, setImpact] = useState(initial);
  const live = (initial?.fixtures.length ?? 0) > 0;

  useEffect(() => {
    if (!live) return;
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
      }
      if (!cancelled) timer = setTimeout(poll, POLL_MS);
    };

    timer = setTimeout(poll, POLL_MS);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [live]);

  return impact;
}
