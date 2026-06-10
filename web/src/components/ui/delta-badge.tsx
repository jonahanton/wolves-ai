import { formatDeltaPts } from "@/lib/format";
import { cn } from "@/lib/utils";

interface DeltaBadgeProps {
  deltaPts: number;
  className?: string;
}

export function DeltaBadge({ deltaPts, className }: DeltaBadgeProps) {
  const up = deltaPts > 0;
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-md px-1.5 py-0.5 text-xs font-semibold",
        up ? "bg-delta-up-bg text-delta-up" : "bg-delta-down-bg text-delta-down",
        className,
      )}
    >
      {formatDeltaPts(deltaPts)}pt
    </span>
  );
}
