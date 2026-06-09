import type { Snapshot } from "@/lib/snapshot";

export interface MarketRow {
  teamId: string;
  name: string;
  modelProb: number;
  marketProb: number | null;
  deltaPts: number | null;
}

export interface MarketsView {
  rows: MarketRow[];
  hasMarketData: boolean;
}

interface MarketLeg {
  team_id: string;
  consensus_prob: number;
}

// Market legs arrive with a later engine run; until then the snapshot carries no markets block
// and team champion probabilities are read defensively for the same reason.
function marketLegs(snapshot: Snapshot): Map<string, number> {
  const markets = (snapshot as unknown as { markets?: { champion?: unknown } | null }).markets;
  const legs = markets?.champion;
  if (!Array.isArray(legs)) return new Map();
  return new Map(
    legs
      .filter(
        (leg): leg is MarketLeg =>
          typeof leg === "object" &&
          leg !== null &&
          typeof (leg as MarketLeg).team_id === "string" &&
          typeof (leg as MarketLeg).consensus_prob === "number",
      )
      .map((leg) => [leg.team_id, leg.consensus_prob]),
  );
}

function championProb(team: unknown): number {
  const prob = (team as { champion_prob?: unknown }).champion_prob;
  return typeof prob === "number" ? prob : 0;
}

const ROW_LIMIT = 6;

export function buildMarketsView(snapshot: Snapshot, names: Map<string, string>): MarketsView {
  const legs = marketLegs(snapshot);
  const rows = [...snapshot.teams]
    .map((team) => ({ teamId: team.team_id, modelProb: championProb(team) }))
    .sort((a, b) => b.modelProb - a.modelProb)
    .slice(0, ROW_LIMIT)
    .map(({ teamId, modelProb }) => {
      const marketProb = legs.get(teamId) ?? null;
      return {
        teamId,
        name: names.get(teamId) ?? teamId,
        modelProb,
        marketProb,
        deltaPts: marketProb === null ? null : (modelProb - marketProb) * 100,
      };
    });
  return { rows, hasMarketData: legs.size > 0 };
}
