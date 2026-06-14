"use client";

import { Check } from "lucide-react";
import { useState } from "react";
import { Accent, ChartHeading } from "@/components/teams/chart-heading";
import { ChartTooltip } from "@/components/charts/chart-tooltip";
import { StageTabs } from "@/components/teams/stage-tabs";
import { opponentDraw, REMAINDER_ID, type OpponentSegment, type StreamRound } from "@/lib/opponents";
import type { PlayedResultRow } from "@/lib/results";
import type { PairingMatrices } from "@/lib/sidecars";
import { chartColour } from "@/lib/team-colours";

interface OpponentDrawProps {
  teamId: string;
  teamName: string;
  colour: string;
  rounds: PairingMatrices["rounds"];
  reachProbs: Record<string, number>;
  results: PlayedResultRow[];
  names: Record<string, string>;
}

const REMAINDER_FILL = "oklch(0.965 0.008 95 / 0.1)";

interface Hover {
  x: number;
  y: number;
  seg: OpponentSegment;
}

export function OpponentDraw({ teamId, teamName, colour, rounds, reachProbs, results, names }: OpponentDrawProps) {
  const draw = opponentDraw(rounds, teamId, reachProbs, results, names);
  const [stage, setStage] = useState<StreamRound>(draw.rounds[0]?.round ?? "r32");
  const [hover, setHover] = useState<Hover | null>(null);

  const bar = draw.rounds.find((r) => r.round === stage) ?? draw.rounds[0];
  const ranked = [...bar.segments].sort((a, b) => {
    if (a.opponentId === REMAINDER_ID) return 1;
    if (b.opponentId === REMAINDER_ID) return -1;
    return b.p - a.p;
  });

  const top = ranked.find((s) => s.opponentId !== REMAINDER_ID);
  const reach = reachProbs[stage] ?? 0;
  const topName = top ? (names[top.opponentId] ?? top.opponentId) : "";

  return (
    <div className="relative">
      <ChartHeading>
        {bar.played ? (
          <>
            <Accent colour={colour}>{teamName}</Accent> faced <Accent colour={chartColour(top?.opponentId ?? "")}>{topName}</Accent>{" "}
            in the {bar.label}.
          </>
        ) : top ? (
          <>
            Most likely {bar.label} opponent:{" "}
            <Accent colour={chartColour(top.opponentId)}>{topName}</Accent> ({Math.round(top.p * 100)}%)
            {bar.confirmedReach ? (
              <>.</>
            ) : (
              <>
                , if <Accent colour={colour}>{teamName}</Accent> qualify ({Math.round(reach * 100)}% chance).
              </>
            )}
          </>
        ) : bar.reachable ? (
          <>
            The field of <Accent colour={colour}>{teamName}</Accent>&rsquo;s likely {bar.label} opponents is wide open.
          </>
        ) : (
          <>
            <Accent colour={colour}>{teamName}</Accent> are unlikely to reach the {bar.label}.
          </>
        )}
      </ChartHeading>

      <StageTabs rounds={draw.rounds} selected={stage} colour={colour} onSelect={setStage} />

      <ol className="mt-4 flex flex-col gap-2">
        {ranked.map((seg) => {
          const isRemainder = seg.opponentId === REMAINDER_ID;
          const fill = isRemainder ? REMAINDER_FILL : chartColour(seg.opponentId);
          const label = isRemainder ? "Other" : (names[seg.opponentId] ?? seg.opponentId);
          return (
            <li
              key={seg.opponentId}
              className="flex items-center gap-3"
              aria-label={bar.played ? `${label}, played` : `${label}, ${Math.round(seg.p * 100)}%`}
              onMouseEnter={(e) => setHover({ x: e.clientX, y: e.clientY, seg })}
              onMouseMove={(e) => setHover({ x: e.clientX, y: e.clientY, seg })}
              onMouseLeave={() => setHover(null)}
            >
              <span
                className={`w-[clamp(72px,12vw,108px)] shrink-0 truncate font-display text-[13px] ${isRemainder ? "text-cream-faint" : "font-medium text-cream-dim"}`}
              >
                {label}
              </span>
              <span className="relative h-[12px] flex-1 overflow-hidden rounded-[2px] bg-cream/[0.05]">
                <span
                  className="absolute inset-y-0 left-0 rounded-[2px] transition-[width] duration-[420ms] ease-[cubic-bezier(0.25,1,0.5,1)] motion-reduce:transition-none"
                  style={{ width: `${seg.p * 100}%`, backgroundColor: fill, opacity: isRemainder ? 1 : 0.85 }}
                />
              </span>
              <span
                className="flex w-11 shrink-0 items-center justify-end gap-0.5 text-right font-mono text-[14px] font-semibold tabular-nums"
                style={{ color: isRemainder ? "var(--color-cream-faint)" : fill }}
              >
                {bar.played ? <Check size={13} strokeWidth={3} /> : `${Math.round(seg.p * 100)}%`}
              </span>
            </li>
          );
        })}
      </ol>

      {hover && (
        <ChartTooltip x={hover.x} y={hover.y}>
          <div className="font-display text-[12.5px]">
            {hover.seg.opponentId === REMAINDER_ID ? (
              <>
                <div className="font-semibold text-cream-dim">Other opponents</div>
                <div className="mt-1 tabular-nums text-cream-faint">
                  {`${Math.round(hover.seg.p * 100)}% of the time, ${teamName} face someone outside the names shown`}
                </div>
              </>
            ) : (
              <>
                <div className="font-semibold" style={{ color: chartColour(hover.seg.opponentId) }}>
                  {names[hover.seg.opponentId] ?? hover.seg.opponentId}
                </div>
                <div className="mt-1 tabular-nums text-cream-dim">
                  {bar.played
                    ? `${teamName} played them in the ${bar.label}`
                    : `${Math.round(hover.seg.p * 100)}% of the time, if ${teamName} reach the ${bar.label}`}
                </div>
              </>
            )}
          </div>
        </ChartTooltip>
      )}
    </div>
  );
}
