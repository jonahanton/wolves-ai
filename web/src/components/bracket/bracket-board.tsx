"use client";

import { useState } from "react";
import { BracketCanvas } from "@/components/bracket/bracket-canvas";
import { RoundRows } from "@/components/bracket/round-rows";
import { SlotCard } from "@/components/bracket/slot-card";
import { SlotSheet } from "@/components/bracket/slot-sheet";
import { Segmented } from "@/components/ui/segmented";
import type { BracketViewModel, SlotView } from "@/lib/bracket-view";

type Mode = "canvas" | "list";
type Half = "left" | "right";

interface BracketBoardProps {
  view: BracketViewModel;
}

export function BracketBoard({ view }: BracketBoardProps) {
  const [mode, setMode] = useState<Mode>("canvas");
  const [half, setHalf] = useState<Half>(view.englandHalf);
  const [selected, setSelected] = useState<SlotView | null>(null);
  const slots = half === "left" ? view.left : view.right;

  return (
    <div className="flex flex-col gap-5">
      <Segmented
        options={[
          { value: "canvas", label: "Canvas" },
          { value: "list", label: "List" },
        ]}
        value={mode}
        onChange={setMode}
      />
      {mode === "canvas" ? (
        <BracketCanvas view={view} onSelect={setSelected} />
      ) : (
        <>
          <section aria-label="Last 32 slots">
            <div className="flex items-center justify-between gap-3">
              <h2 className="font-semibold">Last 32</h2>
              <Segmented
                options={[
                  { value: "left", label: "Left" },
                  { value: "right", label: "Right" },
                ]}
                value={half}
                onChange={setHalf}
                className="w-36"
              />
            </div>
            <div key={half} className="mt-3 flex flex-col gap-3 animate-[fade-up_260ms_var(--ease-out)]">
              {slots.map((slot) => (
                <SlotCard key={slot.match} slot={slot} onSelect={setSelected} />
              ))}
            </div>
          </section>
          <RoundRows rounds={view.rounds} onSelect={setSelected} />
        </>
      )}
      <SlotSheet slot={selected} onClose={() => setSelected(null)} />
    </div>
  );
}
