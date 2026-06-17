"use client";

import { forwardRef, useMemo, useState } from "react";
import { MetricTabs } from "@/components/teams/metric-tabs";
import { useCountUp } from "@/hooks/use-count-up";
import { useFlipReorder } from "@/hooks/use-flip-reorder";
import type { BoardRow } from "@/lib/derive";
import { type MetricKey, METRICS, metricValue } from "@/lib/metrics";
import { chartColour } from "@/lib/team-colours";

interface PredictionBoardProps {
  board: BoardRow[];
  reachProbs: Record<string, Record<string, number>>;
  names: Record<string, string>;
}

const LEAD = 8;

export function PredictionBoard({ board, reachProbs, names }: PredictionBoardProps) {
  const [metric, setMetric] = useState<MetricKey>("champion");
  const [expanded, setExpanded] = useState(false);
  const setRef = useFlipReorder(`${metric}-${expanded}`);

  const ranked = useMemo(
    () =>
      board
        .map((row) => ({ row, value: metricValue(metric, row.prob, reachProbs[row.teamId] ?? {}) }))
        .sort((a, b) => b.value - a.value),
    [board, metric, reachProbs],
  );
  const shown = expanded ? ranked : ranked.slice(0, LEAD);
  const overflow = ranked.length - LEAD;
  const max = ranked[0]?.value ?? 1;
  const column = METRICS.find((m) => m.key === metric)?.column ?? "";

  return (
    <div>
      <MetricTabs selected={metric} onSelect={setMetric} />
      <div aria-hidden className="mt-[clamp(10px,1.4vh,16px)] h-px bg-hairline" />
      <div className="flex items-center gap-3 pb-1 pt-2">
        <span className="w-[clamp(88px,15vw,140px)] shrink-0" />
        <span className="flex-1 text-right font-mono text-[10.5px] font-medium uppercase tracking-[0.04em] text-cream-faint">
          {column}
        </span>
      </div>

      <ol>
        {shown.map(({ row, value }) => (
          <BarRow
            key={row.teamId}
            ref={setRef(row.teamId)}
            name={names[row.teamId] ?? row.name}
            teamId={row.teamId}
            value={value}
            max={max}
          />
        ))}
      </ol>

      {overflow > 0 && (
        <button
          type="button"
          onClick={() => setExpanded((v) => !v)}
          className="mt-3 font-display text-[13px] font-semibold text-cream-dim transition-colors hover:text-cream"
        >
          {expanded ? "Show fewer" : `Show all ${ranked.length}`}
        </button>
      )}
    </div>
  );
}

interface BarRowProps {
  name: string;
  teamId: string;
  value: number;
  max: number;
}

const BarRow = forwardRef<HTMLLIElement, BarRowProps>(function BarRow({ name, teamId, value, max }, ref) {
  const colour = chartColour(teamId);
  const pct = useCountUp(value * 100);
  const width = max > 0 ? Math.min(100, (value / max) * 100) : 0;

  return (
    <li ref={ref} className="flex items-center gap-3 py-1.5">
      <span className="w-[clamp(88px,15vw,140px)] shrink-0 truncate font-display text-[14px] font-semibold text-cream">
        {name}
      </span>
      <span className="relative h-[8px] flex-1 overflow-hidden rounded-[2px] bg-cream/8">
        <span
          className="absolute inset-y-0 left-0 rounded-[2px] transition-[width] duration-[460ms] ease-[cubic-bezier(0.25,1,0.5,1)] motion-reduce:transition-none"
          style={{ width: `${width}%`, backgroundColor: colour, opacity: 0.85 }}
        />
      </span>
      <span className="w-12 shrink-0 text-right font-mono text-[12.5px] font-medium tabular-nums" style={{ color: colour }}>
        {pct.toFixed(1)}%
      </span>
    </li>
  );
});
