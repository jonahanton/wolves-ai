import type { Impact, ReachStage } from "@/lib/impact";

export interface ReachShiftRow {
  stageLabel: string;
  fromPct: number;
  toPct: number;
  deltaPp: number;
}

const STAGE_LABEL: Record<ReachStage | "champion", string> = {
  r32: "Reach R32",
  r16: "Reach R16",
  qf: "Reach QF",
  sf: "Reach SF",
  final: "Reach final",
  champion: "Win cup",
};

const STAGES: (ReachStage | "champion")[] = ["r32", "r16", "qf", "sf", "final", "champion"];
const MIN_PP = 0.1;

// The two biggest in-game stage moves for one team, after-results to estimated.
export function teamReachShifts(impact: Impact | null, teamId: string): ReachShiftRow[] {
  const team = impact?.teams[teamId];
  if (!team) return [];
  return STAGES.map((stage) => {
    const value = stage === "champion" ? team.title : team.reach[stage];
    return {
      stageLabel: STAGE_LABEL[stage],
      fromPct: value.afterResults * 100,
      toPct: value.estimated * 100,
      deltaPp: value.fromIngamePp,
    };
  })
    .filter((row) => Math.abs(row.deltaPp) >= MIN_PP)
    .sort((a, b) => Math.abs(b.deltaPp) - Math.abs(a.deltaPp))
    .slice(0, 2);
}
