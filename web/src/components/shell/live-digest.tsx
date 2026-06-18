"use client";

import { ArrowRight, ChevronDown } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import type { Impact } from "@/lib/impact";
import {
  compactLiveDigest,
  dateTimeLabel,
  type DigestToken,
  panelTimeline,
  type TimelineEntry,
  topTitleMovers,
} from "@/lib/impact-view";
import { nextAgentRunIso } from "@/lib/run-schedule";
import type { LiveState } from "@/lib/live";
import { chartColour } from "@/lib/team-colours";

interface LiveDigestPayload {
  live: LiveState | null;
  impact: Impact | null;
}

interface LiveDigestProps {
  initialLive: LiveState | null;
  initialImpact: Impact | null;
}

function signed(value: number): string {
  return `${value > 0 ? "+" : ""}${value.toFixed(1)}`;
}

const LIP_FILL = "oklch(0.17 0.025 248 / 0.985)";
const LIP_CAP_W = 28;
const LIP_CAP_L = "M0 0 C0 15 7 24 18 24 L28 24 L28 0 Z";
const LIP_CAP_R = "M28 0 C28 15 21 24 10 24 L0 24 L0 0 Z";

function teamStyle(teamId: string | null): { color: string } | undefined {
  return teamId ? { color: chartColour(teamId) } : undefined;
}

function DigestTokens({ tokens }: { tokens: DigestToken[] }) {
  return (
    <>
      {tokens.map((token, index) => {
        if (token.kind === "team") {
          return (
            <span key={index} className="font-semibold" style={teamStyle(token.teamId)}>
              {token.code}
            </span>
          );
        }
        if (token.kind === "shimmer") {
          return (
            <span key={index} className="shimmer-red font-semibold">
              {token.text}
            </span>
          );
        }
        return <span key={index}>{token.text}</span>;
      })}
    </>
  );
}

const TIMELINE_COLS = "grid grid-cols-[5.4rem_1.7rem_1.6rem_1.7rem_auto] items-baseline gap-x-0.5";

function TimelineRow({ entry }: { entry: TimelineEntry }) {
  const live = entry.kind === "live";
  const homeStyle = live ? undefined : teamStyle(entry.homeId);
  const awayStyle = live ? undefined : teamStyle(entry.awayId);
  return (
    <div className={`${TIMELINE_COLS} font-display text-[13px] leading-tight`}>
      <span className="mr-1.5 whitespace-nowrap font-mono text-[10px] text-cream-faint tabular-nums">
        {entry.time}
      </span>
      <span className={`text-right font-semibold ${live ? "shimmer-red" : ""}`} style={homeStyle}>
        {entry.homeCode}
      </span>
      <span className={`text-center font-mono text-[11.5px] tabular-nums ${live ? "shimmer-red font-semibold" : "text-cream"}`}>
        {entry.homeGoals ?? "-"}-{entry.awayGoals ?? "-"}
      </span>
      <span className={`font-semibold ${live ? "shimmer-red" : ""}`} style={awayStyle}>
        {entry.awayCode}
      </span>
      {live && entry.minute !== null ? (
        <span className="shimmer-red font-mono text-[10.5px] font-semibold">{entry.minute}&apos;</span>
      ) : entry.kind === "result" && entry.corrected ? (
        <span className="font-mono text-[9.5px] text-cream-faint">corr.</span>
      ) : null}
    </div>
  );
}

export function LiveDigest({ initialLive, initialImpact }: LiveDigestProps) {
  const [open, setOpen] = useState(false);
  const [payload, setPayload] = useState<LiveDigestPayload>({
    live: initialLive,
    impact: initialImpact,
  });
  const digest = useMemo(() => compactLiveDigest(payload.live, payload.impact), [payload]);
  const timeline = useMemo(() => panelTimeline(payload.live, payload.impact), [payload]);
  const movers = useMemo(() => topTitleMovers(payload.impact), [payload.impact]);
  const liveCount = (payload.live?.fixtures ?? []).filter((fixture) => fixture.status === "live").length;
  const pollMs = liveCount > 0 ? 30_000 : 180_000;

  const [nowEt, setNowEt] = useState<string | null>(null);
  const [nextRun, setNextRun] = useState<string | null>(null);
  useEffect(() => {
    const tick = () => {
      const now = new Date();
      setNowEt(now.toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit", timeZone: "America/New_York" }));
      setNextRun(dateTimeLabel(nextAgentRunIso(now)));
    };
    tick();
    const id = window.setInterval(tick, 15_000);
    return () => window.clearInterval(id);
  }, []);

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
    <section aria-label="Live results digest" className="relative z-10 flex justify-center px-4">
        <div className="w-[min(500px,calc(100vw_-_32px))]">
          <div
            className="grid origin-top transition-[grid-template-rows,opacity,transform] duration-[360ms] ease-[cubic-bezier(0.22,1,0.36,1)] motion-reduce:transition-none"
            style={{
              gridTemplateRows: open ? "1fr" : "0fr",
              opacity: open ? 1 : 0,
              transform: open ? "translateY(0) scaleY(1)" : "translateY(-10px) scaleY(0.96)",
            }}
          >
            <div className="overflow-hidden">
              <div
                className="max-h-[70dvh] overflow-y-auto px-5 pb-3.5 pt-3 shadow-[0_18px_44px_oklch(0_0_0/0.24)]"
                style={{ backgroundColor: LIP_FILL }}
              >
                <div className="mb-2.5 flex flex-wrap items-center gap-x-3 gap-y-0.5 border-b border-hairline pb-2 font-mono text-[11.5px] tabular-nums text-cream-faint">
                  {payload.impact && <span>Last {dateTimeLabel(payload.impact.agentCreatedAt)} ET</span>}
                  {nextRun && <span>Next {nextRun} ET</span>}
                  {nowEt && <span className="ml-auto">Now {nowEt} ET</span>}
                </div>
                {timeline.length === 0 && movers.length === 0 ? (
                  <p className="font-display text-[12px] text-cream-faint">No changes since last forecast</p>
                ) : (
                  <div className="flex flex-col gap-x-4 gap-y-3 sm:flex-row">
                    {timeline.length > 0 && (
                      <div className="min-w-0 flex-1">
                        <h2 className="font-display text-[13.5px] font-semibold text-cream">
                          Since last forecast{" "}
                          <span className="whitespace-nowrap font-mono text-[10px] font-medium text-cream-dim">
                            KO times ET
                          </span>
                        </h2>
                        <div className="mt-2 space-y-1">
                          {timeline.map((entry, index) => (
                            <TimelineRow key={index} entry={entry} />
                          ))}
                        </div>
                      </div>
                    )}

                    {movers.length > 0 && (
                      <div className="min-w-0 flex-1">
                        <h2 className="font-display text-[13.5px] font-semibold text-cream">
                          Estimated WC winner shift
                        </h2>
                        <div className="mt-2 space-y-1">
                          {movers.map((mover, index) => (
                            <div
                              key={mover.teamId}
                              className="grid grid-cols-[0.9rem_2rem_auto_3rem] items-baseline gap-x-1.5 font-display text-[13px] leading-tight"
                            >
                              <span className="font-mono text-[11px] font-semibold text-cream-faint tabular-nums">
                                {index + 1}.
                              </span>
                              <span className="font-semibold" style={teamStyle(mover.teamId)}>
                                {mover.code}
                              </span>
                              <span className="flex items-center gap-0.5 font-mono text-[10.5px] text-cream-dim tabular-nums">
                                <span className="w-8 text-right">{mover.agentPct.toFixed(1)}</span>
                                <ArrowRight size={10} strokeWidth={2.75} className="shrink-0 text-cream-faint" />
                                <span className="w-9 text-right">{mover.estimatedPct.toFixed(1)}%</span>
                              </span>
                              <span
                                className="text-right font-mono text-[10.5px] font-semibold tabular-nums"
                                style={teamStyle(mover.teamId)}
                              >
                                {signed(mover.deltaPp)}ppt
                              </span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>
          </div>

          <button
            type="button"
            data-testid="live-digest-toggle"
            onClick={() => setOpen((value) => !value)}
            aria-expanded={open}
            data-open={open}
            className="group relative z-20 -mt-px mx-auto flex min-h-6 w-full items-center justify-center gap-3 px-8 py-1 text-center outline-none motion-reduce:transition-none"
          >
            <span
              aria-hidden
              className="absolute inset-0 -z-10 flex transition-transform duration-[220ms] ease-out group-hover:translate-y-0.5 group-data-[open=true]:translate-y-0 motion-reduce:transform-none"
            >
              <svg
                viewBox={`0 0 ${LIP_CAP_W} 24`}
                preserveAspectRatio="none"
                className="h-full"
                style={{ width: LIP_CAP_W }}
              >
                <path d={LIP_CAP_L} fill={LIP_FILL} />
              </svg>
              <span className="h-full flex-1" style={{ backgroundColor: LIP_FILL }} />
              <svg
                viewBox={`0 0 ${LIP_CAP_W} 24`}
                preserveAspectRatio="none"
                className="h-full"
                style={{ width: LIP_CAP_W }}
              >
                <path d={LIP_CAP_R} fill={LIP_FILL} />
              </svg>
            </span>
            <span className="line-clamp-2 min-w-0 font-display text-[13px] font-semibold leading-tight text-cream-dim transition-transform duration-[220ms] ease-out group-hover:translate-y-0.5 group-data-[open=true]:translate-y-0 motion-reduce:transform-none">
              <DigestTokens tokens={digest.tokens} />
            </span>
            <ChevronDown
              size={15}
              className="absolute right-3 shrink-0 text-cream-faint transition-transform duration-200 ease-out group-hover:translate-y-0.5 group-data-[open=true]:translate-y-0 motion-reduce:transition-none"
              style={{ transform: open ? "rotate(180deg)" : "none" }}
            />
          </button>
        </div>
    </section>
  );
}
