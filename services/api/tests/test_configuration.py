from __future__ import annotations

import sys
import unittest
from pathlib import Path

from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.bedrock import BedrockReasoner
from app.main import CustomerCaseRequest
from app.settings import Settings


class SettingsTests(unittest.TestCase):
    def test_environment_values_are_normalized(self) -> None:
        settings = Settings.from_environment(
            {
                "DATABASE_URL": "postgresql://example",
                "USE_BEDROCK": "yes",
                "AWS_REGION": "us-west-2",
                "CORS_ORIGINS": "https://one.example, https://two.example ",
            }
        )

        self.assertTrue(settings.use_bedrock)
        self.assertEqual(settings.aws_region, "us-west-2")
        self.assertEqual(
            settings.cors_origins,
            ("https://one.example", "https://two.example"),
        )

    def test_invalid_boolean_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            Settings.from_environment({"USE_BEDROCK": "sometimes"})

    def test_required_mcp_rejects_missing_service_account_configuration(self) -> None:
        with self.assertRaisesRegex(ValueError, "service-account API key and cluster ID"):
            Settings.from_environment({"COCKROACH_MCP_REQUIRED": "true"})

    def test_local_mcp_configuration_is_normalized(self) -> None:
        settings = Settings.from_environment(
            {
                "COCKROACH_MCP_API_KEY": "test-service-account-key",
                "COCKROACH_MCP_CLUSTER_ID": "cluster-test-123",
                "COCKROACH_MCP_REQUIRED": "true",
                "COCKROACH_MCP_TIMEOUT_SECONDS": "9.5",
            }
        )

        self.assertTrue(settings.mcp_configured)
        self.assertTrue(settings.mcp_required)
        self.assertEqual(settings.mcp_timeout_seconds, 9.5)


class RequestValidationTests(unittest.TestCase):
    def test_unknown_request_fields_are_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            CustomerCaseRequest.model_validate(
                {
                    "customer_id": "C-184",
                    "request_text": "I was charged twice.",
                    "requested_amount": 79,
                    "unexpected": True,
                }
            )

    def test_credit_cannot_exceed_requested_amount(self) -> None:
        with self.assertRaises(ValidationError):
            CustomerCaseRequest(
                customer_id="C-184",
                request_text="I was charged twice.",
                requested_amount=79,
                existing_credit=80,
            )


class BedrockResponseValidationTests(unittest.TestCase):
    def test_json_object_is_extracted_without_greedy_matching(self) -> None:
        payload = BedrockReasoner._parse_proposal(
            'Result: {"action_type":"refund","amount":59,"reason":"verified"} trailing'
        )
        self.assertEqual(payload["amount"], 59)

    def test_missing_proposal_fields_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            BedrockReasoner._parse_proposal('{"amount":59}')


if __name__ == "__main__":
    unittest.main()
