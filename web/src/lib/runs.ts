export interface RunRecord {
  runId: string;
  createdAt: string;
  s3Key: string;
  status: "completed" | "failed";
  cost: number | null;
  durationS: number | null;
  kind: string;
}

export interface SnapshotRef {
  runId: string;
  asOf: string;
  kind: string;
  key: string;
  hasDistributions: boolean;
}

export interface TeamHistoryPoint {
  runId: string;
  asOf: string;
  championProb: number;
  reachProbs: Record<string, number>;
  marketProb?: number | null;
  blendProb?: number | null;
}

export interface TeamHistory {
  teamId: string;
  points: TeamHistoryPoint[];
}
