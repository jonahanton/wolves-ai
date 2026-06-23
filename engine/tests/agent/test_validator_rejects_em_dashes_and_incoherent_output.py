from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import build_narrative, build_submission
from tests.graph.conftest import build_run_store
from wolves.agent.ledger import EvidenceLedger
from wolves.agent.validator import ValidatorLimits, validate_submission
from wolves.graph.artifacts import RunArtifactStore


@pytest.fixture
def ledger(tmp_path: Path) -> EvidenceLedger:
    ledger = EvidenceLedger(tmp_path / "ledger.jsonl")
    ledger.append(
        claim="Keeper confirmed fit",
        source_url="https://www.thefa.com/news",
        status="confirmed",
        mechanism="keeper returns",
        team_id="england",
    )
    return ledger


@pytest.fixture
def store(tmp_path: Path) -> RunArtifactStore:
    store = build_run_store(tmp_path)
    store.add(
        kind="mixture",
        created_by="quant-1",
        summary="saka mixture",
        payload={
            "weights": {"plays": 0.6, "out": 0.4},
            "worlds": {
                "plays": {"perturbations": []},
                "out": {"perturbations": [{"team": "england", "delta": -0.1, "reason": "saka out"}]},
            },
            "mixture": {"england": 0.066, "spain": 0.187, "rest": 0.747},
        },
    )
    return store


def _codes(report) -> set[str]:
    return {issue.code for issue in report.issues}


def _validate(submission, store, ledger, **kwargs):
    return validate_submission(submission, artifacts=store, ledger=ledger, limits=ValidatorLimits(), **kwargs)


def test_em_dash_anywhere_rejects(store: RunArtifactStore, ledger: EvidenceLedger):
    headline = "England look sharp \u2014 and the camp is calm."
    submission = build_submission(narrative=build_narrative(headline=headline))
    assert "em_dash" in _codes(_validate(submission, store, ledger))


def test_american_spelling_rejects(store: RunArtifactStore, ledger: EvidenceLedger):
    headline = "England's favorable draw and organized defense set up a calm opener."
    submission = build_submission(narrative=build_narrative(headline=headline))
    assert "american_spelling" in _codes(_validate(submission, store, ledger))


def test_headline_percentage_must_match_published_preview(store: RunArtifactStore, ledger: EvidenceLedger):
    headline = "Spain sit at 16.8% after the latest group results."
    submission = build_submission(narrative=build_narrative(headline=headline))

    report = _validate(
        submission,
        store,
        ledger,
        published_titles={"spain": 0.171, "england": 0.078, "rest": 0.751},
    )

    assert "headline_probability_mismatch" in _codes(report)


def test_headline_rank_claim_must_match_published_preview(store: RunArtifactStore, ledger: EvidenceLedger):
    headline = "Spain lead the field, France are second and England are fourth."
    submission = build_submission(narrative=build_narrative(headline=headline))

    report = _validate(
        submission,
        store,
        ledger,
        published_titles={
            "spain": 0.17,
            "france": 0.103,
            "portugal": 0.096,
            "argentina": 0.094,
            "brazil": 0.083,
            "england": 0.082,
        },
    )

    assert "rank_claim_mismatch" in _codes(report)
    assert "england are fourth" in report.summary()
    assert "6th" in report.summary()


def test_correct_multi_team_rank_copy_does_not_cross_contaminate(store: RunArtifactStore, ledger: EvidenceLedger):
    headline = "Spain are first, France are second and England are sixth."
    submission = build_submission(narrative=build_narrative(headline=headline))

    report = _validate(
        submission,
        store,
        ledger,
        published_titles={
            "spain": 0.17,
            "france": 0.103,
            "portugal": 0.096,
            "argentina": 0.094,
            "brazil": 0.083,
            "england": 0.082,
        },
    )

    assert "rank_claim_mismatch" not in _codes(report)


def test_team_story_rank_claim_must_match_published_preview(store: RunArtifactStore, ledger: EvidenceLedger):
    submission = build_submission(
        narrative=build_narrative(
            team_stories={
                "england": {
                    "summary": "England sit fourth on our published numbers.",
                    "why": "The market is higher than the ratings.",
                }
            }
        )
    )

    report = _validate(
        submission,
        store,
        ledger,
        published_titles={
            "spain": 0.17,
            "france": 0.103,
            "portugal": 0.096,
            "argentina": 0.094,
            "brazil": 0.083,
            "england": 0.082,
        },
    )

    assert "rank_claim_mismatch" in _codes(report)


def test_first_choice_copy_is_not_a_rank_claim(store: RunArtifactStore, ledger: EvidenceLedger):
    submission = build_submission(
        narrative=build_narrative(
            team_stories={
                "england": {
                    "summary": "England's first-choice goalkeeper starts.",
                    "why": "Availability is settled, but the title number is unchanged.",
                }
            }
        )
    )

    report = _validate(
        submission,
        store,
        ledger,
        published_titles={"england": 0.082, "spain": 0.17},
    )

    assert "rank_claim_mismatch" not in _codes(report)


def test_story_count_uses_validator_limit(store: RunArtifactStore, ledger: EvidenceLedger):
    submission = build_submission(
        narrative=build_narrative(
            team_stories={
                "spain": {
                    "summary": "Spain remain first.",
                    "why": "The title number is clear at the top.",
                }
            }
        )
    )

    report = validate_submission(
        submission,
        artifacts=store,
        ledger=ledger,
        limits=ValidatorLimits(story_team_count=1),
        published_titles={"spain": 0.17, "england": 0.08},
    )

    assert "team_stories_missing" not in _codes(report)


def test_non_host_team_story_cannot_claim_home_advantage(store: RunArtifactStore, ledger: EvidenceLedger):
    submission = build_submission(
        narrative=build_narrative(
            team_stories={
                "france": {
                    "summary": "France get a home-continent lift.",
                    "why": "Local conditions should help their attack.",
                }
            }
        )
    )

    report = _validate(submission, store, ledger)

    assert "host_advantage_copy" in _codes(report)


def test_public_copy_cannot_assign_private_cause_to_market(store: RunArtifactStore, ledger: EvidenceLedger):
    submission = build_submission(
        narrative=build_narrative(
            headline="The market reflects France's squad depth more strongly than the ratings do."
        )
    )

    report = _validate(submission, store, ledger)

    assert "market_causal_copy" in _codes(report)


def test_multi_world_artifact_needs_matching_scenario_weights(store: RunArtifactStore, ledger: EvidenceLedger):
    missing = _validate(build_submission(), store, ledger)
    assert "scenario_weights_missing" in _codes(missing)

    wrong = build_submission(
        scenario_weights=[
            {"name": "plays", "weight": 0.7, "rationale": "Keeper plays after training in full."},
            {"name": "out", "weight": 0.3, "rationale": "Keeper absence still carries some squad risk."},
        ]
    )
    report = _validate(wrong, store, ledger)

    assert "scenario_weights_mismatch" in _codes(report)
    assert "wrong weight for out, plays" in report.summary()


def test_generic_camps_need_one_declaration_per_used_key(store: RunArtifactStore, ledger: EvidenceLedger):
    submission = build_submission(
        scenario_weights=[
            {
                "name": "plays",
                "weight": 0.6,
                "rationale": "Keeper plays after training in full.",
                "camp": "keeper-fit",
            },
            {
                "name": "out",
                "weight": 0.4,
                "rationale": "Keeper absence still carries some squad risk.",
                "camp": "keeper-out",
            },
        ],
        camps=[
            {
                "key": "keeper-fit",
                "label": "Keeper fit",
                "summary": "The first-choice goalkeeper starts.",
                "order": 0,
            }
        ],
    )
    report = _validate(submission, store, ledger)

    assert "camp_missing" in _codes(report)
    assert "keeper-out" in report.summary()


def test_matching_non_market_camps_pass_the_contract(store: RunArtifactStore, ledger: EvidenceLedger):
    submission = build_submission(
        scenario_weights=[
            {
                "name": "plays",
                "weight": 0.6,
                "rationale": "Keeper plays after training in full.",
                "camp": "keeper-fit",
            },
            {
                "name": "out",
                "weight": 0.4,
                "rationale": "Keeper absence still carries some squad risk.",
                "camp": "keeper-out",
            },
        ],
        camps=[
            {
                "key": "keeper-fit",
                "label": "Keeper fit",
                "summary": "The first-choice goalkeeper starts.",
                "order": 0,
            },
            {
                "key": "keeper-out",
                "label": "Keeper out",
                "summary": "The defence plays without its first-choice goalkeeper.",
                "order": 1,
            },
        ],
    )
    report = _validate(submission, store, ledger)

    assert not {"scenario_weights_missing", "scenario_weights_mismatch", "camp_missing"} & _codes(report)


def _workbench_payload(factor_audit: dict | None = None) -> dict:
    payload = {
        "weights": {"model_base": 0.7, "france_gap": 0.3},
        "worlds": {
            "model_base": {"perturbations": []},
            "france_gap": {"perturbations": [{"team": "france", "delta": 0.08, "reason": "market gap"}]},
        },
        "mixture": {"france": 0.15, "england": 0.08, "rest": 0.77},
        "conditionals": {"model_base": {"france": 0.1}, "france_gap": {"france": 0.2}},
        "noise_floor_pp": 0.3,
    }
    if factor_audit is not None:
        payload["factor_audit"] = factor_audit
    return payload


def _factor_submission(**overrides):
    fields = {
        "artifact_id": "mixture-002",
        "scenario_weights": [
            {"name": "model_base", "weight": 0.7, "rationale": "Model base remains live."},
            {"name": "france_gap", "weight": 0.3, "rationale": "France market gap remains live."},
        ],
    }
    fields.update(overrides)
    return build_submission(**fields)


def test_workbench_mixture_needs_factor_audit_for_large_non_base_world(store: RunArtifactStore, ledger: EvidenceLedger):
    store.add(kind="mixture", created_by="quant-1", summary="audited", payload=_workbench_payload())

    report = _validate(_factor_submission(), store, ledger)

    assert "factor_audit_missing" in _codes(report)


def test_factor_audit_can_record_checked_negative_coverage(store: RunArtifactStore, ledger: EvidenceLedger):
    audit = {
        "verdict": "France gap is live but bounded by current market and path checks.",
        "checks": [
            {"key": "bases", "status": "checked", "summary": "Both bases rebuilt."},
            {"key": "previous_continuity", "status": "checked", "summary": "Prior France world audited."},
            {"key": "market_gap", "status": "checked", "summary": "France gap cleared the floor.", "teams": ["france"]},
            {"key": "ledger_pricing", "status": "not_material", "summary": "No material fresh ledger item."},
            {"key": "mixture_spread", "status": "checked", "summary": "Spread sits above the floor."},
        ],
    }
    store.add(kind="mixture", created_by="quant-1", summary="audited", payload=_workbench_payload(audit))

    report = _validate(_factor_submission(), store, ledger)

    assert not {code for code in _codes(report) if code.startswith("factor_audit")}


def test_market_gap_audit_names_submitted_gap_teams(store: RunArtifactStore, ledger: EvidenceLedger):
    audit = {
        "verdict": "France gap checked but England omitted.",
        "checks": [
            {"key": "bases", "status": "checked", "summary": "Both bases rebuilt."},
            {"key": "previous_continuity", "status": "checked", "summary": "Prior worlds audited."},
            {"key": "market_gap", "status": "checked", "summary": "France gap cleared the floor.", "teams": ["france"]},
            {"key": "ledger_pricing", "status": "not_material", "summary": "No material fresh ledger item."},
            {"key": "mixture_spread", "status": "checked", "summary": "Spread sits above the floor."},
        ],
    }
    store.add(kind="mixture", created_by="quant-1", summary="audited", payload=_workbench_payload(audit))
    submission = _factor_submission(
        market_justification="quant-1 audited france and england market gaps.",
        market_gaps=[
            {"team_id": "france", "model_prob": 0.08, "market_prob": 0.16, "gap_pp": 8.0},
            {"team_id": "england", "model_prob": 0.07, "market_prob": 0.10, "gap_pp": 3.0},
        ],
    )

    report = _validate(submission, store, ledger)

    assert "market_audit_missing_team" in _codes(report)
    assert "england" in report.summary()


def test_market_gap_pp_is_corrected_in_place_not_rejected(store: RunArtifactStore, ledger: EvidenceLedger):
    submission = build_submission(
        market_gaps=[
            {"team_id": "france", "model_prob": 0.08, "market_prob": 0.16, "gap_pp": 3.0},
        ],
    )

    report = _validate(submission, store, ledger)

    assert "market_gap_malformed" not in _codes(report)
    assert submission.market_gaps[0].gap_pp == 8.0


def test_market_gap_probs_must_match_model_forecast_and_market_anchors(store: RunArtifactStore, ledger: EvidenceLedger):
    submission = build_submission(
        market_gaps=[
            {
                "team_id": "france",
                "model_prob": 0.07,
                "market_prob": 0.14,
                "forecast_prob": 0.09,
                "gap_pp": 7.0,
            },
        ],
    )

    report = _validate(
        submission,
        store,
        ledger,
        published_titles={"france": 0.10, "england": 0.08, "rest": 0.82},
        baseline_titles={"france": 0.08},
        market_titles={"france": 0.16},
    )

    assert "market_gap_malformed" in _codes(report)


def test_scenario_rationale_cannot_describe_a_world_against_its_strength_delta(
    store: RunArtifactStore, ledger: EvidenceLedger
):
    store.add(
        kind="mixture",
        created_by="quant-2",
        summary="brazil downside",
        payload={
            "weights": {"model_base": 0.8, "brazil_net": 0.2},
            "worlds": {
                "model_base": {"perturbations": []},
                "brazil_net": {
                    "perturbations": [{"type": "strength", "team": "brazil", "delta": -0.06, "reason": "availability"}]
                },
            },
            "baseline": {"brazil": 0.07, "rest": 0.93},
            "mixture": {"brazil": 0.06, "rest": 0.94},
        },
    )
    submission = build_submission(
        artifact_id="mixture-002",
        scenario_weights=[
            {"name": "model_base", "weight": 0.8, "rationale": "Model base."},
            {"name": "brazil_net", "weight": 0.2, "rationale": "Brazil get a clear boost from this upside case."},
        ],
    )

    assert "world_direction_contradiction" in _codes(_validate(submission, store, ledger))


def test_scenario_rationale_matching_its_strength_delta_passes(store: RunArtifactStore, ledger: EvidenceLedger):
    store.add(
        kind="mixture",
        created_by="quant-2",
        summary="brazil downside",
        payload={
            "weights": {"model_base": 0.8, "brazil_net": 0.2},
            "worlds": {
                "model_base": {"perturbations": []},
                "brazil_net": {
                    "perturbations": [{"type": "strength", "team": "brazil", "delta": -0.06, "reason": "availability"}]
                },
            },
            "baseline": {"brazil": 0.07, "rest": 0.93},
            "mixture": {"brazil": 0.06, "rest": 0.94},
        },
    )
    submission = build_submission(
        artifact_id="mixture-002",
        scenario_weights=[
            {"name": "model_base", "weight": 0.8, "rationale": "Model base."},
            {"name": "brazil_net", "weight": 0.2, "rationale": "The downside availability case drags Brazil down."},
        ],
    )

    assert "world_direction_contradiction" not in _codes(_validate(submission, store, ledger))


def test_blank_news_impact_does_not_satisfy_material_item(store: RunArtifactStore, ledger: EvidenceLedger):
    store.add(
        kind="quant",
        created_by="quant-1",
        summary="priced keeper",
        payload={
            "priced_items": [
                {
                    "ledger_id": "led-0001",
                    "signed_delta_pp": 0.8,
                    "material": True,
                    "excluded_reason": None,
                    "noise_floor_pp": 0.3,
                }
            ]
        },
    )
    submission = build_submission(news_impacts={"led-0001": ""})

    report = _validate(submission, store, ledger)

    assert "news_impact_missing" in _codes(report)


def test_superseded_immaterial_price_does_not_need_news_impact(store: RunArtifactStore, ledger: EvidenceLedger):
    store.add(
        kind="quant",
        created_by="quant-1",
        summary="priced keeper",
        payload={
            "priced_items": [
                {
                    "ledger_id": "led-0001",
                    "signed_delta_pp": 0.8,
                    "material": True,
                    "excluded_reason": None,
                    "noise_floor_pp": 0.3,
                }
            ]
        },
    )
    store.add(
        kind="quant",
        created_by="quant-2",
        summary="rechecked keeper",
        payload={
            "priced_items": [
                {
                    "ledger_id": "led-0001",
                    "signed_delta_pp": 0.1,
                    "material": False,
                    "excluded_reason": "below_floor",
                    "noise_floor_pp": 0.3,
                }
            ]
        },
    )

    report = _validate(build_submission(news_impacts={}), store, ledger)

    assert "news_impact_missing" not in _codes(report)


def test_market_stance_needs_market_gap_audit_row(store: RunArtifactStore, ledger: EvidenceLedger):
    audit = {
        "verdict": "Audited except market gap.",
        "checks": [{"key": "bases", "status": "checked", "summary": "Both bases rebuilt."}],
    }
    store.add(kind="mixture", created_by="quant-1", summary="audited", payload=_workbench_payload(audit))

    report = _validate(_factor_submission(market_justification="france gap priced by quant-1"), store, ledger)

    assert "market_audit_missing" in _codes(report)


def test_factor_audit_must_include_critical_rows(store: RunArtifactStore, ledger: EvidenceLedger):
    audit = {
        "verdict": "Only spread was checked.",
        "checks": [{"key": "mixture_spread", "status": "checked", "summary": "Spread checked."}],
    }
    store.add(kind="mixture", created_by="quant-1", summary="audited", payload=_workbench_payload(audit))

    report = _validate(_factor_submission(), store, ledger, previous_titles={"france": 0.12})

    assert "factor_audit_missing_coverage" in _codes(report)


def test_factor_audit_does_not_require_previous_continuity_without_previous_titles(
    store: RunArtifactStore, ledger: EvidenceLedger
):
    audit = {
        "verdict": "Fresh run with no previous continuity context.",
        "checks": [
            {"key": "bases", "status": "checked", "summary": "Both bases rebuilt."},
            {"key": "market_gap", "status": "checked", "summary": "France gap cleared the floor.", "teams": ["france"]},
            {"key": "ledger_pricing", "status": "not_material", "summary": "No material fresh ledger item."},
            {"key": "mixture_spread", "status": "checked", "summary": "Spread sits above the floor."},
        ],
    }
    store.add(kind="mixture", created_by="quant-1", summary="audited", payload=_workbench_payload(audit))

    report = _validate(_factor_submission(), store, ledger, previous_titles=None)

    assert "factor_audit_missing_coverage" not in _codes(report)


def test_factor_audit_gate_uses_total_non_base_mass(store: RunArtifactStore, ledger: EvidenceLedger):
    weights = {"model_base": 0.4, **{f"story_{i}": 0.075 for i in range(8)}}
    payload = {
        "weights": weights,
        "worlds": {name: {"perturbations": []} for name in weights},
        "mixture": {"france": 0.15, "england": 0.08, "rest": 0.77},
        "conditionals": {name: {"france": 0.15} for name in weights},
        "noise_floor_pp": 0.3,
    }
    store.add(kind="mixture", created_by="quant-1", summary="fragmented", payload=payload)
    submission = build_submission(
        artifact_id="mixture-002",
        scenario_weights=[
            {"name": name, "weight": weight, "rationale": f"{name} remains live."} for name, weight in weights.items()
        ],
    )

    report = _validate(submission, store, ledger)

    assert "factor_audit_missing" in _codes(report)


def test_factor_audit_rejects_invalid_status_and_empty_summary(store: RunArtifactStore, ledger: EvidenceLedger):
    audit = {
        "verdict": "Malformed.",
        "checks": [
            {"key": "bases", "status": "checked", "summary": "Both bases rebuilt."},
            {"key": "previous_continuity", "status": "guessed", "summary": "Prior worlds copied."},
            {"key": "market_gap", "status": "checked", "summary": "France gap checked."},
            {"key": "ledger_pricing", "status": "not_material", "summary": ""},
            {"key": "mixture_spread", "status": "checked", "summary": "Spread checked."},
        ],
    }
    store.add(kind="mixture", created_by="quant-1", summary="audited", payload=_workbench_payload(audit))

    report = _validate(_factor_submission(), store, ledger)

    assert "factor_audit_malformed" in _codes(report)


def test_typed_probabilities_never_publish(store: RunArtifactStore, ledger: EvidenceLedger):
    submission = build_submission(artifact_id="mixture-999")
    report = _validate(submission, store, ledger)
    assert "unknown_artifact" in _codes(report)
    assert "never typed probabilities" in report.summary()


def test_pinned_scoreline_worlds_never_publish(store: RunArtifactStore, ledger: EvidenceLedger):
    store.add(
        kind="mixture",
        created_by="quant-1",
        summary="what if",
        payload={
            "weights": {"pinned": 1.0},
            "worlds": {
                "pinned": {"perturbations": [{"match": 22, "home_goals": 2, "away_goals": 0, "reason": "what if"}]}
            },
            "mixture": {"england": 0.08},
        },
    )
    submission = build_submission(artifact_id="mixture-002")
    assert "artifact_unpublishable" in _codes(_validate(submission, store, ledger))


def test_mixture_without_world_configs_never_publishes(store: RunArtifactStore, ledger: EvidenceLedger):
    store.add(
        kind="mixture",
        created_by="quant-1",
        summary="typed only",
        payload={
            "weights": {"model": 1.0},
            "mixture": {"england": 0.08},
            "conditionals": {"model": {"england": 0.08}},
        },
    )

    report = _validate(build_submission(artifact_id="mixture-002"), store, ledger)

    assert "artifact_unpublishable" in _codes(report)


def test_incoherent_mixture_rejects(store: RunArtifactStore, ledger: EvidenceLedger):
    store.add(
        kind="mixture",
        created_by="quant-1",
        summary="broken",
        payload={
            "weights": {"model": 1.0},
            "worlds": {"model": {"perturbations": []}},
            "mixture": {"england": 0.4, "spain": 0.2},
        },
    )
    submission = build_submission(artifact_id="mixture-002")
    assert "partition_incoherent" in _codes(_validate(submission, store, ledger))


def test_rumour_cited_weight_rejects(store: RunArtifactStore, ledger: EvidenceLedger):
    ledger.append(
        claim="dressing room unrest",
        source_url="https://www.goal.com/x",
        status="rumour",
        mechanism="morale",
    )
    submission = build_submission(scenario_weights=[{"name": "unrest", "weight": 1.0, "ledger_ids": ["led-0002"]}])
    assert "rumour_cited" in _codes(_validate(submission, store, ledger))


def test_missing_headline_rejects(store: RunArtifactStore, ledger: EvidenceLedger):
    submission = build_submission(narrative=build_narrative(headline=""))
    assert "headline_missing" in _codes(_validate(submission, store, ledger))


def test_jargon_in_the_headline_flags_as_copy(store: RunArtifactStore, ledger: EvidenceLedger):
    headline = "The artifact mixture-002 uses perturbation objects after validator retries."
    submission = build_submission(narrative=build_narrative(headline=headline))
    report = _validate(submission, store, ledger)
    jargon = [i for i in report.issues if i.code == "headline_jargon"]
    assert jargon and all(i.severity == "copy" for i in jargon)


def test_technical_market_language_is_allowed_in_copy(store: RunArtifactStore, ledger: EvidenceLedger):
    headline = "The de-vigged market posterior moves England by 3pp on log odds."
    submission = build_submission(narrative=build_narrative(headline=headline))
    report = _validate(submission, store, ledger)

    assert "headline_jargon" not in _codes(report)


def test_technical_team_story_language_is_allowed(store: RunArtifactStore, ledger: EvidenceLedger):
    narrative = build_narrative(
        team_stories={
            "england": {
                "summary": "England are lifted by a market disagreement.",
                "why": (
                    "The story is technical: a partial perturbation towards the de-vigged market leaves England "
                    "above the fitted model, while the bracket still caps the upside."
                ),
            },
            "spain": {"summary": "Spain stay first.", "why": "Their title chance is stable."},
            "rest": {"summary": "The rest share the tail.", "why": "No single side dominates it."},
        }
    )
    submission = build_submission(narrative=narrative)

    report = _validate(submission, store, ledger)

    assert "team_story_jargon" not in _codes(report)


def test_team_story_internal_ids_still_flag_as_copy(store: RunArtifactStore, ledger: EvidenceLedger):
    narrative = build_narrative(
        team_stories={
            "england": {
                "summary": "England are lifted by mixture-002.",
                "why": "The validator accepted led-0001 after check_forecast.",
            },
            "spain": {"summary": "Spain stay first.", "why": "Their title chance is stable."},
            "rest": {"summary": "The rest share the tail.", "why": "No single side dominates it."},
        }
    )
    submission = build_submission(narrative=narrative)

    report = _validate(submission, store, ledger)

    assert "team_story_jargon" in _codes(report)


def test_team_story_internal_worker_labels_flag_as_copy(store: RunArtifactStore, ledger: EvidenceLedger):
    narrative = build_narrative(
        team_stories={
            "england": {
                "summary": "England are lifted by market disagreement.",
                "why": "The quant confirmed the market gap and moved England up.",
            },
            "spain": {"summary": "Spain stay first.", "why": "Their title chance is stable."},
            "rest": {"summary": "The rest share the tail.", "why": "No single side dominates it."},
        }
    )
    submission = build_submission(narrative=narrative)

    report = _validate(submission, store, ledger)

    assert "team_story_jargon" in _codes(report)


def test_team_story_counts_visible_camps_not_raw_worlds(store: RunArtifactStore, ledger: EvidenceLedger):
    narrative = build_narrative(
        team_stories={
            "england": {
                "summary": "England are lifted by the same visible stance.",
                "why": "England appear across all two worlds with consistent probabilities.",
            },
            "spain": {"summary": "Spain stay first.", "why": "Their title chance is stable."},
            "rest": {"summary": "The rest share the tail.", "why": "No single side dominates it."},
        }
    )
    submission = build_submission(
        narrative=narrative,
        scenario_weights=[
            {"name": "plays", "weight": 0.6, "camp": "single", "label": "Plays", "summary": "Saka plays."},
            {"name": "out", "weight": 0.4, "camp": "single", "label": "Out", "summary": "Saka is out."},
        ],
        camps=[{"key": "single", "label": "Single camp", "summary": "One visible bucket.", "order": 1}],
    )

    report = _validate(submission, store, ledger)

    assert "team_story_bucket_count_mismatch" in _codes(report)


def test_rambling_headline_flags_as_copy(store: RunArtifactStore, ledger: EvidenceLedger):
    headline = (
        "Spain lead but the market keeps France close after a fresh audit of their squad value and recent results. "
        "England are still in the chasing pack with Saka fit and their opening path intact. "
        "Portugal, Argentina, Brazil, Germany and the Netherlands all remain live enough to matter, but none of them "
        "has a single new public fact that moves the board on its own. "
        "The forecast gives partial credit to market disagreement without turning that disagreement into certainty. "
        "That means the top of the board is wider than a quiet model-only day while still leaving Spain first. "
        "The remaining contenders mostly move through bracket interaction rather than direct news. "
        "This copy is intentionally too long for the compact lede target."
    )
    submission = build_submission(narrative=build_narrative(headline=headline))
    report = _validate(submission, store, ledger)
    too_long = [i for i in report.issues if i.code == "headline_too_long"]
    assert too_long and all(i.severity == "copy" for i in too_long)


def test_team_story_summary_numbers_match_published_titles(store: RunArtifactStore, ledger: EvidenceLedger):
    narrative = build_narrative(
        team_stories={
            "england": {
                "summary": "England sit at 9.3% before facing Croatia.",
                "why": "Their opener is still pending.",
            },
            "spain": {
                "summary": "Spain lead at 17.1%.",
                "why": "Their title chance is stable.",
            },
            "rest": {
                "summary": "The rest share the remaining chance.",
                "why": "No single side dominates the tail.",
            },
        }
    )
    submission = build_submission(
        narrative=narrative,
        scenario_weights=[
            {"name": "plays", "weight": 0.6, "rationale": "Keeper plays after training in full."},
            {"name": "out", "weight": 0.4, "rationale": "Keeper absence still carries some squad risk."},
        ],
    )

    report = _validate(
        submission,
        store,
        ledger,
        published_titles={"england": 0.0784, "spain": 0.171, "rest": 0.7506},
    )

    mismatch = [i for i in report.issues if i.code == "team_story_probability_mismatch"]
    assert mismatch and all(i.severity == "copy" for i in mismatch)
    assert "england" in mismatch[0].message


@pytest.mark.parametrize(
    "headline",
    [
        "Spain are still favourites at about one in six. England's chances edge up with Saka back in training.",
        (
            "Spain remain the team to beat after another controlled win. England's chances edge up with Saka "
            "back in full training and no fresh injuries in camp. France drift slightly as Mbappe sits out "
            "again. The bookmakers broadly agree with this picture. Nothing else in today's news moves the "
            "big contenders."
        ),
        (
            "Spain remain the team to beat. England's chances edge up with Saka back. France drift as Mbappe "
            "sits out. Portugal hold their ground. The bookmakers broadly agree. Nothing else moves the big "
            "contenders today."
        ),
    ],
    ids=["two-sentences", "five-sentences-within-budget", "six-sentences-within-grace"],
)
def test_headline_within_the_softened_budget_passes(store: RunArtifactStore, ledger: EvidenceLedger, headline: str):
    submission = build_submission(narrative=build_narrative(headline=headline))
    assert not {code for code in _codes(_validate(submission, store, ledger)) if code.startswith("headline")}
