from __future__ import annotations

import hashlib
from collections.abc import Callable
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from ..domain import AgentProposal, ExecutionResult, WorkflowPlan, WorkflowStepResult


class SimulatedBusinessActionSkill:
    """Idempotent workflow executor with deterministic demo provider receipts."""

    def __init__(self) -> None:
        self._executions: dict[str, ExecutionResult] = {}

    def execute(
        self,
        proposal: AgentProposal,
        idempotency_key: str,
        workflow: WorkflowPlan,
        emit: Callable[[str, dict[str, Any]], None] | None = None,
    ) -> ExecutionResult:
        publish = emit or (lambda _event, _payload: None)
        if idempotency_key in self._executions:
            existing = self._executions[idempotency_key]
            publish(
                "workflow.reused",
                {
                    "workflow_id": str(existing.workflow_id),
                    "idempotency_key": idempotency_key,
                    "side_effect_executed": False,
                },
            )
            return existing

        workflow_id = uuid5(NAMESPACE_URL, f"workflow:{idempotency_key}")
        publish(
            "workflow.started",
            {
                "workflow_id": str(workflow_id),
                "workflow_name": workflow.name,
                "step_count": len(workflow.steps),
            },
        )
        step_results: list[WorkflowStepResult] = []
        artifacts: dict[str, str] = {}
        for step in workflow.steps:
            publish(
                "workflow.step.started",
                {
                    "workflow_id": str(workflow_id),
                    "step_id": step.step_id,
                    "title": step.title,
                    "system": step.system,
                    "operation": step.operation,
                },
            )
            provider_reference = _provider_reference(idempotency_key, step.step_id)
            step_result = WorkflowStepResult(
                step_id=step.step_id,
                status="succeeded",
                provider_reference=provider_reference,
                detail=f"{step.system} accepted {step.operation}.",
            )
            step_results.append(step_result)
            artifact_name = _ARTIFACT_BY_OPERATION.get(step.operation)
            if artifact_name:
                artifacts[artifact_name] = provider_reference
            publish(
                "workflow.step.completed",
                {
                    "workflow_id": str(workflow_id),
                    "step_id": step.step_id,
                    "status": step_result.status,
                    "provider_reference": provider_reference,
                },
            )

        result = ExecutionResult(
            action_id=uuid5(NAMESPACE_URL, f"action:{idempotency_key}"),
            idempotency_key=idempotency_key,
            executed_amount=proposal.amount,
            status="succeeded",
            provider_reference=_provider_reference(idempotency_key, "workflow"),
            workflow_id=workflow_id,
            workflow_name=workflow.name,
            steps=tuple(step_results),
            artifacts=artifacts,
        )
        self._executions[idempotency_key] = result
        publish(
            "workflow.completed",
            {
                "workflow_id": str(workflow_id),
                "status": result.status,
                "completed_steps": len(result.steps),
                "artifacts": result.artifacts,
            },
        )
        return result


def _provider_reference(idempotency_key: str, step_id: str) -> str:
    digest = hashlib.sha256(f"{idempotency_key}:{step_id}".encode()).hexdigest()[:12]
    return f"sim_{digest}"


_ARTIFACT_BY_OPERATION = {
    "create_replacement_order": "replacement_order",
    "create_priority_reship": "tracking_number",
    "create_exchange_return": "return_authorization",
    "create_exchange_shipment": "tracking_number",
    "create_component_shipment": "tracking_number",
    "issue_refund": "refund_receipt",
    "issue_partial_refund": "adjustment_receipt",
    "issue_store_credit": "credit_memo",
    "create_repair_authorization": "repair_authorization",
    "start_guided_session": "support_session",
    "create_safety_incident": "safety_incident",
    "open_seller_investigation": "investigation_case",
    "create_recovery_snapshot": "recovery_snapshot",
    "restore_healthy_release": "deployment_receipt",
    "apply_least_privilege_grant": "policy_change",
    "provision_temporary_read_capacity": "capacity_change",
    "apply_retry_backoff_policy": "traffic_policy",
    "open_security_incident": "security_incident",
    "restore_verified_backup": "restore_job",
    "request_temporary_quota": "quota_request",
    "create_appeal_path": "appeal_case",
}
