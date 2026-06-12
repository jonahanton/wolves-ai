import { formatPct1 } from "@/lib/format";
import type { StaircaseStep } from "@/lib/team-view";

interface SurvivalStaircaseProps {
  steps: StaircaseStep[];
  featured: boolean;
}

export function SurvivalStaircase({ steps, featured }: SurvivalStaircaseProps) {
  return (
    <div className="max-w-[880px]">
      {steps.map((step) => (
        <div
          key={step.stage}
          className="grid grid-cols-[110px_1fr_auto] items-center gap-x-[clamp(14px,3vw,28px)] border-b border-hairline py-3"
        >
          <span className="font-mono text-[12px] uppercase tracking-[0.12em] text-cream-faint">{step.label}</span>
          <span className="relative h-[3px] rounded-pill bg-hairline">
            <i
              className={`absolute inset-y-0 left-0 rounded-pill ${featured ? "bg-red" : "bg-cream-dim"}`}
              style={{ width: `${(step.prob * 100).toFixed(1)}%` }}
            />
          </span>
          <span className="font-mono text-[clamp(16px,2.2vw,19px)]">{formatPct1(step.prob)}</span>
        </div>
      ))}
    </div>
  );
}
