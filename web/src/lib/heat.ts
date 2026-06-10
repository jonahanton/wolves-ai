const MAX_MIX_PCT = 55;

export function heatFill(prob: number, gold = false): string | undefined {
  if (prob < 0.005) return undefined;
  const mix = Math.round(Math.min(prob, 1) * MAX_MIX_PCT);
  return `color-mix(in oklab, var(${gold ? "--gold" : "--heat"}) ${mix}%, transparent)`;
}
