"use client";

import { ArrowRight, ChevronRight } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import type { ForecastIndexRow as Row } from "@/lib/forecast";
import { formatPctBare, formatRunStampEastern } from "@/lib/format";
import { chartColour, teamCode } from "@/lib/team-colours";

interface ForecastIndexRowProps {
  row: Row;
  names: Record<string, string>;
  latest: boolean;
}

export function ForecastIndexRow({ row, names, latest }: ForecastIndexRowProps) {
  const [open, setOpen] = useState(false);
  const overflow = row.totalTeams - row.top.length;

  const stamp = (
    <span className="flex items-baseline gap-2.5">
      <span className="font-display text-[14px] font-semibold tracking-[-0.01em] text-cream">
        {formatRunStampEastern(row.createdAt)} ET
      </span>
      {latest && (
        <span className="shimmer-cream font-display text-[11px] font-bold uppercase tracking-[0.08em]">Latest</span>
      )}
      {row.cost !== null && (
        <span className="font-mono text-[12px] tabular-nums text-cream-faint">${row.cost.toFixed(2)}</span>
      )}
    </span>
  );

  const detail = (
    <div className="flex flex-wrap items-center gap-x-3.5 gap-y-2">
      <span className="flex flex-wrap items-baseline gap-x-3.5 gap-y-1">
        {row.top.map((team) => (
          <span key={team.teamId} className="flex items-baseline gap-1.5">
            <span className="font-display text-[13px] font-semibold" style={{ color: chartColour(team.teamId) }}>
              {teamCode(names[team.teamId] ?? team.name)}
            </span>
            <span className="font-mono text-[12.5px] font-medium tabular-nums text-cream-dim">
              {formatPctBare(team.prob)}%
            </span>
          </span>
        ))}
        {overflow > 0 && <span className="font-display text-[12px] text-cream-faint">+{overflow} more</span>}
      </span>
      <Link
        href={`/forecast/${row.runId}`}
        className="flex items-center gap-1.5 font-display text-[14px] font-bold tracking-[-0.01em] text-cream transition-colors hover:text-cream-dim"
      >
        See run log
        <ArrowRight size={15} className="shrink-0" />
      </Link>
    </div>
  );

  if (latest) {
    return (
      <li className="border-b border-hairline last:border-b-0 py-3">
        {stamp}
        <div className="mt-2.5">{detail}</div>
      </li>
    );
  }

  return (
    <li className="border-b border-hairline last:border-b-0">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="flex w-full items-center gap-3 py-3 text-left"
      >
        {stamp}
        <ChevronRight
          size={15}
          className="ml-auto shrink-0 text-cream-faint transition-transform duration-300 motion-reduce:transition-none"
          style={{ transform: open ? "rotate(90deg)" : "none" }}
        />
      </button>
      <div
        className="grid transition-[grid-template-rows] duration-300 ease-out motion-reduce:transition-none"
        style={{ gridTemplateRows: open ? "1fr" : "0fr" }}
      >
        <div className="overflow-hidden" inert={!open}>
          <div className="pb-3">{detail}</div>
        </div>
      </div>
    </li>
  );
}
