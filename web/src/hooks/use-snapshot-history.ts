"use client";

import { useEffect, useRef, useState, useSyncExternalStore } from "react";
import type { SnapshotSummary } from "@/lib/derive";
import { appendSummary, readSnapshotHistory, writeSnapshotHistory } from "@/lib/snapshot-history";

const subscribeNever = () => () => {};

export function useSnapshotHistory(summary: SnapshotSummary): SnapshotSummary[] | null {
  const hydrated = useSyncExternalStore(
    subscribeNever,
    () => true,
    () => false,
  );

  // summary is a fresh object every server render; keying the localStorage
  // round trip on runId keeps re-renders from thrashing storage.
  const writtenRunId = useRef<string | null>(null);
  const [entries, setEntries] = useState<SnapshotSummary[] | null>(null);

  useEffect(() => {
    if (!hydrated || writtenRunId.current === summary.runId) return;
    writtenRunId.current = summary.runId;
    const next = appendSummary(readSnapshotHistory(), summary);
    writeSnapshotHistory(next);
    setEntries(next);
  }, [hydrated, summary]);

  return entries;
}
