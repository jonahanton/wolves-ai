import type { LedgerEntryOut, Snapshot } from "@/lib/snapshot";

const TIER_LABELS: Record<number, string> = { 1: "official", 2: "press", 3: "aggregator" };

export function tierLabel(tier: number | null): string | null {
  return tier === null ? null : (TIER_LABELS[tier] ?? null);
}

export function statusMark(status: string): string {
  return status === "confirmed" ? "✓" : "·";
}

// Relevance is partly null on real runs; nulls rank last, newest first within.
export function rankedLedger(snapshot: Snapshot, limit: number, teamId?: string): LedgerEntryOut[] {
  const entries = snapshot.agent?.ledger_entries ?? [];
  const filtered = teamId ? entries.filter((entry) => entry.team_id === teamId) : entries;
  return [...filtered]
    .sort((a, b) => (b.relevance ?? -1) - (a.relevance ?? -1) || b.created_at.localeCompare(a.created_at))
    .slice(0, limit);
}

export function sourceHost(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return url;
  }
}
