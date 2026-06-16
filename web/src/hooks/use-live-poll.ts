"use client";

import { useEffect, useState } from "react";
import type { Impact } from "@/lib/impact";
import type { LiveState } from "@/lib/live";

const FAST_MS = 30_000;
const SLOW_MS = 180_000;

interface LivePayload {
  live: LiveState | null;
  impact: Impact | null;
}

function liveCount(state: LiveState | null): number {
  return (state?.fixtures ?? []).filter((f) => f.status === "live").length;
}

// Live scorelines and the impact deltas keyed to them are polled together, so the
// reach strip's minute and its numbers never drift onto different clocks.
export function useLivePoll(initial: LivePayload): LivePayload {
  const [payload, setPayload] = useState(initial);
  const pollMs = liveCount(payload.live) > 0 ? FAST_MS : SLOW_MS;

  useEffect(() => {
    const controller = new AbortController();
    const load = async () => {
      try {
        const response = await fetch("/api/fixtures-live", { cache: "no-store", signal: controller.signal });
        if (!response.ok) return;
        setPayload((await response.json()) as LivePayload);
      } catch {
        return;
      }
    };
    const id = window.setInterval(load, pollMs);
    return () => {
      controller.abort();
      window.clearInterval(id);
    };
  }, [pollMs]);

  return payload;
}
