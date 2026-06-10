import { formatPct } from "@/lib/format";
import type { LiveFixtureView } from "@/lib/live-view";
import { ENGLAND } from "@/lib/schedule";
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
      className: fixture.homeId === ENGLAND ? "bg-gold" : "bg-foreground/60",
    },
    ...(forecast.pDraw !== null ? [{ key: "draw", prob: forecast.pDraw, className: "bg-foreground/20" }] : []),
    {
      key: "away",
      prob: forecast.pAway,
      className: fixture.awayId === ENGLAND ? "bg-gold" : "bg-foreground/40",
    },
  ];

  const notes = [
    forecast.pDraw !== null ? `Draw ${formatPct(forecast.pDraw)}` : null,
    forecast.modalScore ? `Most likely ${forecast.modalScore}` : null,
    forecast.pDecided90 !== null ? `${formatPct(forecast.pDecided90)} settled in 90` : null,
  ].filter((note) => note !== null);

  return (
    <div className="px-3 pb-3">
      <div className="flex h-0.5 gap-px overflow-hidden bg-secondary">
        {segments.map((segment) => (
          <div
            key={segment.key}
            className={cn("h-full", segment.className)}
            style={{ width: `${Math.max(segment.prob * 100, 1.5)}%` }}
          />
        ))}
      </div>
      {notes.length > 0 && (
        <p className="mt-1.5 flex flex-wrap gap-x-2.5 gap-y-0.5 text-[11px] text-muted-foreground">
          {notes.map((note) => (
            <span key={note}>{note}</span>
          ))}
        </p>
      )}
      {forecast.pPairing !== null && (
        <p className="mt-0.5 text-[11px] text-muted-foreground">
          Most likely pairing, seen in {formatPct(forecast.pPairing)} of sims; the chances assume it happens.
        </p>
      )}
    </div>
  );
}
