import type { PlayedResultRow } from "@/lib/results";
import type { PairingMatrices } from "@/lib/sidecars";

export const STREAM_ROUNDS = ["r32", "r16", "qf", "sf", "final"] as const;
export type StreamRound = (typeof STREAM_ROUNDS)[number];

const ROUND_LABEL: Record<StreamRound, string> = {
  r32: "R32",
  r16: "R16",
  qf: "QF",
  sf: "SF",
  final: "Final",
};

export const REMAINDER_ID = "__remainder__";

export interface OpponentSegment {
  opponentId: string;
  p: number;
}

export interface RoundBar {
  round: StreamRound;
  label: string;
  played: boolean;
  confirmedReach: boolean;
  reachable: boolean;
  segments: OpponentSegment[];
}

export interface OpponentDraw {
  rounds: RoundBar[];
}

// Stable colour/order: opponents sorted by total unconditional p across rounds.
function bandOrder(rounds: PairingMatrices["rounds"], teamId: string): string[] {
  const total = new Map<string, number>();
  for (const round of STREAM_ROUNDS) {
    for (const { opponent, p } of rounds[round]?.[teamId] ?? []) {
      total.set(opponent, (total.get(opponent) ?? 0) + p);
    }
  }
  return [...total.entries()].sort((a, b) => b[1] - a[1]).map(([id]) => id);
}

function playedOpponent(results: PlayedResultRow[], round: StreamRound, teamId: string): string | null {
  const row = results.find((r) => r.stage === round && (r.homeId === teamId || r.awayId === teamId));
  if (!row) return null;
  return row.homeId === teamId ? row.awayId : row.homeId;
}

// Conditional view: given the team reaches round R, who do they face? Each p is
// the unconditional pairing probability divided by the team's reach probability;
// the remainder (truncated tail + within-round elimination) keeps the bar honest.
export function opponentDraw(
  rounds: PairingMatrices["rounds"],
  teamId: string,
  reachProbs: Record<string, number>,
  results: PlayedResultRow[],
  names: Record<string, string>,
): OpponentDraw {
  const order = bandOrder(rounds, teamId).filter((id) => names[id] !== undefined);

  const roundBars: RoundBar[] = STREAM_ROUNDS.map((round, i) => {
    const reached = reachProbs[round] ?? 0;
    const realised = playedOpponent(results, round, teamId);
    if (realised) {
      return { round, label: ROUND_LABEL[round], played: true, confirmedReach: true, reachable: true, segments: [{ opponentId: realised, p: 1 }] };
    }

    // Reaching this round is certain once the previous round has been played.
    const confirmedReach = i > 0 && playedOpponent(results, STREAM_ROUNDS[i - 1], teamId) !== null;
    const reachable = reached > 0;

    const listed = rounds[round]?.[teamId] ?? [];
    const segments = order
      .map((id) => ({ opponentId: id, p: listed.find((o) => o.opponent === id)?.p ?? 0 }))
      .filter((s) => s.p > 0)
      .map((s) => ({ opponentId: s.opponentId, p: reached > 0 ? Math.min(1, s.p / reached) : 0 }));

    const sum = segments.reduce((acc, s) => acc + s.p, 0);
    if (sum < 1) segments.push({ opponentId: REMAINDER_ID, p: 1 - sum });

    return { round, label: ROUND_LABEL[round], played: false, confirmedReach, reachable, segments };
  });

  return { rounds: roundBars };
}
