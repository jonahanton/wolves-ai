from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from wolves.sim.format import FormatData

STAGE_ORDER = ("r32", "r16", "qf", "sf", "final")
STAGE_LABELS = {
    "r32": "round of 32",
    "r16": "round of 16",
    "qf": "quarter-final",
    "sf": "semi-final",
    "final": "final",
}


@dataclass(frozen=True)
class KnockoutRationaleSlot:
    match: int
    stage: str
    date: str
    city: str
    home: str
    away: str

    @property
    def key(self) -> str:
        return str(self.match)


def open_knockout_rationale_slots(fmt: FormatData, played: Mapping[int, object]) -> list[KnockoutRationaleSlot]:
    """Return open knockout slots in the earliest unresolved round."""
    by_stage: dict[str, list[KnockoutRationaleSlot]] = {stage: [] for stage in STAGE_ORDER}
    for match in fmt.knockout:
        if match.match in played or match.stage not in by_stage:
            continue
        by_stage[match.stage].append(
            KnockoutRationaleSlot(
                match=match.match,
                stage=match.stage,
                date=match.date,
                city=match.city,
                home=match.home,
                away=match.away,
            )
        )
    for stage in STAGE_ORDER:
        if by_stage[stage]:
            return sorted(by_stage[stage], key=lambda slot: slot.match)
    return []


def slot_rationale_keys(slots: list[KnockoutRationaleSlot]) -> set[str]:
    """Return slot rationale keys for a validator check."""
    return {slot.key for slot in slots}


def format_slot_rationale_brief(slots: list[KnockoutRationaleSlot]) -> str:
    """Describe the slot rationale contract for the forecast dossier."""
    if not slots:
        return (
            "Knockout rationale slots: no open knockout tie remains; submit an empty "
            "slot_rationales object and still write the travel memo."
        )
    stage = STAGE_LABELS.get(slots[0].stage, slots[0].stage)
    rows = ", ".join(f"{slot.key} {slot.home} v {slot.away} ({slot.date[:10]}, {slot.city})" for slot in slots)
    return (
        "Knockout rationale slots: write exactly one slot_rationales line for each "
        f"currently open {stage} slot, using these match ids as keys: {rows}. Do not "
        "write rationales for played slots or later rounds yet."
    )
