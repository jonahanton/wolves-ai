"use client";

import clsx from "clsx";

interface ToggleTabsProps<T extends string> {
  options: { key: T; label: string }[];
  value: T;
  onChange: (value: T) => void;
  ariaLabel: string;
}

export function ToggleTabs<T extends string>({ options, value, onChange, ariaLabel }: ToggleTabsProps<T>) {
  return (
    <div role="group" aria-label={ariaLabel} className="flex flex-wrap gap-x-5">
      {options.map((option) => {
        const active = option.key === value;
        return (
          <button
            key={option.key}
            type="button"
            aria-pressed={active}
            onClick={() => onChange(option.key)}
            className={clsx(
              "border-b-2 px-0.5 pt-2.5 pb-2 font-mono text-[12px] uppercase tracking-[0.14em] transition-colors duration-200",
              active ? "border-gold text-cream" : "border-transparent text-cream-faint hover:text-cream-dim",
            )}
          >
            {option.label}
          </button>
        );
      })}
    </div>
  );
}
