from __future__ import annotations

import sys
import unittest
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.case_catalog import analyst_case_records
from app.domain import AgentProposal, CustomerCase, DecisionMode, ResolutionEvidence
from app.policy import DeterministicPolicyEngine
from app.reliability import HistoricalStats, ReliabilityEngine
from app.resolution_evidence import assess_resolution_evidence


class ResolutionEvidenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.record = next(
            record for record in analyst_case_records() if record["case_id"] == "CASE-202-26"
        )
        self.case = CustomerCase(
            customer_id="C-202",
            task_type=self.record["task_type"],
            request_text=self.record["request_text"],
            requested_amount=self.record["requested_amount"],
        )
        self.reliability = ReliabilityEngine().evaluate(
            HistoricalStats(
                verified_cases=500,
                successes=498,
                failures=1,
                human_overrides=1,
                average_similarity=0.96,
                last_verified_at=datetime.now(timezone.utc),
            ),
            novelty="LOW",
        )

    def test_complete_issue_packet_can_support_the_selected_action(self) -> None:
        evidence = self.build_evidence(self.record)

        self.assertIsNotNone(evidence)
        assert evidence is not None
        self.assertTrue(evidence.evidence_complete)
        self.assertTrue(evidence.autonomy_eligible)
        self.assertEqual(evidence.evidence_grade, "EXACT")
        self.assertEqual(evidence.recommended_action, "replacement")
        self.assertEqual(evidence.company_cost, 48)
        decision = DeterministicPolicyEngine().evaluate(
            self.case,
            AgentProposal("replacement", 89, "Replace the verified failed unit."),
            self.reliability,
            resolution_evidence=evidence,
        )
        self.assertEqual(decision.mode, DecisionMode.AUTO)

    def test_missing_required_source_forces_human_review(self) -> None:
        record = deepcopy(self.record)
        record["evidence_sources"] = [
            source for source in record["evidence_sources"] if source["key"] != "diagnostics"
        ]
        evidence = self.build_evidence(record)

        assert evidence is not None
        self.assertFalse(evidence.evidence_complete)
        self.assertTrue(any("diagnostics" in reason for reason in evidence.blocking_reasons))
        decision = DeterministicPolicyEngine().evaluate(
            self.case,
            AgentProposal("replacement", 89, "Replace the failed unit."),
            self.reliability,
            resolution_evidence=evidence,
        )
        self.assertEqual(decision.mode, DecisionMode.HUMAN)
        self.assertEqual(decision.rule_id, "required-evidence-incomplete")

    def test_model_cannot_substitute_a_cheaper_unproven_action(self) -> None:
        evidence = self.build_evidence(self.record)

        assert evidence is not None
        decision = DeterministicPolicyEngine().evaluate(
            self.case,
            AgentProposal("store_credit", 25, "Use a cheaper generic recovery."),
            self.reliability,
            resolution_evidence=evidence,
        )
        self.assertEqual(decision.mode, DecisionMode.DENY)
        self.assertEqual(decision.rule_id, "evidence-plan-mismatch-deny")

    def test_task_mismatched_bundle_is_ignored(self) -> None:
        record = deepcopy(self.record)
        record["issue_type"] = "delivery_not_found"

        self.assertIsNone(self.build_evidence(record))

    def test_non_finite_resolution_economics_are_rejected(self) -> None:
        record = deepcopy(self.record)
        record["resolution_options"][0]["company_cost"] = "nan"

        with self.assertRaisesRegex(ValueError, "finite and nonnegative"):
            self.build_evidence(record)

    def test_runtime_selector_derives_keep_offer_and_value_breakdown(self) -> None:
        record = next(item for item in analyst_case_records() if item["case_id"] == "CASE-184-26")

        evidence = self.build_evidence(record)

        assert evidence is not None
        self.assertEqual(evidence.recommended_action, "partial_refund")
        self.assertEqual(evidence.recommended_amount, 60)
        self.assertEqual(evidence.customer_value, 95)
        self.assertEqual(
            sum(component["amount"] for component in evidence.value_components),
            95,
        )
        self.assertIn("goal fit 100%", evidence.selection_rationale)
        self.assertTrue(
            next(option for option in evidence.alternatives if option["selected"])["selected"]
        )

    def test_selector_changes_to_replacement_when_keep_offer_economics_change(self) -> None:
        record = next(item for item in analyst_case_records() if item["case_id"] == "CASE-184-26")
        changed = deepcopy(record)
        keep_offer = changed["resolution_options"][0]
        keep_offer["company_cost"] = 200

        evidence = self.build_evidence(changed)

        assert evidence is not None
        self.assertEqual(evidence.recommended_action, "replacement")
        self.assertEqual(evidence.recommended_amount, 249)
        self.assertEqual(evidence.company_cost, 152)

    def test_customer_value_components_must_reconcile(self) -> None:
        record = next(item for item in analyst_case_records() if item["case_id"] == "CASE-184-26")
        changed = deepcopy(record)
        changed["resolution_options"][0]["value_components"][1]["amount"] = 34

        with self.assertRaisesRegex(ValueError, "sum to customer value"):
            self.build_evidence(changed)

    def test_ineligible_option_cannot_win_even_with_better_economics(self) -> None:
        record = next(item for item in analyst_case_records() if item["case_id"] == "CASE-184-26")
        changed = deepcopy(record)
        changed["resolution_options"][0]["eligible"] = False

        evidence = self.build_evidence(changed)

        assert evidence is not None
        self.assertEqual(evidence.recommended_action, "replacement")
        rejected = next(
            option for option in evidence.alternatives if option["action"] == "partial_refund"
        )
        self.assertFalse(rejected["selection_eligible"])
        self.assertIn("ineligible", rejected["selection_exclusions"][0])

    def test_case_cost_limit_excludes_over_limit_options(self) -> None:
        record = next(item for item in analyst_case_records() if item["case_id"] == "CASE-184-26")
        changed = deepcopy(record)
        changed["resolution_constraints"]["resolution_cost_cap"] = 100

        evidence = self.build_evidence(changed)

        assert evidence is not None
        self.assertEqual(evidence.recommended_action, "partial_refund")
        over_limit = [option for option in evidence.alternatives if option["company_cost"] > 100]
        self.assertTrue(over_limit)
        self.assertTrue(all(not option["selection_eligible"] for option in over_limit))

    def test_tampered_record_integrity_blocks_the_decision(self) -> None:
        record = deepcopy(self.record)
        record["evidence_sources"][0]["summary"] = "Tampered after collection"

        evidence = self.build_evidence(record)

        assert evidence is not None
        self.assertEqual(evidence.evidence_grade, "BLOCKED")
        self.assertTrue(any("integrity" in reason for reason in evidence.blocking_reasons))

    def test_stale_record_blocks_the_decision(self) -> None:
        record = deepcopy(self.record)
        record["evidence_sources"][0]["observed_at"] = "2025-01-01T00:00:00Z"
        record["evidence_sources"][0]["max_age_seconds"] = 60

        evidence = self.build_evidence(record)

        assert evidence is not None
        self.assertEqual(evidence.evidence_grade, "BLOCKED")
        self.assertTrue(any("stale" in reason for reason in evidence.blocking_reasons))

    def test_mismatched_customer_correlation_blocks_the_decision(self) -> None:
        record = deepcopy(self.record)
        record["evidence_sources"][0]["correlation"]["customer_id"] = "C-other"

        evidence = self.build_evidence(record)

        assert evidence is not None
        self.assertEqual(evidence.evidence_grade, "BLOCKED")
        self.assertTrue(any("customer_id" in reason for reason in evidence.blocking_reasons))

    @staticmethod
    def build_evidence(record: dict[str, object]) -> ResolutionEvidence | None:
        bundle = {
            "issue_type": record["task_type"],
            "evidence_as_of": record["evidence_as_of"],
            "customer_goal": record["customer_goal"],
            "business_guardrail": record["business_guardrail"],
            "evidence_required": record["evidence_required"],
            "evidence_sources": record["evidence_sources"],
            "resolution_options": record["resolution_options"],
            "resolution_constraints": record["resolution_constraints"],
        }
        if "issue_type" in record:
            bundle["issue_type"] = record["issue_type"]
        customer = record.get("customer")
        customer_id = str(customer.get("customer_id")) if isinstance(customer, dict) else "C-202"
        case = CustomerCase(
            customer_id=customer_id,
            task_type=str(record["task_type"]),
            request_text=str(record["request_text"]),
            requested_amount=float(str(record["requested_amount"])),
            metadata={"case_id": record["case_id"]},
        )
        return assess_resolution_evidence(case, {"case_evidence": bundle})


if __name__ == "__main__":
    unittest.main()
