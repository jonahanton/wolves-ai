export interface PlayedResultRow {
  match: number;
  date: string;
  stage: string;
  homeId: string | null;
  awayId: string | null;
  homeGoals: number;
  awayGoals: number;
  winner: string | null;
}
