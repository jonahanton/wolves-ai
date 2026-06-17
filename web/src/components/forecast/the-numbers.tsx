"use client";

import { ChevronRight } from "lucide-react";
import { useState } from "react";
import { SectionTitle } from "@/components/forecast/section-title";
import type { Working } from "@/lib/forecast";

interface TheNumbersProps {
  workings: Working[];
}

export function TheNumbers({ workings }: TheNumbersProps) {
  const [open, setOpen] = useState(false);
  if (workings.length === 0) return null;

  return (
    <section>
      <SectionTitle>Internal forecast workings</SectionTitle>

      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="flex items-center gap-1.5 font-display text-[13px] font-semibold text-cream-dim transition-colors hover:text-cream"
      >
        <ChevronRight
          size={14}
          className="shrink-0 transition-transform duration-300 motion-reduce:transition-none"
          style={{ transform: open ? "rotate(90deg)" : "none" }}
        />
        {open ? "Hide the workings" : "Show the workings"}
      </button>

      <div
        className="grid transition-[grid-template-rows] duration-300 ease-out motion-reduce:transition-none"
        style={{ gridTemplateRows: open ? "1fr" : "0fr" }}
      >
        <div className="overflow-hidden" inert={!open}>
          <ol className="-mx-1.5 mt-2 space-y-3 rounded-md bg-night-2/60 px-4 py-4">
            {workings.map((working, i) => (
              <li key={i} className="border-b border-hairline/60 pb-3 last:border-b-0 last:pb-0">
                <p className="flex items-baseline gap-2">
                  <span className="font-mono text-[11px] tabular-nums text-cream-faint">{i + 1}</span>
                  <span className="font-display text-[13.5px] font-bold text-cream">{working.title}</span>
                </p>
                <p className="mt-1.5 font-display text-[12.5px] leading-relaxed text-cream-dim">{working.summary}</p>
                {working.findings.length > 0 && (
                  <ul className="mt-2 space-y-1.5">
                    {working.findings.map((finding, j) => (
                      <li key={j} className="flex gap-2 font-mono text-[11.5px] leading-relaxed text-cream-faint">
                        <span aria-hidden className="shrink-0">·</span>
                        <span className="min-w-0">{finding}</span>
                      </li>
                    ))}
                  </ul>
                )}
              </li>
            ))}
          </ol>
        </div>
      </div>
    </section>
  );
}
