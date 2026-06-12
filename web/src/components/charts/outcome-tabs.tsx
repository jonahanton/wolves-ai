"use client";

import clsx from "clsx";
import type { Outcome } from "@/lib/forecast-series";

interface OutcomeTabsProps {
  options: { key: Outcome; label: string; short: string }[];
  value: Outcome;
  onChange: (value: Outcome) => void;
}

// Stub-bracket icons read as tournament depth: the champion takes the trophy,
// each earlier round shows the teams still left in that round's matches.
const STUBS: Record<Outcome, number> = { champion: 0, final: 2, sf: 4, qf: 8 };

function OutcomeIcon({ outcome }: { outcome: Outcome }) {
  if (outcome === "champion") {
    return (
      <svg viewBox="0 0 16 16" className="h-[13px] w-[13px]" fill="none" stroke="currentColor" strokeWidth={1.3} strokeLinecap="round" strokeLinejoin="round" aria-hidden>
        <path d="M4.6 3h6.8v2.1a3.4 3.4 0 0 1-6.8 0Z" />
        <path d="M4.6 3.5H3.1a1.6 1.6 0 0 0 1.8 2.1M11.4 3.5h1.5a1.6 1.6 0 0 1-1.8 2.1" />
        <path d="M8 8.5v2.4M5.7 12.9h4.6" />
      </svg>
    );
  }
  const n = STUBS[outcome];
  const ys = Array.from({ length: n }, (_, i) => 2.5 + (11 * i) / (n - 1));
  return (
    <svg viewBox="0 0 16 16" className="h-[13px] w-[13px]" fill="none" stroke="currentColor" strokeWidth={1.15} strokeLinecap="round" aria-hidden>
      {ys.map((yy, i) => (
        <line key={i} x1="3.2" y1={yy} x2="9.6" y2={yy} />
      ))}
      <line x1="9.6" y1={ys[0]} x2="9.6" y2={ys[ys.length - 1]} />
      <line x1="9.6" y1="8" x2="13" y2="8" />
    </svg>
  );
}

export function OutcomeTabs({ options, value, onChange }: OutcomeTabsProps) {
  return (
    <div role="group" aria-label="Outcome" className="flex flex-wrap gap-x-4 gap-y-1 sm:gap-x-5">
      {options.map((option) => {
        const active = option.key === value;
        return (
          <button
            key={option.key}
            type="button"
            aria-pressed={active}
            onClick={() => onChange(option.key)}
            className={clsx(
              "flex items-center gap-1.5 border-b-2 px-0.5 pt-2.5 pb-2 font-mono text-[12px] uppercase tracking-[0.13em] transition-colors duration-200",
              active ? "border-gold text-cream" : "border-transparent text-cream-faint hover:text-cream-dim",
            )}
          >
            <span className={active ? "text-gold" : "text-cream-faint"}>
              <OutcomeIcon outcome={option.key} />
            </span>
            <span className="sm:hidden">{option.short}</span>
            <span className="hidden sm:inline">{option.label}</span>
          </button>
        );
      })}
    </div>
  );
}
