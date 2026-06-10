import { slotRationale } from "@/lib/agent-fields";
import { focusSpine } from "@/lib/bracket";
import { formatMatchDate } from "@/lib/format";
import type { Finish, Snapshot } from "@/lib/snapshot";
import { venueLine } from "@/lib/venues";

const STAGE_LABELS: Record<string, string> = {
  r32: "Last 32",
  r16: "Last 16",
  qf: "Quarter-final",
  sf: "Semi-final",
  final: "Final",
};

function finishLabel(finish: Finish, group: string): string {
  const labels: Record<Finish, string> = {
    win_group: `Win Group ${group}`,
    runner_up: "Finish second",
    third: "Through in third",
  };
  return labels[finish];
}

export interface OpponentView {
  teamId: string;
  name: string;
  prob: number;
}

export interface SpineStageView {
  stage: string;
  stageLabel: string;
  match: number;
  city: string;
  venueLabel: string | null;
  dateLabel: string;
  rationale: string | null;
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
  return snapshot.focus.paths.map((path) => ({
    finish: path.finish,
    finishLabel: finishLabel(path.finish, snapshot.focus.group),
    toggleLabel: TOGGLE_LABELS[path.finish] ?? path.finish,
    prob: path.prob,
    stages: focusSpine(snapshot, path.finish).map((stage) => ({
      stage: stage.stage,
      stageLabel: STAGE_LABELS[stage.stage] ?? stage.stage,
      match: stage.match,
      city: stage.city,
      venueLabel: venueLine(stage.city),
      dateLabel: formatMatchDate(stage.date),
      rationale: slotRationale(snapshot, stage.match),
      opponents: stage.opponents.slice(0, 3).map((c) => ({
        teamId: c.team_id,
        name: names.get(c.team_id) ?? c.team_id,
        prob: c.prob,
      })),
      moreCount: Math.max(0, stage.opponents.length - 3),
    })),
  }));
}
