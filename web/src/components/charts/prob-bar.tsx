import { formatPct } from "@/lib/format";

interface ProbBarProps {
  label: string;
  prob: number;
  highlight?: boolean;
}

export function ProbBar({ label, prob, highlight = false }: ProbBarProps) {
  const pct = Math.round(prob * 100);
  return (
    <div className="flex items-center gap-2 text-sm">
      <span className="w-28 shrink-0 truncate">{label}</span>
      <div className="h-2 flex-1 overflow-hidden rounded-full bg-secondary">
        <div
          className={`h-full rounded-full transition-[width] duration-300 ease-[var(--ease-out)] ${
            highlight ? "bg-gold" : "bg-foreground/40"
          }`}
          style={{ width: `${Math.max(pct, 2)}%` }}
        />
      </div>
      <span className="w-10 shrink-0 text-right tabular-nums text-muted-foreground">{formatPct(prob)}</span>
    </div>
  );
}
