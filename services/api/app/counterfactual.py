from __future__ import annotations

from dataclasses import replace

from .domain import (
    AgentProposal,
    CounterfactualRequirement,
    CustomerCase,
    DecisionCounterfactual,
    DecisionMode,
    PermissionDecision,
    ReliabilityEvidence,
    ResolutionEvidence,
)
from .policy import DeterministicPolicyEngine
from .reliability import HistoricalStats, ReliabilityEngine


AUTO_RELIABILITY = 0.98
AUTO_VERIFIED_CASES = 100


def explain_auto_counterfactual(
    case: CustomerCase,
    proposal: AgentProposal,
    evidence: ReliabilityEvidence,
    resolution: ResolutionEvidence | None,
    permission: PermissionDecision,
) -> DecisionCounterfactual:
    """Return the smallest inspectable input changes that can produce AUTO.

    The explanation is not heuristic prose. Suggested changes are applied to copies of the
    typed policy inputs and evaluated again by the same deterministic policy engine. Hard
    boundaries are reported as non-negotiable instead of suggesting that more history can
    override them.
    """

    if permission.mode == DecisionMode.AUTO:
        return DecisionCounterfactual(
            target_mode=DecisionMode.AUTO,
            attainable=True,
            validated_by_policy=True,
            resulting_mode=DecisionMode.AUTO,
            requirements=(),
            hard_boundaries=(),
            summary="The case already satisfies every current-evidence and earned-autonomy rule.",
        )

    hard_boundaries = _hard_boundaries(case, proposal, resolution)
    requirements: list[CounterfactualRequirement] = []
    candidate_evidence = evidence
    candidate_resolution = resolution

    if resolution is None:
        hard_boundaries.append(
            "No task-matching evidence contract exists; define and admit one before delegation."
        )
    else:
        if not resolution.evidence_complete:
            requirements.append(
                CounterfactualRequirement(
                    signal="current_evidence",
                    current=resolution.evidence_grade,
                    required="EXACT",
                    delta="Repair every blocked record in the evidence contract.",
                    rationale="AUTO requires every required source to pass provenance, integrity, freshness, correlation, uniqueness, and conflict checks.",
                )
            )
        elif not resolution.autonomy_eligible:
            requirements.append(
                CounterfactualRequirement(
                    signal="source_status",
                    current=resolution.evidence_grade,
                    required="EXACT",
                    delta="Resolve review-only warnings at their authoritative source.",
                    rationale="A warning can support review but cannot authorize an autonomous side effect.",
                )
            )
        candidate_resolution = replace(
            resolution,
            evidence_complete=True,
            autonomy_eligible=True,
            evidence_grade="EXACT",
            blocking_reasons=(),
        )

        delegated_cost_limit = min(resolution.auto_cost_cap, 500.0)
        if resolution.company_cost > delegated_cost_limit:
            requirements.append(
                CounterfactualRequirement(
                    signal="company_cost",
                    current=f"${resolution.company_cost:.2f}",
                    required=f"≤ ${delegated_cost_limit:.2f}",
                    delta=f"Reduce verified company exposure by ${resolution.company_cost - delegated_cost_limit:.2f} or select another eligible remedy.",
                    rationale="The selected remedy must remain inside both its scenario delegation cap and the low-risk boundary.",
                )
            )
            candidate_resolution = replace(candidate_resolution, company_cost=delegated_cost_limit)

    additional_successes, projected_evidence = _successful_outcomes_to_auto(evidence)
    if evidence.verified_cases < AUTO_VERIFIED_CASES or evidence.reliability < AUTO_RELIABILITY:
        requirements.append(
            CounterfactualRequirement(
                signal="verified_outcomes",
                current=f"{evidence.verified_cases} cases at {evidence.reliability:.1%}",
                required=f"≥ {AUTO_VERIFIED_CASES} cases at ≥ {AUTO_RELIABILITY:.0%}",
                delta=f"Record {additional_successes} additional independently verified successful outcome{'s' if additional_successes != 1 else ''} in this exact task context.",
                rationale="Only observed outcomes—not model confidence—can expand the reliability envelope.",
            )
        )
        candidate_evidence = projected_evidence

    attainable = not hard_boundaries and candidate_resolution is not None
    resulting_mode: DecisionMode = permission.mode
    validated = False
    if attainable and candidate_resolution is not None:
        candidate = DeterministicPolicyEngine().evaluate(
            case,
            proposal,
            candidate_evidence,
            resolution_evidence=candidate_resolution,
        )
        resulting_mode = candidate.mode
        validated = candidate.mode == DecisionMode.AUTO
        attainable = validated

    if hard_boundaries:
        summary = (
            "AUTO is intentionally unavailable in this context. The listed boundary requires "
            "a person, customer confirmation, or denial/appeal workflow."
        )
    elif validated:
        summary = (
            "Applying every listed change to the typed inputs flips the same policy engine to AUTO."
        )
    else:
        summary = "The current case cannot reach AUTO through an evidence-only change."

    return DecisionCounterfactual(
        target_mode=DecisionMode.AUTO,
        attainable=attainable,
        validated_by_policy=validated,
        resulting_mode=resulting_mode,
        requirements=tuple(requirements),
        hard_boundaries=tuple(hard_boundaries),
        summary=summary,
    )


def _hard_boundaries(
    case: CustomerCase,
    proposal: AgentProposal,
    resolution: ResolutionEvidence | None,
) -> list[str]:
    boundaries: list[str] = []
    if case.fraud_signal:
        boundaries.append("An abuse signal requires human evidence review.")
    if case.contract_type == "custom_sla":
        boundaries.append("A custom contract requires human authorization.")
    if proposal.action_type == "deny" or (
        resolution is not None and resolution.permission_floor == DecisionMode.DENY
    ):
        boundaries.append(
            "A denial must preserve the evidence appeal path; more history cannot grant AUTO."
        )
    if resolution is not None:
        if resolution.safety_critical:
            boundaries.append("Safety-critical cases always require a human safety owner.")
        elif resolution.permission_floor == DecisionMode.HUMAN:
            boundaries.append("This scenario has an explicit HUMAN permission floor.")
        elif resolution.permission_floor == DecisionMode.VERIFY:
            boundaries.append("This remedy requires customer or analyst confirmation by design.")
    return boundaries


def _successful_outcomes_to_auto(
    evidence: ReliabilityEvidence,
) -> tuple[int, ReliabilityEvidence]:
    if evidence.verified_cases >= AUTO_VERIFIED_CASES and evidence.reliability >= AUTO_RELIABILITY:
        return 0, evidence

    engine = ReliabilityEngine()
    for additional in range(0, 10_001):
        projected = engine.evaluate(
            HistoricalStats(
                verified_cases=evidence.verified_cases + additional,
                successes=evidence.successes + additional,
                failures=evidence.failures,
                human_overrides=evidence.human_overrides,
                average_similarity=evidence.average_similarity,
                last_verified_at=evidence.last_verified_at,
            ),
            novelty="LOW",
            relevant_corrections=evidence.relevant_corrections,
            memory_enabled=evidence.memory_enabled,
        )
        if (
            projected.verified_cases >= AUTO_VERIFIED_CASES
            and projected.reliability >= AUTO_RELIABILITY
        ):
            return additional, projected
    return 10_000, projected
