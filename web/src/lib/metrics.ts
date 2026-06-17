export type MetricKey = "champion" | "final" | "sf" | "qf" | "r16" | "r32";

export interface Metric {
  key: MetricKey;
  tab: string;
  column: string;
}

export const METRICS: Metric[] = [
  { key: "r32", tab: "Last 32", column: "% reach R32" },
  { key: "r16", tab: "Last 16", column: "% reach R16" },
  { key: "qf", tab: "Quarters", column: "% reach QF" },
  { key: "sf", tab: "Semis", column: "% reach semis" },
  { key: "final", tab: "Final", column: "% reach final" },
  { key: "champion", tab: "Champion", column: "% win WC" },
];

export function metricValue(
  key: MetricKey,
  championProb: number,
  reachProbs: Record<string, number>,
): number {
  return key === "champion" ? championProb : (reachProbs[key] ?? 0);
}
