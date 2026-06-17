import { ForecastIndexRow } from "@/components/forecast/forecast-index-row";
import type { ForecastIndexRow as Row } from "@/lib/forecast";

interface ForecastIndexProps {
  rows: Row[];
  names: Record<string, string>;
}

export function ForecastIndex({ rows, names }: ForecastIndexProps) {
  return (
    <div className="mx-auto max-w-[680px] px-1">
      <h1 className="font-display text-[clamp(20px,3vw,28px)] font-semibold tracking-[-0.02em] text-cream">
        Forecasts
      </h1>

      {rows.length === 0 ? (
        <p className="mt-8 font-display text-[14px] text-cream-faint">No forecasts published yet.</p>
      ) : (
        <ul className="mt-[clamp(16px,2.5vh,28px)] border-t border-hairline">
          {rows.map((row, i) => (
            <ForecastIndexRow key={row.runId} row={row} names={names} latest={i === 0} />
          ))}
        </ul>
      )}
    </div>
  );
}
