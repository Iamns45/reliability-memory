from __future__ import annotations

import hashlib
import json
import math
import os
from dataclasses import asdict
from typing import Any, Protocol

from .domain import (
    AgentProposal,
    DuplicatePaymentEvidence,
    CustomerCase,
    ResolutionEvidence,
    SimilarExperience,
)

SUPPORTED_ACTIONS = {
    "cost_containment",
    "database_capacity_recovery",
    "deny",
    "exchange",
    "guided_troubleshooting",
    "isolated_restore",
    "least_privilege_fix",
    "partial_refund",
    "quota_adjustment",
    "refund",
    "replacement",
    "reship",
    "rollback_deployment",
    "safety_escalation",
    "seller_investigation",
    "security_containment",
    "ship_missing_part",
    "store_credit",
    "traffic_stabilization",
    "warranty_repair",
}


class Reasoner(Protocol):
    def propose(
        self,
        case: CustomerCase,
        customer_context: dict[str, Any],
        experiences: tuple[SimilarExperience, ...],
        payment_evidence: DuplicatePaymentEvidence | None,
        resolution_evidence: ResolutionEvidence | None,
    ) -> AgentProposal: ...


class EmbeddingProvider(Protocol):
    model_id: str

    def embed(self, text: str) -> list[float]: ...


class BedrockReasoner:
    """Amazon Bedrock Converse adapter. The response is only a proposal, never permission."""

    def __init__(self, region: str | None = None, model_id: str | None = None) -> None:
        import boto3
        from botocore.config import Config

        self.client = boto3.client(
            "bedrock-runtime",
            region_name=region or os.getenv("AWS_REGION", "us-east-1"),
            config=Config(
                connect_timeout=3,
                read_timeout=25,
                retries={"max_attempts": 3, "mode": "standard"},
            ),
        )
        self.model_id = model_id or os.getenv("BEDROCK_MODEL_ID", "amazon.nova-lite-v1:0")

    def propose(
        self,
        case: CustomerCase,
        customer_context: dict[str, Any],
        experiences: tuple[SimilarExperience, ...],
        payment_evidence: DuplicatePaymentEvidence | None,
        resolution_evidence: ResolutionEvidence | None,
    ) -> AgentProposal:
        prompt = {
            "case": asdict(case),
            "customer_context": customer_context,
            "payment_evidence": asdict(payment_evidence) if payment_evidence else None,
            "resolution_evidence": (asdict(resolution_evidence) if resolution_evidence else None),
            "verified_experience": [asdict(item) for item in experiences],
            "instruction": (
                "Return JSON only: action_type, amount, reason, checks_performed. "
                "Select only an action supported by the issue-specific evidence. Match the "
                "recommended bounded amount unless explaining why evidence is incomplete. "
                "For duplicate charges, use only the exact payment evidence. Never claim permission."
            ),
        }
        response = self.client.converse(
            modelId=self.model_id,
            system=[
                {
                    "text": (
                        "You are one careful resolution-operations agent. Optimize stakeholder "
                        "recovery and bounded company cost from supplied evidence. Policy outside "
                        "the model decides permission."
                    )
                }
            ],
            messages=[{"role": "user", "content": [{"text": json.dumps(prompt, default=str)}]}],
            inferenceConfig={"maxTokens": 400, "temperature": 0.0},
        )
        text = next(
            block["text"] for block in response["output"]["message"]["content"] if "text" in block
        )
        payload = self._parse_proposal(text)
        amount = float(payload["amount"])
        if not math.isfinite(amount):
            raise ValueError("Bedrock proposal amount must be finite")

        action_type = str(payload["action_type"])
        if action_type not in SUPPORTED_ACTIONS:
            raise ValueError("Bedrock returned an unsupported action type")

        reason = str(payload["reason"]).strip()
        if not reason or len(reason) > 1_000:
            raise ValueError("Bedrock proposal reason is empty or too long")

        checks = payload.get("checks_performed", [])
        if not isinstance(checks, list) or len(checks) > 20:
            raise ValueError("Bedrock proposal checks_performed must be a short list")

        return AgentProposal(
            action_type=action_type,
            amount=round(amount, 2),
            reason=reason,
            checks_performed=tuple(str(item)[:100] for item in checks),
        )

    @staticmethod
    def _parse_proposal(text: str) -> dict[str, Any]:
        start = text.find("{")
        if start < 0:
            raise ValueError("Bedrock response did not contain a JSON object")
        payload, _ = json.JSONDecoder().raw_decode(text[start:])
        if not isinstance(payload, dict):
            raise ValueError("Bedrock response JSON must be an object")
        required_fields = {"action_type", "amount", "reason"}
        if not required_fields.issubset(payload):
            raise ValueError("Bedrock response is missing required proposal fields")
        return payload


class TitanEmbeddingProvider:
    model_id = "amazon.titan-embed-text-v2:0"

    def __init__(self, region: str | None = None) -> None:
        import boto3
        from botocore.config import Config

        self.client = boto3.client(
            "bedrock-runtime",
            region_name=region or os.getenv("AWS_REGION", "us-east-1"),
            config=Config(
                connect_timeout=3,
                read_timeout=15,
                retries={"max_attempts": 3, "mode": "standard"},
            ),
        )

    def embed(self, text: str) -> list[float]:
        response = self.client.invoke_model(
            modelId=self.model_id,
            body=json.dumps({"inputText": text, "dimensions": 1024, "normalize": True}),
        )
        embedding = [float(value) for value in json.loads(response["body"].read())["embedding"]]
        if len(embedding) != 1_024 or not all(math.isfinite(value) for value in embedding):
            raise ValueError("Titan returned an invalid 1024-dimensional embedding")
        return embedding


class DeterministicDemoReasoner:
    """Credential-free fallback that keeps the complete trust loop demonstrable."""

    def propose(
        self,
        case: CustomerCase,
        customer_context: dict[str, Any],
        experiences: tuple[SimilarExperience, ...],
        payment_evidence: DuplicatePaymentEvidence | None,
        resolution_evidence: ResolutionEvidence | None,
    ) -> AgentProposal:
        del customer_context
        checks: tuple[str, ...]

        if resolution_evidence is not None:
            amount = resolution_evidence.recommended_amount
            action_type = resolution_evidence.recommended_action
            reason = resolution_evidence.reason
            checks = tuple([*resolution_evidence.completed_sources, "resolution_economics"][:20])
        elif case.task_type == "duplicate_charge_refund":
            if payment_evidence and payment_evidence.duplicate_confirmed:
                amount = float(payment_evidence.amount or 0)
                action_type = "refund"
                reason = (
                    "Refund the second settled payment in the deterministically matched duplicate pair. "
                    "The separate goodwill credit does not reduce the duplicated charge."
                )
                checks = (
                    "authoritative_payment_ledger",
                    "exact_bill_and_payment_method_match",
                    "both_payments_settled",
                    "no_refund_reversal_or_dispute",
                    "requested_amount_matches_duplicate",
                    "similar_experience",
                )
            else:
                amount = 0.0
                action_type = "deny"
                reason = (
                    "Do not refund until the payment ledger confirms one unremediated duplicate."
                )
                checks = ("authoritative_payment_ledger", "duplicate_not_confirmed")
        else:
            amount = 0.0
            action_type = "deny"
            reason = "Withhold action until a task-matching current-evidence contract is available."
            checks = ("issue_evidence_required",)

        return AgentProposal(
            action_type=action_type,
            amount=round(amount, 2),
            reason=reason,
            confidence=None,
            checks_performed=checks,
        )


class DeterministicEmbeddingProvider:
    """Stable normalized 1024d embeddings for tests; production uses Titan."""

    DIMENSIONS = 1024
    model_id = "deterministic-demo-sha256-v1"

    def embed(self, text: str) -> list[float]:
        values: list[float] = []
        counter = 0
        while len(values) < self.DIMENSIONS:
            digest = hashlib.sha256(f"{counter}:{text}".encode()).digest()
            values.extend(((byte / 127.5) - 1.0) for byte in digest)
            counter += 1
        values = values[: self.DIMENSIONS]
        norm = math.sqrt(sum(value * value for value in values)) or 1.0
        return [value / norm for value in values]
