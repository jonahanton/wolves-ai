"use client";

import { ReachCurve } from "@/components/team/reach-curve";
import { BottomSheet } from "@/components/ui/sheet";
import { formatPct } from "@/lib/format";
import type { RouteStep, TeamSheetView } from "@/lib/team-sheet-view";
import { cn } from "@/lib/utils";

function StatCell({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-[11px] font-semibold tracking-wide text-muted-foreground uppercase">{label}</dt>
      <dd className="mt-0.5 text-base font-semibold tabular-nums">{value}</dd>
    </div>
  );
}

function RouteRow({ step }: { step: RouteStep }) {
  return (
    <li className="rounded-lg border px-3 py-2 text-sm">
      <div className="flex items-baseline justify-between gap-3 text-xs text-muted-foreground">
        <span className="font-semibold">{step.stageLabel}</span>
        <span className="truncate">
          {step.city} &middot; {step.dateLabel}
        </span>
      </div>
      <div className="mt-0.5 flex items-baseline justify-between gap-3">
        <span className="truncate">v {step.opponentName}</span>
        <span className="shrink-0 tabular-nums text-muted-foreground">
          {formatPct(step.winProb)} to win
          {step.pairingProb !== null && <> &middot; pairing {formatPct(step.pairingProb)}</>}
        </span>
      </div>
    </li>
  );
}

interface TeamSheetProps {
  view: TeamSheetView | null;
  onClose: () => void;
}

export function TeamSheet({ view, onClose }: TeamSheetProps) {
  return (
    <BottomSheet
      open={view !== null}
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
      title={view?.name ?? ""}
    >
      {view && (
        <div className="pb-2">
          <p className={cn("text-sm", view.isEngland ? "text-gold" : "text-muted-foreground")}>
            Group {view.group}
          </p>
          <dl className="mt-3 grid grid-cols-3 gap-3">
            <StatCell label="Title" value={formatPct(view.championProb)} />
            <StatCell label="Rating" value={`${Math.round(view.rating)}`} />
            <StatCell
              label="Squad value"
              value={view.valueEurM === null ? "n/a" : `€${Math.round(view.valueEurM)}m`}
            />
          </dl>
          <p className="mt-2 text-xs text-muted-foreground">
            {view.marketProb === null
              ? "No market price in this snapshot yet."
              : `Market says ${formatPct(view.marketProb)} for the title; the model says ${formatPct(view.championProb)}.`}
          </p>
          <section className="mt-4">
            <h3 className="text-xs font-semibold tracking-wide text-muted-foreground uppercase">
              Reach probability by round
            </h3>
            <ReachCurve reach={view.reach} highlight={view.isEngland} />
          </section>
          <section className="mt-4">
            <h3 className="text-xs font-semibold tracking-wide text-muted-foreground uppercase">Likely route</h3>
            {view.route.length > 0 ? (
              <>
                <ol className="mt-2 space-y-2">
                  {view.route.map((step) => (
                    <RouteRow key={step.match} step={step} />
                  ))}
                </ol>
                <p className="mt-2 text-xs text-muted-foreground">
                  The route through the most likely bracket. Win chances assume each pairing happens; the
                  pairing share shows how often it does.
                </p>
              </>
            ) : (
              <p className="mt-2 text-xs text-muted-foreground">
                No knockout route: they do not appear in the most likely bracket.
              </p>
            )}
          </section>
        </div>
      )}
    </BottomSheet>
  );
}
