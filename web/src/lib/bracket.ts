import { knockoutMatches } from "@/lib/schedule";
import type { Candidate, Finish, Slot, Snapshot } from "@/lib/snapshot";

const SEMI_LEFT = 101;

function feederMatch(label: string): number | null {
  const m = /^W(\d+)$/.exec(label);
  return m ? Number(m[1]) : null;
}

function r32Ancestors(match: number): Set<number> {
  const fixture = knockoutMatches.find((k) => k.match === match);
  if (!fixture) return new Set();
  const result = new Set<number>();
  for (const label of [fixture.home, fixture.away]) {
    const feeder = feederMatch(label);
    if (feeder === null) continue;
    const feederFixture = knockoutMatches.find((k) => k.match === feeder);
    if (feederFixture?.stage === "r32") result.add(feeder);
    else for (const a of r32Ancestors(feeder)) result.add(a);
  }
  return result;
}

export function r32Halves(slots: Slot[]): { left: Slot[]; right: Slot[] } {
  const leftMatches = r32Ancestors(SEMI_LEFT);
  const r32 = slots.filter((s) => s.stage === "r32").sort((a, b) => a.match - b.match);
  return {
    left: r32.filter((s) => leftMatches.has(s.match)),
    right: r32.filter((s) => !leftMatches.has(s.match)),
  };
}

export function focusSlotProb(slot: Slot, teamId: string): number {
  const sideProb = (candidates: Candidate[]) =>
    candidates.find((c) => c.team_id === teamId)?.prob ?? 0;
  return sideProb(slot.home.candidates) + sideProb(slot.away.candidates);
}

export function pinFocusFirst(slots: Slot[], teamId: string): Slot[] {
  return [...slots].sort(
    (a, b) => focusSlotProb(b, teamId) - focusSlotProb(a, teamId) || a.match - b.match,
  );
}

export interface SpineStage {
  stage: string;
  match: number;
  city: string;
  date: string;
  opponents: Candidate[];
}

export function focusSpine(snapshot: Snapshot, finish: Finish): SpineStage[] {
  const path = snapshot.focus.paths.find((p) => p.finish === finish);
  if (!path) return [];

  const slotByMatch = new Map(snapshot.slots.map((s) => [s.match, s]));
  const stages: SpineStage[] = [
    {
      stage: "r32",
      match: path.r32_match,
      city: path.city,
      date: path.date,
      opponents: path.opponents,
    },
  ];

  let current = path.r32_match;
  for (;;) {
    const next = knockoutMatches.find(
      (k) =>
        k.stage !== "third_place" &&
        (feederMatch(k.home) === current || feederMatch(k.away) === current),
    );
    if (!next) break;
    const slot = slotByMatch.get(next.match);
    if (!slot) break;
    const opposing = feederMatch(next.home) === current ? slot.away : slot.home;
    stages.push({
      stage: next.stage,
      match: next.match,
      city: next.city,
      date: next.date,
      opponents: opposing.candidates.filter((c) => c.team_id !== snapshot.focus.team_id),
    });
    current = next.match;
  }
  return stages;
}
