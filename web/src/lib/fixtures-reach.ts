import type { Impact, ReachStage } from "@/lib/impact";

export interface ReachShiftRow {
  teamId: string;
  code: string;
  stageLabel: string;
  fromPct: number;
  toPct: number;
  deltaPp: number;
}

const STAGE_LABEL: Record<ReachStage | "champion", string> = {
  r32: "reach R32",
  r16: "reach R16",
  qf: "reach QF",
  sf: "reach SF",
  final: "reach final",
  champion: "win cup",
};

const STAGES: (ReachStage | "champion")[] = ["r32", "r16", "qf", "sf", "final", "champion"];
const MIN_PP = 0.1;

// The two biggest in-game stage moves for one team, after-results to estimated.
export function teamReachShifts(impact: Impact | null, teamId: string, code: string): ReachShiftRow[] {
  const team = impact?.teams[teamId];
  if (!team) return [];
  return STAGES.map((stage) => {
    const value = stage === "champion" ? team.title : team.reach[stage];
    return {
      teamId,
      code,
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
