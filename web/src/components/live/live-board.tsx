"use client";

import { useState } from "react";
import { MatchList } from "@/components/live/match-list";
import { TeamSheet } from "@/components/team/team-sheet";
import type { LiveFixtureView } from "@/lib/live-view";
import type { TeamSheetView } from "@/lib/team-sheet-view";

interface LiveBoardProps {
  preTournament: boolean;
  day: string | null;
  fixtures: LiveFixtureView[];
  teamSheets: Record<string, TeamSheetView>;
}

export function LiveBoard({ preTournament, day, fixtures, teamSheets }: LiveBoardProps) {
  const [selectedTeam, setSelectedTeam] = useState<string | null>(null);

  return (
    <>
      <MatchList preTournament={preTournament} day={day} fixtures={fixtures} onSelectTeam={setSelectedTeam} />
      <TeamSheet
        view={selectedTeam ? (teamSheets[selectedTeam] ?? null) : null}
        onClose={() => setSelectedTeam(null)}
      />
    </>
  );
}
