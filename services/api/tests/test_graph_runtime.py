from __future__ import annotations

import sys
import unittest
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.bedrock import DeterministicDemoReasoner, DeterministicEmbeddingProvider
from app.domain import DecisionMode, CustomerCase
from app.graph_runtime import (
    AgentGraphState,
    ReliabilityGraphRuntime,
    _setup_cockroach_checkpointer,
)
from app.repository import InMemoryMemoryRepository
from app.runtime import ReliabilityMemoryAgent


class OneNodeGraphTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repository = InMemoryMemoryRepository()
        self.agent = ReliabilityMemoryAgent(
            self.repository,
            DeterministicDemoReasoner(),
            DeterministicEmbeddingProvider(),
        )
        self.runtime = ReliabilityGraphRuntime(self.agent)

    def test_graph_has_exactly_one_executable_node_and_typed_state(self) -> None:
        self.assertEqual(self.runtime.executable_nodes, ("reliability_memory_agent",))
        self.assertIn("case", AgentGraphState.__required_keys__)
        self.assertIn("result", AgentGraphState.__optional_keys__)

    def test_stream_contains_actual_stage_events_and_persisted_result(self) -> None:
        state = self._state(
            CustomerCase(
                "C-202",
                "early_product_failure",
                "The blender motor failed on day two.",
                89,
                metadata={"ground_truth_amount": 89},
            ),
            "stream-test-0001",
        )
        events = list(self.runtime.stream(state, thread_id=state["thread_id"]))
        event_types = [event["type"] for event in events]

        self.assertIn("memory.completed", event_types)
        self.assertIn("case_evidence.completed", event_types)
        self.assertIn("policy.completed", event_types)
        self.assertIn("decision.persisted", event_types)
        self.assertIn("workflow.planned", event_types)
        self.assertIn("workflow.step.completed", event_types)
        self.assertIn("workflow.completed", event_types)
        self.assertIn("verification.completed", event_types)
        self.assertEqual(events[-1]["type"], "graph.completed")
        self.assertEqual(events[-1]["data"]["status"], "COMPLETED")

    def test_interrupt_supplies_summary_and_resume_returns_correction_id(self) -> None:
        state = self._state(
            CustomerCase(
                "C-771",
                "warranty_grace_exception",
                "Repair the known battery defect just after warranty.",
                170,
            ),
            "interrupt-test-0001",
        )
        initial = list(self.runtime.stream(state, thread_id=state["thread_id"]))
        review = next(event for event in initial if event["type"] == "review.required")
        summary = review["data"]["review_summary"]

        self.assertEqual(summary["suggested_resolution"]["action_type"], "warranty_repair")
        self.assertEqual(summary["suggested_resolution"]["amount"], 170.0)
        self.assertEqual(summary["workflow_plan"]["name"], "Warranty service recovery")
        self.assertEqual(len(summary["workflow_plan"]["steps"]), 4)
        self.assertIn("reviewer_task", summary)
        resumed = list(
            self.runtime.stream(
                None,
                thread_id=state["thread_id"],
                resolution={"resolution": "approve_suggestion"},
            )
        )
        completed = resumed[-1]["data"]
        self.assertEqual(completed["status"], "RESUMED")
        self.assertTrue(completed["correction_id"])
        self.assertIsNotNone(completed["result"]["execution"])
        self.assertEqual(
            completed["result"]["execution"]["workflow_name"],
            "Warranty service recovery",
        )
        self.assertEqual(len(completed["result"]["execution"]["steps"]), 4)
        resumed_event_types = [event["type"] for event in resumed]
        self.assertIn("workflow.step.completed", resumed_event_types)
        self.assertIn("verification.completed", resumed_event_types)
        self.assertEqual(len(self.repository.corrections), 1)

    def test_correction_replay_changes_future_proposal_and_permission(self) -> None:
        first = CustomerCase(
            "C-771",
            "warranty_grace_exception",
            "Repair the known battery defect just after warranty.",
            170,
        )
        state = self._state(first, "replay-first-0001")
        list(self.runtime.stream(state, thread_id=state["thread_id"]))
        list(
            self.runtime.stream(
                None,
                thread_id=state["thread_id"],
                resolution={"resolution": "approve_suggestion"},
            )
        )

        replay = self.agent.run(
            CustomerCase(
                "C-841",
                "warranty_grace_exception",
                "Repair the matching speaker battery defect just after warranty.",
                130,
            ),
            "replay-second-0001",
        )
        self.assertEqual(replay.proposal.action_type, "warranty_repair")
        self.assertEqual(replay.proposal.amount, 130.0)
        self.assertEqual(replay.permission.mode, DecisionMode.VERIFY)

    @staticmethod
    def _state(case: CustomerCase, thread_id: str) -> AgentGraphState:
        return {
            "thread_id": thread_id,
            "request_id": thread_id,
            "case": asdict(case),
            "status": "RUNNING",
        }


class ReliabilityExperimentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repository = InMemoryMemoryRepository()
        self.agent = ReliabilityMemoryAgent(
            self.repository,
            DeterministicDemoReasoner(),
            DeterministicEmbeddingProvider(),
        )
        self.case = CustomerCase(
            "C-202",
            "early_product_failure",
            "The blender motor failed on day two.",
            89,
            metadata={"ground_truth_amount": 89},
        )

    def test_memory_ablation_removes_earned_autonomy(self) -> None:
        comparison = self.agent.compare_memory(self.case)
        self.assertEqual(comparison["with_memory"]["permission"]["mode"], DecisionMode.AUTO)
        self.assertEqual(comparison["without_memory"]["permission"]["mode"], DecisionMode.HUMAN)
        self.assertTrue(comparison["difference"]["permission_changed"])

    def test_policy_versions_can_produce_different_permissions(self) -> None:
        comparison = self.agent.compare_policies(
            CustomerCase(
                "C-184",
                "damaged_item_keep_offer",
                "The espresso machine arrived dented but functional.",
                249,
            )
        )
        self.assertEqual(comparison["customer-resolution-v4.9"]["mode"], DecisionMode.AUTO)
        self.assertEqual(comparison["customer-resolution-v5.0"]["mode"], DecisionMode.VERIFY)
        self.assertTrue(comparison["changed"])

    def test_delayed_failure_reduces_future_reliability(self) -> None:
        run = self.agent.run(self.case, "delayed-test-0001")
        result = self.agent.record_delayed_outcome(
            run.run_id,
            run.case.task_type,
            False,
            "A later customer report invalidated the successful immediate outcome.",
        )
        self.assertLess(result["reliability_after"], result["reliability_before"])
        self.assertTrue(result["permission_may_contract"])


class CheckpointerSetupTests(unittest.TestCase):
    class FakeConnection:
        def __init__(self, versions: list[int]) -> None:
            self.versions = iter(versions)

        def execute(self, statement: str) -> "CheckpointerSetupTests.FakeConnection":
            del statement
            return self

        def fetchone(self) -> dict[str, int]:
            return {"v": next(self.versions)}

    class FakeSaver:
        MIGRATIONS = tuple(f"migration-{index}" for index in range(13))

        def __init__(self, error: Exception | None = None) -> None:
            self.error = error
            self.setup_calls = 0

        def setup(self) -> None:
            self.setup_calls += 1
            if self.error is not None:
                error = self.error
                self.error = None
                raise error

    class RetryableSetupError(RuntimeError):
        sqlstate = "23505"

    def test_complete_checkpoint_schema_skips_setup(self) -> None:
        saver = self.FakeSaver()

        _setup_cockroach_checkpointer(saver, self.FakeConnection([12]))

        self.assertEqual(saver.setup_calls, 0)

    def test_concurrent_setup_conflict_rechecks_completed_schema(self) -> None:
        saver = self.FakeSaver(self.RetryableSetupError("migration already inserted"))

        _setup_cockroach_checkpointer(saver, self.FakeConnection([-1, 12]))

        self.assertEqual(saver.setup_calls, 1)


if __name__ == "__main__":
    unittest.main()
