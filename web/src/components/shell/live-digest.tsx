"use client";

import { ChevronDown } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import type { Impact } from "@/lib/impact";
import {
  compactLiveDigest,
  fixtureLabel,
  resultLabel,
  teamDisplayName,
  topTitleMovers,
} from "@/lib/impact-view";
import type { LiveState } from "@/lib/live";
import { liveIsFresh } from "@/lib/live";

interface LiveDigestPayload {
  live: LiveState | null;
  impact: Impact | null;
}

interface LiveDigestProps {
  initialLive: LiveState | null;
  initialImpact: Impact | null;
}

function pct(value: number | null | undefined): string {
  return value === null || value === undefined
    ? ""
    : `${Math.round(value * 100)}%`;
}

function signed(value: number): string {
  return `${value > 0 ? "+" : ""}${value.toFixed(1)}`;
}

function timeLabel(value: string): string {
  return new Date(value).toLocaleTimeString("en-GB", {
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "America/New_York",
  });
}

export function LiveDigest({ initialLive, initialImpact }: LiveDigestProps) {
  const [open, setOpen] = useState(false);
  const [payload, setPayload] = useState<LiveDigestPayload>({
    live: initialLive,
    impact: initialImpact,
  });
  const digest = useMemo(
    () => compactLiveDigest(payload.live, payload.impact),
    [payload],
  );
  const liveFixtures = (payload.live?.fixtures ?? []).filter(
    (fixture) => fixture.status === "live",
  );
  const movers = topTitleMovers(payload.impact);
  const pollMs = liveFixtures.length > 0 ? 30_000 : 180_000;
  const fresh = liveIsFresh(payload.live);

  useEffect(() => {
    let active = true;
    const load = async () => {
      try {
        const response = await fetch("/api/live-digest", { cache: "no-store" });
        if (!response.ok || !active) return;
        setPayload((await response.json()) as LiveDigestPayload);
      } catch {
        return;
      }
    };
    const id = window.setInterval(load, pollMs);
    return () => {
      active = false;
      window.clearInterval(id);
    };
  }, [pollMs]);

  return (
    <section
      aria-label="Live results digest"
      className="pointer-events-none sticky top-10 z-10"
    >
      <div className="absolute inset-x-0 top-0 flex justify-center px-4">
        <div className="pointer-events-auto w-[min(430px,calc(100vw_-_32px))]">
          <div
            className="grid origin-top transition-[grid-template-rows,opacity,transform] duration-[360ms] ease-[cubic-bezier(0.22,1,0.36,1)] motion-reduce:transition-none"
            style={{
              gridTemplateRows: open ? "1fr" : "0fr",
              opacity: open ? 1 : 0,
              transform: open
                ? "translateY(0) scaleY(1)"
                : "translateY(-10px) scaleY(0.96)",
            }}
          >
            <div className="overflow-hidden">
              <div
                className="max-h-[70dvh] overflow-y-auto px-4 pb-3 pt-4 shadow-[0_18px_44px_oklch(0_0_0/0.24)] backdrop-blur-md"
                style={{ backgroundColor: "oklch(0.17 0.025 248 / 0.88)" }}
              >
                <div className="grid gap-3">
                  <div className="min-w-0">
                    <h2 className="font-display text-[11.5px] font-semibold text-cream">
                      Live now
                    </h2>
                    <div className="mt-2 space-y-2">
                      {liveFixtures.length > 0 ? (
                        liveFixtures.map((fixture) => (
                          <div
                            key={fixture.externalId}
                            className="font-display text-[12.5px] text-cream-dim"
                          >
                            <div className="flex items-baseline justify-between gap-3">
                              <span className="truncate text-cream">
                                {fixtureLabel(fixture)}
                              </span>
                              <span className="shrink-0 font-mono text-[11px] text-cream-faint">
                                {fixture.minute ? `${fixture.minute}'` : ""}
                              </span>
                            </div>
                            {fixture.forecast && (
                              <div className="mt-1 font-mono text-[10.5px] text-cream-faint">
                                {pct(fixture.forecast.pHome)} home,{" "}
                                {pct(fixture.forecast.pDraw)} draw,{" "}
                                {pct(fixture.forecast.pAway)} away
                              </div>
                            )}
                          </div>
                        ))
                      ) : (
                        <p className="font-display text-[12.5px] text-cream-faint">
                          No live matches.
                        </p>
                      )}
                    </div>
                  </div>

                  <div className="min-w-0 border-t border-hairline pt-3">
                    <h2 className="font-display text-[11.5px] font-semibold text-cream">
                      Since the full forecast
                    </h2>
                    <div className="mt-2 space-y-1.5">
                      {(payload.impact?.resultsSinceAgent ?? []).length > 0 ? (
                        payload.impact!.resultsSinceAgent.map((result) => (
                          <div
                            key={`${result.match}-${result.kind}`}
                            className="font-display text-[12.5px] text-cream-dim"
                          >
                            {resultLabel(result)}
                          </div>
                        ))
                      ) : (
                        <p className="font-display text-[12.5px] text-cream-faint">
                          No results yet.
                        </p>
                      )}
                    </div>
                  </div>

                  <div className="min-w-0 border-t border-hairline pt-3">
                    <h2 className="font-display text-[11.5px] font-semibold text-cream">
                      Moved most
                    </h2>
                    <div className="mt-2 space-y-1.5">
                      {movers.length > 0 ? (
                        movers.map((mover) => (
                          <div
                            key={mover.teamId}
                            className="flex justify-between gap-3 font-display text-[12.5px]"
                          >
                            <span className="truncate text-cream-dim">
                              {teamDisplayName(mover.teamId)}
                            </span>
                            <span className="shrink-0 font-mono text-[11px] text-cream">
                              {signed(mover.deltaPp)}pp
                            </span>
                          </div>
                        ))
                      ) : (
                        <p className="font-display text-[12.5px] text-cream-faint">
                          No material movement.
                        </p>
                      )}
                    </div>
                  </div>
                </div>

                <div className="mt-3 flex flex-wrap justify-between gap-x-4 gap-y-1 border-t border-hairline pt-2 font-mono text-[10px] text-cream-faint">
                  {payload.impact && (
                    <span>
                      Full forecast: {timeLabel(payload.impact.agentCreatedAt)}{" "}
                      ET
                    </span>
                  )}
                  {payload.live && (
                    <span>
                      {fresh ? "Checked" : "Last checked"}{" "}
                      {timeLabel(payload.live.fetchedAt)} ET
                    </span>
                  )}
                </div>
              </div>
            </div>
          </div>

          <button
            type="button"
            data-testid="live-digest-toggle"
            onClick={() => setOpen((value) => !value)}
            aria-expanded={open}
            className="relative z-20 -mt-px mx-auto flex h-[24px] w-full items-center justify-between gap-3 px-7 text-left outline-none transition-transform duration-[220ms] ease-out hover:translate-y-0.5 focus-visible:drop-shadow-[0_0_0_1px_oklch(0.965_0.008_95/0.5)] motion-reduce:transition-none"
          >
            <svg
              aria-hidden
              viewBox="0 0 430 24"
              preserveAspectRatio="none"
              className="absolute inset-0 -z-10 h-full w-full overflow-visible"
            >
              <path
                d="M0 0H430L412 17Q405 24 388 24H42Q25 24 18 17L0 0Z"
                fill="oklch(0.17 0.025 248 / 0.88)"
              />
            </svg>
            <span className="min-w-0 truncate font-display text-[11.5px] font-semibold text-cream">
              <span
                className="mr-2 font-mono text-[9px] font-semibold uppercase tracking-[0.08em] text-cream-faint"
                data-tone={digest.tone}
              >
                {digest.tone === "live"
                  ? "Live"
                  : digest.tone === "stale"
                    ? "Stale"
                    : "Update"}
              </span>
              {digest.label}
            </span>
            <ChevronDown
              size={15}
              className="shrink-0 text-cream-faint transition-transform duration-200 motion-reduce:transition-none"
              style={{ transform: open ? "rotate(180deg)" : "none" }}
            />
          </button>
        </div>
      </div>
    </section>
  );
}
