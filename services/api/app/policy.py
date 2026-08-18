from __future__ import annotations

import math

from .domain import (
    AgentProposal,
    DecisionMode,
    DuplicatePaymentEvidence,
    PermissionDecision,
    CustomerCase,
    ReliabilityEvidence,
    ResolutionEvidence,
    RiskLevel,
)
from .payment_evidence import MATCH_FIELDS, REQUIRED_SAFEGUARDS


class DeterministicPolicyEngine:
    """The trust boundary. No model-provided field can grant execution permission."""

    VERSION = "customer-resolution-v5.0"
    SUPPORTED_VERSIONS = {
        "customer-resolution-v4.9",
        VERSION,
        "refund-policy-v4.2",
        "refund-policy-v4.3",
    }

    def __init__(self, version: str = VERSION) -> None:
        if version not in self.SUPPORTED_VERSIONS:
            raise ValueError(f"Unsupported policy version: {version}")
        self.version = version

    def evaluate(
        self,
        case: CustomerCase,
        proposal: AgentProposal,
        evidence: ReliabilityEvidence,
        payment_evidence: DuplicatePaymentEvidence | None = None,
        resolution_evidence: ResolutionEvidence | None = None,
    ) -> PermissionDecision:
        risk = self.evaluate_risk(case, proposal, resolution_evidence)

        if (
            not math.isfinite(proposal.amount)
            or proposal.amount < 0
            or proposal.amount > case.requested_amount
        ):
            return self._decision(
                DecisionMode.DENY,
                RiskLevel.HIGH,
                "action-value-invariant-deny",
                "The proposed value is negative, non-finite, or exceeds the customer claim.",
            )

        if case.fraud_signal:
            return self._decision(
                DecisionMode.HUMAN,
                RiskLevel.HIGH,
                "abuse-signal-human",
                "An abuse signal requires evidence review by a human; it is not treated as proof of customer wrongdoing.",
            )

        if resolution_evidence is not None:
            return self._evaluate_resolution(case, proposal, evidence, resolution_evidence, risk)

        if case.task_type != "duplicate_charge_refund":
            return self._decision(
                DecisionMode.HUMAN,
                risk,
                "issue-evidence-required",
                "No task-matching current-case evidence contract was supplied.",
                "Historical reliability and model confidence cannot replace present operational facts.",
            )

        duplicate_decision = self._evaluate_duplicate(
            case,
            proposal,
            payment_evidence,
            risk,
        )
        if duplicate_decision is not None:
            return duplicate_decision

        if proposal.amount > 1000 or case.contract_type == "custom_sla":
            return self._decision(
                DecisionMode.HUMAN,
                risk,
                "high-impact-human",
                "Financial exposure or a custom contract crosses a hard review boundary.",
                "Empirical reliability cannot override this deterministic limit.",
            )

        return self._evidence_tier_decision(case, proposal, evidence, risk)

    def _evaluate_resolution(
        self,
        case: CustomerCase,
        proposal: AgentProposal,
        evidence: ReliabilityEvidence,
        resolution: ResolutionEvidence,
        risk: RiskLevel,
    ) -> PermissionDecision:
        if self.version == "customer-resolution-v4.9":
            return self._legacy_resolution_decision(proposal, evidence, risk)

        if (
            proposal.action_type != resolution.recommended_action
            or proposal.amount != resolution.recommended_amount
        ):
            if resolution.permission_floor == DecisionMode.HUMAN:
                return self._decision(
                    DecisionMode.HUMAN,
                    risk,
                    "proposal-conflicts-with-evidence-human",
                    "The model proposal conflicts with the resolution derived from current evidence.",
                    resolution.reason,
                    "A reviewer receives the evidence-derived resolution prefilled instead of reconstructing the case.",
                )
            return self._decision(
                DecisionMode.DENY,
                RiskLevel.HIGH,
                "evidence-plan-mismatch-deny",
                "The proposal does not match the action and bounded value derived from current case evidence.",
            )

        if resolution.permission_floor == DecisionMode.DENY or proposal.action_type == "deny":
            return self._decision(
                DecisionMode.DENY,
                risk,
                "current-evidence-deny",
                resolution.reason,
                "The customer receives an evidence appeal path; historical reliability cannot override identity or eligibility facts.",
            )

        if not resolution.evidence_complete:
            return self._decision(
                DecisionMode.HUMAN,
                risk,
                "required-evidence-incomplete",
                "The issue-specific evidence bundle is incomplete.",
                *resolution.blocking_reasons,
            )

        if not resolution.autonomy_eligible and resolution.permission_floor == DecisionMode.AUTO:
            return self._decision(
                DecisionMode.VERIFY,
                RiskLevel.MEDIUM,
                "evidence-grade-review",
                f"Evidence grade is {resolution.evidence_grade}; automatic execution requires EXACT.",
                "Every required record is admissible, but at least one source contains a review-only warning.",
            )

        if resolution.safety_critical:
            return self._decision(
                DecisionMode.HUMAN,
                RiskLevel.HIGH,
                "safety-human",
                "A possible safety incident requires a human safety owner and cannot receive a retention discount.",
                resolution.business_guardrail,
            )

        if (
            resolution.permission_floor == DecisionMode.HUMAN
            and evidence.relevant_corrections > 0
            and case.task_type == "warranty_grace_exception"
        ):
            return self._decision(
                DecisionMode.VERIFY,
                risk,
                "corrected-warranty-exception-verify",
                resolution.reason,
                "A verified human lesson now supports this narrow grace-period context, but the exception remains supervised until enough replay outcomes succeed.",
                self._economics_reason(resolution),
            )

        if resolution.permission_floor == DecisionMode.HUMAN:
            return self._decision(
                DecisionMode.HUMAN,
                risk,
                "scenario-human-boundary",
                resolution.reason,
                resolution.business_guardrail,
            )

        if evidence.verified_cases < 20 or evidence.novelty == "HIGH":
            return self._decision(
                DecisionMode.HUMAN,
                risk,
                "novelty-human",
                "Comparable verified evidence is insufficient for delegated action.",
            )

        if resolution.permission_floor == DecisionMode.VERIFY:
            return self._decision(
                DecisionMode.VERIFY,
                risk,
                "customer-choice-or-exception-verify",
                resolution.reason,
                "A reviewer confirms customer preference or an explicit exception before execution.",
                self._economics_reason(resolution),
            )

        if resolution.company_cost > resolution.auto_cost_cap:
            return self._decision(
                DecisionMode.VERIFY,
                RiskLevel.MEDIUM,
                "resolution-cost-cap-verify",
                self._economics_reason(resolution),
                f"Company cost exceeds the ${resolution.auto_cost_cap:.0f} delegated limit for this scenario.",
            )

        if (
            evidence.reliability >= 0.98
            and evidence.verified_cases >= 100
            and risk == RiskLevel.LOW
        ):
            return self._decision(
                DecisionMode.AUTO,
                risk,
                "earned-resolution-autonomy",
                f"Evidence grade is {resolution.evidence_grade} at {resolution.evidence_as_of}.",
                f"Every required source is present: {', '.join(resolution.completed_sources)}.",
                f"Historical evidence is {evidence.reliability:.1%} across {evidence.verified_cases} verified comparable outcomes.",
                self._economics_reason(resolution),
                resolution.business_guardrail,
            )

        if evidence.reliability >= 0.90 and risk != RiskLevel.HIGH:
            return self._decision(
                DecisionMode.VERIFY,
                risk,
                "supervised-resolution-verify",
                "Current facts support the bounded resolution, but historical evidence has not earned automatic execution.",
                self._economics_reason(resolution),
            )

        return self._decision(
            DecisionMode.HUMAN,
            risk,
            "default-human",
            "The case is outside the agent's proven reliability envelope.",
        )

    def _legacy_resolution_decision(
        self,
        proposal: AgentProposal,
        evidence: ReliabilityEvidence,
        risk: RiskLevel,
    ) -> PermissionDecision:
        if (
            proposal.amount <= 100
            and evidence.reliability >= 0.95
            and evidence.verified_cases >= 50
            and risk != RiskLevel.HIGH
        ):
            return self._decision(
                DecisionMode.AUTO,
                risk,
                "legacy-amount-first-auto",
                "Legacy policy treats a low proposed amount as sufficient for automatic execution.",
            )
        return self._decision(
            DecisionMode.HUMAN,
            risk,
            "legacy-default-human",
            "Legacy policy lacks scenario-specific evidence and economics rules.",
        )

    def _evaluate_duplicate(
        self,
        case: CustomerCase,
        proposal: AgentProposal,
        payment_evidence: DuplicatePaymentEvidence | None,
        risk: RiskLevel,
    ) -> PermissionDecision | None:
        if case.task_type != "duplicate_charge_refund":
            return None
        if self.version == "refund-policy-v4.2":
            return None

        receipt_complete = bool(
            payment_evidence is not None
            and payment_evidence.original_payment_id
            and payment_evidence.duplicate_payment_id
            and payment_evidence.amount is not None
            and payment_evidence.currency
            and set(MATCH_FIELDS).issubset(payment_evidence.matched_on)
            and set(REQUIRED_SAFEGUARDS).issubset(payment_evidence.safeguards)
        )
        if (
            payment_evidence is None
            or not payment_evidence.duplicate_confirmed
            or not receipt_complete
        ):
            blockers = (
                payment_evidence.blocking_reasons
                if payment_evidence is not None and payment_evidence.blocking_reasons
                else ("No authoritative payment-ledger evidence was supplied.",)
            )
            return self._decision(
                DecisionMode.HUMAN,
                risk,
                "duplicate-ledger-evidence-required",
                "Automatic refunds require one deterministic duplicate pair from the payment ledger.",
                *blockers,
            )
        if proposal.action_type != "refund" or proposal.amount != payment_evidence.amount:
            return self._decision(
                DecisionMode.DENY,
                RiskLevel.HIGH,
                "duplicate-amount-invariant-deny",
                "The proposal does not exactly refund the confirmed duplicate payment.",
            )
        return None

    def _evidence_tier_decision(
        self,
        case: CustomerCase,
        proposal: AgentProposal,
        evidence: ReliabilityEvidence,
        risk: RiskLevel,
    ) -> PermissionDecision:
        if evidence.verified_cases < 20 or evidence.novelty == "HIGH":
            return self._decision(
                DecisionMode.HUMAN,
                risk,
                "novelty-human",
                "Comparable verified evidence is insufficient for delegated action.",
            )
        auto_amount = 250 if case.account_type == "premium" else 100
        auto_reliability = 0.95 if self.version == "refund-policy-v4.2" else 0.98
        auto_cases = 50 if self.version == "refund-policy-v4.2" else 100
        if (
            proposal.amount <= auto_amount
            and evidence.reliability >= auto_reliability
            and evidence.verified_cases >= auto_cases
            and risk == RiskLevel.LOW
        ):
            return self._decision(
                DecisionMode.AUTO,
                risk,
                "earned-autonomy-low-risk",
                f"Historical evidence is {evidence.reliability:.1%} across {evidence.verified_cases} verified outcomes.",
                f"The action is within the ${auto_amount} operational limit.",
            )
        if evidence.reliability >= 0.90 and risk != RiskLevel.HIGH:
            return self._decision(
                DecisionMode.VERIFY,
                risk,
                "supervised-verify",
                "Evidence supports a supervised proposal but not autonomous execution.",
            )
        return self._decision(
            DecisionMode.HUMAN,
            risk,
            "default-human",
            "The case is outside the agent's proven reliability envelope.",
        )

    def evaluate_risk(
        self,
        case: CustomerCase,
        proposal: AgentProposal,
        resolution: ResolutionEvidence | None = None,
    ) -> RiskLevel:
        if (
            case.fraud_signal
            or case.contract_type == "custom_sla"
            or (resolution is not None and resolution.safety_critical)
        ):
            return RiskLevel.HIGH
        company_cost = resolution.company_cost if resolution is not None else proposal.amount
        if company_cost > 500 or proposal.amount > 1000:
            return RiskLevel.HIGH
        cap = (
            resolution.auto_cost_cap
            if resolution is not None
            else (250 if case.account_type == "premium" else 100)
        )
        if company_cost > cap or case.account_type == "enterprise":
            return RiskLevel.MEDIUM
        return RiskLevel.LOW

    def _decision(
        self,
        mode: DecisionMode,
        risk: RiskLevel,
        rule_id: str,
        *reasons: str,
    ) -> PermissionDecision:
        return PermissionDecision(
            mode=mode,
            risk=risk,
            policy_version=self.version,
            reasons=tuple(reason for reason in reasons if reason),
            rule_id=rule_id,
        )

    @staticmethod
    def _economics_reason(resolution: ResolutionEvidence) -> str:
        return (
            f"The computed resolution creates ${resolution.customer_value:.0f} customer value "
            f"at ${resolution.company_cost:.0f} estimated company cost."
        )
