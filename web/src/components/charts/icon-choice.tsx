"use client";

import clsx from "clsx";
import { Fragment } from "react";

interface IconChoiceProps<T extends string> {
  options: { key: T; label: string; icon: React.ReactNode }[];
  value: T;
  onChange: (value: T) => void;
  ariaLabel: string;
}

export function IconChoice<T extends string>({ options, value, onChange, ariaLabel }: IconChoiceProps<T>) {
  return (
    <div role="group" aria-label={ariaLabel} className="flex items-center gap-2">
      {options.map((option, index) => {
        const active = option.key === value;
        return (
          <Fragment key={option.key}>
            {index > 0 && (
              <span aria-hidden className="select-none text-[13px] text-cream-faint/40">
                /
              </span>
            )}
            <button
              type="button"
              aria-pressed={active}
              aria-label={option.label}
              title={option.label}
              onClick={() => onChange(option.key)}
              className={clsx(
                "flex items-center rounded-[3px] p-1 transition-colors duration-200",
                active ? "text-cream" : "text-cream-faint hover:text-cream-dim",
              )}
            >
              {option.icon}
            </button>
          </Fragment>
        );
      })}
    </div>
  );
}
