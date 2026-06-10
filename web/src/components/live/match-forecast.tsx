import { formatPct } from "@/lib/format";
import type { LiveFixtureView } from "@/lib/live-view";
import { cn } from "@/lib/utils";

interface MatchForecastProps {
  fixture: LiveFixtureView;
}

export function MatchForecast({ fixture }: MatchForecastProps) {
  const forecast = fixture.forecast;
  if (!forecast) return null;

  const segments = [
    {
      key: "home",
      prob: forecast.pHome,
      className: fixture.homeId === "england" ? "bg-gold" : "bg-foreground/60",
    },
    ...(forecast.pDraw !== null ? [{ key: "draw", prob: forecast.pDraw, className: "bg-foreground/20" }] : []),
    {
      key: "away",
      prob: forecast.pAway,
      className: fixture.awayId === "england" ? "bg-gold" : "bg-foreground/40",
    },
  ];

  return (
    <div className="mt-2">
      <div className="flex h-1.5 gap-px overflow-hidden rounded-full bg-secondary">
        {segments.map((segment) => (
          <div
            key={segment.key}
            className={cn("rounded-full", segment.className)}
            style={{ width: `${Math.max(segment.prob * 100, 1.5)}%` }}
          />
        ))}
      </div>
      <p className="mt-1.5 flex flex-wrap gap-x-2.5 gap-y-0.5 text-[11px] tabular-nums text-muted-foreground">
        <span>
          {fixture.homeName} {formatPct(forecast.pHome)}
        </span>
        {forecast.pDraw !== null && <span>Draw {formatPct(forecast.pDraw)}</span>}
        <span>
          {fixture.awayName} {formatPct(forecast.pAway)}
        </span>
        {forecast.modalScore && <span>Most likely {forecast.modalScore}</span>}
        {forecast.pDecided90 !== null && <span>{formatPct(forecast.pDecided90)} settled in 90</span>}
      </p>
      {forecast.pPairing !== null && (
        <p className="mt-0.5 text-[11px] text-muted-foreground">
          Most likely pairing, seen in {formatPct(forecast.pPairing)} of sims; the chances assume it happens.
        </p>
      )}
    </div>
  );
}
