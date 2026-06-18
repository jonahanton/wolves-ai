"use client";

import { useEffect, useRef, useState } from "react";
import type { BoardRow } from "@/lib/derive";
import { formatPct1 } from "@/lib/format";
import { chartColour, teamCode } from "@/lib/team-colours";

interface TeamSelectorProps {
  segments: BoardRow[];
  overflow: BoardRow[];
  selectedTeamId: string;
  onSelect: (teamId: string) => void;
}

export function TeamSelector({ segments, overflow, selectedTeamId, onSelect }: TeamSelectorProps) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onDown);
    return () => document.removeEventListener("mousedown", onDown);
  }, [open]);

  const selectedOverflow = overflow.find((row) => row.teamId === selectedTeamId) ?? null;
  const restOverflow = overflow.filter((row) => row.teamId !== selectedTeamId);

  return (
    <div ref={ref} className="relative flex flex-col items-end gap-1">
      <div className="flex items-start gap-[clamp(10px,1.4vw,18px)]">
        {segments.map((row) => {
          const selected = row.teamId === selectedTeamId;
          const colour = chartColour(row.teamId);
          return (
            <Tab
              key={row.teamId}
              label={teamCode(row.name)}
              colour={colour}
              selected={selected}
              title={`${row.name} ${formatPct1(row.prob)}`}
              onClick={() => onSelect(row.teamId)}
            />
          );
        })}
        {selectedOverflow && (
          <Tab
            label={teamCode(selectedOverflow.name)}
            colour={chartColour(selectedOverflow.teamId)}
            selected
            title={`${selectedOverflow.name} ${formatPct1(selectedOverflow.prob)}`}
            onClick={() => onSelect(selectedOverflow.teamId)}
          />
        )}
        {restOverflow.length > 0 && (
          <button
            type="button"
            onClick={() => setOpen((v) => !v)}
            aria-expanded={open}
            aria-label="More teams"
            className="-my-2 py-2 font-display text-[clamp(13px,1.4vw,15px)] font-semibold tracking-[0.01em] text-cream-faint transition-colors hover:text-cream"
          >
            +{restOverflow.length}
          </button>
        )}
      </div>

      {open && (
        <ul className="no-scrollbar absolute right-0 top-[calc(100%+8px)] z-30 max-h-[300px] w-[172px] overflow-y-auto rounded-lg bg-night-2/95 p-1 shadow-[0_16px_40px_-12px_oklch(0_0_0/0.6)] backdrop-blur-md">
          {restOverflow.map((row) => {
            const colour = chartColour(row.teamId);
            return (
              <li key={row.teamId}>
                <button
                  type="button"
                  onClick={() => {
                    onSelect(row.teamId);
                    setOpen(false);
                  }}
                  className="flex w-full items-center gap-2 rounded px-2 py-2 text-left font-display text-[12.5px] font-semibold text-cream-dim transition-colors hover:bg-cream/10 hover:text-cream"
                >
                  <span className="h-1.5 w-1.5 shrink-0" style={{ backgroundColor: colour }} />
                  <span className="flex-1 truncate">{row.name}</span>
                  <span className="tabular-nums text-cream-faint">{formatPct1(row.prob)}</span>
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}

interface TabProps {
  label: string;
  colour: string;
  selected: boolean;
  title: string;
  onClick: () => void;
}

function Tab({ label, colour, selected, title, onClick }: TabProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={selected}
      title={title}
      className="relative -my-2 py-2 font-display text-[clamp(13px,1.4vw,15px)] font-bold tracking-[0.02em] transition-opacity hover:opacity-100"
      style={{ color: colour, opacity: selected ? 1 : 0.55 }}
    >
      <span className="relative pb-1">
        {label}
        {selected && (
          <span className="absolute inset-x-0 bottom-0 h-[2px] rounded-full" style={{ backgroundColor: colour }} />
        )}
      </span>
    </button>
  );
}
