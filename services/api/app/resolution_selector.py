from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from .domain import DecisionMode


SELECTION_METHOD = "goal-adjusted-customer-value-per-company-dollar-v1"


@dataclass(frozen=True)
class ResolutionSelection:
    """A deterministic choice among evidence-supplied resolution options."""

    option: dict[str, Any]
    evaluated_options: tuple[dict[str, Any], ...]
    method: str
    score: float
    rationale: str
    eligible_option_count: int


def select_resolution(
    raw_options: object,
    raw_constraints: object,
) -> ResolutionSelection:
    """Choose the best admissible option without using a seeded recommendation.

    Source systems provide feasible options and their economics. This function validates
    those inputs, rejects options outside the case guardrails, and ranks the remainder by
    goal-adjusted customer value per company dollar. Permission remains a separate policy
    decision.
    """

    if not isinstance(raw_options, list) or not raw_options:
        raise ValueError("At least one resolution option is required")
    constraints = raw_constraints if isinstance(raw_constraints, dict) else {}
    cost_cap = _number(constraints.get("resolution_cost_cap", 1_000_000_000_000), "cost cap")
    minimum_goal_fit = _number(constraints.get("minimum_goal_fit", 0), "minimum goal fit")
    if minimum_goal_fit > 1:
        raise ValueError("Minimum goal fit must be between zero and one")
    default_floor = _decision_mode(constraints.get("default_permission_floor", "HUMAN"))
    default_auto_cap = _number(constraints.get("auto_cost_cap", 150), "auto cost cap")
    case_safety_critical = bool(constraints.get("safety_critical", False))

    evaluated: list[dict[str, Any]] = []
    eligible: list[dict[str, Any]] = []
    for index, raw_option in enumerate(raw_options):
        if not isinstance(raw_option, dict):
            raise ValueError(f"Resolution option {index + 1} must be an object")
        option = _normalize_option(
            raw_option,
            index=index,
            default_floor=default_floor,
            default_auto_cap=default_auto_cap,
            case_safety_critical=case_safety_critical,
        )
        exclusion_reasons: list[str] = []
        if not option["eligible"]:
            exclusion_reasons.append("Source systems marked this option ineligible.")
        if option["company_cost"] > cost_cap:
            exclusion_reasons.append(
                f"Estimated company cost exceeds the ${cost_cap:.2f} resolution limit."
            )
        if option["goal_fit"] < minimum_goal_fit:
            exclusion_reasons.append(f"Goal fit is below the {minimum_goal_fit:.0%} case minimum.")

        option["selection_score"] = _score(option)
        option["selection_eligible"] = not exclusion_reasons
        option["selection_exclusions"] = exclusion_reasons
        option["selected"] = False
        evaluated.append(option)
        if not exclusion_reasons:
            eligible.append(option)

    if not eligible:
        details = tuple(
            reason for option in evaluated for reason in option.get("selection_exclusions", [])
        )
        raise ValueError(
            "No resolution option satisfies the case constraints"
            + (f": {'; '.join(details)}" if details else "")
        )

    selected = max(
        eligible,
        key=lambda option: (
            option["selection_score"],
            option["goal_fit"],
            option["customer_value"],
            -option["company_cost"],
            -option["source_rank"],
        ),
    )
    selected["selected"] = True
    rationale = (
        f"Selected {selected['label']} from {len(eligible)} eligible option"
        f"{'s' if len(eligible) != 1 else ''}: goal fit {selected['goal_fit']:.0%} × "
        f"${selected['customer_value']:.2f} customer value ÷ "
        f"${selected['company_cost']:.2f} company cost = "
        f"{selected['selection_score']:.3f}."
    )
    return ResolutionSelection(
        option=dict(selected),
        evaluated_options=tuple(dict(option) for option in evaluated),
        method=SELECTION_METHOD,
        score=float(selected["selection_score"]),
        rationale=rationale,
        eligible_option_count=len(eligible),
    )


def _normalize_option(
    raw_option: dict[str, Any],
    *,
    index: int,
    default_floor: DecisionMode,
    default_auto_cap: float,
    case_safety_critical: bool,
) -> dict[str, Any]:
    action = str(raw_option.get("action") or "").strip()
    label = str(raw_option.get("label") or "").strip()
    if not action or not label:
        raise ValueError(f"Resolution option {index + 1} requires an action and label")

    company_cost = _number(raw_option.get("company_cost"), "company cost")
    customer_value = _number(raw_option.get("customer_value"), "customer value")
    amount = _number(raw_option.get("amount", 0), "action amount")
    goal_fit = _number(raw_option.get("goal_fit", 1), "goal fit")
    if goal_fit > 1:
        raise ValueError("Goal fit must be between zero and one")
    eligible = raw_option.get("eligible", True)
    if not isinstance(eligible, bool):
        raise ValueError("Resolution-option eligibility must be boolean")

    components = _value_components(raw_option.get("value_components"), customer_value)
    floor = _decision_mode(raw_option.get("permission_floor", default_floor))
    safety_critical = bool(raw_option.get("safety_critical", case_safety_critical))
    if safety_critical:
        floor = DecisionMode.HUMAN

    return {
        **raw_option,
        "action": action,
        "label": label,
        "amount": amount,
        "company_cost": company_cost,
        "customer_value": customer_value,
        "goal_fit": goal_fit,
        "eligible": eligible,
        "permission_floor": floor.value,
        "auto_cost_cap": _number(
            raw_option.get("auto_cost_cap", default_auto_cap), "auto cost cap"
        ),
        "safety_critical": safety_critical,
        "value_components": components,
        "source_rank": index,
        "reason": str(
            raw_option.get("reason")
            or f"Current evidence supports {label.lower()} within the case guardrails."
        ),
        "lesson": str(
            raw_option.get("lesson")
            or "Reuse this option only when the same evidence and eligibility constraints hold."
        ),
    }


def _value_components(raw_components: object, customer_value: float) -> list[dict[str, Any]]:
    if raw_components is None:
        return [
            {
                "label": "Resolved customer value",
                "amount": customer_value,
                "basis": "Supplied by the case economics source",
            }
        ]
    if not isinstance(raw_components, list) or not raw_components:
        raise ValueError("Customer-value components must be a non-empty list")
    components: list[dict[str, Any]] = []
    for raw_component in raw_components:
        if not isinstance(raw_component, dict) or not str(raw_component.get("label") or ""):
            raise ValueError("Each customer-value component requires a label")
        components.append(
            {
                **raw_component,
                "label": str(raw_component["label"]),
                "amount": _number(raw_component.get("amount"), "customer-value component"),
                "basis": str(raw_component.get("basis") or "Case economics source"),
            }
        )
    if not math.isclose(
        sum(float(component["amount"]) for component in components),
        customer_value,
        abs_tol=0.01,
    ):
        raise ValueError("Customer-value components must sum to customer value")
    return components


def _score(option: dict[str, Any]) -> float:
    if option["company_cost"] == 0:
        return float(option["goal_fit"] * option["customer_value"])
    return round(
        float(option["goal_fit"] * option["customer_value"] / option["company_cost"]),
        6,
    )


def _number(value: object, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise ValueError(f"Resolution {field} must be numeric")
    number = float(value)
    if not math.isfinite(number) or number < 0:
        raise ValueError(f"Resolution {field} must be finite and nonnegative")
    return round(number, 2)


def _decision_mode(value: object) -> DecisionMode:
    try:
        return DecisionMode(str(value))
    except ValueError:
        return DecisionMode.HUMAN
