from __future__ import annotations

import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.case_catalog import analyst_case_record
from app.counterfactual import explain_auto_counterfactual
from app.domain import AgentProposal, CustomerCase, DecisionMode
from app.policy import DeterministicPolicyEngine
from app.reliability import HistoricalStats, ReliabilityEngine
from app.resolution_evidence import assess_resolution_evidence


class CounterfactualTests(unittest.TestCase):
    def test_verified_outcome_delta_is_re_evaluated_by_the_same_policy(self) -> None:
        record = analyst_case_record("CASE-202-26")
        assert record is not None
        case = self.case_from_record(record)
        resolution = assess_resolution_evidence(
            case,
            {"case_evidence": case.metadata["case_evidence"]},
        )
        assert resolution is not None
        proposal = AgentProposal(
            resolution.recommended_action,
            resolution.recommended_amount,
            resolution.reason,
        )
        evidence = ReliabilityEngine().evaluate(
            HistoricalStats(
                verified_cases=50,
                successes=50,
                failures=0,
                human_overrides=0,
                average_similarity=1.0,
                last_verified_at=datetime.now(timezone.utc),
            )
        )
        permission = DeterministicPolicyEngine().evaluate(
            case,
            proposal,
            evidence,
            resolution_evidence=resolution,
        )

        result = explain_auto_counterfactual(
            case,
            proposal,
            evidence,
            resolution,
            permission,
        )

        self.assertEqual(permission.mode, DecisionMode.VERIFY)
        self.assertTrue(result.attainable)
        self.assertTrue(result.validated_by_policy)
        self.assertEqual(result.resulting_mode, DecisionMode.AUTO)
        outcome_requirement = next(
            item for item in result.requirements if item.signal == "verified_outcomes"
        )
        self.assertIn("50 additional", outcome_requirement.delta)

    def test_permission_floor_is_reported_as_a_hard_boundary(self) -> None:
        record = analyst_case_record("CASE-184-26")
        assert record is not None
        case = self.case_from_record(record)
        resolution = assess_resolution_evidence(
            case,
            {"case_evidence": case.metadata["case_evidence"]},
        )
        assert resolution is not None
        proposal = AgentProposal(
            resolution.recommended_action,
            resolution.recommended_amount,
            resolution.reason,
        )
        evidence = ReliabilityEngine().evaluate(
            HistoricalStats(
                verified_cases=500,
                successes=498,
                failures=1,
                human_overrides=1,
                average_similarity=1.0,
                last_verified_at=datetime.now(timezone.utc),
            )
        )
        permission = DeterministicPolicyEngine().evaluate(
            case,
            proposal,
            evidence,
            resolution_evidence=resolution,
        )

        result = explain_auto_counterfactual(
            case,
            proposal,
            evidence,
            resolution,
            permission,
        )

        self.assertFalse(result.attainable)
        self.assertFalse(result.validated_by_policy)
        self.assertTrue(any("confirmation" in item for item in result.hard_boundaries))

    @staticmethod
    def case_from_record(record: dict[str, object]) -> CustomerCase:
        customer = record["customer"]
        assert isinstance(customer, dict)
        bundle = {
            "issue_type": record["task_type"],
            "customer_segment": record["customer_segment"],
            "evidence_as_of": record["evidence_as_of"],
            "customer_goal": record["customer_goal"],
            "business_guardrail": record["business_guardrail"],
            "evidence_required": record["evidence_required"],
            "evidence_sources": record["evidence_sources"],
            "resolution_options": record["resolution_options"],
            "resolution_constraints": record["resolution_constraints"],
        }
        return CustomerCase(
            customer_id=str(customer["customer_id"]),
            task_type=str(record["task_type"]),
            request_text=str(record["request_text"]),
            requested_amount=float(str(record["requested_amount"])),
            account_type=str(customer["account_type"]),
            region=str(customer["region"]),
            contract_type=str(customer["contract_type"]),
            metadata={"case_id": record["case_id"], "case_evidence": bundle},
        )


if __name__ == "__main__":
    unittest.main()
