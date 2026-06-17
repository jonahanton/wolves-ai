"""Detect weight-dilution in an elicited mixture.

Bayesian model averaging dilutes when near-duplicate hypotheses split a vote:
two optimistic worlds that say the same thing out-weight a single pessimistic
world purely by being two. We detect the split and nudge a merge rather than
silently reweighting, because the agent is scored on the numbers it chose and a
silent rewrite would break that adjustment-P&L story.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass


@dataclass(frozen=True)
class DilutedGroup:
    names: list[str]
    combined_weight: float
    signature: frozenset[tuple[str, str, int]]


def world_signature(perturbations: list[dict]) -> frozenset[tuple[str, str, int]]:
    """A world's directional fingerprint: (kind, target, sign) per perturbation.

    Two worlds share a signature when they perturb the same targets the same
    way, so they are near-duplicates even if their magnitudes differ slightly."""
    marks: set[tuple[str, str, int]] = set()
    for pert in perturbations:
        kind = str(pert.get("type") or pert.get("kind") or _infer_kind(pert))
        target = str(pert.get("team") or pert.get("match") or "")
        marks.add((kind, target, _sign(pert)))
    return frozenset(marks)


def near_duplicate_groups(worlds: dict[str, tuple[float, list[dict]]]) -> list[list[str]]:
    """Group active (non-empty, non-base) worlds that share a directional signature."""
    by_signature = _worlds_by_signature(worlds)
    return [names for names in by_signature.values() if len(names) > 1]


def diluted_groups(
    worlds: dict[str, tuple[float, list[dict]]], *, min_combined_weight: float
) -> list[tuple[list[str], float]]:
    """Near-duplicate groups whose split weight is material enough to bias the mix."""
    return [(group.names, group.combined_weight) for group in diluted_group_details(worlds, min_combined_weight)]


def diluted_group_details(
    worlds: dict[str, tuple[float, list[dict]]], min_combined_weight: float
) -> list[DilutedGroup]:
    """Near-duplicate groups with the shared directional footprint."""
    details: list[DilutedGroup] = []
    by_signature = _worlds_by_signature(worlds)
    for signature, names in by_signature.items():
        if len(names) < 2:
            continue
        combined = sum(worlds[name][0] for name in names)
        if combined >= min_combined_weight:
            details.append(DilutedGroup(names=sorted(names), combined_weight=round(combined, 4), signature=signature))
    return details


def describe_signature(signature: frozenset[tuple[str, str, int]]) -> str:
    """Plain directional description for validator feedback."""
    if not signature:
        return "no perturbations"
    parts = []
    for kind, target, sign in sorted(signature, key=lambda item: (item[0], item[1], item[2])):
        direction = "up" if sign > 0 else "down" if sign < 0 else "changed"
        parts.append(f"{kind}:{target} {direction}")
    return ", ".join(parts)


def _sign(pert: dict) -> int:
    delta = pert.get("delta")
    if isinstance(delta, dict):
        delta = delta.get("mean", 0.0)
    if isinstance(delta, int | float):
        return (delta > 0) - (delta < 0)
    # Outcome/rate perturbations carry no single signed magnitude; the
    # direction is the perturbation's mere presence on its target.
    return 0


def _infer_kind(pert: dict) -> str:
    if "p_home" in pert:
        return "outcome"
    if "home_goals_delta" in pert or "away_goals_delta" in pert:
        return "rate"
    if "delta" in pert:
        return "strength"
    return "unknown"


def _worlds_by_signature(
    worlds: dict[str, tuple[float, list[dict]]]
) -> dict[frozenset[tuple[str, str, int]], list[str]]:
    by_signature: dict[frozenset[tuple[str, str, int]], list[str]] = defaultdict(list)
    for name, (_, perturbations) in worlds.items():
        if not perturbations:
            continue
        by_signature[world_signature(perturbations)].append(name)
    return by_signature
