import Link from "next/link";
import { Kicker } from "@/components/shell/kicker";
import { PhotoWall } from "@/components/walls/photo-wall";
import { rankedLedger, sourceHost, statusMark } from "@/lib/ledger";
import type { Snapshot } from "@/lib/snapshot";

interface MarketSectionProps {
  snapshot: Snapshot;
}

export function MarketSection({ snapshot }: MarketSectionProps) {
  const focusId = snapshot.focus.team_id;
  const ours = snapshot.markets?.model_probs?.[focusId];
  const market = snapshot.markets?.market_probs?.[focusId];
  if (ours === undefined || market === undefined) return null;

  const gapPp = (ours - market) * 100;
  const story = snapshot.agent?.narrative.focus_story ?? null;
  const sources = rankedLedger(snapshot, 4);

  return (
    <section className="relative border-t border-hairline py-[clamp(60px,10vh,120px)]">
      <PhotoWall family="wc" />
      <div className="wrap relative z-[1]">
        <Kicker>Us v the market</Kicker>
        <h2 className="statement">
          The market remembers.
          <br />
          <b className="font-medium">The model counts.</b>
        </h2>
        <div className="my-[clamp(26px,4vh,44px)] flex gap-[clamp(30px,7vw,80px)]">
          <div>
            <span className="block font-mono text-[clamp(38px,6.4vw,64px)] tracking-[-0.02em] text-red">
              {(ours * 100).toFixed(1)}%
            </span>
            <span className="mt-2.5 block font-mono text-[12px] uppercase tracking-[0.14em] text-cream-faint">
              our model
            </span>
          </div>
          <div>
            <span className="block font-mono text-[clamp(38px,6.4vw,64px)] tracking-[-0.02em] text-cream-dim">
              {(market * 100).toFixed(1)}%
            </span>
            <span className="mt-2.5 block font-mono text-[12px] uppercase tracking-[0.14em] text-cream-faint">
              the market
            </span>
          </div>
          <div>
            <span className="block font-mono text-[clamp(38px,6.4vw,64px)] tracking-[-0.02em] text-green">
              {gapPp > 0 ? "+" : "−"}
              {Math.abs(gapPp).toFixed(1)}
            </span>
            <span className="mt-2.5 block font-mono text-[12px] uppercase tracking-[0.14em] text-cream-faint">
              gap, pp
            </span>
          </div>
        </div>
        {story && (
          <>
            <p className="max-w-[44ch] text-[clamp(19px,2.7vw,24px)] font-light leading-[1.55]">
              &ldquo;{firstSentences(story, 2)}&rdquo;
            </p>
            <div className="mt-3.5 font-mono text-[12.5px] text-cream-faint">
              agent synthesis · <Link href={`/runs/${snapshot.run.run_id}`} className="border-b border-hairline pb-0.5">{snapshot.run.run_id}</Link>
            </div>
          </>
        )}
        {sources.length > 0 && (
          <div className="mt-[clamp(22px,3vh,34px)] max-w-[760px] border-t border-hairline">
            {sources.map((entry) => (
              <div
                key={entry.id}
                className="flex justify-between gap-4 border-b border-hairline py-3.5 text-[15.5px] font-light text-cream-dim"
              >
                <span className="line-clamp-2">
                  {entry.claim} — {sourceHost(entry.source_url)}
                </span>
                <span className="whitespace-nowrap font-mono text-[12px] text-cream-faint">
                  {entry.id} {statusMark(entry.status)}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </section>
  );
}

function firstSentences(text: string, count: number): string {
  const sentences = text.match(/[^.!?]+[.!?]+/g) ?? [text];
  return sentences.slice(0, count).join(" ").trim();
}
