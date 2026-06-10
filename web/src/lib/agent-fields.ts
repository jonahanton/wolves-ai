import type { LedgerEntryOut, Snapshot } from "@/lib/snapshot";

// The agent block arrives with later engine runs; every read tolerates it being absent or partial.
function narrativeField(snapshot: Snapshot, field: string): unknown {
  const agent = (snapshot as unknown as { agent?: { narrative?: Record<string, unknown> } | null }).agent;
  return agent?.narrative?.[field];
}

function asText(value: unknown): string | null {
  return typeof value === "string" && value.trim() !== "" ? value : null;
}

export function focusStory(snapshot: Snapshot): string | null {
  return asText(narrativeField(snapshot, "focus_story"));
}

export function travelMemo(snapshot: Snapshot): string | null {
  return asText(narrativeField(snapshot, "travel_memo"));
}

export function slotRationale(snapshot: Snapshot, match: number): string | null {
  const rationales = narrativeField(snapshot, "slot_rationales");
  if (typeof rationales !== "object" || rationales === null) return null;
  return asText((rationales as Record<string, unknown>)[String(match)]);
}

export function ledgerEntries(snapshot: Snapshot): LedgerEntryOut[] {
  const agent = (snapshot as unknown as { agent?: { ledger_entries?: unknown } | null }).agent;
  const entries = agent?.ledger_entries;
  if (!Array.isArray(entries)) return [];
  return entries.filter(
    (entry): entry is LedgerEntryOut =>
      typeof entry === "object" &&
      entry !== null &&
      typeof (entry as { claim?: unknown }).claim === "string",
  );
}
