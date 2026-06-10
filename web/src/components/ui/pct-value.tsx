import { formatPctBare } from "@/lib/format";
import { cn } from "@/lib/utils";

interface PctValueProps {
  prob: number;
  className?: string;
}

export function PctValue({ prob, className }: PctValueProps) {
  return (
    <span className={cn("font-semibold", className)}>
      {formatPctBare(prob)}
      <span className="text-[0.6em] font-medium">%</span>
    </span>
  );
}
