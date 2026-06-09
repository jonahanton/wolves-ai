import { englandSpine } from "@/lib/bracket";
import { formatMatchDate } from "@/lib/format";
import type { Finish, Snapshot } from "@/lib/snapshot";
import { venueTraits, type VenueTraits } from "@/lib/venues";

const STAGE_LABELS: Record<string, string> = {
  r32: "Last 32",
  r16: "Last 16",
  qf: "Quarter-final",
  sf: "Semi-final",
  final: "Final",
};

const FINISH_LABELS: Record<Finish, string> = {
  win_group: "Win Group L",
  runner_up: "Finish second",
  third: "Through in third",
};

export interface OpponentView {
  teamId: string;
  name: string;
  prob: number;
}

export interface SpineStageView {
  stage: string;
  stageLabel: string;
  city: string;
  dateLabel: string;
  traits: VenueTraits;
  opponents: OpponentView[];
  moreCount: number;
}

export interface SpineView {
  finish: Finish;
  finishLabel: string;
  toggleLabel: string;
  prob: number;
  stages: SpineStageView[];
}

const TOGGLE_LABELS: Record<Finish, string> = {
  win_group: "Win",
  runner_up: "2nd",
  third: "3rd",
};

export function buildSpineViews(snapshot: Snapshot, names: Map<string, string>): SpineView[] {
  return snapshot.england.paths.map((path) => ({
    finish: path.finish,
    finishLabel: FINISH_LABELS[path.finish] ?? path.finish,
    toggleLabel: TOGGLE_LABELS[path.finish] ?? path.finish,
    prob: path.prob,
    stages: englandSpine(snapshot, path.finish).map((stage) => ({
      stage: stage.stage,
      stageLabel: STAGE_LABELS[stage.stage] ?? stage.stage,
      city: stage.city,
      dateLabel: formatMatchDate(stage.date),
      traits: venueTraits(stage.city),
      opponents: stage.opponents.slice(0, 3).map((c) => ({
        teamId: c.team_id,
        name: names.get(c.team_id) ?? c.team_id,
        prob: c.prob,
      })),
      moreCount: Math.max(0, stage.opponents.length - 3),
    })),
  }));
}
