"""Detect weight-dilution in an elicited mixture.

Bayesian model averaging dilutes when near-duplicate hypotheses split a vote:
two optimistic worlds that say the same thing out-weight a single pessimistic
world purely by being two. We detect the split and nudge a merge rather than
silently reweighting, because the agent is scored on the numbers it chose and a
silent rewrite would break that adjustment-P&L story.
"""

from __future__ import annotations

from collections import defaultdict


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
    by_signature: dict[frozenset[tuple[str, str, int]], list[str]] = defaultdict(list)
    for name, (_, perturbations) in worlds.items():
        if not perturbations:
            continue
        by_signature[world_signature(perturbations)].append(name)
    return [names for names in by_signature.values() if len(names) > 1]


def diluted_groups(
    worlds: dict[str, tuple[float, list[dict]]], *, min_combined_weight: float
) -> list[tuple[list[str], float]]:
    """Near-duplicate groups whose split weight is material enough to bias the mix."""
    out: list[tuple[list[str], float]] = []
    for names in near_duplicate_groups(worlds):
        combined = sum(worlds[name][0] for name in names)
        if combined >= min_combined_weight:
            out.append((sorted(names), round(combined, 4)))
    return out


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
