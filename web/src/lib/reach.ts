export type ExitStageKey =
  | "groups"
  | "r32"
  | "r16"
  | "qf"
  | "sf"
  | "final"
  | "champion";

export interface ExitStageBar {
  key: ExitStageKey;
  label: string;
  short: string;
  phrase: string;
  noun: string;
  p: number;
}

interface ExitStage {
  key: ExitStageKey;
  label: string;
  short: string;
  phrase: string;
  noun: string;
}

const EXIT_STAGES: ExitStage[] = [
  { key: "groups", label: "Groups", short: "Grp", phrase: "Out in groups", noun: "the group stage" },
  { key: "r32", label: "R32", short: "R32", phrase: "Out in R32", noun: "the round of 32" },
  { key: "r16", label: "R16", short: "R16", phrase: "Out in R16", noun: "the round of 16" },
  { key: "qf", label: "QF", short: "QF", phrase: "Out in QF", noun: "the quarter-finals" },
  { key: "sf", label: "SF", short: "SF", phrase: "Out in SF", noun: "the semi-finals" },
  { key: "final", label: "Final", short: "Fin", phrase: "Runners-up", noun: "the final" },
  { key: "champion", label: "Champion", short: "Win", phrase: "Champions", noun: "the title" },
];

// Successive differences of the cumulative reach chain; champion bin == board %.
export function exitStageBars(reachProbs: Record<string, number>): ExitStageBar[] {
  const reach = (key: string): number => reachProbs[key] ?? 0;
  const probs: Record<ExitStageKey, number> = {
    groups: 1 - reach("r32"),
    r32: reach("r32") - reach("r16"),
    r16: reach("r16") - reach("qf"),
    qf: reach("qf") - reach("sf"),
    sf: reach("sf") - reach("final"),
    final: reach("final") - reach("champion"),
    champion: reach("champion"),
  };
  return EXIT_STAGES.map((stage) => ({
    ...stage,
    p: Math.max(0, probs[stage.key]),
  }));
}

const SETTLED_SHARE = 0.99;

export function settledBar(bars: ExitStageBar[]): ExitStageBar | null {
  return bars.find((bar) => bar.p >= SETTLED_SHARE) ?? null;
}

// Probability-weighted average finishing stage, as a fractional bar index.
export function meanStageIndex(bars: ExitStageBar[]): number {
  const total = bars.reduce((sum, b) => sum + b.p, 0);
  if (total <= 0) return 0;
  return bars.reduce((sum, b, i) => sum + i * b.p, 0) / total;
}

// The single most likely finishing stage.
export function modeBar(bars: ExitStageBar[]): ExitStageBar {
  return bars.reduce((best, b) => (b.p > best.p ? b : best), bars[0]);
}
