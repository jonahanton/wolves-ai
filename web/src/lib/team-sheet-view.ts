import { STAGE_LABELS } from "@/lib/bracket-view";
import { formatMatchDate } from "@/lib/format";
import { championMarketLegs } from "@/lib/markets";
import { REACH_STAGES } from "@/lib/reach-stages";
import type { MatchProbs, Snapshot } from "@/lib/snapshot";

export interface ReachPoint {
  label: string;
  prob: number;
}

export interface RouteStep {
  match: number;
  stageLabel: string;
  opponentName: string;
  city: string;
  dateLabel: string;
  winProb: number;
  pairingProb: number | null;
}

export interface TeamSheetView {
  teamId: string;
  name: string;
  group: string;
  isFocus: boolean;
  rating: number;
  valueEurM: number | null;
  championProb: number;
  marketProb: number | null;
  reach: ReachPoint[];
  route: RouteStep[];
}

function routeStep(match: MatchProbs, teamId: string, names: Map<string, string>): RouteStep {
  const home = match.home_id === teamId;
  const opponentId = home ? match.away_id : match.home_id;
  return {
    match: match.match,
    stageLabel: STAGE_LABELS[match.stage] ?? match.stage,
    opponentName: names.get(opponentId) ?? opponentId,
    city: match.city,
    dateLabel: formatMatchDate(match.date),
    winProb: home ? match.p_home : match.p_away,
    pairingProb: match.p_pairing ?? null,
  };
}

export function buildTeamSheetViews(snapshot: Snapshot, names: Map<string, string>): Record<string, TeamSheetView> {
  const legs = championMarketLegs(snapshot);
  const knockoutsByTeam = new Map<string, MatchProbs[]>();
  for (const match of snapshot.matches ?? []) {
    if (match.stage === "group") continue;
    for (const teamId of [match.home_id, match.away_id]) {
      const list = knockoutsByTeam.get(teamId) ?? [];
      list.push(match);
      knockoutsByTeam.set(teamId, list);
    }
  }

  const views: Record<string, TeamSheetView> = {};
  for (const team of snapshot.teams) {
    views[team.team_id] = {
      teamId: team.team_id,
      name: names.get(team.team_id) ?? team.team_id,
      group: team.group,
      isFocus: team.team_id === snapshot.focus.team_id,
      rating: team.rating ?? team.elo,
      valueEurM: team.value_eur_m ?? null,
      championProb: team.champion_prob ?? team.reach_probs?.champion ?? 0,
      marketProb: legs.get(team.team_id) ?? null,
      reach: REACH_STAGES.map((stage) => ({ label: stage.label, prob: team.reach_probs?.[stage.key] ?? 0 })),
      route: (knockoutsByTeam.get(team.team_id) ?? [])
        .sort((a, b) => a.date.localeCompare(b.date))
        .map((match) => routeStep(match, team.team_id, names)),
    };
  }
  return views;
}
