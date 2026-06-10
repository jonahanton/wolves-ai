"use client";

import { useEffect, useMemo, useSyncExternalStore } from "react";
import type { SnapshotSummary } from "@/lib/derive";
import { appendSummary, readSnapshotHistory, writeSnapshotHistory } from "@/lib/snapshot-history";

const subscribeNever = () => () => {};

export function useSnapshotHistory(summary: SnapshotSummary): SnapshotSummary[] | null {
  const hydrated = useSyncExternalStore(
    subscribeNever,
    () => true,
    () => false,
  );

  const entries = useMemo(
    () => (hydrated ? appendSummary(readSnapshotHistory(), summary) : null),
    [hydrated, summary],
  );

  useEffect(() => {
    if (entries) writeSnapshotHistory(entries);
  }, [entries]);

  return entries;
}
