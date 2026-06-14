"use client";

import { METRICS, type MetricKey } from "@/lib/metrics";

interface MetricTabsProps {
  selected: MetricKey;
  onSelect: (key: MetricKey) => void;
}

export function MetricTabs({ selected, onSelect }: MetricTabsProps) {
  return (
    <div className="flex flex-wrap items-center gap-x-[clamp(12px,1.8vw,22px)] gap-y-1.5">
      {METRICS.map((m) => {
        const active = m.key === selected;
        return (
          <button
            key={m.key}
            type="button"
            onClick={() => onSelect(m.key)}
            aria-pressed={active}
            className="relative pb-1 font-display text-[clamp(13px,1.4vw,15px)] font-semibold tracking-[0.01em] text-cream transition-opacity hover:opacity-100"
            style={{ opacity: active ? 1 : 0.45 }}
          >
            {m.tab}
            {active && <span className="absolute inset-x-0 bottom-0 h-[2px] rounded-full bg-cream" />}
          </button>
        );
      })}
    </div>
  );
}
