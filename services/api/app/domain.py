from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4


class RiskLevel(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class DecisionMode(StrEnum):
    AUTO = "AUTO"
    VERIFY = "VERIFY"
    HUMAN = "HUMAN"
    DENY = "DENY"


class OutcomeStatus(StrEnum):
    PENDING = "PENDING"
    VERIFIED_SUCCESS = "VERIFIED_SUCCESS"
    VERIFIED_FAILURE = "VERIFIED_FAILURE"
    HUMAN_CORRECTED = "HUMAN_CORRECTED"


@dataclass(frozen=True)
class CustomerCase:
    customer_id: str
    task_type: str
    request_text: str
    requested_amount: float
    account_type: str = "standard"
    region: str = "US"
    contract_type: str = "standard"
    fraud_signal: bool = False
    existing_credit: float = 0.0
    memory_enabled: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AgentProposal:
    action_type: str
    amount: float
    reason: str
    confidence: float | None = None
    checks_performed: tuple[str, ...] = ()


@dataclass(frozen=True)
class ReliabilityEvidence:
    reliability: float
    verified_cases: int
    successes: int
    failures: int
    human_overrides: int
    average_similarity: float
    evidence_quality: str
    novelty: str
    relevant_corrections: int = 0
    memory_enabled: bool = True
    last_verified_at: datetime | None = None


@dataclass(frozen=True)
class PermissionDecision:
    mode: DecisionMode
    risk: RiskLevel
    policy_version: str
    reasons: tuple[str, ...]
    rule_id: str


@dataclass(frozen=True)
class CounterfactualRequirement:
    """One inspectable change required to reach the requested permission mode."""

    signal: str
    current: str
    required: str
    delta: str
    rationale: str


@dataclass(frozen=True)
class DecisionCounterfactual:
    """Policy-validated explanation of whether and how a decision could become AUTO."""

    target_mode: DecisionMode
    attainable: bool
    validated_by_policy: bool
    resulting_mode: DecisionMode
    requirements: tuple[CounterfactualRequirement, ...]
    hard_boundaries: tuple[str, ...]
    summary: str


@dataclass(frozen=True)
class SimilarExperience:
    episode_id: UUID
    summary: str
    similarity: float
    verified_success: bool
    correction_lesson: str | None = None


@dataclass(frozen=True)
class DuplicatePaymentEvidence:
    """Deterministic evidence derived from the authoritative payment ledger."""

    duplicate_confirmed: bool
    checked_payments: int
    original_payment_id: str | None
    duplicate_payment_id: str | None
    amount: float | None
    currency: str | None
    subscription_reference: str | None
    capture_gap_seconds: int | None
    matched_on: tuple[str, ...]
    safeguards: tuple[str, ...]
    blocking_reasons: tuple[str, ...]


@dataclass(frozen=True)
class ResolutionEvidence:
    """Issue-specific evidence and bounded resolution economics."""

    issue_type: str
    evidence_complete: bool
    autonomy_eligible: bool
    evidence_grade: str
    evidence_as_of: str
    required_sources: tuple[str, ...]
    completed_sources: tuple[str, ...]
    source_checks: tuple[dict[str, Any], ...]
    recommended_action: str
    recommended_amount: float
    company_cost: float
    customer_value: float
    permission_floor: DecisionMode
    auto_cost_cap: float
    safety_critical: bool
    customer_goal: str
    business_guardrail: str
    positive_facts: tuple[str, ...]
    blocking_reasons: tuple[str, ...]
    alternatives: tuple[dict[str, Any], ...]
    selection_method: str
    selection_score: float
    selection_rationale: str
    eligible_option_count: int
    value_components: tuple[dict[str, Any], ...]
    reason: str
    lesson: str


@dataclass(frozen=True)
class WorkflowStepPlan:
    """A bounded operation the agent is authorized to execute after permission."""

    step_id: str
    title: str
    system: str
    operation: str
    detail: str
    reversible: bool


@dataclass(frozen=True)
class WorkflowPlan:
    """Issue-specific execution contract produced before any side effect occurs."""

    workflow_type: str
    name: str
    objective: str
    steps: tuple[WorkflowStepPlan, ...]
    compensation: str


@dataclass(frozen=True)
class WorkflowStepResult:
    """Provider receipt for one completed workflow operation."""

    step_id: str
    status: str
    provider_reference: str
    detail: str


@dataclass(frozen=True)
class ExecutionResult:
    action_id: UUID
    idempotency_key: str
    executed_amount: float
    status: str
    provider_reference: str
    workflow_id: UUID
    workflow_name: str
    steps: tuple[WorkflowStepResult, ...]
    artifacts: dict[str, str]


@dataclass(frozen=True)
class VerificationResult:
    success: bool
    expected_amount: float
    actual_amount: float
    reason: str


@dataclass(frozen=True)
class ContainmentProof:
    """Machine-readable proof that a case was resolved inside its earned boundary."""

    status: str
    level: str
    root_cause: str
    evidence_grade: str
    evidence_record_ids: tuple[str, ...]
    required_evidence_count: int
    admissible_evidence_count: int
    decision_rule: str
    workflow_id: UUID | None
    executed_operations: int
    verified: bool
    human_minutes_avoided: int
    estimated_company_cost: float
    customer_value: float
    reopen_monitor_until: str


@dataclass(frozen=True)
class McpVerificationReceipt:
    """Independent, read-only proof returned by CockroachDB Cloud Managed MCP."""

    provider: str
    endpoint: str
    cluster_scope: str
    database: str
    tool_name: str
    required: bool
    verified: bool
    episode_id: UUID
    observed_episode_id: str | None
    observed_decision: str | None
    observed_policy_version: str | None
    vector_check_performed: bool
    expected_neighbor_ids: tuple[str, ...]
    vector_neighbor_ids: tuple[str, ...]
    matching_neighbor_ids: tuple[str, ...]
    checked_at: datetime
    receipt_hash: str
    failure_reason: str | None = None


@dataclass(frozen=True)
class AgentRun:
    run_id: UUID
    case: CustomerCase
    proposal: AgentProposal
    evidence: ReliabilityEvidence
    permission: PermissionDecision
    counterfactual: DecisionCounterfactual
    similar_experiences: tuple[SimilarExperience, ...]
    payment_evidence: DuplicatePaymentEvidence | None
    resolution_evidence: ResolutionEvidence | None
    workflow_plan: WorkflowPlan
    containment: ContainmentProof
    execution: ExecutionResult | None
    verification: VerificationResult | None
    mcp_verification: McpVerificationReceipt | None
    created_at: datetime
    idempotency_reused: bool = False

    @classmethod
    def create(
        cls,
        case: CustomerCase,
        proposal: AgentProposal,
        evidence: ReliabilityEvidence,
        permission: PermissionDecision,
        counterfactual: DecisionCounterfactual,
        similar_experiences: tuple[SimilarExperience, ...],
        payment_evidence: DuplicatePaymentEvidence | None = None,
        resolution_evidence: ResolutionEvidence | None = None,
        workflow_plan: WorkflowPlan | None = None,
        containment: ContainmentProof | None = None,
        execution: ExecutionResult | None = None,
        verification: VerificationResult | None = None,
        mcp_verification: McpVerificationReceipt | None = None,
    ) -> "AgentRun":
        if workflow_plan is None:
            raise ValueError("workflow_plan is required")
        if containment is None:
            raise ValueError("containment is required")
        return cls(
            run_id=uuid4(),
            case=case,
            proposal=proposal,
            evidence=evidence,
            permission=permission,
            counterfactual=counterfactual,
            similar_experiences=similar_experiences,
            payment_evidence=payment_evidence,
            resolution_evidence=resolution_evidence,
            workflow_plan=workflow_plan,
            containment=containment,
            execution=execution,
            verification=verification,
            mcp_verification=mcp_verification,
            created_at=datetime.now(timezone.utc),
        )
