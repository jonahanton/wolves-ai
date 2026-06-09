"use client";

import { useEffect, useMemo } from "react";
import { Maximize, Minus, Plus } from "lucide-react";
import { usePanZoom } from "@/hooks/use-pan-zoom";
import { buildCanvasLayout, edgePath, NODE_H, NODE_W, type CanvasNode } from "@/lib/bracket-canvas";
import { formatPct } from "@/lib/format";
import type { BracketViewModel, SlotView } from "@/lib/bracket-view";

const NAME_CHARS = 15;

function truncate(text: string, max: number): string {
  return text.length > max ? `${text.slice(0, max - 1)}…` : text;
}

function TieNode({ node, onSelect, wasDrag }: TieNodeProps) {
  const { slot } = node;
  const england = slot.englandProb > 0;
  const home = slot.home.candidates[0];
  const away = slot.away.candidates[0];

  return (
    <g
      transform={`translate(${node.x}, ${node.y})`}
      role="button"
      tabIndex={-1}
      style={{ cursor: "pointer" }}
      onClick={() => {
        if (!wasDrag()) onSelect(slot);
      }}
    >
      <rect
        width={NODE_W}
        height={NODE_H}
        rx={8}
        fill="var(--card)"
        stroke={england ? "var(--gold)" : "var(--border-strong)"}
        strokeWidth={england ? 1.5 : 1}
      />
      <text x={8} y={15} fontSize={9} fill="var(--muted-foreground)">
        {truncate(`M${slot.match} · ${slot.city} · ${slot.dateLabel}`, 30)}
      </text>
      {[home, away].map((candidate, i) => {
        const y = 33 + i * 18;
        const side = i === 0 ? slot.home : slot.away;
        const isEngland = candidate?.teamId === "england";
        return (
          <g key={side.label}>
            <text
              x={8}
              y={y}
              fontSize={11.5}
              fontWeight={600}
              fill={isEngland ? "var(--gold)" : "var(--foreground)"}
            >
              {truncate(candidate?.name ?? side.description, NAME_CHARS)}
            </text>
            {candidate && (
              <text
                x={NODE_W - 8}
                y={y}
                fontSize={11}
                textAnchor="end"
                fill="var(--muted-foreground)"
                style={{ fontVariantNumeric: "tabular-nums" }}
              >
                {formatPct(candidate.prob)}
              </text>
            )}
          </g>
        );
      })}
    </g>
  );
}

interface TieNodeProps {
  node: CanvasNode;
  onSelect: (slot: SlotView) => void;
  wasDrag: () => boolean;
}

interface BracketCanvasProps {
  view: BracketViewModel;
  onSelect: (slot: SlotView) => void;
}

export function BracketCanvas({ view, onSelect }: BracketCanvasProps) {
  const layout = useMemo(() => buildCanvasLayout(view), [view]);
  const { containerRef, contentRef, focusOn, fit, zoomBy, wasDrag } = usePanZoom({
    contentWidth: layout.width,
    contentHeight: layout.height,
  });

  useEffect(() => {
    const england = layout.nodes.find((node) => node.slot.match === layout.englandMatch);
    if (england) focusOn(england.x + NODE_W / 2, england.y + NODE_H / 2, 1);
    else fit();
  }, [layout, focusOn, fit]);

  const controls = [
    { label: "Zoom in", icon: Plus, action: () => zoomBy(1.4) },
    { label: "Zoom out", icon: Minus, action: () => zoomBy(1 / 1.4) },
    { label: "Fit bracket", icon: Maximize, action: fit },
  ];

  return (
    <div>
      <div className="relative">
        <div
          ref={containerRef}
          className="h-[62dvh] touch-none overflow-hidden rounded-xl border bg-secondary/40 select-none"
          aria-label="Bracket canvas. Drag to pan, pinch or double-tap to zoom."
        >
          <svg
            ref={contentRef}
            width={layout.width}
            height={layout.height}
            viewBox={`0 0 ${layout.width} ${layout.height}`}
            className="origin-top-left will-change-transform"
          >
            {layout.columnLabels.map(({ label, x }, i) => (
              <text
                key={i}
                x={x + NODE_W / 2}
                y={16}
                fontSize={11}
                fontWeight={600}
                textAnchor="middle"
                fill="var(--muted-foreground)"
                style={{ textTransform: "uppercase", letterSpacing: "0.08em" }}
              >
                {label}
              </text>
            ))}
            {layout.edges.map((edge) => {
              const d = edgePath(layout, edge);
              return d ? (
                <path
                  key={`${edge.fromMatch}-${edge.toMatch}`}
                  d={d}
                  fill="none"
                  stroke="var(--border-strong)"
                  strokeWidth={1}
                />
              ) : null;
            })}
            {layout.nodes.map((node) => (
              <TieNode key={node.slot.match} node={node} onSelect={onSelect} wasDrag={wasDrag} />
            ))}
          </svg>
        </div>
        <div className="absolute right-2.5 bottom-2.5 flex flex-col gap-1.5">
          {controls.map(({ label, icon: Icon, action }) => (
            <button
              key={label}
              type="button"
              aria-label={label}
              onClick={action}
              className="rounded-full border bg-background/90 p-2 text-muted-foreground shadow-sm backdrop-blur-sm active:scale-95"
            >
              <Icon size={15} />
            </button>
          ))}
        </div>
      </div>
      <p className="mt-2 text-center text-xs text-muted-foreground">
        Drag to pan &middot; pinch or double-tap to zoom &middot; tap a tie for the full picture
      </p>
    </div>
  );
}
