import { memo } from "react";
import { cn } from "@/lib/utils";

type MeterSize = "sm" | "md";

interface MeterProps {
  value: number;
  max: number;
  size?: MeterSize;
  className?: string;
  "aria-label"?: string;
}

// Ordered high → low; first match wins.
const FILL_THRESHOLDS: ReadonlyArray<readonly [number, string]> = [
  [1, "bg-red-500 motion-safe:animate-pulse dark:bg-red-400"],
  [0.8, "bg-orange-500 dark:bg-orange-400"],
  [0.6, "bg-amber-500 dark:bg-amber-400"],
];
const FILL_DEFAULT = "bg-[var(--fg-secondary)]";

function fillColour(pct: number): string {
  return FILL_THRESHOLDS.find(([threshold]) => pct >= threshold)?.[1] ?? FILL_DEFAULT;
}

export const Meter = memo(function Meter({
  value,
  max,
  size = "md",
  className,
  "aria-label": ariaLabel,
}: MeterProps) {
  const pct = max > 0 ? value / max : 0;
  const width = `${Math.min(100, Math.max(0, pct * 100))}%`;
  const trackHeight = size === "sm" ? "h-[2px]" : "h-1.5";

  return (
    <div
      role="meter"
      aria-valuenow={value}
      aria-valuemin={0}
      aria-valuemax={max}
      aria-label={ariaLabel}
      className={cn(
        "w-full overflow-hidden rounded-[1px] bg-border/60",
        trackHeight,
        className,
      )}
    >
      <div
        className={cn("h-full rounded-[1px] transition-[width]", fillColour(pct))}
        style={{ width }}
      />
    </div>
  );
});
