"use client";

import { useEffect, useState } from "react";
import type { LiveState } from "@/lib/live";

const POLL_MS = 30_000;

// no-cache revalidates with If-None-Match, so polls ride the ETag contract.
export function useLiveState(initial: LiveState | null): LiveState | null {
  const [state, setState] = useState(initial);

  useEffect(() => {
    let timer: ReturnType<typeof setTimeout>;
    let cancelled = false;

    const poll = async () => {
      if (document.visibilityState === "visible") {
        try {
          const response = await fetch("/api/live", { cache: "no-cache" });
          if (response.ok && !cancelled) setState((await response.json()) as LiveState);
        } catch {
          // keep the previous state; the staleness banner covers it
        }
      }
      timer = setTimeout(poll, POLL_MS);
    };

    timer = setTimeout(poll, POLL_MS);
    const onVisible = () => {
      if (document.visibilityState === "visible") {
        clearTimeout(timer);
        void poll();
      }
    };
    document.addEventListener("visibilitychange", onVisible);
    return () => {
      cancelled = true;
      clearTimeout(timer);
      document.removeEventListener("visibilitychange", onVisible);
    };
  }, []);

  return state;
}
