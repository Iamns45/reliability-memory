from __future__ import annotations

from ..domain import (
    AgentProposal,
    AgentRun,
    DuplicatePaymentEvidence,
    ExecutionResult,
    CustomerCase,
    ResolutionEvidence,
    VerificationResult,
)
from ..repository import MemoryRepository


class OutcomeLearningSkill:
    def __init__(self, repository: MemoryRepository) -> None:
        self.repository = repository

    @staticmethod
    def verify(
        case: CustomerCase,
        execution: ExecutionResult,
        payment_evidence: DuplicatePaymentEvidence | None,
        resolution_evidence: ResolutionEvidence | None,
        approved_action: AgentProposal | None = None,
    ) -> VerificationResult:
        has_confirmed_duplicate = bool(
            payment_evidence is not None and payment_evidence.duplicate_confirmed
        )
        ground_truth: float | int | str | None
        if approved_action is not None:
            ground_truth = approved_action.amount
            source = "human-approved resolution"
        elif has_confirmed_duplicate and payment_evidence is not None:
            ground_truth = payment_evidence.amount
            source = "confirmed duplicate payment"
        elif resolution_evidence is not None:
            ground_truth = resolution_evidence.recommended_amount
            source = "evidence-derived resolution"
        else:
            ground_truth = case.metadata.get("ground_truth_amount")
            source = "simulator ground truth"
        if ground_truth is None:
            ground_truth = case.requested_amount
        expected = round(float(ground_truth), 2)
        actual = round(execution.executed_amount, 2)
        return VerificationResult(
            success=expected == actual,
            expected_amount=expected,
            actual_amount=actual,
            reason=(
                f"Executed action matches the {source}."
                if expected == actual
                else f"Executed amount differs from the {source}."
            ),
        )

    def record(self, run: AgentRun) -> None:
        self.repository.complete_episode(run)
