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
  homePossession: number | null;
  awayPossession: number | null;
  homeTotalShots: number | null;
  awayTotalShots: number | null;
  homeShotsOn: number | null;
  awayShotsOn: number | null;
}

// A jointly-zero stat has no signal yet, so skip it rather than show a 50/50 bar.
function pair(home: number | null, away: number | null): [number, number] | null {
  return home === null || away === null || home + away === 0 ? null : [home, away];
}

function buildRows(props: LiveStatsStripProps): StatRow[] {
  const rows: StatRow[] = [];
  const possession = pair(props.homePossession, props.awayPossession);
  if (possession) {
    rows.push({
      label: "Possession",
      home: possession[0],
      away: possession[1],
      homeText: `${Math.round((possession[0] / (possession[0] + possession[1])) * 100)}%`,
      awayText: `${Math.round((possession[1] / (possession[0] + possession[1])) * 100)}%`,
    });
  }
  const shots = pair(props.homeTotalShots, props.awayTotalShots);
  if (shots) {
    rows.push({ label: "Shots", home: shots[0], away: shots[1], homeText: `${shots[0]}`, awayText: `${shots[1]}` });
  }
  const onTarget = pair(props.homeShotsOn, props.awayShotsOn);
  if (onTarget) {
    rows.push({
      label: "On target",
      home: onTarget[0],
      away: onTarget[1],
      homeText: `${onTarget[0]}`,
      awayText: `${onTarget[1]}`,
    });
  }
  return rows;
}

function StatBar({ row, colours, morphMs }: { row: StatRow; colours: RowColours; morphMs?: number }) {
  const total = row.home + row.away;
  const homePct = total > 0 ? (row.home / total) * 100 : 50;
  const transition = morphMs ? `width ${morphMs}ms cubic-bezier(0.65, 0, 0.35, 1)` : undefined;
  return (
    <div className="flex flex-col items-center gap-0.5">
      <span className="font-display text-[9px] uppercase tracking-[0.07em] text-cream-faint">{row.label}</span>
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
    <div className="space-y-2">
      {rows.map((row) => (
        <StatBar key={row.label} row={row} colours={props.colours} morphMs={props.morphMs} />
      ))}
    </div>
  );
}
