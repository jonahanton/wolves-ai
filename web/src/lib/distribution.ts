export interface Frequency {
  denominator: number;
  capped: boolean;
}

export function oneInN(p: number, cap = 100): Frequency | null {
  if (!(p > 0)) return null;
  const n = Math.round(1 / p);
  if (n >= cap) return { denominator: cap, capped: true };
  return { denominator: Math.max(2, n), capped: false };
}
