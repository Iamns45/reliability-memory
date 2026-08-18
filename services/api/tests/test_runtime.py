from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.bedrock import DeterministicDemoReasoner, DeterministicEmbeddingProvider
from app.domain import DecisionMode, CustomerCase
from app.repository import EpisodeNotReviewableError, InMemoryMemoryRepository
from app.runtime import ReliabilityMemoryAgent


class RuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repository = InMemoryMemoryRepository()
        self.agent = ReliabilityMemoryAgent(
            self.repository,
            DeterministicDemoReasoner(),
            DeterministicEmbeddingProvider(),
        )

    def test_auto_case_executes_verifies_and_records(self) -> None:
        case = CustomerCase(
            customer_id="C-202",
            task_type="early_product_failure",
            request_text="The blender motor failed on day two.",
            requested_amount=89,
            metadata={"ground_truth_amount": 89},
        )
        run = self.agent.run(case, "runtime-test-0001")
        self.assertEqual(run.permission.mode, DecisionMode.AUTO)
        self.assertEqual(run.proposal.action_type, "replacement")
        self.assertEqual(run.proposal.amount, 89)
        self.assertTrue(run.resolution_evidence and run.resolution_evidence.evidence_complete)
        self.assertEqual(run.workflow_plan.name, "Replacement recovery")
        self.assertEqual(len(run.workflow_plan.steps), 4)
        self.assertIsNotNone(run.execution)
        self.assertEqual(len(run.execution.steps if run.execution else ()), 4)
        self.assertIn("replacement_order", run.execution.artifacts if run.execution else {})
        self.assertTrue(run.verification and run.verification.success)
        self.assertIn(run.run_id, self.repository.episodes)

    def test_idempotency_key_prevents_duplicate_provider_action(self) -> None:
        case = CustomerCase(
            "C-202",
            "early_product_failure",
            "blender motor failed",
            89,
            metadata={"ground_truth_amount": 89},
        )
        first = self.agent.run(case, "runtime-test-0002")
        second = self.agent.run(case, "runtime-test-0002")
        self.assertIsNotNone(first.execution)
        self.assertIsNone(second.execution)
        self.assertEqual(first.run_id, second.run_id)
        self.assertEqual(len(self.repository.idempotency_keys), 1)

    def test_human_correction_is_attached_to_reviewable_episode(self) -> None:
        case = CustomerCase(
            "C-771",
            "warranty_grace_exception",
            "known battery defect just after warranty",
            170,
        )
        run = self.agent.run(case, "runtime-test-0003")
        self.assertEqual(run.permission.mode, DecisionMode.HUMAN)

        self.agent.record_human_correction(
            run.run_id,
            {"action_type": "warranty_repair", "amount": 170.0},
            "Reviewer confirmed the documented warranty grace exception.",
            "Within 14 days after warranty, repair a service-bulletin defect when diagnostics exclude customer damage.",
        )

        self.assertIn(run.run_id, self.repository.corrections)

        # An identical retry is safe after an ambiguous client response.
        self.agent.record_human_correction(
            run.run_id,
            {"action_type": "warranty_repair", "amount": 170.0},
            "Reviewer confirmed the documented warranty grace exception.",
            "Within 14 days after warranty, repair a service-bulletin defect when diagnostics exclude customer damage.",
        )
        self.assertEqual(len(self.repository.corrections), 1)

    def test_completed_auto_episode_cannot_be_corrected(self) -> None:
        case = CustomerCase(
            "C-202",
            "early_product_failure",
            "blender motor failed",
            89,
            metadata={"ground_truth_amount": 89},
        )
        run = self.agent.run(case, "runtime-test-0004")

        with self.assertRaises(EpisodeNotReviewableError):
            self.agent.record_human_correction(
                run.run_id,
                {"action_type": "replacement", "amount": 89.0},
                "Reviewer attempted to alter a completed action.",
                "Completed actions must remain immutable after verification.",
            )


if __name__ == "__main__":
    unittest.main()
