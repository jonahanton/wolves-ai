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
  homePossession: number | null;
  awayPossession: number | null;
  homeTotalShots: number | null;
  awayTotalShots: number | null;
  homeShotsOn: number | null;
  awayShotsOn: number | null;
}

function pair(home: number | null, away: number | null): [number, number] | null {
  return home === null || away === null ? null : [home, away];
}

function buildRows(props: LiveStatsStripProps): StatRow[] {
  const rows: StatRow[] = [];
  const possession = pair(props.homePossession, props.awayPossession);
  if (possession) {
    rows.push({
      label: "Possession",
      home: possession[0],
      away: possession[1],
      homeText: `${Math.round(possession[0] * 100)}%`,
      awayText: `${Math.round(possession[1] * 100)}%`,
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

function StatBar({ row, colours }: { row: StatRow; colours: RowColours }) {
  const total = row.home + row.away;
  const homePct = total > 0 ? (row.home / total) * 100 : 50;
  return (
    <div className="space-y-1">
      <p className="text-center font-display text-[10.5px] uppercase tracking-[0.06em] text-cream-faint">{row.label}</p>
      <div className="grid grid-cols-[2rem_1fr_2rem] items-center gap-2.5">
        <span className="text-right font-mono text-[12.5px] tabular-nums text-cream-dim">{row.homeText}</span>
        <span className="flex h-[7px] overflow-hidden rounded-full bg-night-2">
          <span style={{ width: `${homePct}%`, backgroundColor: colours.home }} />
          <span style={{ width: `${100 - homePct}%`, backgroundColor: colours.away }} />
        </span>
        <span className="font-mono text-[12.5px] tabular-nums text-cream-dim">{row.awayText}</span>
      </div>
    </div>
  );
}

export function LiveStatsStrip(props: LiveStatsStripProps) {
  const rows = buildRows(props);
  if (rows.length === 0) return null;
  return (
    <div className="space-y-3">
      {rows.map((row) => (
        <StatBar key={row.label} row={row} colours={props.colours} />
      ))}
      <p className="font-display text-[11.5px] text-cream-faint">Shots and possession nudge the live forecast.</p>
    </div>
  );
}
