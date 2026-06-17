"use client";

import { ExternalLink } from "lucide-react";
import { useState } from "react";
import { SectionTitle } from "@/components/forecast/section-title";
import type { ReadingItem } from "@/lib/forecast";

interface ReadingListProps {
  sources: ReadingItem[];
}

const LEAD = 6;

export function ReadingList({ sources }: ReadingListProps) {
  const [showAll, setShowAll] = useState(false);
  const lead = sources.slice(0, LEAD);
  const rest = sources.slice(LEAD);

  return (
    <section>
      <SectionTitle>Sources considered by the agent</SectionTitle>

      <ul className="space-y-px">
        {lead.map((source, i) => (
          <SourceRow key={source.url} source={source} rank={i + 1} />
        ))}
      </ul>

      {rest.length > 0 && (
        <>
          <div
            className="grid transition-[grid-template-rows] duration-300 ease-out motion-reduce:transition-none"
            style={{ gridTemplateRows: showAll ? "1fr" : "0fr" }}
          >
            <div className="overflow-hidden" inert={!showAll}>
              <ul className="space-y-px">
                {rest.map((source, i) => (
                  <SourceRow key={source.url} source={source} rank={LEAD + i + 1} />
                ))}
              </ul>
            </div>
          </div>
          <button
            type="button"
            onClick={() => setShowAll((v) => !v)}
            aria-expanded={showAll}
            className="mt-1.5 px-2 font-display text-[13px] font-semibold text-cream-dim transition-colors hover:text-cream"
          >
            {showAll ? "Show fewer" : `Show ${rest.length} more ${rest.length === 1 ? "source" : "sources"}`}
          </button>
        </>
      )}
    </section>
  );
}

function SourceRow({ source, rank }: { source: ReadingItem; rank: number }) {
  return (
    <li className="rounded-sm px-2 py-1 transition-colors hover:bg-cream/5">
      <a href={source.url} target="_blank" rel="noopener noreferrer" className="flex min-w-0 items-baseline gap-2">
        <span className="shrink-0 font-mono text-[11px] tabular-nums text-cream-faint">{rank}.</span>
        <span className="min-w-0 flex-1 truncate font-display text-[13px] font-medium text-cream">{source.title}</span>
        {source.cited && (
          <span className="shrink-0 font-mono text-[10px] uppercase tracking-[0.06em] text-cream-faint">cited</span>
        )}
        <span className="shrink-0 font-mono text-[10.5px] text-cream-faint">{source.hostname}</span>
        <ExternalLink size={11} className="shrink-0 text-cream-faint" aria-hidden />
      </a>
    </li>
  );
}
