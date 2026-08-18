from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from copy import deepcopy
from dataclasses import asdict, replace
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from .bedrock import EmbeddingProvider, Reasoner
from .counterfactual import explain_auto_counterfactual
from .domain import (
    AgentProposal,
    AgentRun,
    ContainmentProof,
    CustomerCase,
    DecisionMode,
    PermissionDecision,
    ResolutionEvidence,
    SimilarExperience,
)
from .mcp_memory import DisabledMcpVerifier, McpVerifier
from .payment_evidence import assess_duplicate_payment
from .policy import DeterministicPolicyEngine
from .reliability import ReliabilityEngine
from .resolution_evidence import assess_resolution_evidence
from .repository import MemoryRepository
from .skills.business_action import SimulatedBusinessActionSkill
from .skills.customer_context import CustomerContextSkill
from .skills.experience_memory import ExperienceMemorySkill
from .skills.outcome_learning import OutcomeLearningSkill
from .skills.policy_risk import PolicyRiskSkill
from .workflows import build_workflow_plan


class ReliabilityMemoryAgent:
    """One agent with five skills: observe, remember, propose, gate, act, verify, learn."""

    def __init__(
        self,
        repository: MemoryRepository,
        reasoner: Reasoner,
        embeddings: EmbeddingProvider,
        mcp_verifier: McpVerifier | None = None,
    ) -> None:
        self.repository = repository
        self.reasoner = reasoner
        self.embeddings = embeddings
        self.mcp_verifier = mcp_verifier or DisabledMcpVerifier()
        self.customer_context = CustomerContextSkill(repository)
        self.experience_memory = ExperienceMemorySkill(repository, embeddings, ReliabilityEngine())
        self.policy_risk = PolicyRiskSkill(DeterministicPolicyEngine())
        self.business_action = SimulatedBusinessActionSkill()
        self.outcome_learning = OutcomeLearningSkill(repository)

    def run(
        self,
        case: CustomerCase,
        request_id: str,
        emit: Callable[[str, dict[str, Any]], None] | None = None,
    ) -> AgentRun:
        publish = emit or (lambda _event, _payload: None)
        publish("context.started", {"customer_id": case.customer_id})
        customer_context = self.customer_context.load(case.customer_id)
        case = self._apply_authoritative_customer(case, customer_context)
        publish(
            "context.completed",
            {
                "customer_id": case.customer_id,
                "event_count": len(customer_context.get("events", [])),
            },
        )
        publish("case_evidence.started", {"task_type": case.task_type})
        resolution_evidence = assess_resolution_evidence(case, customer_context)
        publish(
            "case_evidence.completed",
            (
                asdict(resolution_evidence)
                if resolution_evidence is not None
                else {"not_applicable": True, "task_type": case.task_type}
            ),
        )
        if resolution_evidence is not None:
            publish(
                "evidence.admissibility.completed",
                {
                    "grade": resolution_evidence.evidence_grade,
                    "autonomy_eligible": resolution_evidence.autonomy_eligible,
                    "evidence_as_of": resolution_evidence.evidence_as_of,
                    "record_ids": self._evidence_record_ids(resolution_evidence),
                    "blocking_reasons": resolution_evidence.blocking_reasons,
                },
            )
        publish("payments.started", {"customer_id": case.customer_id})
        payment_evidence = assess_duplicate_payment(case, customer_context)
        publish(
            "payments.completed",
            (
                asdict(payment_evidence)
                if payment_evidence is not None
                else {"not_applicable": True, "task_type": case.task_type}
            ),
        )
        publish(
            "memory.started",
            {"enabled": case.memory_enabled, "task_type": case.task_type},
        )
        experiences, evidence, embedding = self.experience_memory.retrieve(case)
        publish(
            "memory.completed",
            {
                "enabled": case.memory_enabled,
                "experience_count": len(experiences),
                "verified_cases": evidence.verified_cases,
                "reliability": evidence.reliability,
                "relevant_corrections": evidence.relevant_corrections,
            },
        )
        publish("proposal.started", {"reasoner": type(self.reasoner).__name__})
        proposal = self.reasoner.propose(
            case,
            customer_context,
            experiences,
            payment_evidence,
            resolution_evidence,
        )
        proposal, correction_replayed = self._replay_verified_correction(
            case,
            experiences,
            proposal,
            resolution_evidence,
        )
        if correction_replayed:
            publish(
                "correction.replayed",
                {
                    "action_type": proposal.action_type,
                    "amount": proposal.amount,
                    "source": "verified_human_correction",
                },
            )
        publish(
            "proposal.completed",
            {
                "action_type": proposal.action_type,
                "amount": proposal.amount,
                "reason": proposal.reason,
            },
        )
        publish("policy.started", {"policy_version": DeterministicPolicyEngine.VERSION})
        permission = self.policy_risk.gate(
            case,
            proposal,
            evidence,
            payment_evidence,
            resolution_evidence,
        )
        counterfactual = explain_auto_counterfactual(
            case,
            proposal,
            evidence,
            resolution_evidence,
            permission,
        )
        publish(
            "policy.completed",
            {
                "mode": permission.mode.value,
                "risk": permission.risk.value,
                "rule_id": permission.rule_id,
                "policy_version": permission.policy_version,
            },
        )
        workflow_plan = build_workflow_plan(case, proposal, resolution_evidence)
        publish(
            "workflow.planned",
            {
                "workflow_type": workflow_plan.workflow_type,
                "workflow_name": workflow_plan.name,
                "step_count": len(workflow_plan.steps),
            },
        )
        containment = self._containment_proof(
            case,
            permission,
            resolution_evidence,
            workflow_plan,
        )
        run = AgentRun.create(
            case,
            proposal,
            evidence,
            permission,
            counterfactual,
            experiences,
            payment_evidence=payment_evidence,
            resolution_evidence=resolution_evidence,
            workflow_plan=workflow_plan,
            containment=containment,
        )

        # Persist the authorization decision before the external side effect.
        # The provider call remains outside the CockroachDB transaction.
        decision_record = self.repository.create_decision_record(
            run,
            request_id,
            embedding,
            self.embeddings.model_id,
        )
        if not decision_record.created:
            run = replace(
                run,
                run_id=decision_record.episode_id,
                idempotency_reused=True,
            )
            publish(
                "decision.reused",
                {
                    "episode_id": str(run.run_id),
                    "side_effect_executed": False,
                },
            )
            return run
        publish(
            "decision.persisted",
            {"episode_id": str(run.run_id), "mode": permission.mode.value},
        )

        expected_neighbor_ids = tuple(
            str(experience.episode_id)
            for experience in experiences
            if experience.correction_lesson is None
        )
        publish(
            "mcp.verification.started",
            {
                "episode_id": str(run.run_id),
                "provider": self.mcp_verifier.provider,
                "required": self.mcp_verifier.required,
                "checks": ["persisted-episode", "vector-neighbor-overlap"],
            },
        )
        mcp_receipt = self.mcp_verifier.verify(run, expected_neighbor_ids)
        if (
            mcp_receipt.required
            and not mcp_receipt.verified
            and permission.mode
            in {
                DecisionMode.AUTO,
                DecisionMode.DENY,
            }
        ):
            permission = PermissionDecision(
                mode=DecisionMode.HUMAN,
                risk=permission.risk,
                policy_version=permission.policy_version,
                reasons=(
                    *permission.reasons,
                    "Required Managed MCP persistence and vector-memory proof did not pass.",
                ),
                rule_id="mcp-verification-required",
            )
            counterfactual = replace(
                counterfactual,
                attainable=False,
                resulting_mode=DecisionMode.HUMAN,
                hard_boundaries=(
                    *counterfactual.hard_boundaries,
                    "Managed MCP must independently verify the episode and vector evidence.",
                ),
                summary=(
                    "Autonomous execution is withheld until Managed MCP verification succeeds "
                    "or a reviewer approves the prefilled resolution."
                ),
            )
            containment = self._containment_proof(
                case,
                permission,
                resolution_evidence,
                workflow_plan,
            )
            publish(
                "policy.contracted",
                {
                    "episode_id": str(run.run_id),
                    "mode": permission.mode.value,
                    "rule_id": permission.rule_id,
                    "reason": mcp_receipt.failure_reason,
                },
            )
        run = replace(
            run,
            permission=permission,
            counterfactual=counterfactual,
            containment=containment,
            mcp_verification=mcp_receipt,
        )
        self.repository.record_mcp_verification(run)
        publish(
            "mcp.verification.completed",
            {
                "episode_id": str(run.run_id),
                "verified": mcp_receipt.verified,
                "required": mcp_receipt.required,
                "tool_name": mcp_receipt.tool_name,
                "observed_episode_id": mcp_receipt.observed_episode_id,
                "vector_check_performed": mcp_receipt.vector_check_performed,
                "vector_neighbor_count": len(mcp_receipt.vector_neighbor_ids),
                "matching_neighbor_count": len(mcp_receipt.matching_neighbor_ids),
                "receipt_hash": mcp_receipt.receipt_hash,
                "failure_reason": mcp_receipt.failure_reason,
            },
        )

        executable_denial = bool(
            permission.mode == DecisionMode.DENY
            and proposal.action_type == "deny"
            and resolution_evidence is not None
            and resolution_evidence.evidence_complete
            and resolution_evidence.recommended_action == "deny"
            and proposal.amount == resolution_evidence.recommended_amount
        )
        if permission.mode != DecisionMode.AUTO and not executable_denial:
            publish(
                "action.withheld",
                {"episode_id": str(run.run_id), "mode": permission.mode.value},
            )
            return run

        publish("action.started", {"idempotency_key": request_id})
        execution = self.business_action.execute(
            proposal,
            request_id,
            workflow_plan,
            emit=publish,
        )
        publish(
            "action.completed",
            {
                "action_id": str(execution.action_id),
                "provider_reference": execution.provider_reference,
                "amount": execution.executed_amount,
            },
        )
        publish("verification.started", {"episode_id": str(run.run_id)})
        verification = self.outcome_learning.verify(
            case,
            execution,
            payment_evidence,
            resolution_evidence,
        )
        completed = replace(
            run,
            execution=execution,
            verification=verification,
            containment=self._containment_proof(
                case,
                permission,
                resolution_evidence,
                workflow_plan,
                execution=execution,
                verification_success=verification.success,
            ),
        )
        self.outcome_learning.record(completed)
        publish(
            "verification.completed",
            {
                "success": verification.success,
                "expected_amount": verification.expected_amount,
                "actual_amount": verification.actual_amount,
            },
        )
        return completed

    def execute_reviewed_workflow(
        self,
        run: AgentRun,
        human_action: dict[str, Any],
        emit: Callable[[str, dict[str, Any]], None] | None = None,
    ) -> AgentRun:
        """Execute a human-approved action using the same bounded, idempotent workflow path."""

        publish = emit or (lambda _event, _payload: None)
        approved = AgentProposal(
            action_type=str(human_action["action_type"]),
            amount=round(float(human_action["amount"]), 2),
            reason="Human-approved resolution executed from the prefilled review summary.",
            checks_performed=("human_permission_granted",),
        )
        workflow_plan = build_workflow_plan(run.case, approved, run.resolution_evidence)
        reviewed = replace(run, proposal=approved, workflow_plan=workflow_plan)
        idempotency_key = f"review:{run.run_id}"
        publish(
            "action.started",
            {
                "idempotency_key": idempotency_key,
                "authorization": "human_review",
            },
        )
        execution = self.business_action.execute(
            approved,
            idempotency_key,
            workflow_plan,
            emit=publish,
        )
        publish(
            "action.completed",
            {
                "action_id": str(execution.action_id),
                "provider_reference": execution.provider_reference,
                "amount": execution.executed_amount,
                "authorization": "human_review",
            },
        )
        publish("verification.started", {"episode_id": str(run.run_id)})
        verification = self.outcome_learning.verify(
            run.case,
            execution,
            run.payment_evidence,
            run.resolution_evidence,
            approved_action=approved,
        )
        completed = replace(
            reviewed,
            execution=execution,
            verification=verification,
            containment=self._containment_proof(
                run.case,
                run.permission,
                run.resolution_evidence,
                workflow_plan,
                execution=execution,
                verification_success=verification.success,
                supervised=True,
            ),
        )
        self.outcome_learning.record(completed)
        publish(
            "verification.completed",
            {
                "success": verification.success,
                "expected_amount": verification.expected_amount,
                "actual_amount": verification.actual_amount,
                "authorization": "human_review",
            },
        )
        return completed

    def record_human_correction(
        self,
        episode_id: UUID,
        human_action: dict[str, object],
        reason: str,
        lesson: str,
    ) -> UUID:
        embedding = self.embeddings.embed(f"human correction | {reason} | {lesson}")
        return self.repository.record_human_correction(
            episode_id,
            human_action,
            reason,
            lesson,
            embedding,
            self.embeddings.model_id,
        )

    def save_review_summary(self, episode_id: UUID, summary: dict[str, Any]) -> None:
        self.repository.save_review_summary(episode_id, summary)

    def list_analyst_cases(self) -> list[dict[str, Any]]:
        return self.repository.list_analyst_cases()

    def get_analyst_case(self, case_id: str) -> dict[str, Any] | None:
        return self.repository.get_analyst_case(case_id)

    def compare_memory(self, case: CustomerCase) -> dict[str, Any]:
        with_memory = self._evaluate(replace(case, memory_enabled=True))
        without_memory = self._evaluate(replace(case, memory_enabled=False))
        return {
            "with_memory": asdict(with_memory),
            "without_memory": asdict(without_memory),
            "difference": {
                "permission_changed": with_memory.permission.mode != without_memory.permission.mode,
                "proposal_amount_delta": round(
                    with_memory.proposal.amount - without_memory.proposal.amount,
                    2,
                ),
                "reliability_delta": round(
                    with_memory.evidence.reliability - without_memory.evidence.reliability,
                    4,
                ),
            },
        }

    def compare_policies(self, case: CustomerCase) -> dict[str, Any]:
        customer_context = self.customer_context.load(case.customer_id)
        case = self._apply_authoritative_customer(case, customer_context)
        payment_evidence = assess_duplicate_payment(case, customer_context)
        resolution_evidence = assess_resolution_evidence(case, customer_context)
        experiences, evidence, _embedding = self.experience_memory.retrieve(case)
        proposal = self.reasoner.propose(
            case,
            customer_context,
            experiences,
            payment_evidence,
            resolution_evidence,
        )
        proposal, _correction_replayed = self._replay_verified_correction(
            case,
            experiences,
            proposal,
            resolution_evidence,
        )
        if (
            case.task_type == "duplicate_charge_refund"
            and payment_evidence is not None
            and not payment_evidence.duplicate_confirmed
        ):
            proposal = AgentProposal(
                action_type="refund",
                amount=case.requested_amount,
                reason=(
                    "Counterfactual candidate held constant to compare legacy amount-first "
                    "policy with payment-ledger-first policy."
                ),
                checks_performed=("policy_comparison_only",),
            )
        legacy = DeterministicPolicyEngine("customer-resolution-v4.9").evaluate(
            case,
            proposal,
            evidence,
            payment_evidence,
            resolution_evidence,
        )
        current = DeterministicPolicyEngine().evaluate(
            case,
            proposal,
            evidence,
            payment_evidence,
            resolution_evidence,
        )
        return {
            "proposal": asdict(proposal),
            "evidence": asdict(evidence),
            "payment_evidence": asdict(payment_evidence) if payment_evidence else None,
            "resolution_evidence": (asdict(resolution_evidence) if resolution_evidence else None),
            "customer-resolution-v4.9": asdict(legacy),
            "customer-resolution-v5.0": asdict(current),
            "changed": legacy.mode != current.mode,
        }

    def record_delayed_outcome(
        self,
        episode_id: UUID,
        task_type: str,
        success: bool,
        reason: str,
    ) -> dict[str, Any]:
        before = self.experience_memory.reliability.evaluate(
            self.repository.get_historical_stats(task_type)
        )
        outcome_id = self.repository.record_delayed_outcome(episode_id, success, reason)
        after = self.experience_memory.reliability.evaluate(
            self.repository.get_historical_stats(task_type)
        )
        return {
            "outcome_id": outcome_id,
            "episode_id": episode_id,
            "success": success,
            "reliability_before": before.reliability,
            "reliability_after": after.reliability,
            "permission_may_contract": after.reliability < before.reliability,
        }

    def evidence_receipt(self, episode_id: UUID) -> dict[str, Any]:
        return self.repository.get_evidence_receipt(episode_id)

    def reliability_envelope(self) -> list[dict[str, Any]]:
        contexts = self.list_analyst_cases()[:8]
        rows: list[dict[str, Any]] = []
        for record in contexts:
            customer = record["customer"]
            case = CustomerCase(
                customer_id=str(customer["customer_id"]),
                task_type=str(record["task_type"]),
                request_text=str(record["request_text"]),
                requested_amount=float(record["requested_amount"]),
                account_type=str(customer["account_type"]),
                region=str(customer["region"]),
                contract_type=str(customer["contract_type"]),
                fraud_signal=bool(record["fraud_signal"]),
                metadata={
                    "case_id": str(record["case_id"]),
                    "case_evidence": self._case_evidence_from_record(record),
                },
            )
            stats = self.repository.get_historical_stats(case.task_type)
            customer_context = self.customer_context.load(case.customer_id)
            case = self._apply_authoritative_customer(case, customer_context)
            payment_evidence = assess_duplicate_payment(case, customer_context)
            resolution_evidence = assess_resolution_evidence(case, customer_context)
            evidence = self.experience_memory.reliability.evaluate(
                stats,
                novelty="HIGH" if stats.verified_cases < 20 else "LOW",
            )
            proposal = AgentProposal(
                resolution_evidence.recommended_action if resolution_evidence else "deny",
                resolution_evidence.recommended_amount if resolution_evidence else 0,
                resolution_evidence.reason if resolution_evidence else "No evidence",
            )
            decision = DeterministicPolicyEngine().evaluate(
                case,
                proposal,
                evidence,
                payment_evidence,
                resolution_evidence,
            )
            rows.append(
                {
                    "context": str(record["title"]),
                    "task_type": case.task_type,
                    "constraints": {
                        "amount": proposal.amount,
                        "account_type": case.account_type,
                        "contract_type": case.contract_type,
                        "company_cost": (
                            resolution_evidence.company_cost if resolution_evidence else None
                        ),
                    },
                    "evidence": asdict(evidence),
                    "payment_evidence": (asdict(payment_evidence) if payment_evidence else None),
                    "resolution_evidence": (
                        asdict(resolution_evidence) if resolution_evidence else None
                    ),
                    "permission": asdict(decision),
                }
            )
        return rows

    def impact_summary(self) -> dict[str, Any]:
        """Aggregate realized economics over independently verified task outcomes."""

        stats_by_task = self.repository.get_all_historical_stats()
        seen_tasks: set[str] = set()
        verified_outcomes = 0
        successful_outcomes = 0
        customer_value = 0.0
        company_cost = 0.0
        refund_first_cost = 0.0
        contexts = 0

        for record in self.list_analyst_cases():
            task_type = str(record["task_type"])
            if task_type in seen_tasks:
                continue
            seen_tasks.add(task_type)
            stats = stats_by_task.get(task_type)
            if stats is None or stats.verified_cases <= 0:
                continue
            case = self._catalog_case(record)
            resolution = assess_resolution_evidence(
                case,
                {"case_evidence": self._case_evidence_from_record(record)},
            )
            if resolution is None:
                continue
            verified_outcomes += stats.verified_cases
            successful_outcomes += stats.successes
            customer_value += resolution.customer_value * stats.successes
            company_cost += resolution.company_cost * stats.successes
            refund_first_cost += case.requested_amount * stats.successes
            contexts += 1

        avoided_cost = max(0.0, refund_first_cost - company_cost)
        return {
            "currency": "USD",
            "verified_outcomes": verified_outcomes,
            "successful_outcomes": successful_outcomes,
            "task_contexts": contexts,
            "customer_value_delivered": round(customer_value, 2),
            "evidence_selected_company_cost": round(company_cost, 2),
            "refund_first_baseline_cost": round(refund_first_cost, 2),
            "estimated_cost_avoided": round(avoided_cost, 2),
            "methodology": (
                "For each task, multiply independently verified successes by the current "
                "evidence-selected customer value and company cost. The comparison baseline "
                "refunds the full case value for every successful resolution."
            ),
        }

    def autonomy_ledger(self) -> dict[str, Any]:
        """Return a dated, hash-chained register of the current authority boundary."""

        rows = sorted(self.reliability_envelope(), key=lambda item: str(item["task_type"]))
        previous_hash = "GENESIS"
        entries: list[dict[str, Any]] = []
        for index, row in enumerate(rows, start=1):
            evidence = row["evidence"]
            permission = row["permission"]
            effective_at = evidence.get("last_verified_at") or "not-yet-earned"
            event = {
                "sequence": index,
                "effective_at": str(effective_at),
                "task_type": row["task_type"],
                "context": row["context"],
                "event": (
                    "AUTONOMY_EARNED"
                    if permission["mode"] == DecisionMode.AUTO
                    else "AUTONOMY_WITHHELD"
                ),
                "mode": permission["mode"],
                "rule_id": permission["rule_id"],
                "policy_version": permission["policy_version"],
                "verified_cases": evidence["verified_cases"],
                "reliability": evidence["reliability"],
                "previous_hash": previous_hash,
            }
            canonical = json.dumps(event, sort_keys=True, separators=(",", ":"), default=str)
            entry_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
            event["entry_hash"] = entry_hash
            entries.append(event)
            previous_hash = entry_hash
        return {
            "ledger_version": "autonomy-ledger-v1",
            "policy_version": DeterministicPolicyEngine.VERSION,
            "entry_count": len(entries),
            "head_hash": previous_hash,
            "entries": entries,
        }

    def simulate_evidence_fault(
        self,
        case: CustomerCase,
        fault_type: str,
        source_key: str | None = None,
    ) -> dict[str, Any]:
        """Evaluate a corrupted evidence copy without persistence or workflow execution."""

        customer_context = self.customer_context.load(case.customer_id)
        case = self._apply_authoritative_customer(case, customer_context)
        baseline = assess_resolution_evidence(case, customer_context)
        if baseline is None:
            raise ValueError("Evidence fault simulation requires a task-matching evidence bundle")

        raw_bundle = customer_context.get("case_evidence") or case.metadata.get("case_evidence")
        if not isinstance(raw_bundle, dict):
            raise ValueError("Evidence bundle is unavailable")
        faulted_bundle = deepcopy(raw_bundle)
        sources = faulted_bundle.get("evidence_sources")
        if not isinstance(sources, list) or not sources:
            raise ValueError("Evidence bundle has no source records")
        target = next(
            (
                source
                for source in sources
                if isinstance(source, dict)
                and (source_key is None or str(source.get("key")) == source_key)
            ),
            None,
        )
        if not isinstance(target, dict):
            raise ValueError("Requested evidence source was not found")

        if fault_type == "corrupt_hash":
            current_hash = str(target.get("integrity_hash") or "")
            target["integrity_hash"] = (
                "1" if current_hash.startswith("0") else "0"
            ) + current_hash[1:]
        elif fault_type == "stale_record":
            target["observed_at"] = "2025-01-01T00:00:00Z"
            target["max_age_seconds"] = 60
        elif fault_type == "mismatch_correlation":
            correlation = target.get("correlation")
            if not isinstance(correlation, dict):
                correlation = {}
                target["correlation"] = correlation
            correlation["customer_id"] = "C-UNRELATED"
        else:
            raise ValueError("Unsupported evidence fault type")

        faulted_context = {**customer_context, "case_evidence": faulted_bundle}
        faulted = assess_resolution_evidence(case, faulted_context)
        if faulted is None:  # pragma: no cover - task type is unchanged by supported faults
            raise RuntimeError("Faulted evidence packet could not be assessed")
        stats = self.repository.get_historical_stats(case.task_type)
        reliability = self.experience_memory.reliability.evaluate(
            stats,
            novelty="HIGH" if stats.verified_cases < 20 else "LOW",
        )
        proposal = AgentProposal(
            action_type=baseline.recommended_action,
            amount=baseline.recommended_amount,
            reason=baseline.reason,
            checks_performed=("evidence_fault_simulation",),
        )
        baseline_permission = DeterministicPolicyEngine().evaluate(
            case,
            proposal,
            reliability,
            resolution_evidence=baseline,
        )
        faulted_permission = DeterministicPolicyEngine().evaluate(
            case,
            proposal,
            reliability,
            resolution_evidence=faulted,
        )
        counterfactual = explain_auto_counterfactual(
            case,
            proposal,
            reliability,
            faulted,
            faulted_permission,
        )
        return {
            "simulation": fault_type,
            "source_key": target.get("key"),
            "source_record_id": target.get("source_record_id"),
            "before": {
                "evidence_grade": baseline.evidence_grade,
                "permission": baseline_permission.mode,
                "rule_id": baseline_permission.rule_id,
            },
            "after": {
                "evidence_grade": faulted.evidence_grade,
                "permission": faulted_permission.mode,
                "rule_id": faulted_permission.rule_id,
                "blocking_reasons": faulted.blocking_reasons,
            },
            "counterfactual": asdict(counterfactual),
            "side_effects_executed": False,
        }

    def _evaluate(self, case: CustomerCase) -> AgentRun:
        customer_context = self.customer_context.load(case.customer_id)
        case = self._apply_authoritative_customer(case, customer_context)
        payment_evidence = assess_duplicate_payment(case, customer_context)
        resolution_evidence = assess_resolution_evidence(case, customer_context)
        experiences, evidence, _embedding = self.experience_memory.retrieve(case)
        proposal = self.reasoner.propose(
            case,
            customer_context,
            experiences,
            payment_evidence,
            resolution_evidence,
        )
        proposal, _correction_replayed = self._replay_verified_correction(
            case,
            experiences,
            proposal,
            resolution_evidence,
        )
        permission = self.policy_risk.gate(
            case,
            proposal,
            evidence,
            payment_evidence,
            resolution_evidence,
        )
        counterfactual = explain_auto_counterfactual(
            case,
            proposal,
            evidence,
            resolution_evidence,
            permission,
        )
        workflow_plan = build_workflow_plan(case, proposal, resolution_evidence)
        containment = self._containment_proof(
            case,
            permission,
            resolution_evidence,
            workflow_plan,
        )
        return AgentRun.create(
            case,
            proposal,
            evidence,
            permission,
            counterfactual,
            experiences,
            payment_evidence=payment_evidence,
            resolution_evidence=resolution_evidence,
            workflow_plan=workflow_plan,
            containment=containment,
        )

    @staticmethod
    def _evidence_record_ids(evidence: ResolutionEvidence) -> tuple[str, ...]:
        return tuple(
            str(source["source_record_id"])
            for source in evidence.source_checks
            if source.get("admissible") and source.get("source_record_id")
        )

    @classmethod
    def _containment_proof(
        cls,
        case: CustomerCase,
        permission: Any,
        evidence: ResolutionEvidence | None,
        workflow_plan: Any,
        *,
        execution: Any | None = None,
        verification_success: bool = False,
        supervised: bool = False,
    ) -> ContainmentProof:
        evidence_ids = cls._evidence_record_ids(evidence) if evidence else ()
        required_count = len(evidence.required_sources) if evidence else 0
        admissible_count = len(evidence.completed_sources) if evidence else 0
        if execution is not None and verification_success:
            status = "CONTAINED_AFTER_APPROVAL" if supervised else "CONTAINED"
        elif permission.mode in {DecisionMode.VERIFY, DecisionMode.HUMAN}:
            status = "AWAITING_CONFIRMATION"
        else:
            status = "EXECUTION_PENDING"
        level = (
            "L3_SUPERVISED"
            if supervised or permission.mode in {DecisionMode.VERIFY, DecisionMode.HUMAN}
            else "L2_AUTONOMOUS"
        )
        root_cause = (
            evidence.reason
            if evidence is not None
            else "No issue-specific root cause has been admitted."
        )
        operation_count = len(execution.steps) if execution is not None else 0
        minutes = 0
        if execution is not None:
            minutes = (10 if supervised else 16) + operation_count * (2 if supervised else 4)
        created_at = datetime.now(timezone.utc)
        return ContainmentProof(
            status=status,
            level=level,
            root_cause=root_cause,
            evidence_grade=evidence.evidence_grade if evidence else "BLOCKED",
            evidence_record_ids=evidence_ids,
            required_evidence_count=required_count,
            admissible_evidence_count=admissible_count,
            decision_rule=permission.rule_id,
            workflow_id=execution.workflow_id if execution is not None else None,
            executed_operations=operation_count,
            verified=verification_success,
            human_minutes_avoided=minutes,
            estimated_company_cost=evidence.company_cost if evidence else 0.0,
            customer_value=evidence.customer_value if evidence else 0.0,
            reopen_monitor_until=(created_at + timedelta(days=7)).isoformat(),
        )

    @staticmethod
    def _case_evidence_from_record(record: dict[str, Any]) -> dict[str, Any]:
        return {
            "issue_type": record.get("task_type"),
            "customer_segment": record.get("customer_segment", "consumer"),
            "evidence_as_of": record.get("evidence_as_of"),
            "customer_goal": record.get("customer_goal"),
            "business_guardrail": record.get("business_guardrail"),
            "evidence_required": record.get("evidence_required", []),
            "evidence_sources": record.get("evidence_sources", []),
            "resolution_options": record.get("resolution_options", []),
            "resolution_constraints": record.get("resolution_constraints", {}),
        }

    @classmethod
    def _catalog_case(cls, record: dict[str, Any]) -> CustomerCase:
        customer = record["customer"]
        return CustomerCase(
            customer_id=str(customer["customer_id"]),
            task_type=str(record["task_type"]),
            request_text=str(record["request_text"]),
            requested_amount=float(record["requested_amount"]),
            account_type=str(customer["account_type"]),
            region=str(customer["region"]),
            contract_type=str(customer["contract_type"]),
            fraud_signal=bool(record["fraud_signal"]),
            existing_credit=float(record["existing_credit"]),
            metadata={
                "case_id": str(record["case_id"]),
                "case_evidence": cls._case_evidence_from_record(record),
            },
        )

    @staticmethod
    def _apply_authoritative_customer(
        case: CustomerCase,
        customer_context: dict[str, Any],
    ) -> CustomerCase:
        customer = customer_context.get("customer", {})
        if not isinstance(customer, dict):
            return case
        return replace(
            case,
            account_type=str(customer.get("account_type") or case.account_type),
            region=str(customer.get("region") or case.region),
            contract_type=str(customer.get("contract_type") or case.contract_type),
        )

    @staticmethod
    def _replay_verified_correction(
        case: CustomerCase,
        experiences: tuple[SimilarExperience, ...],
        proposal: AgentProposal,
        resolution_evidence: ResolutionEvidence | None = None,
    ) -> tuple[AgentProposal, bool]:
        lessons = " ".join(
            str(experience.correction_lesson or "") for experience in experiences
        ).lower()
        if case.task_type == "warranty_grace_exception":
            if resolution_evidence is not None and (
                "within 14 days" in lessons or "warranty grace" in lessons
            ):
                return (
                    AgentProposal(
                        action_type=resolution_evidence.recommended_action,
                        amount=resolution_evidence.recommended_amount,
                        reason=(
                            "Replayed the context-matched warranty-grace correction after "
                            "matching the service bulletin, diagnostic exclusions, and grace window."
                        ),
                        confidence=None,
                        checks_performed=(
                            *proposal.checks_performed,
                            "verified_correction_replay",
                        ),
                    ),
                    True,
                )
            return (
                AgentProposal(
                    action_type="store_credit",
                    amount=min(40.0, round(case.requested_amount * 0.25, 2)),
                    reason=(
                        "Without a verified grace-period lesson, proposed a generic goodwill "
                        "credit for human review."
                    ),
                    confidence=None,
                    checks_performed=(*proposal.checks_performed, "exception_not_learned"),
                ),
                False,
            )
        return proposal, False
