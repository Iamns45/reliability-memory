from __future__ import annotations

import sys
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.main import create_app
from app.settings import Settings


class ApiIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        settings = Settings(
            database_url=None,
            use_bedrock=False,
            aws_region="us-east-1",
            bedrock_model_id="amazon.nova-lite-v1:0",
            cors_origins=("http://localhost:3000",),
        )
        self.client = TestClient(create_app(settings))

    def test_health_proves_one_typed_langgraph_node(self) -> None:
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["graph"]["node_count"], 1)
        self.assertEqual(response.json()["graph"]["typed_state"], "AgentGraphState")
        self.assertIn("distributed-vector-indexing", response.json()["cockroachdb_tools"])
        self.assertEqual(response.json()["mcp"]["status"], "disabled")
        self.assertTrue(response.json()["mcp"]["read_only"])

    def test_sse_endpoint_returns_backend_events_not_a_fixture(self) -> None:
        response = self.client.post(
            "/v1/cases/stream",
            headers={"Idempotency-Key": "api-stream-test-0001"},
            json={
                "case_id": "CASE-202-26",
                "customer_id": "C-202",
                "request_text": "Run the early-failure case.",
                "requested_amount": 89,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/event-stream", response.headers["content-type"])
        self.assertIn("event: memory.completed", response.text)
        self.assertIn("event: case_evidence.completed", response.text)
        self.assertIn("event: evidence.admissibility.completed", response.text)
        self.assertIn("event: workflow.planned", response.text)
        self.assertIn("event: mcp.verification.started", response.text)
        self.assertIn("event: mcp.verification.completed", response.text)
        self.assertIn("event: workflow.step.completed", response.text)
        self.assertIn("event: workflow.completed", response.text)
        self.assertIn("event: verification.completed", response.text)
        self.assertIn("event: graph.completed", response.text)
        result_event = next(
            block for block in response.text.split("\n\n") if "event: run.result" in block
        )
        self.assertIn('"status": "CONTAINED"', result_event)

    def test_catalog_returns_twenty_six_detailed_repository_cases(self) -> None:
        response = self.client.get("/v1/cases/catalog")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["count"], 26)
        self.assertEqual(len(payload["cases"]), 26)
        primary = next(item for item in payload["cases"] if item["case_id"] == "CASE-184-26")
        self.assertEqual(primary["customer"]["display_name"], "Srinivas")
        self.assertGreaterEqual(len(primary["evidence_sources"]), 5)
        self.assertNotIn("selected_resolution", primary)
        self.assertEqual(primary["resolution_options"][0]["action"], "partial_refund")
        self.assertEqual(primary["resolution_constraints"]["default_permission_floor"], "VERIFY")
        self.assertGreater(len({item["task_type"] for item in payload["cases"]}), 12)
        self.assertEqual(
            {item["customer_segment"] for item in payload["cases"]},
            {"consumer", "enterprise"},
        )
        enterprise = next(item for item in payload["cases"] if item["case_id"] == "CASE-302-26")
        self.assertEqual(enterprise["resolution_options"][0]["action"], "rollback_deployment")
        self.assertGreaterEqual(len(enterprise["evidence_sources"]), 5)

        for case_id in ("CASE-203-26", "CASE-204-26", "CASE-206-26", "CASE-211-26", "CASE-044-26"):
            consumer_case = next(item for item in payload["cases"] if item["case_id"] == case_id)
            self.assertGreaterEqual(len(consumer_case["resolution_options"]), 2)

    def test_catalog_case_id_uses_server_facts_instead_of_browser_values(self) -> None:
        response = self.client.post(
            "/v1/cases/run",
            headers={"Idempotency-Key": "catalog-authority-0001"},
            json={
                "case_id": "CASE-184-26",
                "customer_id": "C-tampered",
                "task_type": "billing_error_refund",
                "request_text": "Tampered browser request",
                "requested_amount": 1,
                "account_type": "standard",
                "fraud_signal": True,
                "existing_credit": 0,
                "ground_truth_amount": 1,
            },
        )
        self.assertEqual(response.status_code, 200)
        run = response.json()["result"]
        self.assertEqual(run["case"]["customer_id"], "C-184")
        self.assertEqual(run["case"]["requested_amount"], 249)
        self.assertFalse(run["case"]["fraud_signal"])
        self.assertEqual(run["case"]["task_type"], "damaged_item_keep_offer")
        self.assertEqual(run["proposal"]["action_type"], "partial_refund")
        self.assertEqual(run["proposal"]["amount"], 60)
        self.assertEqual(run["permission"]["mode"], "VERIFY")
        self.assertIn("counterfactual", run)
        self.assertFalse(run["counterfactual"]["attainable"])

    def test_evidence_fault_control_blocks_without_executing(self) -> None:
        response = self.client.post(
            "/v1/experiments/evidence-fault",
            json={"case_id": "CASE-202-26", "fault_type": "corrupt_hash"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["before"]["evidence_grade"], "EXACT")
        self.assertEqual(payload["before"]["permission"], "AUTO")
        self.assertEqual(payload["after"]["evidence_grade"], "BLOCKED")
        self.assertEqual(payload["after"]["permission"], "HUMAN")
        self.assertFalse(payload["side_effects_executed"])
        self.assertTrue(payload["counterfactual"]["validated_by_policy"])

    def test_impact_summary_and_hash_chained_autonomy_ledger_are_real_api_results(self) -> None:
        impact = self.client.get("/v1/impact/summary")
        ledger = self.client.get("/v1/reliability/autonomy-ledger")

        self.assertEqual(impact.status_code, 200)
        self.assertGreater(impact.json()["verified_outcomes"], 0)
        self.assertGreater(impact.json()["customer_value_delivered"], 0)
        self.assertGreaterEqual(impact.json()["refund_first_baseline_cost"], 0)

        self.assertEqual(ledger.status_code, 200)
        ledger_payload = ledger.json()
        self.assertGreater(ledger_payload["entry_count"], 0)
        self.assertEqual(ledger_payload["entries"][0]["previous_hash"], "GENESIS")
        for previous, current in zip(
            ledger_payload["entries"],
            ledger_payload["entries"][1:],
        ):
            self.assertEqual(current["previous_hash"], previous["entry_hash"])
        self.assertEqual(ledger_payload["head_hash"], ledger_payload["entries"][-1]["entry_hash"])


if __name__ == "__main__":
    unittest.main()
