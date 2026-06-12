import type { Outcome } from "@/lib/forecast-series";

// Stub-bracket icons read as tournament depth: the champion takes the trophy,
// each earlier round shows the teams still left in that round.
const STUBS: Record<Outcome, number> = { champion: 0, final: 2, sf: 4, qf: 8 };

export function OutcomeIcon({ outcome }: { outcome: Outcome }) {
  if (outcome === "champion") {
    return (
      <svg viewBox="0 0 16 16" className="h-[15px] w-[15px]" fill="none" stroke="currentColor" strokeWidth={1.25} strokeLinecap="round" strokeLinejoin="round" aria-hidden>
        <path d="M4.6 2.6h6.8v2.2a3.4 3.4 0 0 1-6.8 0Z" />
        <path d="M4.6 3.1H3a1.6 1.6 0 0 0 1.8 2.2M11.4 3.1H13a1.6 1.6 0 0 1-1.8 2.2" />
        <path d="M8 8.2v2.5M5.6 13h4.8" />
      </svg>
    );
  }
  const n = STUBS[outcome];
  const ys = Array.from({ length: n }, (_, i) => 2.6 + (10.8 * i) / (n - 1));
  return (
    <svg viewBox="0 0 16 16" className="h-[15px] w-[15px]" fill="none" stroke="currentColor" strokeWidth={1.15} strokeLinecap="round" aria-hidden>
      {ys.map((yy, i) => (
        <line key={i} x1="3" y1={yy} x2="9.6" y2={yy} />
      ))}
      <line x1="9.6" y1={ys[0]} x2="9.6" y2={ys[ys.length - 1]} />
      <line x1="9.6" y1="8" x2="13.2" y2="8" />
    </svg>
  );
}

export function WolfIcon() {
  return (
    <svg viewBox="0 0 16 16" className="h-[15px] w-[15px]" fill="currentColor" aria-hidden>
      <path d="M1.7 2.2 4 5.1l1.9-.5L8 5.7l2.1-1.1 1.9.5 2.3-2.9-.5 4.2-1.4 2.6L8 14.4 3.6 8.5 2.2 5.9Z" />
      <circle cx="6.1" cy="7.2" r="0.85" fill="var(--color-night)" />
      <circle cx="9.9" cy="7.2" r="0.85" fill="var(--color-night)" />
    </svg>
  );
}

export function MarketIcon() {
  return (
    <svg viewBox="0 0 16 16" className="h-[15px] w-[15px]" fill="none" stroke="currentColor" strokeWidth={1.2} strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <line x1="4" y1="2.4" x2="4" y2="13.6" />
      <rect x="2.4" y="5" width="3.2" height="5" rx="0.4" fill="currentColor" stroke="none" />
      <line x1="11.4" y1="2.4" x2="11.4" y2="13.6" />
      <rect x="9.8" y="7" width="3.2" height="4.6" rx="0.4" fill="currentColor" stroke="none" />
    </svg>
  );
}
