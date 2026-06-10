"use client";

import { useState } from "react";
import { BracketBoard } from "@/components/bracket/bracket-board";
import { PageHeader } from "@/components/shell/page-header";
import { TeamSheet } from "@/components/team/team-sheet";
import { GroupTables } from "@/components/tournament/group-tables";
import { OddsTable } from "@/components/tournament/odds-table";
import { Segmented } from "@/components/ui/segmented";
import type { BracketViewModel } from "@/lib/bracket-view";
import type { GroupView } from "@/lib/groups-view";
import type { OddsView } from "@/lib/odds-view";
import type { TeamSheetView } from "@/lib/team-sheet-view";

type View = "bracket" | "odds" | "groups";

const HEADERS: Record<View, { title: string; subtitle: string }> = {
  bracket: { title: "Bracket", subtitle: "Every knockout slot, most likely occupants" },
  odds: { title: "Champion odds", subtitle: "All 48 teams, ranked by title chance" },
  groups: { title: "Groups", subtitle: "Finish probabilities across all twelve groups" },
};

interface TournamentBoardProps {
  bracket: BracketViewModel;
  odds: OddsView;
  groups: GroupView[];
  teamSheets: Record<string, TeamSheetView>;
}

export function TournamentBoard({ bracket, odds, groups, teamSheets }: TournamentBoardProps) {
  const [view, setView] = useState<View>("bracket");
  const [selectedTeam, setSelectedTeam] = useState<string | null>(null);
  const header = HEADERS[view];

  return (
    <div className="flex flex-col gap-5">
      <PageHeader title={header.title} subtitle={header.subtitle} />
      <Segmented
        options={[
          { value: "bracket", label: "Bracket" },
          { value: "odds", label: "Odds" },
          { value: "groups", label: "Groups" },
        ]}
        value={view}
        onChange={setView}
      />
      {view === "bracket" && <BracketBoard view={bracket} />}
      {view === "odds" && <OddsTable view={odds} onSelectTeam={setSelectedTeam} />}
      {view === "groups" && <GroupTables groups={groups} onSelectTeam={setSelectedTeam} />}
      <TeamSheet
        view={selectedTeam ? (teamSheets[selectedTeam] ?? null) : null}
        onClose={() => setSelectedTeam(null)}
      />
    </div>
  );
}
