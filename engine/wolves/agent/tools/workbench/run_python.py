from __future__ import annotations

import ast
import json
from typing import Any

from pydantic import BaseModel

from wolves.agent.audit_policy import advisory_missing_rows, branch_audit_contradictions, intrinsic_missing_rows
from wolves.agent.deps import AgentDeps
from wolves.quant.context import build_sandbox_context
from wolves.quant.inputs import prepare_inputs
from wolves.toolkit.core import ToolSpec
from wolves.toolkit.result import ToolError, ToolResult

_RESULT_CAP_CHARS = 8_000
_STDOUT_CAP_CHARS = 2_000


class RunPythonArgs(BaseModel):
    code: str


def _called_helpers(code: str) -> set[str]:
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return set()
    return {
        name
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and (name := node.func.attr if isinstance(node.func, ast.Attribute) else getattr(node.func, "id", None))
    }


def _python_budget_refusal(deps: AgentDeps) -> ToolResult[Any] | None:
    limit = deps.settings.graph_quant_python_call_limit
    if limit <= 0 or deps.python_calls < limit:
        return None
    return ToolResult(
        ok=False,
        payload={"limit": limit, "used": deps.python_calls},
        error=ToolError(
            type="python_budget_exhausted",
            message=(
                f"run_python limit reached after {deps.python_calls} script(s). "
                "Synthesise a quant output from the completed scripts and direct tools."
            ),
        ),
    )


async def _run_python(args: RunPythonArgs, deps: AgentDeps) -> ToolResult[Any]:
    if refusal := _python_budget_refusal(deps):
        return refusal
    workspace = deps.quant.workspace(deps.actor)
    context = build_sandbox_context(deps)
    helpers = _called_helpers(args.code)
    capability = next(
        (
            capability
            for capability, helper in (("market_history", "market_movement"), ("market_gaps", "market_gaps"))
            if capability in deps.unavailable_capabilities and helper in helpers
        ),
        None,
    )
    if capability is not None:
        alternative = "Use current-only market_gaps instead." if capability == "market_history" else ""
        return ToolResult(
            ok=False,
            payload={"capability": capability, "available": False},
            error=ToolError(
                type="capability_unavailable",
                message=f"{capability.replace('_', ' ').title()} is unavailable. {alternative}".strip(),
            ),
        )
    deps.python_calls += 1
    deps.quant.write_context(workspace, context)
    prepare_inputs(workspace, context)
    script = workspace.next_analysis_name()
    deps.quant.write_analysis(actor=deps.actor, workspace=workspace, code=args.code, filename=script)
    result = await deps.quant.execute(actor=deps.actor, workspace=workspace, script=script)
    clean_missing_result = result.no_result and result.exit_code == 0 and not result.timed_out
    registered, audit_warnings = (
        _register_mixtures(
            deps,
            workspace_dir=workspace.dir.name,
            files=[o.filename for o in result.output_files],
        )
        if result.ok or clean_missing_result
        else ([], [])
    )
    result_text = json.dumps(result.result_value, ensure_ascii=False, default=str)
    return ToolResult(
        ok=result.ok,
        payload={
            "result": result.result_value if len(result_text) <= _RESULT_CAP_CHARS else result_text[:_RESULT_CAP_CHARS],
            "stdout": result.stdout[:_STDOUT_CAP_CHARS],
            "stderr": result.stderr[-_STDOUT_CAP_CHARS:],
            "script": script,
            "exit_code": result.exit_code,
            "timed_out": result.timed_out,
            "usage": result.usage,
            "output_files": [o.filename for o in result.output_files],
            "registered_artifact_ids": registered,
            **(
                {"recovery_hint": "valid mixture outputs were registered despite the missing result"}
                if registered
                else {}
            ),
            **({"audit_warnings": audit_warnings} if audit_warnings else {}),
            **({"error": result.error} if result.error else {}),
        },
    )


def _register_mixtures(deps: AgentDeps, *, workspace_dir: str, files: list[str]) -> tuple[list[str], list[str]]:
    """Mixture artifacts computed in the sandbox become run artifacts the
    forecast node can cite and submit by reference. A large-non-base mixture
    missing factor_audit coverage is still registered, but the gap is surfaced
    here so the quant node authors the row now, not at the unrecoverable submit."""
    store = deps.artifacts
    if store is None:
        return [], []
    artifact_ids: list[str] = []
    warnings: list[str] = []
    registered = {r.summary.split(":", 1)[0]: r.id for r in store.all() if r.kind == "mixture"}
    for filename in files:
        if not filename.endswith(".json"):
            continue
        marker = f"{workspace_dir}/{filename}"
        workspace = deps.quant.workspace(deps.actor)
        try:
            payload = json.loads((workspace.outputs / filename).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        # Mixture artifacts are recognised by shape, not filename, so any
        # scenario_mixture(name=...) output registers.
        if not (isinstance(payload, dict) and {"mixture", "conditionals", "weights", "worlds"} <= payload.keys()):
            continue
        contradictions = branch_audit_contradictions(payload)
        if contradictions:
            warnings.append(f"{marker} was not registered: " + "; ".join(contradictions))
            continue
        if marker in registered:
            artifact = store.get(registered[marker])
            if artifact is not None and artifact.payload != payload:
                store.amend_payload(artifact.id, payload)
                artifact_ids.append(artifact.id)
                warnings.extend(_audit_gap_warning(payload, marker))
            continue
        artifact = store.add(
            kind="mixture",
            created_by=deps.actor,
            summary=f"{marker}: {_describe_mixture(payload)}",
            payload=payload,
            workspace_prefix=f"runs/{store.run_id}/workspace/quant/{workspace_dir}",
        )
        artifact_ids.append(artifact.id)
        warnings.extend(_audit_gap_warning(payload, marker))
    return artifact_ids, warnings


def _audit_gap_warning(payload: dict, marker: str) -> list[str]:
    missing = intrinsic_missing_rows(payload) + advisory_missing_rows(payload)
    if not missing:
        return []
    return [
        f"{marker} is a large non-base mixture missing factor_audit rows: {', '.join(missing)}. "
        "Add them with wq.factor_audit now (a mixture_spread row from wq.mixture_spread; a market_gap row "
        "naming the teams it checks, or status not_material if the published probs sit on-market) and "
        "re-register; the submit validator rejects this artifact otherwise and only a quant node can repair it."
    ]


def _describe_mixture(payload: dict) -> str:
    worlds = payload.get("worlds") or {}
    mixture = payload.get("mixture") or {}
    details = f"{len(worlds)} world(s)"
    if mixture:
        top = max(mixture, key=mixture.get)
        details += f", top {top} {mixture[top] * 100:.1f}%"
    floor = payload.get("noise_floor_pp")
    if floor is not None:
        details += f", floor {floor}pp"
    return details


SPEC = ToolSpec(
    name="run_python",
    description=(
        "Run Python in your persistent analysis workspace (no network; numbered scripts share one "
        "directory per node, so earlier variables are gone but files under inputs/ and outputs/ "
        "persist between calls). Preloaded names: wq (the workbench: wq.query/load_* over the "
        "research data, wq.simulate/baseline/impact with common random numbers, wq.match_probs "
        "(pass match=<id> to bind match-keyed perturbations), wq.scenario_mixture for factor "
        "lattices, wq.posterior_draws, wq.teams/fixtures/artifacts to orient, "
        "wq.reach for per-round probabilities, wq.model_explain/path_tree/market_gaps/market_movement "
        "for the model's own diagnostics, wq.artifact/artifact_path to open prior nodes' work), "
        "pd (pandas) and np (numpy); scipy, statsmodels, sklearn, emcee, polars, duckdb and "
        "matplotlib are importable. "
        "Exact common shapes: wq.teams() columns are team, name, group, strength; wq.fixtures() "
        "columns are match, stage, group, date, city, home, away; wq.market_gaps() columns are "
        "team, model_p_title, market_p_title, polymarket_p_title, blend_p_title, gap_pp, "
        "polymarket_gap_pp, legs_disagree_pp; wq.mixture_spread(...) returns a dict whose teams "
        "value is a DataFrame indexed by team and also carrying a team column; "
        "wq.title_uncertainty() and wq.path_difficulty() also return DataFrames indexed by team and "
        "also carrying a team column. Build mixtures with "
        "wq.Scenario(...) or dicts and wq.scenario_mixture(..., name='...'); there is no wq.scenario "
        "helper, no label= argument, and scenario_mixture returns mixture/conditionals/worlds/weights, "
        "not a teams table. wq.update_from_result(...) returns a dict with posterior_mean_delta, "
        "posterior_sd and prior_sd, not a scalar. "
        "For submit-ready mixtures, build a factor audit with wq.factor_audit(checks=[...], verdict=...) "
        "and pass factor_audit=audit to wq.scenario_mixture; checked negative findings are valid, "
        "missing marks work the forecast should not publish without. Optional branch audits use "
        "wq.branch_audit(checks=[{key,status,hypothesis,summary,teams,ledger_ids,artifacts,world_names,"
        "parent_branch_ids}], "
        "verdict=...) and pass branch_audit=... plus world_metadata={world:{label,summary,camp,branch_keys}} "
        "to wq.scenario_mixture when research branches were priced, collapsed or rejected. "
        "End every script by assigning the finding to `result` "
        "(JSON-safe; a bare expression or print() does not count). Deltas from wq.impact carry a "
        "paired-seed noise floor; pass include_teams=[...] when you need a named team even if it is "
        "not a top mover. Treat anything below the floor as simulation noise. This tool is capped "
        "per node, including failed scripts, so compute in compact scripts and publish from the "
        "material already gathered once the cap is near. If a script writes a valid mixture JSON "
        "under outputs/, registered_artifact_ids returns the artifact ids to cite or submit."
    ),
    args_model=RunPythonArgs,
    fn=_run_python,
)
