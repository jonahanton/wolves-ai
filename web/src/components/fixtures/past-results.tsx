"use client";

import { ChevronDown } from "lucide-react";
import { useState } from "react";
import { StageSection } from "@/components/fixtures/stage-section";
import type { StageSection as Section } from "@/lib/fixtures";

interface PastResultsProps {
  sections: Section[];
}

export function PastResults({ sections }: PastResultsProps) {
  const [open, setOpen] = useState(false);
  const [everOpened, setEverOpened] = useState(false);
  const [openStageKey, setOpenStageKey] = useState<string | null>(null);
  const [openDay, setOpenDay] = useState<string | null>(null);
  if (open && !everOpened) setEverOpened(true);

  return (
    <section className="mt-8 first:mt-0">
      <button type="button" onClick={() => setOpen((v) => !v)} aria-expanded={open} className="group flex w-full items-center gap-2 py-1.5 text-left">
        <h2 className="font-mono text-[11px] font-medium uppercase tracking-[0.1em] text-cream-faint transition-colors group-hover:text-cream-dim">
          Past results
        </h2>
        <ChevronDown
          size={13}
          className="shrink-0 text-cream-faint transition-transform duration-300 group-hover:text-cream-dim motion-reduce:transition-none"
          style={{ transform: open ? "rotate(180deg)" : "none" }}
        />
        <span className="h-px flex-1" />
      </button>
      <div className="grid transition-[grid-template-rows] duration-300 ease-out motion-reduce:transition-none" style={{ gridTemplateRows: open ? "1fr" : "0fr" }}>
        <div className="overflow-hidden" inert={!open}>
          {everOpened && (
            <div className="pl-3 opacity-90">
              {sections.map((section) => (
                <StageSection
                  key={section.key}
                  section={section}
                  open={openStageKey === section.key}
                  onToggle={() => setOpenStageKey((current) => (current === section.key ? null : section.key))}
                  openDay={openDay}
                  onToggleDay={(key) => setOpenDay((current) => (current === key ? null : key))}
                  muted
                />
              ))}
            </div>
          )}
        </div>
      </div>
    </section>
  );
}
