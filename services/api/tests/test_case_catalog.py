from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.bedrock import DeterministicDemoReasoner, DeterministicEmbeddingProvider
from app.case_catalog import analyst_case_records
from app.domain import CustomerCase
from app.repository import InMemoryMemoryRepository
from app.resolution_selector import select_resolution
from app.runtime import ReliabilityMemoryAgent


class AnalystCaseCatalogTests(unittest.TestCase):
    def test_all_twenty_six_case_expectations_match_the_real_runtime(self) -> None:
        records = analyst_case_records()
        self.assertEqual(len(records), 26)
        for record in records:
            with self.subTest(case_id=record["case_id"]):
                customer = record["customer"]
                ground_truth = record["ground_truth_amount"]
                case = CustomerCase(
                    customer_id=customer["customer_id"],
                    task_type=record["task_type"],
                    request_text=record["request_text"],
                    requested_amount=record["requested_amount"],
                    account_type=customer["account_type"],
                    region=customer["region"],
                    contract_type=customer["contract_type"],
                    fraud_signal=record["fraud_signal"],
                    existing_credit=record["existing_credit"],
                    metadata={
                        "case_id": record["case_id"],
                        **(
                            {"ground_truth_amount": ground_truth}
                            if ground_truth is not None
                            else {}
                        ),
                    },
                )
                agent = ReliabilityMemoryAgent(
                    InMemoryMemoryRepository(),
                    DeterministicDemoReasoner(),
                    DeterministicEmbeddingProvider(),
                )
                run = agent.run(case, f"catalog-test-{record['case_id']}")
                self.assertEqual(run.permission.mode.value, record["expected_mode"])
                assert run.resolution_evidence is not None
                expected_grade = (
                    "REVIEW"
                    if any(source["status"] == "warning" for source in record["evidence_sources"])
                    else "EXACT"
                )
                self.assertEqual(run.resolution_evidence.evidence_grade, expected_grade)
                self.assertEqual(
                    len(run.containment.evidence_record_ids),
                    len(record["evidence_required"]),
                )
                if record["expected_mode"] in {"AUTO", "DENY"}:
                    self.assertIsNotNone(run.execution)
                    self.assertTrue(run.containment.verified)
                    self.assertEqual(run.containment.status, "CONTAINED")
                else:
                    self.assertIsNone(run.execution)
                    self.assertFalse(run.containment.verified)

    def test_catalog_uses_issue_specific_sources_and_resolution_economics(self) -> None:
        records = analyst_case_records()
        self.assertGreaterEqual(len({record["task_type"] for record in records}), 12)
        self.assertGreaterEqual(
            len(
                {
                    select_resolution(
                        record["resolution_options"], record["resolution_constraints"]
                    ).option["action"]
                    for record in records
                }
            ),
            8,
        )
        for record in records:
            with self.subTest(case_id=record["case_id"]):
                self.assertEqual(
                    set(record["evidence_required"]),
                    {source["key"] for source in record["evidence_sources"]},
                )
                selection = select_resolution(
                    record["resolution_options"], record["resolution_constraints"]
                )
                self.assertGreaterEqual(selection.option["customer_value"], 0)
                self.assertGreaterEqual(selection.option["company_cost"], 0)
                self.assertTrue(selection.rationale)
                for source in record["evidence_sources"]:
                    self.assertEqual(source["integrity"], "sha256_verified")
                    self.assertTrue(source["source_record_id"].startswith("EV-CASE-"))
                    self.assertEqual(source["correlation"]["case_id"], record["case_id"])


if __name__ == "__main__":
    unittest.main()
