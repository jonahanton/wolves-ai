import { englandSlotProb, pinEnglandFirst, r32Halves } from "@/lib/bracket";
import { formatMatchDate } from "@/lib/format";
import type { Slot, SlotSide, Snapshot } from "@/lib/snapshot";
import type { OpponentView } from "@/lib/spine-view";
import { venueTraits, type VenueTraits } from "@/lib/venues";

const STAGE_LABELS: Record<string, string> = {
  r32: "Last 32",
  r16: "Last 16",
  qf: "Quarter-finals",
  sf: "Semi-finals",
  third_place: "Third place",
  final: "The final",
};

export interface SideView {
  label: string;
  description: string;
  candidates: OpponentView[];
}

export interface SlotView {
  match: number;
  stage: string;
  stageLabel: string;
  city: string;
  dateLabel: string;
  traits: VenueTraits;
  englandProb: number;
  home: SideView;
  away: SideView;
}

export interface RoundView {
  stage: string;
  stageLabel: string;
  slots: SlotView[];
}

export interface BracketViewModel {
  left: SlotView[];
  right: SlotView[];
  englandHalf: "left" | "right";
  rounds: RoundView[];
}

export function describeSlotLabel(label: string): string {
  const seeded = /^([123])([A-L])$/.exec(label);
  if (seeded) {
    const place = { "1": "Winner", "2": "Runner-up", "3": "Third" }[seeded[1]];
    return `${place}, Group ${seeded[2]}`;
  }
  const thirds = /^3:([A-L]+)$/.exec(label);
  if (thirds) return `Third from ${thirds[1].split("").join("/")}`;
  const winner = /^W(\d+)$/.exec(label);
  if (winner) return `Winner of match ${winner[1]}`;
  return label;
}

function sideView(side: SlotSide, names: Map<string, string>): SideView {
  return {
    label: side.label,
    description: describeSlotLabel(side.label),
    candidates: side.candidates.map((c) => ({
      teamId: c.team_id,
      name: names.get(c.team_id) ?? c.team_id,
      prob: c.prob,
    })),
  };
}

function slotView(slot: Slot, names: Map<string, string>, englandProb: number): SlotView {
  return {
    match: slot.match,
    stage: slot.stage,
    stageLabel: STAGE_LABELS[slot.stage] ?? slot.stage,
    city: slot.city,
    dateLabel: formatMatchDate(slot.date),
    traits: venueTraits(slot.city),
    englandProb,
    home: sideView(slot.home, names),
    away: sideView(slot.away, names),
  };
}

const ENGLAND_PIN_THRESHOLD = 0.02;

const LATER_ROUNDS = ["r16", "qf", "sf", "final", "third_place"];

export function buildBracketView(snapshot: Snapshot, names: Map<string, string>): BracketViewModel {
  const halves = r32Halves(snapshot.slots);
  const englandHalf =
    Math.max(...halves.left.map(englandSlotProb), 0) > Math.max(...halves.right.map(englandSlotProb), 0)
      ? "left"
      : "right";

  const buildHalf = (slots: Slot[]) =>
    pinEnglandFirst(slots).map((slot) => {
      const prob = englandSlotProb(slot);
      return slotView(slot, names, prob >= ENGLAND_PIN_THRESHOLD ? prob : 0);
    });

  const rounds = LATER_ROUNDS.map((stage) => ({
    stage,
    stageLabel: STAGE_LABELS[stage] ?? stage,
    slots: snapshot.slots
      .filter((s) => s.stage === stage)
      .sort((a, b) => a.match - b.match)
      .map((s) => slotView(s, names, 0)),
  })).filter((round) => round.slots.length > 0);

  return {
    left: buildHalf(halves.left),
    right: buildHalf(halves.right),
    englandHalf,
    rounds,
  };
}
