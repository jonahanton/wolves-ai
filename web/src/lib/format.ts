export function roundPct(prob: number): number {
  return Math.round(prob * 100);
}

export function formatPct(prob: number): string {
  const pct = roundPct(prob);
  if (pct === 0 && prob > 0) return "<1%";
  return `${pct}%`;
}

export function formatPctBare(prob: number): string {
  const pct = roundPct(prob);
  if (pct === 0 && prob > 0) return "<1";
  return `${pct}`;
}

export function frequencyFrame(prob: number): string | null {
  if (prob <= 0) return null;
  if (prob < 0.01) return "under 1 in 100 sims";
  if (prob < 0.55) {
    const n = Math.max(2, Math.round(1 / prob));
    return `about 1 in ${n} sims`;
  }
  return `${Math.round(prob * 10)} in 10 sims`;
}

export function formatDeltaPts(deltaPts: number): string {
  const rounded = Math.round(deltaPts * 10) / 10;
  return `${rounded > 0 ? "+" : ""}${rounded}`;
}

const LONDON = "Europe/London";

export function formatMatchDate(iso: string): string {
  return new Date(iso).toLocaleDateString("en-GB", {
    weekday: "short",
    day: "numeric",
    month: "short",
    timeZone: LONDON,
  });
}

export function formatKickoff(iso: string): string {
  return new Date(iso).toLocaleString("en-GB", {
    weekday: "short",
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
    timeZone: LONDON,
  });
}

export function formatUpdated(iso: string): string {
  return new Date(iso).toLocaleString("en-GB", {
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
    timeZone: LONDON,
  });
}
