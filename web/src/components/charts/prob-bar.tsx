import { formatPct } from "@/lib/format";
import { cn } from "@/lib/utils";

interface ProbBarProps {
  label: string;
  prob: number;
  highlight?: boolean;
  gold?: boolean;
}

export function ProbBar({ label, prob, highlight = false, gold = false }: ProbBarProps) {
  const pct = Math.round(prob * 100);
  return (
    <div className="text-sm">
      <div className="flex items-baseline justify-between gap-2">
        <span
          className={cn(
            "min-w-0 truncate",
            highlight ? "font-medium" : "text-muted-foreground",
            gold && "text-gold",
          )}
        >
          {label}
        </span>
        <span className={cn("shrink-0", highlight ? "font-semibold" : "text-muted-foreground")}>
          {formatPct(prob)}
        </span>
      </div>
      <div className="mt-1 h-0.5 w-full bg-secondary">
        <div
          className={cn(
            "h-full transition-[width] duration-300 ease-[var(--ease-out)]",
            gold ? "bg-gold" : highlight ? "bg-foreground/70" : "bg-foreground/30",
          )}
          style={{ width: prob === 0 ? "0%" : `${Math.max(pct, 1)}%` }}
        />
      </div>
    </div>
  );
}
