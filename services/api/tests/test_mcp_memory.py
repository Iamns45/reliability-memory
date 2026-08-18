from __future__ import annotations

import sys
import unittest
from dataclasses import replace
from pathlib import Path
from typing import Any, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.bedrock import DeterministicDemoReasoner, DeterministicEmbeddingProvider
from app.domain import CustomerCase, DecisionMode
from app.mcp_memory import McpMemoryVerifier, _select_arguments
from app.repository import CockroachMemoryRepository, InMemoryMemoryRepository
from app.runtime import ReliabilityMemoryAgent


class FakeGateway:
    endpoint = "https://cockroachlabs.cloud/mcp"
    cluster_id = "cluster-test-123"
    database = "reliability_memory"

    def __init__(
        self, outputs: tuple[Any, ...] | None = None, error: Exception | None = None
    ) -> None:
        self.outputs = outputs
        self.error = error
        self.statements: tuple[str, ...] = ()

    def execute_selects(self, statements: Sequence[str]) -> tuple[Any, ...]:
        self.statements = tuple(statements)
        if self.error is not None:
            raise self.error
        assert self.outputs is not None
        return self.outputs


def _completed_local_run() -> Any:
    agent = ReliabilityMemoryAgent(
        InMemoryMemoryRepository(),
        DeterministicDemoReasoner(),
        DeterministicEmbeddingProvider(),
    )
    return agent.run(
        CustomerCase(
            customer_id="C-202",
            task_type="early_product_failure",
            request_text="The blender motor failed on day two.",
            requested_amount=89,
            metadata={"ground_truth_amount": 89},
        ),
        "mcp-verifier-fixture-0001",
    )


class ManagedMcpVerifierTests(unittest.TestCase):
    def test_verifies_persisted_episode_and_vector_neighbor_overlap(self) -> None:
        run = _completed_local_run()
        expected_id = str(run.similar_experiences[0].episode_id)
        gateway = FakeGateway(
            (
                {
                    "rows": [
                        {
                            "episode_id": str(run.run_id),
                            "autonomy_decision": run.permission.mode.value,
                            "policy_version": run.permission.policy_version,
                        }
                    ]
                },
                {"rows": [{"episode_id": expected_id, "similarity": 0.97}]},
            )
        )

        receipt = McpMemoryVerifier(gateway, required=True).verify(run, [expected_id])

        self.assertTrue(receipt.verified)
        self.assertTrue(receipt.required)
        self.assertEqual(receipt.observed_episode_id, str(run.run_id))
        self.assertEqual(receipt.matching_neighbor_ids, (expected_id,))
        self.assertEqual(len(receipt.receipt_hash), 64)
        self.assertEqual(len(gateway.statements), 2)
        self.assertTrue(gateway.statements[0].startswith("SELECT"))
        self.assertTrue(gateway.statements[1].startswith("SELECT"))
        self.assertIn("embedding <-> target.embedding", gateway.statements[1])

    def test_transport_failure_returns_failed_receipt_without_exposing_credentials(self) -> None:
        run = _completed_local_run()
        gateway = FakeGateway(error=RuntimeError("service unavailable"))

        receipt = McpMemoryVerifier(gateway, required=True).verify(run, [])

        self.assertFalse(receipt.verified)
        self.assertIn("service unavailable", receipt.failure_reason or "")
        self.assertNotIn("Authorization", str(receipt))

    def test_cluster_scoped_tool_arguments_omit_duplicate_cluster_id(self) -> None:
        arguments = _select_arguments(
            {
                "type": "object",
                "properties": {
                    "sql": {"type": "string"},
                    "database_name": {"type": "string"},
                    "cluster_id": {"type": "string"},
                },
            },
            "SELECT 1",
            database="reliability_memory",
        )

        self.assertEqual(
            arguments,
            {
                "sql": "SELECT 1",
                "database_name": "reliability_memory",
            },
        )

    def test_column_oriented_tool_payload_is_supported(self) -> None:
        run = _completed_local_run()
        expected_id = str(run.similar_experiences[0].episode_id)
        gateway = FakeGateway(
            (
                {
                    "columns": ["episode_id", "autonomy_decision", "policy_version"],
                    "rows": [
                        [
                            str(run.run_id),
                            run.permission.mode.value,
                            run.permission.policy_version,
                        ]
                    ],
                },
                {
                    "columns": [{"name": "episode_id"}, {"name": "similarity"}],
                    "rows": [[expected_id, 0.97]],
                },
            )
        )

        receipt = McpMemoryVerifier(gateway, required=True).verify(run, [expected_id])

        self.assertTrue(receipt.verified)
        self.assertEqual(receipt.vector_neighbor_ids, (expected_id,))

    def test_required_failure_contracts_auto_permission_before_execution(self) -> None:
        repository = InMemoryMemoryRepository()
        agent = ReliabilityMemoryAgent(
            repository,
            DeterministicDemoReasoner(),
            DeterministicEmbeddingProvider(),
            mcp_verifier=McpMemoryVerifier(
                FakeGateway(error=RuntimeError("independent proof unavailable")),
                required=True,
            ),
        )

        run = agent.run(
            CustomerCase(
                customer_id="C-202",
                task_type="early_product_failure",
                request_text="The blender motor failed on day two.",
                requested_amount=89,
                metadata={"ground_truth_amount": 89},
            ),
            "mcp-required-failure-0001",
        )

        self.assertEqual(run.permission.mode, DecisionMode.HUMAN)
        self.assertEqual(run.permission.rule_id, "mcp-verification-required")
        self.assertIsNone(run.execution)
        self.assertIsNotNone(run.mcp_verification)
        self.assertFalse(run.mcp_verification.verified if run.mcp_verification else True)
        self.assertEqual(repository.episodes[run.run_id].permission.mode, DecisionMode.HUMAN)
        self.assertIn(run.run_id, repository.mcp_receipts)

    def test_persisted_mcp_audit_uses_schema_approved_verifier_actor(self) -> None:
        run = _completed_local_run()
        expected_id = str(run.similar_experiences[0].episode_id)
        receipt = McpMemoryVerifier(
            FakeGateway(
                (
                    {
                        "rows": [
                            {
                                "episode_id": str(run.run_id),
                                "autonomy_decision": run.permission.mode.value,
                                "policy_version": run.permission.policy_version,
                            }
                        ]
                    },
                    {"rows": [{"episode_id": expected_id, "similarity": 0.97}]},
                )
            ),
            required=True,
        ).verify(run, [expected_id])
        completed_run = replace(run, mcp_verification=receipt)
        statements: list[str] = []

        class RecordingConnection:
            def execute(self, statement: str, parameters: Any = None) -> None:
                del parameters
                statements.append(statement)

        repository = CockroachMemoryRepository("unused")
        repository._transaction = lambda operation: operation(RecordingConnection())  # type: ignore[method-assign]

        repository.record_mcp_verification(completed_run)

        audit_statement = next(
            statement for statement in statements if "mcp_memory_verified" in statement
        )
        self.assertIn("'verifier'", audit_statement)
        self.assertNotIn("'mcp-verifier'", audit_statement)


if __name__ == "__main__":
    unittest.main()
