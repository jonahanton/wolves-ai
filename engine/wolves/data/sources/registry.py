"""Team dimension: dataset keys joined to the 2026 registry, Elo and squad values."""

from __future__ import annotations

import json
from pathlib import Path

from wolves.data.contracts import MatchRecord, TeamRecord
from wolves.data.teams import UnmappedTeamError, expected_results_name, registry_team_key


def _elo_by_code(tsv_path: Path) -> dict[str, float]:
    by_code: dict[str, float] = {}
    for line in tsv_path.read_text().splitlines():
        parts = line.split("\t")
        if len(parts) > 3:
            by_code[parts[2]] = float(parts[3])
    return by_code


def build_team_dimension(data_dir: Path, *, elo_tsv: Path, matches: list[MatchRecord]) -> list[TeamRecord]:
    """Every team in the results backbone, with registry id and covariates for the 48."""
    teams_raw = json.loads((data_dir / "format" / "teams.json").read_text(encoding="utf-8"))
    squad_values = json.loads((data_dir / "ratings" / "squad-values.json").read_text(encoding="utf-8"))["valuesEurM"]
    elo = _elo_by_code(elo_tsv)

    keys = sorted({match.home_team for match in matches} | {match.away_team for match in matches})
    by_key: dict[str, TeamRecord] = {key: TeamRecord(team=key) for key in keys}
    for entry in teams_raw:
        app_id = entry["id"]
        key = registry_team_key(app_id)
        if key not in by_key:
            raise UnmappedTeamError(app_id, expected_results_name(app_id))
        by_key[key] = TeamRecord(
            team=key,
            app_team_id=app_id,
            elo=elo.get(entry["eloCode"]),
            squad_value_eur_m=squad_values.get(app_id),
        )
    return list(by_key.values())
