from __future__ import annotations

import sys
import unittest
from dataclasses import replace
from math import nan
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.domain import (
    AgentProposal,
    DecisionMode,
    DuplicatePaymentEvidence,
    CustomerCase,
    RiskLevel,
)
from app.policy import DeterministicPolicyEngine
from app.reliability import HistoricalStats, ReliabilityEngine


class ReliabilityEngineTests(unittest.TestCase):
    def test_strong_verified_history_produces_high_empirical_reliability(self) -> None:
        evidence = ReliabilityEngine().evaluate(
            HistoricalStats(
                verified_cases=217,
                successes=215,
                failures=1,
                human_overrides=1,
                average_similarity=0.94,
                last_verified_at=datetime.now(timezone.utc),
            ),
            novelty="LOW",
        )
        self.assertGreaterEqual(evidence.reliability, 0.98)
        self.assertEqual(evidence.evidence_quality, "HIGH")

    def test_small_novel_sample_is_not_presented_as_reliable(self) -> None:
        evidence = ReliabilityEngine().evaluate(
            HistoricalStats(
                verified_cases=3,
                successes=2,
                failures=0,
                human_overrides=1,
                average_similarity=0.82,
            ),
            novelty="HIGH",
        )
        self.assertLess(evidence.reliability, 0.70)
        self.assertEqual(evidence.evidence_quality, "LOW")

    def test_invalid_outcome_counts_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            ReliabilityEngine().evaluate(HistoricalStats(3, 3, 1, 0))

    def test_negative_outcome_counts_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            ReliabilityEngine().evaluate(HistoricalStats(3, 3, -1, 0))


class PolicyBoundaryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = DeterministicPolicyEngine()
        self.evidence = ReliabilityEngine().evaluate(
            HistoricalStats(217, 215, 1, 1, 0.94, datetime.now(timezone.utc)),
            novelty="LOW",
        )

    def test_low_risk_case_can_earn_auto_execution(self) -> None:
        case = CustomerCase(
            "C-184", "duplicate_charge_refund", "charged twice", 79, existing_credit=20
        )
        proposal = AgentProposal("refund", 79, "refund exact duplicate", confidence=1.0)
        decision = self.engine.evaluate(
            case,
            proposal,
            self.evidence,
            self.confirmed_payment_evidence(),
        )
        self.assertEqual(decision.mode, DecisionMode.AUTO)
        self.assertEqual(decision.risk, RiskLevel.LOW)

    def test_duplicate_refund_requires_payment_ledger_evidence(self) -> None:
        case = CustomerCase("C-184", "duplicate_charge_refund", "charged twice", 79)
        proposal = AgentProposal("refund", 79, "customer asked", confidence=1.0)
        decision = self.engine.evaluate(case, proposal, self.evidence)
        self.assertEqual(decision.mode, DecisionMode.HUMAN)
        self.assertEqual(decision.rule_id, "duplicate-ledger-evidence-required")

    def test_goodwill_credit_cannot_reduce_a_confirmed_duplicate_refund(self) -> None:
        case = CustomerCase(
            "C-184", "duplicate_charge_refund", "charged twice", 79, existing_credit=20
        )
        proposal = AgentProposal("refund", 59, "netted unrelated credit", confidence=1.0)
        decision = self.engine.evaluate(
            case,
            proposal,
            self.evidence,
            self.confirmed_payment_evidence(),
        )
        self.assertEqual(decision.mode, DecisionMode.DENY)
        self.assertEqual(decision.rule_id, "duplicate-amount-invariant-deny")

    def test_incomplete_payment_receipt_cannot_grant_permission(self) -> None:
        case = CustomerCase("C-184", "duplicate_charge_refund", "charged twice", 79)
        proposal = AgentProposal("refund", 79, "refund exact duplicate", confidence=1.0)
        incomplete = replace(
            self.confirmed_payment_evidence(),
            matched_on=("amount", "currency"),
        )
        decision = self.engine.evaluate(case, proposal, self.evidence, incomplete)
        self.assertEqual(decision.mode, DecisionMode.HUMAN)
        self.assertEqual(decision.rule_id, "duplicate-ledger-evidence-required")

    def test_llm_confidence_cannot_bypass_high_value_gate(self) -> None:
        case = CustomerCase(
            "C-044",
            "enterprise_sla_credit",
            "SLA credit",
            8000,
            account_type="enterprise",
            contract_type="custom_sla",
        )
        proposal = AgentProposal("refund", 8000, "contractual credit", confidence=1.0)
        decision = self.engine.evaluate(case, proposal, self.evidence)
        self.assertEqual(decision.mode, DecisionMode.HUMAN)
        self.assertNotEqual(decision.mode, DecisionMode.AUTO)

    def test_generic_task_without_current_evidence_cannot_auto_execute(self) -> None:
        case = CustomerCase(
            "C-900",
            "general_customer_resolution",
            "Please replace this item.",
            49,
        )
        proposal = AgentProposal("replacement", 49, "High model confidence", confidence=1.0)

        decision = self.engine.evaluate(case, proposal, self.evidence)

        self.assertEqual(decision.mode, DecisionMode.HUMAN)
        self.assertEqual(decision.rule_id, "issue-evidence-required")

    def test_invalid_over_refund_is_denied(self) -> None:
        case = CustomerCase("C-184", "duplicate_charge_refund", "charged twice", 79)
        proposal = AgentProposal("refund", 158, "model mistake", confidence=1.0)
        decision = self.engine.evaluate(case, proposal, self.evidence)
        self.assertEqual(decision.mode, DecisionMode.DENY)

    def test_non_finite_refund_is_denied(self) -> None:
        case = CustomerCase("C-184", "duplicate_charge_refund", "charged twice", 79)
        proposal = AgentProposal("refund", nan, "invalid model output", confidence=1.0)
        decision = self.engine.evaluate(case, proposal, self.evidence)
        self.assertEqual(decision.mode, DecisionMode.DENY)

    @staticmethod
    def confirmed_payment_evidence() -> DuplicatePaymentEvidence:
        return DuplicatePaymentEvidence(
            duplicate_confirmed=True,
            checked_payments=2,
            original_payment_id="pay_original",
            duplicate_payment_id="pay_duplicate",
            amount=79,
            currency="USD",
            subscription_reference="sub_C184_premium",
            capture_gap_seconds=87,
            matched_on=(
                "provider",
                "amount",
                "currency",
                "merchant_reference",
                "subscription_reference",
                "billing_period",
                "payment_method_fingerprint",
            ),
            safeguards=(
                "both_charges_settled",
                "no_existing_refund",
                "no_reversal",
                "no_dispute_or_chargeback",
                "captured_within_ten_minutes",
                "requested_amount_matches_duplicate",
            ),
            blocking_reasons=(),
        )


if __name__ == "__main__":
    unittest.main()
