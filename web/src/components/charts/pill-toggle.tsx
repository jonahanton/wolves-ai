"use client";

import clsx from "clsx";

interface PillToggleProps<T extends string> {
  options: { key: T; label: string }[];
  value: T;
  onChange: (value: T) => void;
  ariaLabel: string;
}

export function PillToggle<T extends string>({ options, value, onChange, ariaLabel }: PillToggleProps<T>) {
  return (
    <div role="group" aria-label={ariaLabel} className="flex flex-wrap gap-1.5">
      {options.map((option) => {
        const active = option.key === value;
        return (
          <button
            key={option.key}
            type="button"
            aria-pressed={active}
            onClick={() => onChange(option.key)}
            className={clsx(
              "rounded-pill border px-3 py-1.5 font-mono text-[12px] uppercase tracking-[0.1em] transition-colors duration-200",
              active
                ? "border-gold/60 text-gold"
                : "border-hairline text-cream-faint hover:border-cream-faint hover:text-cream-dim",
            )}
          >
            {option.label}
          </button>
        );
      })}
    </div>
  );
}
