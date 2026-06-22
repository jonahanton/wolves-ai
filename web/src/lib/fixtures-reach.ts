import type { Impact } from "@/lib/impact";

const GROUP_REACH_STAGES = [
  { key: "r32", label: "Reach R32" },
  { key: "r16", label: "Reach R16" },
] as const;

export function teamReachShifts(impact: Impact | null, teamId: string) {
  const team = impact?.teams[teamId];
  if (!team) return [];
  return GROUP_REACH_STAGES.map((stage) => {
    const value = team.reach[stage.key];
    return {
      stageLabel: stage.label,
      fromPct: value.afterResults * 100,
      toPct: value.estimated * 100,
    };
  });
}
