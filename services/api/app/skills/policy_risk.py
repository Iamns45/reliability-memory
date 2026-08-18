from __future__ import annotations

from ..domain import (
    AgentProposal,
    DuplicatePaymentEvidence,
    PermissionDecision,
    CustomerCase,
    ReliabilityEvidence,
    ResolutionEvidence,
)
from ..policy import DeterministicPolicyEngine


class PolicyRiskSkill:
    def __init__(self, engine: DeterministicPolicyEngine) -> None:
        self.engine = engine

    def gate(
        self,
        case: CustomerCase,
        proposal: AgentProposal,
        evidence: ReliabilityEvidence,
        payment_evidence: DuplicatePaymentEvidence | None,
        resolution_evidence: ResolutionEvidence | None,
    ) -> PermissionDecision:
        return self.engine.evaluate(
            case,
            proposal,
            evidence,
            payment_evidence,
            resolution_evidence,
        )
