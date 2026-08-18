from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Any

from .domain import DecisionMode, CustomerCase, ResolutionEvidence
from .resolution_selector import select_resolution


def assess_resolution_evidence(
    case: CustomerCase,
    customer_context: dict[str, Any],
) -> ResolutionEvidence | None:
    """Build a typed decision packet from the issue-specific database evidence bundle."""

    bundle = customer_context.get("case_evidence") or case.metadata.get("case_evidence")
    if not isinstance(bundle, dict) or not bundle:
        return None
    if bundle.get("issue_type") not in {None, case.task_type}:
        return None

    required = _string_tuple(bundle.get("evidence_required"))
    evidence_as_of = str(bundle.get("evidence_as_of") or "")
    decision_time = _timestamp(evidence_as_of)
    raw_sources = bundle.get("evidence_sources", [])
    raw_source_records = tuple(dict(item) for item in raw_sources if isinstance(item, dict))
    sources = tuple(_validate_source(source, case, decision_time) for source in raw_source_records)
    source_keys = [str(source.get("key")) for source in sources if source.get("key")]
    duplicate_keys = sorted({key for key in source_keys if source_keys.count(key) > 1})
    completed = tuple(
        str(source.get("key"))
        for source in sources
        if source.get("admissible") and source.get("key")
    )
    missing = tuple(key for key in required if key not in completed)
    source_blockers = tuple(
        reason for source in sources for reason in source.get("admissibility_reasons", [])
    )

    selection = select_resolution(
        bundle.get("resolution_options"),
        bundle.get("resolution_constraints"),
    )
    selected = selection.option
    action_type = str(selected["action"])
    amount = float(selected["amount"])
    company_cost = float(selected["company_cost"])
    customer_value = float(selected["customer_value"])
    floor = _decision_mode(selected["permission_floor"])
    safety_critical = bool(selected["safety_critical"])
    auto_cost_cap = float(selected["auto_cost_cap"])

    positive_facts = tuple(
        str(source.get("summary"))
        for source in sources
        if source.get("status") == "verified" and source.get("summary")
    )
    blockers = (
        *(f"Required source '{key}' is missing." for key in missing),
        *(f"Evidence key '{key}' appears more than once." for key in duplicate_keys),
        *source_blockers,
    )
    evidence_complete = not blockers and bool(required) and decision_time is not None
    has_review_only_source = any(source.get("status") == "warning" for source in sources)
    autonomy_eligible = evidence_complete and not has_review_only_source
    evidence_grade = (
        "BLOCKED" if not evidence_complete else "REVIEW" if not autonomy_eligible else "EXACT"
    )
    alternatives = selection.evaluated_options

    return ResolutionEvidence(
        issue_type=case.task_type,
        evidence_complete=evidence_complete,
        autonomy_eligible=autonomy_eligible,
        evidence_grade=evidence_grade,
        evidence_as_of=evidence_as_of,
        required_sources=required,
        completed_sources=completed,
        source_checks=sources,
        recommended_action=action_type,
        recommended_amount=amount,
        company_cost=company_cost,
        customer_value=customer_value,
        permission_floor=floor,
        auto_cost_cap=auto_cost_cap,
        safety_critical=safety_critical,
        customer_goal=str(bundle.get("customer_goal", "Resolve the customer's issue fairly.")),
        business_guardrail=str(
            bundle.get("business_guardrail", "Keep the action inside deterministic policy limits.")
        ),
        positive_facts=positive_facts,
        blocking_reasons=tuple(blockers),
        alternatives=alternatives,
        selection_method=selection.method,
        selection_score=selection.score,
        selection_rationale=selection.rationale,
        eligible_option_count=selection.eligible_option_count,
        value_components=tuple(dict(item) for item in selected["value_components"]),
        reason=str(selected["reason"]),
        lesson=str(selected["lesson"]),
    )


def _validate_source(
    source: dict[str, Any],
    case: CustomerCase,
    decision_time: datetime | None,
) -> dict[str, Any]:
    checked = dict(source)
    key = str(source.get("key") or "unknown")
    record_id = str(source.get("source_record_id") or f"unidentified:{key}")
    reasons: list[str] = []

    if source.get("status") not in {"verified", "warning"}:
        reasons.append(f"{record_id} has blocking status '{source.get('status')}'.")
    if source.get("authority") not in {
        "system_of_record",
        "independent_verifier",
        "customer_evidence",
    }:
        reasons.append(f"{record_id} does not identify an admissible authority.")
    if not source.get("source_system") or not source.get("source_record_id"):
        reasons.append(f"{record_id} is missing source-system provenance.")

    expected_hash = _source_hash(source)
    if (
        source.get("integrity") != "sha256_verified"
        or source.get("integrity_hash") != expected_hash
    ):
        reasons.append(f"{record_id} failed its integrity check.")

    correlation = source.get("correlation")
    expected_correlation = {
        "case_id": case.metadata.get("case_id"),
        "customer_id": case.customer_id,
        "task_type": case.task_type,
    }
    if not isinstance(correlation, dict):
        reasons.append(f"{record_id} is missing entity correlation.")
    else:
        for field, expected in expected_correlation.items():
            if expected is not None and correlation.get(field) != expected:
                reasons.append(f"{record_id} does not match the case {field}.")

    observed_at = _timestamp(source.get("observed_at"))
    max_age = source.get("max_age_seconds")
    freshness_status = "invalid"
    if decision_time is None:
        reasons.append("The evidence bundle is missing a valid decision snapshot time.")
    elif observed_at is None or isinstance(max_age, bool) or not isinstance(max_age, int):
        reasons.append(f"{record_id} is missing a valid freshness window.")
    else:
        age_seconds = (decision_time - observed_at).total_seconds()
        if age_seconds < 0:
            reasons.append(f"{record_id} was observed after the decision snapshot.")
        elif age_seconds > max_age:
            reasons.append(f"{record_id} is stale by {int(age_seconds - max_age)} seconds.")
        else:
            freshness_status = "current"

    conflicts = source.get("conflicts")
    if not isinstance(conflicts, list):
        reasons.append(f"{record_id} is missing conflict metadata.")
    elif conflicts:
        reasons.append(f"{record_id} has unresolved conflicts: {', '.join(map(str, conflicts))}.")

    checked["freshness_status"] = freshness_status
    checked["admissible"] = not reasons
    checked["admissibility_reasons"] = reasons
    return checked


def _source_hash(source: dict[str, Any]) -> str:
    raw_facts = source.get("facts")
    facts: list[Any] = raw_facts if isinstance(raw_facts, list) else []
    return hashlib.sha256(
        "|".join(
            (
                str(source.get("key") or ""),
                str(source.get("label") or ""),
                str(source.get("summary") or ""),
                *(str(fact) for fact in facts),
            )
        ).encode("utf-8")
    ).hexdigest()


def _timestamp(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _string_tuple(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(str(item) for item in value if str(item))


def _decision_mode(value: object) -> DecisionMode:
    try:
        return DecisionMode(str(value))
    except ValueError:
        return DecisionMode.HUMAN
