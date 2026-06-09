"use client";

import { useState } from "react";
import { Minus, Plus } from "lucide-react";

function Stepper({ label, value, onChange }: { label: string; value: number; onChange: (v: number) => void }) {
  return (
    <div className="flex flex-1 flex-col items-center gap-1.5">
      <span className="max-w-full truncate text-sm font-medium">{label}</span>
      <div className="flex items-center gap-3">
        <button
          type="button"
          aria-label={`${label} score down`}
          onClick={() => onChange(Math.max(0, value - 1))}
          className="rounded-full border p-1.5 text-muted-foreground active:scale-95"
        >
          <Minus size={14} />
        </button>
        <span className="w-6 text-center text-xl font-semibold tabular-nums">{value}</span>
        <button
          type="button"
          aria-label={`${label} score up`}
          onClick={() => onChange(value + 1)}
          className="rounded-full border p-1.5 text-muted-foreground active:scale-95"
        >
          <Plus size={14} />
        </button>
      </div>
    </div>
  );
}

interface ScoreEntryProps {
  home: string;
  away: string;
}

export function ScoreEntry({ home, away }: ScoreEntryProps) {
  const [homeScore, setHomeScore] = useState(0);
  const [awayScore, setAwayScore] = useState(0);

  return (
    <section className="rounded-xl border bg-card p-4" aria-label="Manual score entry">
      <h2 className="font-semibold">Manual score entry</h2>
      <p className="mt-0.5 text-sm text-muted-foreground">For when the feed is stale or you are offline.</p>
      <div className="mt-4 flex items-start gap-2">
        <Stepper label={home} value={homeScore} onChange={setHomeScore} />
        <span className="pt-7 text-muted-foreground">:</span>
        <Stepper label={away} value={awayScore} onChange={setAwayScore} />
      </div>
      <button
        type="button"
        disabled
        className="mt-4 w-full rounded-lg border bg-secondary py-2 text-sm font-medium text-muted-foreground"
      >
        What-ifs not wired up yet
      </button>
      <p className="mt-2 text-xs text-muted-foreground">
        W/D/L chips and instant path re-renders arrive once the daily run ships conditional tables.
      </p>
    </section>
  );
}
