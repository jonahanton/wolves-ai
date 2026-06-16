"use client";

import { useEffect, useState } from "react";
import type { LiveState } from "@/lib/live";

const FAST_MS = 30_000;
const SLOW_MS = 180_000;

function liveCount(state: LiveState | null): number {
  return (state?.fixtures ?? []).filter((f) => f.status === "live").length;
}

export function useLivePoll(initial: LiveState | null): LiveState | null {
  const [state, setState] = useState(initial);
  const pollMs = liveCount(state) > 0 ? FAST_MS : SLOW_MS;

  useEffect(() => {
    const controller = new AbortController();
    const load = async () => {
      try {
        const response = await fetch("/api/fixtures-live", { cache: "no-store", signal: controller.signal });
        if (!response.ok) return;
        setState((await response.json()) as LiveState | null);
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

  return state;
}
