import scheduleData from "@/lib/schedule.json";

export interface GroupMatch {
  match: number;
  group: string;
  date: string;
  city: string;
  home: string;
  away: string;
}

export interface KnockoutMatch {
  match: number;
  stage: string;
  date: string;
  city: string;
  home: string;
  away: string;
}

const schedule = scheduleData as { groupMatches: GroupMatch[]; knockout: KnockoutMatch[] };

export const groupMatches: GroupMatch[] = schedule.groupMatches;
export const knockoutMatches: KnockoutMatch[] = schedule.knockout;

export const ENGLAND = "england";

export const groupStageStart = groupMatches
  .map((m) => m.date)
  .sort()[0];

export function englandGroupFixtures(): GroupMatch[] {
  return groupMatches
    .filter((m) => m.home === ENGLAND || m.away === ENGLAND)
    .sort((a, b) => a.date.localeCompare(b.date));
}

export function nextEnglandFixture(now: Date): GroupMatch | null {
  return englandGroupFixtures().find((m) => new Date(m.date) >= now) ?? null;
}

export function nextMatchday(now: Date): { day: string; matches: GroupMatch[] } | null {
  const upcoming = groupMatches
    .filter((m) => new Date(m.date) >= now)
    .sort((a, b) => a.date.localeCompare(b.date));
  if (upcoming.length === 0) return null;
  const day = upcoming[0].date.slice(0, 10);
  return { day, matches: upcoming.filter((m) => m.date.slice(0, 10) === day) };
}
