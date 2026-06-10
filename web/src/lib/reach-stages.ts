export interface ReachStage {
  key: string;
  label: string;
}

export const REACH_STAGES: ReachStage[] = [
  { key: "r32", label: "R32" },
  { key: "r16", label: "R16" },
  { key: "qf", label: "QF" },
  { key: "sf", label: "SF" },
  { key: "final", label: "F" },
  { key: "champion", label: "W" },
];

// At 390px the odds table shows at most four probability columns; the rest live in the team sheet.
const TABLE_KEYS = new Set(["r16", "qf", "sf", "champion"]);

export const TABLE_STAGES: ReachStage[] = REACH_STAGES.filter((stage) => TABLE_KEYS.has(stage.key));
