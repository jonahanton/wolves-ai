import type { RowColours } from "@/lib/team-colours";

interface StatRow {
  label: string;
  home: number;
  away: number;
  homeText: string;
  awayText: string;
}

interface LiveStatsStripProps {
  homeCode: string;
  awayCode: string;
  colours: RowColours;
  // When a replay is morphing the curve, the bars slide over the same duration.
  morphMs?: number;
  // During a replay the strip holds every row, splitting evenly with placeholder
  // text before a stat has been published, rather than popping rows in and out.
  replaying?: boolean;
  homePossession: number | null;
  awayPossession: number | null;
  homeTotalShots: number | null;
  awayTotalShots: number | null;
  homeShotsOn: number | null;
  awayShotsOn: number | null;
}

function countRow(label: string, home: number | null, away: number | null, replaying: boolean): StatRow | null {
  if (home === null || away === null) {
    return replaying ? { label, home: 0, away: 0, homeText: "0", awayText: "0" } : null;
  }
  return { label, home, away, homeText: `${home}`, awayText: `${away}` };
}

function possessionRow(home: number | null, away: number | null): StatRow {
  const total = (home ?? 0) + (away ?? 0);
  if (home === null || away === null || total === 0) {
    return { label: "Possession", home: 50, away: 50, homeText: "-", awayText: "-" };
  }
  return {
    label: "Possession",
    home,
    away,
    homeText: `${Math.round((home / total) * 100)}%`,
    awayText: `${Math.round((away / total) * 100)}%`,
  };
}

function buildRows(props: LiveStatsStripProps): StatRow[] {
  const replaying = props.replaying ?? false;
  return [
    possessionRow(props.homePossession, props.awayPossession),
    countRow("Shots", props.homeTotalShots, props.awayTotalShots, replaying),
    countRow("On target", props.homeShotsOn, props.awayShotsOn, replaying),
  ].filter((row): row is StatRow => row !== null);
}

function StatBar({ row, colours, morphMs }: { row: StatRow; colours: RowColours; morphMs?: number }) {
  const total = row.home + row.away;
  const homePct = total > 0 ? (row.home / total) * 100 : 50;
  const transition = morphMs ? `width ${morphMs}ms cubic-bezier(0.65, 0, 0.35, 1)` : undefined;
  return (
    <div className="flex flex-col items-center gap-0.5">
      <span className="font-display text-[11.5px] tracking-[0.01em] text-cream-dim">{row.label}</span>
      <span className="grid w-[64%] grid-cols-[1.4rem_1fr_1.4rem] items-center gap-2">
        <span className="text-right font-mono text-[11px] tabular-nums text-cream-faint">{row.homeText}</span>
        <span className="flex h-[5px] overflow-hidden rounded-full bg-night-2">
          <span style={{ width: `${homePct}%`, backgroundColor: colours.home, opacity: 0.7, transition }} />
          <span style={{ width: `${100 - homePct}%`, backgroundColor: colours.away, opacity: 0.7, transition }} />
        </span>
        <span className="font-mono text-[11px] tabular-nums text-cream-faint">{row.awayText}</span>
      </span>
    </div>
  );
}

export function LiveStatsStrip(props: LiveStatsStripProps) {
  const rows = buildRows(props);
  if (rows.length === 0) return null;
  return (
    <div className="space-y-1">
      {rows.map((row) => (
        <StatBar key={row.label} row={row} colours={props.colours} morphMs={props.morphMs} />
      ))}
    </div>
  );
}
