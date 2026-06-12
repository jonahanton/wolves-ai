import { Kicker } from "@/components/shell/kicker";
import { sourceHost, statusMark, tierLabel } from "@/lib/ledger";
import type { LedgerEntryOut } from "@/lib/snapshot";

interface WhySectionProps {
  reasoning: string;
  runLabel: string;
  evidence: LedgerEntryOut[];
}

export function WhySection({ reasoning, runLabel, evidence }: WhySectionProps) {
  return (
    <div className="mt-[clamp(36px,6vh,60px)] max-w-[720px]">
      <Kicker>Why · {runLabel}</Kicker>
      <p className="mt-3 text-[clamp(17px,2.2vw,21px)] font-light leading-[1.45] text-cream">{reasoning}</p>
      {evidence.length > 0 && (
        <details className="group mt-5">
          <summary className="cursor-pointer list-none font-mono text-[12.5px] uppercase tracking-[0.14em] text-cream-faint transition-colors hover:text-cream-dim">
            <span className="mr-2 inline-block transition-transform group-open:rotate-90">›</span>
            The evidence it weighed
          </summary>
          <ul className="mt-4 space-y-3 border-l border-hairline pl-5">
            {evidence.map((entry) => (
              <li key={entry.id} className="text-[14.5px] leading-snug text-cream-dim">
                <span className="mr-1.5 text-gold">{statusMark(entry.status)}</span>
                {entry.claim}
                <span className="ml-2 font-mono text-[11.5px] text-cream-faint">
                  {sourceHost(entry.source_url)}
                  {tierLabel(entry.source_tier) && ` · ${tierLabel(entry.source_tier)}`}
                </span>
              </li>
            ))}
          </ul>
        </details>
      )}
    </div>
  );
}
