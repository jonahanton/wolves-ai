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
