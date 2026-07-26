import { LandingForecast } from "@/components/landing/landing-forecast";
import { ArchiveDateControl } from "@/components/shell/archive-date-control";
import { FestivalBand } from "@/components/walls/festival-band";
import type { ArchiveDay, ArchiveDayPayload, ArchiveManifest } from "@/lib/archive/contracts";
import { titleBoard } from "@/lib/derive";
import { cleanStories } from "@/lib/forecast";
import type { ChartTeamInput } from "@/lib/forecast-series";
import { formatRunStampEastern } from "@/lib/format";
import type { TeamHistory } from "@/lib/runs";
import { chartColour } from "@/lib/team-colours";

interface ArchiveLandingPageProps {
  manifest: ArchiveManifest;
  day: ArchiveDay;
  payload: ArchiveDayPayload;
}

const CHART_TEAM_IDS = ["france", "spain", "england", "argentina"];

export function ArchiveLandingPage({ manifest, day, payload }: ArchiveLandingPageProps) {
  const snapshot = payload.selected_snapshot;
  const names = Object.fromEntries(snapshot.teams.map((team) => [team.team_id, team.name]));
  const fullBoard = titleBoard(snapshot, snapshot.teams.length);
  const board = fullBoard.filter((row) => CHART_TEAM_IDS.includes(row.teamId));
  const leaderId = board[0]?.teamId ?? snapshot.focus.team_id;
  const topIds = new Set(board.map((row) => row.teamId));
  const allIds = fullBoard.map((row) => row.teamId);
  const historyByTeam = archiveHistories(payload, allIds);
  const championCells = Object.fromEntries(
    Object.entries(payload.sidecars.distributions.teams)
      .map(([teamId, stages]) => [teamId, stages.champion] as const)
      .filter(([, cell]) => cell !== undefined),
  );
  const cellUppers = Object.values(championCells)
    .filter((cell) => cell.bin_edges.length > 0)
    .map((cell) => cell.bin_edges[cell.bin_edges.length - 1]);
  const xMax = cellUppers.length > 0 ? Math.max(...cellUppers) : 1;
  const chartTeams: ChartTeamInput[] = allIds.map((teamId) => ({
    teamId,
    name: names[teamId] ?? teamId,
    featured: teamId === leaderId,
    tier: topIds.has(teamId) ? "top" : "rest",
    colour: chartColour(teamId),
    history: historyByTeam.get(teamId)?.points ?? [],
  }));

  return (
    <>
      <main>
        <div className="wrap pt-5">
          <ArchiveDateControl days={manifest.days} selectedDay={day} section="home" />
        </div>
        <LandingForecast
          runLabel={formatRunStampEastern(snapshot.run.created_at)}
          teams={chartTeams}
          leaderId={leaderId}
          board={board}
          fullBoard={fullBoard}
          championCells={championCells}
          xMax={xMax}
          weights={snapshot.agent?.scenario_weights ?? []}
          camps={(snapshot.agent?.camps ?? []).slice().sort((a, b) => (a.order ?? 0) - (b.order ?? 0))}
          drivers={snapshot.distributions?.drivers ?? {}}
          stories={cleanStories(snapshot.agent?.narrative.team_stories ?? {})}
        />
      </main>
      <div className="max-h-[clamp(120px,18vh,200px)] overflow-hidden">
        <FestivalBand family="euros" tag="Euros 2024 · the Wolves" />
      </div>
    </>
  );
}

function archiveHistories(payload: ArchiveDayPayload, teamIds: string[]): Map<string, TeamHistory> {
  const histories = new Map<string, TeamHistory>(teamIds.map((teamId) => [teamId, { teamId, points: [] }]));
  for (const snapshot of payload.forecast_history) {
    for (const team of snapshot.teams) {
      const history = histories.get(team.team_id);
      if (!history) continue;
      history.points.push({
        runId: snapshot.run.run_id,
        asOf: snapshot.run.as_of ?? snapshot.run.created_at.slice(0, 10),
        championProb: team.champion_prob ?? 0,
        reachProbs: team.reach_probs ?? {},
      });
    }
  }
  return histories;
}
