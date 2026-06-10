import type { BracketViewModel, SlotView } from "@/lib/bracket-view";

export interface CanvasNode {
  slot: SlotView;
  x: number;
  y: number;
}

export interface CanvasEdge {
  fromMatch: number;
  toMatch: number;
}

export interface CanvasLayout {
  nodes: CanvasNode[];
  edges: CanvasEdge[];
  width: number;
  height: number;
  nodeWidth: number;
  nodeHeight: number;
  focusMatch: number | null;
  columnLabels: { label: string; x: number }[];
}

export const NODE_W = 172;
export const NODE_H = 64;
const COL_GAP = 40;
const ROW_PITCH = 80;
const TOP_PAD = 34;

const LEFT_COLUMNS: Record<string, number> = { r32: 0, r16: 1, qf: 2, sf: 3 };
const RIGHT_COLUMNS: Record<string, number> = { r32: 8, r16: 7, qf: 6, sf: 5 };
const FINAL_COLUMN = 4;
const COLUMN_COUNT = 9;

function feederMatch(label: string): number | null {
  const m = /^W(\d+)$/.exec(label);
  return m ? Number(m[1]) : null;
}

function feeders(slot: SlotView): number[] {
  return [slot.home.label, slot.away.label]
    .map(feederMatch)
    .filter((match): match is number => match !== null);
}

function r32Ancestors(slot: SlotView, byMatch: Map<number, SlotView>): Set<number> {
  if (slot.stage === "r32") return new Set([slot.match]);
  const result = new Set<number>();
  for (const feeder of feeders(slot)) {
    const feederSlot = byMatch.get(feeder);
    if (!feederSlot) continue;
    for (const ancestor of r32Ancestors(feederSlot, byMatch)) result.add(ancestor);
  }
  return result;
}

function columnX(column: number): number {
  return column * (NODE_W + COL_GAP);
}

export function buildCanvasLayout(view: BracketViewModel): CanvasLayout {
  const slots = [
    ...view.left,
    ...view.right,
    ...view.rounds.flatMap((round) => round.slots),
  ].filter((slot) => slot.stage !== "third_place");
  const byMatch = new Map(slots.map((slot) => [slot.match, slot]));

  const semis = slots.filter((slot) => slot.stage === "sf").sort((a, b) => a.match - b.match);
  const leftR32 = semis[0] ? r32Ancestors(semis[0], byMatch) : new Set<number>();
  const inLeftHalf = (slot: SlotView) =>
    [...r32Ancestors(slot, byMatch)].every((match) => leftR32.has(match));

  const nodeByMatch = new Map<number, CanvasNode>();
  for (const half of ["left", "right"] as const) {
    const columnMap = half === "left" ? LEFT_COLUMNS : RIGHT_COLUMNS;
    const r32 = slots
      .filter((slot) => slot.stage === "r32" && leftR32.has(slot.match) === (half === "left"))
      .sort((a, b) => a.match - b.match);
    r32.forEach((slot, i) => {
      nodeByMatch.set(slot.match, { slot, x: columnX(columnMap.r32), y: TOP_PAD + i * ROW_PITCH });
    });
  }

  const placeRound = (stage: string) => {
    for (const slot of slots.filter((s) => s.stage === stage)) {
      const column =
        stage === "final"
          ? FINAL_COLUMN
          : (inLeftHalf(slot) ? LEFT_COLUMNS : RIGHT_COLUMNS)[stage];
      const feederYs = feeders(slot)
        .map((match) => nodeByMatch.get(match)?.y)
        .filter((y): y is number => y !== undefined);
      const y = feederYs.length > 0 ? feederYs.reduce((a, b) => a + b, 0) / feederYs.length : TOP_PAD;
      nodeByMatch.set(slot.match, { slot, x: columnX(column), y });
    }
  };
  for (const stage of ["r16", "qf", "sf", "final"]) placeRound(stage);

  const edges: CanvasEdge[] = [];
  for (const slot of slots) {
    for (const feeder of feeders(slot)) {
      if (nodeByMatch.has(feeder)) edges.push({ fromMatch: feeder, toMatch: slot.match });
    }
  }

  const focusR32 = slots
    .filter((slot) => slot.stage === "r32" && slot.focusProb > 0)
    .sort((a, b) => b.focusProb - a.focusProb)[0];

  const columnLabels = [
    { label: "Last 32", x: columnX(0) },
    { label: "Last 16", x: columnX(1) },
    { label: "Quarters", x: columnX(2) },
    { label: "Semis", x: columnX(3) },
    { label: "Final", x: columnX(FINAL_COLUMN) },
    { label: "Semis", x: columnX(5) },
    { label: "Quarters", x: columnX(6) },
    { label: "Last 16", x: columnX(7) },
    { label: "Last 32", x: columnX(8) },
  ];

  return {
    nodes: [...nodeByMatch.values()],
    edges,
    width: COLUMN_COUNT * NODE_W + (COLUMN_COUNT - 1) * COL_GAP,
    height: TOP_PAD + 8 * ROW_PITCH - (ROW_PITCH - NODE_H),
    nodeWidth: NODE_W,
    nodeHeight: NODE_H,
    focusMatch: focusR32?.match ?? null,
    columnLabels,
  };
}

export function edgePath(layout: CanvasLayout, edge: CanvasEdge): string | null {
  const from = layout.nodes.find((n) => n.slot.match === edge.fromMatch);
  const to = layout.nodes.find((n) => n.slot.match === edge.toMatch);
  if (!from || !to) return null;

  const rightward = to.x > from.x;
  const fromX = rightward ? from.x + NODE_W : from.x;
  const toX = rightward ? to.x : to.x + NODE_W;
  const fromY = from.y + NODE_H / 2;
  const toY = to.y + NODE_H / 2;
  const midX = (fromX + toX) / 2;
  return `M${fromX},${fromY} H${midX} V${toY} H${toX}`;
}
