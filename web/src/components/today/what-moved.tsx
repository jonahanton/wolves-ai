"use client";

import { useEffect, useMemo, useSyncExternalStore } from "react";
import { TrendingDown, TrendingUp } from "lucide-react";
import { computeDeltas, type SnapshotSummary } from "@/lib/derive";
import { formatDeltaPts, formatPct } from "@/lib/format";

const STORAGE_KEY = "wolves:snapshot-history";

interface StoredHistory {
  current: SnapshotSummary;
  previous: SnapshotSummary | null;
}

function readHistory(): StoredHistory | null {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as StoredHistory) : null;
  } catch {
    return null;
  }
}

function peekPrevious(summary: SnapshotSummary): SnapshotSummary | null {
  const stored = readHistory();
  if (stored === null) return null;
  return stored.current.runId === summary.runId ? stored.previous : stored.current;
}

function persistHistory(summary: SnapshotSummary): void {
  try {
    const previous = peekPrevious(summary);
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify({ current: summary, previous }));
  } catch {
    return;
  }
}

const subscribeNever = () => () => {};

interface WhatMovedProps {
  summary: SnapshotSummary;
}

export function WhatMoved({ summary }: WhatMovedProps) {
  const hydrated = useSyncExternalStore(
    subscribeNever,
    () => true,
    () => false,
  );

  const chips = useMemo(() => {
    if (!hydrated) return undefined;
    const previous = peekPrevious(summary);
    return previous ? computeDeltas(summary, previous) : null;
  }, [hydrated, summary]);

  useEffect(() => persistHistory(summary), [summary]);

  return (
    <section aria-label="What moved">
      <h2 className="mb-2 text-xs font-semibold tracking-wide text-muted-foreground uppercase">What moved</h2>
      {chips === undefined && <div className="h-8 w-2/3 animate-pulse rounded-full bg-secondary" />}
      {chips === null && (
        <p className="text-sm text-muted-foreground">
          First snapshot on this device. Movement appears after the next run.
        </p>
      )}
      {chips?.length === 0 && <p className="text-sm text-muted-foreground">Nothing meaningful moved overnight.</p>}
      {chips && chips.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {chips.map((chip) => (
            <span
              key={chip.key}
              className="inline-flex items-center gap-1.5 rounded-full border bg-card px-3 py-1.5 text-sm"
            >
              <span className="font-medium">{chip.label}</span>
              <span className="tabular-nums text-muted-foreground">{formatPct(chip.prob)}</span>
              <span
                className={`inline-flex items-center gap-0.5 tabular-nums ${
                  chip.deltaPts > 0 ? "text-gold" : "text-muted-foreground"
                }`}
              >
                {chip.deltaPts > 0 ? <TrendingUp size={13} /> : <TrendingDown size={13} />}
                {formatDeltaPts(chip.deltaPts)}
              </span>
            </span>
          ))}
        </div>
      )}
    </section>
  );
}
