import { describeSlotLabel } from "@/lib/bracket-view";
import type { Fixture } from "@/lib/schedule";
import type { Snapshot } from "@/lib/snapshot";

export interface MatchForecastView {
  pHome: number;
  pDraw: number | null;
  pAway: number;
  pDecided90: number | null;
  pPairing: number | null;
  modalScore: string | null;
}

export interface LiveFixtureView {
  match: number;
  date: string;
  city: string;
  isGroup: boolean;
  homeId: string | null;
  awayId: string | null;
  homeName: string;
  awayName: string;
  forecast: MatchForecastView | null;
}

export function buildLiveFixtures(
  snapshot: Snapshot,
  fixtures: Fixture[],
  names: Map<string, string>,
): LiveFixtureView[] {
  const byMatch = new Map((snapshot.matches ?? []).map((m) => [m.match, m]));
  return fixtures.map((fixture) => {
    const probs = byMatch.get(fixture.match) ?? null;
    const isGroup = fixture.stage === "group";
    const homeId = isGroup ? fixture.home : (probs?.home_id ?? null);
    const awayId = isGroup ? fixture.away : (probs?.away_id ?? null);
    return {
      match: fixture.match,
      date: fixture.date,
      city: fixture.city,
      isGroup,
      homeId,
      awayId,
      homeName: homeId ? (names.get(homeId) ?? homeId) : describeSlotLabel(fixture.home),
      awayName: awayId ? (names.get(awayId) ?? awayId) : describeSlotLabel(fixture.away),
      forecast: probs
        ? {
            pHome: probs.p_home,
            pDraw: probs.p_draw ?? null,
            pAway: probs.p_away,
            pDecided90: probs.p_decided_90 ?? null,
            pPairing: probs.p_pairing ?? null,
            modalScore: probs.modal_score ?? null,
          }
        : null,
    };
  });
}
