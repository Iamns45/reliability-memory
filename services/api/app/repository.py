from __future__ import annotations

import json
import math
import random
import time
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Iterator, Protocol, TypeVar, cast
from uuid import UUID, uuid4

from .case_catalog import analyst_case_record, analyst_case_records, customer_context
from .domain import AgentRun, SimilarExperience
from .reliability import HistoricalStats

T = TypeVar("T")


@dataclass(frozen=True)
class DecisionRecord:
    episode_id: UUID
    created: bool


class EpisodeNotReviewableError(RuntimeError):
    """Raised when a correction targets an unknown or completed episode."""


class AmbiguousCommitError(RuntimeError):
    """Raised when CockroachDB cannot confirm whether a transaction committed."""


class MemoryRepository(Protocol):
    def list_analyst_cases(self) -> list[dict[str, Any]]: ...
    def get_analyst_case(self, case_id: str) -> dict[str, Any] | None: ...
    def get_customer_context(self, customer_id: str) -> dict[str, Any]: ...
    def find_similar_experiences(
        self,
        task_type: str,
        embedding: list[float],
        embedding_model: str,
        limit: int = 5,
    ) -> tuple[SimilarExperience, ...]: ...
    def get_historical_stats(self, task_type: str) -> HistoricalStats: ...
    def get_all_historical_stats(self) -> dict[str, HistoricalStats]: ...
    def create_decision_record(
        self,
        run: AgentRun,
        idempotency_key: str,
        embedding: list[float],
        embedding_model: str,
    ) -> DecisionRecord: ...
    def complete_episode(self, run: AgentRun) -> None: ...
    def record_mcp_verification(self, run: AgentRun) -> None: ...
    def save_review_summary(self, episode_id: UUID, summary: dict[str, Any]) -> None: ...
    def record_human_correction(
        self,
        episode_id: UUID,
        human_action: dict[str, Any],
        reason: str,
        lesson: str,
        embedding: list[float],
        embedding_model: str,
    ) -> UUID: ...
    def record_delayed_outcome(
        self,
        episode_id: UUID,
        success: bool,
        reason: str,
    ) -> UUID: ...
    def get_evidence_receipt(self, episode_id: UUID) -> dict[str, Any]: ...


class CockroachMemoryRepository:
    """Production adapter using short CockroachDB transactions and retry-safe writes."""

    def __init__(self, database_url: str, max_retries: int = 5) -> None:
        self.database_url = database_url
        self.max_retries = max_retries

    @contextmanager
    def _connection(self) -> Iterator[Any]:
        try:
            import psycopg
            from psycopg.rows import dict_row
        except ImportError as exc:  # pragma: no cover - deployment dependency
            raise RuntimeError("Install psycopg[binary,pool] to use CockroachDB") from exc
        with psycopg.connect(
            self.database_url,
            autocommit=True,
            connect_timeout=5,
            row_factory=dict_row,
        ) as connection:
            yield connection

    def _transaction(self, operation: Callable[[Any], T]) -> T:
        delay = 0.05
        for attempt in range(self.max_retries):
            try:
                with self._connection() as connection:
                    with connection.transaction():
                        return operation(connection)
            except Exception as exc:
                sqlstate = getattr(exc, "sqlstate", None)
                if sqlstate == "40003":
                    raise AmbiguousCommitError("CockroachDB returned SQLSTATE 40003") from exc
                if sqlstate != "40001" or attempt == self.max_retries - 1:
                    raise
                time.sleep(delay + random.uniform(0, delay))
                delay = min(delay * 2, 1.0)
        raise RuntimeError("transaction retry budget exhausted")

    def get_customer_context(self, customer_id: str) -> dict[str, Any]:
        with self._connection() as connection:
            customer = connection.execute(
                "SELECT customer_id, display_name, account_type, region, contract_type FROM customers WHERE customer_id = %s",
                (customer_id,),
            ).fetchone()
            events = connection.execute(
                "SELECT event_type, event_at, data FROM customer_events WHERE customer_id = %s ORDER BY event_at DESC LIMIT 50",
                (customer_id,),
            ).fetchall()
            payments = connection.execute(
                """
                SELECT payment_id, provider, merchant_reference, subscription_reference,
                       billing_period, payment_method_fingerprint, amount, currency,
                       status, captured_at, refunded_at IS NOT NULL AS refunded,
                       reversed_at IS NOT NULL AS reversed,
                       disputed_at IS NOT NULL AS disputed
                FROM payment_transactions
                WHERE customer_id = %s
                ORDER BY captured_at DESC
                LIMIT 100
                """,
                (customer_id,),
            ).fetchall()
            case_row = connection.execute(
                """
                SELECT evidence_bundle
                FROM analyst_cases
                WHERE customer_id = %s AND queue_status != 'CLOSED'
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (customer_id,),
            ).fetchone()
        return {
            "customer": customer or {},
            "events": list(events),
            "payments": [dict(payment) for payment in payments],
            "case_evidence": (
                dict(case_row["evidence_bundle"])
                if case_row is not None and case_row.get("evidence_bundle")
                else {}
            ),
        }

    def list_analyst_cases(self) -> list[dict[str, Any]]:
        with self._connection() as connection:
            cases = connection.execute(
                """
                SELECT ac.case_id, ac.title, ac.queue_status, ac.priority,
                       ac.task_type, ac.request_text, ac.requested_amount,
                       ac.existing_credit, ac.fraud_signal, ac.ground_truth_amount,
                       ac.expected_mode, ac.created_at, ac.evidence_bundle,
                       c.customer_id, c.display_name, c.account_type, c.region,
                       c.contract_type
                FROM analyst_cases AS ac
                JOIN customers AS c ON c.customer_id = ac.customer_id
                WHERE ac.queue_status != 'CLOSED'
                ORDER BY ac.created_at DESC, ac.case_id
                """
            ).fetchall()
            events = connection.execute(
                """
                SELECT customer_id, event_type, event_at, data
                FROM customer_events
                WHERE customer_id IN (SELECT customer_id FROM analyst_cases)
                ORDER BY event_at DESC
                """
            ).fetchall()
            payments = connection.execute(
                """
                SELECT customer_id, payment_id, provider, merchant_reference,
                       subscription_reference, billing_period,
                       payment_method_fingerprint, amount, currency, status,
                       captured_at, refunded_at IS NOT NULL AS refunded,
                       reversed_at IS NOT NULL AS reversed,
                       disputed_at IS NOT NULL AS disputed
                FROM payment_transactions
                WHERE customer_id IN (SELECT customer_id FROM analyst_cases)
                ORDER BY captured_at DESC
                """
            ).fetchall()

        events_by_customer: dict[str, list[dict[str, Any]]] = {}
        for event in events:
            row = dict(event)
            customer_id = str(row.pop("customer_id"))
            events_by_customer.setdefault(customer_id, []).append(row)
        payments_by_customer: dict[str, list[dict[str, Any]]] = {}
        for payment in payments:
            row = dict(payment)
            customer_id = str(row.pop("customer_id"))
            row["amount"] = float(row["amount"])
            payments_by_customer.setdefault(customer_id, []).append(row)

        records: list[dict[str, Any]] = []
        for case in cases:
            row = dict(case)
            customer_id = str(row["customer_id"])
            bundle = dict(row.get("evidence_bundle") or {})
            records.append(
                {
                    "case_id": row["case_id"],
                    "title": row["title"],
                    "queue_status": row["queue_status"],
                    "priority": row["priority"],
                    "task_type": row["task_type"],
                    "request_text": row["request_text"],
                    "requested_amount": float(row["requested_amount"]),
                    "existing_credit": float(row["existing_credit"]),
                    "fraud_signal": row["fraud_signal"],
                    "ground_truth_amount": (
                        float(row["ground_truth_amount"])
                        if row["ground_truth_amount"] is not None
                        else None
                    ),
                    "expected_mode": row["expected_mode"],
                    "created_at": row["created_at"],
                    "customer_segment": bundle.get("customer_segment", "consumer"),
                    "evidence_as_of": bundle.get("evidence_as_of"),
                    "customer": {
                        "customer_id": customer_id,
                        "display_name": row["display_name"],
                        "account_type": row["account_type"],
                        "region": row["region"],
                        "contract_type": row["contract_type"],
                    },
                    "events": events_by_customer.get(customer_id, []),
                    "payments": payments_by_customer.get(customer_id, []),
                    "customer_goal": bundle.get("customer_goal", ""),
                    "business_guardrail": bundle.get("business_guardrail", ""),
                    "evidence_required": bundle.get("evidence_required", []),
                    "evidence_sources": bundle.get("evidence_sources", []),
                    "resolution_options": bundle.get("resolution_options", []),
                    "resolution_constraints": bundle.get("resolution_constraints", {}),
                }
            )
        return records

    def get_analyst_case(self, case_id: str) -> dict[str, Any] | None:
        return next(
            (record for record in self.list_analyst_cases() if record["case_id"] == case_id),
            None,
        )

    def find_similar_experiences(
        self,
        task_type: str,
        embedding: list[float],
        embedding_model: str,
        limit: int = 5,
    ) -> tuple[SimilarExperience, ...]:
        vector = _vector_literal(embedding)
        with self._connection() as connection:
            episode_rows = connection.execute(
                """
                SELECT e.episode_id,
                       e.summary,
                       1 - (e.embedding <=> %s::VECTOR) AS similarity,
                       e.verified_success,
                       NULL AS correction_lesson
                FROM episodes AS e
                WHERE e.task_type = %s
                  AND e.outcome_status IN ('VERIFIED_SUCCESS', 'VERIFIED_FAILURE')
                  AND e.embedding IS NOT NULL
                  AND e.embedding_model = %s
                ORDER BY e.embedding <-> %s::VECTOR
                LIMIT %s
                """,
                (vector, task_type, embedding_model, vector, limit),
            ).fetchall()
            correction_rows = connection.execute(
                """
                SELECT c.episode_id,
                       e.summary,
                       1 - (c.embedding <=> %s::VECTOR) AS similarity,
                       false AS verified_success,
                       c.lesson AS correction_lesson
                FROM human_corrections AS c
                JOIN episodes AS e ON e.episode_id = c.episode_id
                WHERE c.task_type = %s
                  AND c.embedding IS NOT NULL
                  AND c.embedding_model = %s
                ORDER BY c.embedding <-> %s::VECTOR
                LIMIT %s
                """,
                (vector, task_type, embedding_model, vector, limit),
            ).fetchall()
        experiences = [
            SimilarExperience(
                episode_id=row["episode_id"],
                summary=row["summary"],
                similarity=max(0.0, min(1.0, float(row["similarity"]))),
                verified_success=bool(row["verified_success"]),
                correction_lesson=row["correction_lesson"],
            )
            for row in [*episode_rows, *correction_rows]
        ]
        experiences.sort(key=lambda item: item.similarity, reverse=True)
        return tuple(experiences[:limit])

    def get_historical_stats(self, task_type: str) -> HistoricalStats:
        with self._connection() as connection:
            row = connection.execute(
                """
                SELECT count(*) FILTER (WHERE outcome_status != 'PENDING') AS verified_cases,
                       count(*) FILTER (WHERE outcome_status = 'VERIFIED_SUCCESS') AS successes,
                       count(*) FILTER (WHERE outcome_status = 'VERIFIED_FAILURE') AS failures,
                       count(*) FILTER (WHERE outcome_status = 'HUMAN_CORRECTED') AS human_overrides,
                       max(verified_at) AS last_verified_at
                FROM episodes WHERE task_type = %s
                """,
                (task_type,),
            ).fetchone()
        if row is None:  # pragma: no cover - aggregate queries always return one row
            raise RuntimeError("CockroachDB did not return reliability statistics")
        return HistoricalStats(
            verified_cases=int(row["verified_cases"] or 0),
            successes=int(row["successes"] or 0),
            failures=int(row["failures"] or 0),
            human_overrides=int(row["human_overrides"] or 0),
            average_similarity=1.0,
            last_verified_at=row["last_verified_at"],
        )

    def get_all_historical_stats(self) -> dict[str, HistoricalStats]:
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT task_type,
                       count(*) FILTER (WHERE outcome_status != 'PENDING') AS verified_cases,
                       count(*) FILTER (WHERE outcome_status = 'VERIFIED_SUCCESS') AS successes,
                       count(*) FILTER (WHERE outcome_status = 'VERIFIED_FAILURE') AS failures,
                       count(*) FILTER (WHERE outcome_status = 'HUMAN_CORRECTED') AS human_overrides,
                       max(verified_at) AS last_verified_at
                FROM episodes
                GROUP BY task_type
                """
            ).fetchall()
        return {
            str(row["task_type"]): HistoricalStats(
                verified_cases=int(row["verified_cases"] or 0),
                successes=int(row["successes"] or 0),
                failures=int(row["failures"] or 0),
                human_overrides=int(row["human_overrides"] or 0),
                average_similarity=1.0,
                last_verified_at=row["last_verified_at"],
            )
            for row in rows
        }

    def create_decision_record(
        self,
        run: AgentRun,
        idempotency_key: str,
        embedding: list[float],
        embedding_model: str,
    ) -> DecisionRecord:
        episode_id = run.run_id
        vector = _vector_literal(embedding)

        def operation(connection: Any) -> DecisionRecord:
            row = connection.execute(
                """
                INSERT INTO episodes (
                    episode_id, agent_id, customer_id, task_type, summary, context,
                    proposed_action, risk_level, autonomy_decision, policy_version,
                    outcome_status, idempotency_key, embedding, embedding_model,
                    embedding_input_version, embedded_at, created_at
                ) VALUES (
                    %s, 'customer-resolution-agent-v2', %s, %s, %s, %s::JSONB, %s::JSONB,
                    %s, %s, %s, 'PENDING', %s, %s::VECTOR, %s,
                    'case-semantic-v1', %s, %s
                )
                ON CONFLICT (idempotency_key) DO UPDATE SET idempotency_key = excluded.idempotency_key
                RETURNING episode_id
                """,
                (
                    episode_id,
                    run.case.customer_id,
                    run.case.task_type,
                    run.case.request_text[:400],
                    json.dumps(
                        {
                            "case": asdict(run.case),
                            "payment_evidence": (
                                asdict(run.payment_evidence) if run.payment_evidence else None
                            ),
                            "resolution_evidence": (
                                asdict(run.resolution_evidence) if run.resolution_evidence else None
                            ),
                            "workflow_plan": asdict(run.workflow_plan),
                            "containment": asdict(run.containment),
                        }
                    ),
                    json.dumps(asdict(run.proposal)),
                    run.permission.risk.value,
                    run.permission.mode.value,
                    run.permission.policy_version,
                    idempotency_key,
                    vector,
                    embedding_model,
                    run.created_at,
                    run.created_at,
                ),
            ).fetchone()
            if row is None:  # pragma: no cover - INSERT RETURNING always returns one row
                raise RuntimeError("CockroachDB did not return the decision record")
            stored_episode_id = row["episode_id"]
            if stored_episode_id == episode_id:
                connection.execute(
                    """
                    INSERT INTO audit_events (episode_id, actor_type, event_type, payload)
                    VALUES (%s, 'policy', 'permission_decided', %s::JSONB)
                    """,
                    (
                        episode_id,
                        json.dumps(
                            {
                                "mode": run.permission.mode.value,
                                "risk": run.permission.risk.value,
                                "rule_id": run.permission.rule_id,
                                "policy_version": run.permission.policy_version,
                                "memory_enabled": run.case.memory_enabled,
                                "payment_evidence": (
                                    asdict(run.payment_evidence) if run.payment_evidence else None
                                ),
                                "resolution_evidence": (
                                    asdict(run.resolution_evidence)
                                    if run.resolution_evidence
                                    else None
                                ),
                            }
                        ),
                    ),
                )
            return DecisionRecord(
                episode_id=stored_episode_id,
                created=stored_episode_id == episode_id,
            )

        try:
            return self._transaction(operation)
        except AmbiguousCommitError:
            with self._connection() as connection:
                row = connection.execute(
                    "SELECT episode_id FROM episodes WHERE idempotency_key = %s",
                    (idempotency_key,),
                ).fetchone()
            if row is None:
                raise
            stored_episode_id = row["episode_id"]
            return DecisionRecord(
                episode_id=stored_episode_id,
                created=stored_episode_id == episode_id,
            )

    def save_review_summary(self, episode_id: UUID, summary: dict[str, Any]) -> None:
        def operation(connection: Any) -> None:
            row = connection.execute(
                """
                INSERT INTO approvals (
                    episode_id, status, proposed_action, review_summary
                )
                SELECT episode_id, 'PENDING', proposed_action, %s::JSONB
                FROM episodes
                WHERE episode_id = %s
                  AND autonomy_decision IN ('VERIFY', 'HUMAN')
                  AND outcome_status = 'PENDING'
                ON CONFLICT (episode_id) DO UPDATE SET
                    review_summary = excluded.review_summary
                RETURNING approval_id
                """,
                (json.dumps(summary), episode_id),
            ).fetchone()
            if row is None:
                raise EpisodeNotReviewableError("Episode is not awaiting human review")

        self._transaction(operation)

    def record_mcp_verification(self, run: AgentRun) -> None:
        receipt = run.mcp_verification
        if receipt is None:
            raise ValueError("mcp_verification is required")

        def operation(connection: Any) -> None:
            connection.execute(
                """
                INSERT INTO mcp_verification_receipts (
                    episode_id, provider, endpoint, cluster_scope, database_name,
                    tool_name, required, verified, observed_episode_id,
                    observed_decision, observed_policy_version, vector_check_performed,
                    expected_neighbor_ids, vector_neighbor_ids, matching_neighbor_ids,
                    receipt_hash, failure_reason, checked_at
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s::JSONB, %s::JSONB, %s::JSONB, %s, %s, %s
                )
                ON CONFLICT (episode_id) DO UPDATE SET
                    provider = excluded.provider,
                    endpoint = excluded.endpoint,
                    cluster_scope = excluded.cluster_scope,
                    database_name = excluded.database_name,
                    tool_name = excluded.tool_name,
                    required = excluded.required,
                    verified = excluded.verified,
                    observed_episode_id = excluded.observed_episode_id,
                    observed_decision = excluded.observed_decision,
                    observed_policy_version = excluded.observed_policy_version,
                    vector_check_performed = excluded.vector_check_performed,
                    expected_neighbor_ids = excluded.expected_neighbor_ids,
                    vector_neighbor_ids = excluded.vector_neighbor_ids,
                    matching_neighbor_ids = excluded.matching_neighbor_ids,
                    receipt_hash = excluded.receipt_hash,
                    failure_reason = excluded.failure_reason,
                    checked_at = excluded.checked_at
                """,
                (
                    run.run_id,
                    receipt.provider,
                    receipt.endpoint,
                    receipt.cluster_scope,
                    receipt.database,
                    receipt.tool_name,
                    receipt.required,
                    receipt.verified,
                    receipt.observed_episode_id,
                    receipt.observed_decision,
                    receipt.observed_policy_version,
                    receipt.vector_check_performed,
                    json.dumps(receipt.expected_neighbor_ids),
                    json.dumps(receipt.vector_neighbor_ids),
                    json.dumps(receipt.matching_neighbor_ids),
                    receipt.receipt_hash,
                    receipt.failure_reason,
                    receipt.checked_at,
                ),
            )
            connection.execute(
                """
                UPDATE episodes
                SET autonomy_decision = %s,
                    context = jsonb_set(
                        context,
                        '{mcp_verification}',
                        %s::JSONB,
                        true
                    )
                WHERE episode_id = %s
                """,
                (
                    run.permission.mode.value,
                    json.dumps(asdict(receipt), default=str),
                    run.run_id,
                ),
            )
            connection.execute(
                """
                INSERT INTO audit_events (episode_id, actor_type, event_type, payload)
                VALUES (%s, 'verifier', 'mcp_memory_verified', %s::JSONB)
                """,
                (run.run_id, json.dumps(asdict(receipt), default=str)),
            )

        self._transaction(operation)

    def complete_episode(self, run: AgentRun) -> None:
        execution = run.execution
        verification = run.verification
        if execution is None or verification is None:
            raise ValueError("execution and verification are required to complete an episode")

        def operation(connection: Any) -> None:
            connection.execute(
                """
                UPDATE episodes
                SET executed_action = %s::JSONB,
                    immediate_outcome = %s::JSONB,
                    outcome_status = CASE
                        WHEN outcome_status = 'HUMAN_CORRECTED' THEN 'HUMAN_CORRECTED'
                        ELSE %s
                    END,
                    verified_success = %s,
                    verified_at = now()
                WHERE episode_id = %s
                  AND outcome_status IN ('PENDING', 'HUMAN_CORRECTED')
                """,
                (
                    json.dumps(asdict(execution), default=str),
                    json.dumps(asdict(verification), default=str),
                    "VERIFIED_SUCCESS" if verification.success else "VERIFIED_FAILURE",
                    verification.success,
                    run.run_id,
                ),
            )
            connection.execute(
                """
                INSERT INTO outcomes (episode_id, outcome_type, data, verified, observed_at)
                VALUES (%s, 'immediate', %s::JSONB, true, now())
                ON CONFLICT (episode_id, outcome_type) DO NOTHING
                """,
                (run.run_id, json.dumps(asdict(verification), default=str)),
            )
            connection.execute(
                """
                INSERT INTO audit_events (episode_id, actor_type, event_type, payload)
                VALUES (%s, 'verifier', 'containment_verified', %s::JSONB)
                """,
                (run.run_id, json.dumps(asdict(run.containment), default=str)),
            )

        try:
            self._transaction(operation)
        except AmbiguousCommitError:
            with self._connection() as connection:
                row = connection.execute(
                    "SELECT outcome_status FROM episodes WHERE episode_id = %s",
                    (run.run_id,),
                ).fetchone()
            if row is None or row["outcome_status"] not in {
                "VERIFIED_SUCCESS",
                "VERIFIED_FAILURE",
                "HUMAN_CORRECTED",
            }:
                raise

    def record_human_correction(
        self,
        episode_id: UUID,
        human_action: dict[str, Any],
        reason: str,
        lesson: str,
        embedding: list[float],
        embedding_model: str,
    ) -> UUID:
        vector = _vector_literal(embedding)

        def operation(connection: Any) -> UUID:
            row = connection.execute(
                """
                INSERT INTO human_corrections (
                    episode_id, task_type, agent_proposal, human_action, reason, lesson,
                    embedding, embedding_model, embedding_input_version, embedded_at
                )
                SELECT episode_id, task_type, proposed_action, %s::JSONB, %s, %s, %s::VECTOR,
                       %s, 'human-correction-v1', now()
                FROM episodes
                WHERE episode_id = %s
                  AND autonomy_decision IN ('VERIFY', 'HUMAN')
                  AND outcome_status = 'PENDING'
                ON CONFLICT (episode_id) DO UPDATE SET
                    human_action = excluded.human_action,
                    reason = excluded.reason,
                    lesson = excluded.lesson,
                    embedding = excluded.embedding,
                    embedding_model = excluded.embedding_model,
                    embedding_input_version = excluded.embedding_input_version,
                    embedded_at = excluded.embedded_at
                RETURNING correction_id
                """,
                (
                    json.dumps(human_action),
                    reason,
                    lesson,
                    vector,
                    embedding_model,
                    episode_id,
                ),
            ).fetchone()
            if row is None:
                existing = connection.execute(
                    """
                    SELECT human_action, reason, lesson
                    FROM human_corrections
                    WHERE episode_id = %s
                    """,
                    (episode_id,),
                ).fetchone()
                if existing == {
                    "human_action": human_action,
                    "reason": reason,
                    "lesson": lesson,
                }:
                    existing_id = connection.execute(
                        "SELECT correction_id FROM human_corrections WHERE episode_id = %s",
                        (episode_id,),
                    ).fetchone()
                    if existing_id is None:
                        raise RuntimeError("Correction disappeared during idempotency check")
                    return cast(UUID, existing_id["correction_id"])
                raise EpisodeNotReviewableError("Episode is not awaiting human review")
            connection.execute(
                """
                UPDATE episodes
                SET outcome_status = 'HUMAN_CORRECTED',
                    verified_success = false,
                    verified_at = now()
                WHERE episode_id = %s
                """,
                (episode_id,),
            )
            connection.execute(
                """
                UPDATE approvals
                SET status = 'CORRECTED',
                    reviewer_id = 'demo-reviewer',
                    reviewer_reason = %s,
                    resolved_action = %s::JSONB,
                    resolved_at = now()
                WHERE episode_id = %s
                """,
                (reason, json.dumps(human_action), episode_id),
            )
            connection.execute(
                """
                INSERT INTO audit_events (episode_id, actor_type, event_type, payload)
                VALUES (%s, 'human', 'correction_recorded', %s::JSONB)
                """,
                (
                    episode_id,
                    json.dumps(
                        {
                            "correction_id": str(row["correction_id"]),
                            "human_action": human_action,
                            "reason": reason,
                            "lesson": lesson,
                        }
                    ),
                ),
            )
            return cast(UUID, row["correction_id"])

        try:
            return self._transaction(operation)
        except AmbiguousCommitError:
            with self._connection() as connection:
                existing = connection.execute(
                    """
                    SELECT human_action, reason, lesson
                    FROM human_corrections
                    WHERE episode_id = %s
                    """,
                    (episode_id,),
                ).fetchone()
            if existing != {
                "human_action": human_action,
                "reason": reason,
                "lesson": lesson,
            }:
                raise
            with self._connection() as connection:
                correction = connection.execute(
                    "SELECT correction_id FROM human_corrections WHERE episode_id = %s",
                    (episode_id,),
                ).fetchone()
            if correction is None:
                raise RuntimeError("Correction commit could not be reconciled")
            return cast(UUID, correction["correction_id"])

    def record_delayed_outcome(
        self,
        episode_id: UUID,
        success: bool,
        reason: str,
    ) -> UUID:
        payload = {"success": success, "reason": reason, "source": "chargeback-simulator"}

        def operation(connection: Any) -> UUID:
            row = connection.execute(
                """
                INSERT INTO outcomes (
                    episode_id, outcome_type, data, verified, verifier, observed_at
                )
                SELECT episode_id, 'delayed', %s::JSONB, true,
                       'chargeback-simulator-v1', now()
                FROM episodes
                WHERE episode_id = %s AND outcome_status != 'PENDING'
                ON CONFLICT (episode_id, outcome_type) DO UPDATE SET
                    data = excluded.data,
                    verified = true,
                    verifier = excluded.verifier,
                    observed_at = now()
                RETURNING outcome_id
                """,
                (json.dumps(payload), episode_id),
            ).fetchone()
            if row is None:
                raise EpisodeNotReviewableError(
                    "Delayed outcomes require a completed, verified episode"
                )
            connection.execute(
                """
                UPDATE episodes
                SET delayed_outcome = %s::JSONB,
                    outcome_status = %s,
                    verified_success = %s,
                    verified_at = now()
                WHERE episode_id = %s
                """,
                (
                    json.dumps(payload),
                    "VERIFIED_SUCCESS" if success else "VERIFIED_FAILURE",
                    success,
                    episode_id,
                ),
            )
            connection.execute(
                """
                INSERT INTO audit_events (episode_id, actor_type, event_type, payload)
                VALUES (%s, 'verifier', 'delayed_outcome_recorded', %s::JSONB)
                """,
                (episode_id, json.dumps({"outcome_id": str(row["outcome_id"]), **payload})),
            )
            return cast(UUID, row["outcome_id"])

        return self._transaction(operation)

    def get_evidence_receipt(self, episode_id: UUID) -> dict[str, Any]:
        with self._connection() as connection:
            episode = connection.execute(
                """
                SELECT episode_id, customer_id, task_type, summary, context,
                       proposed_action, executed_action, risk_level, autonomy_decision,
                       policy_version, outcome_status, immediate_outcome, delayed_outcome,
                       verified_success, idempotency_key, created_at, verified_at
                FROM episodes WHERE episode_id = %s
                """,
                (episode_id,),
            ).fetchone()
            if episode is None:
                raise KeyError(str(episode_id))
            approval = connection.execute(
                """
                SELECT approval_id, status, review_summary, reviewer_reason,
                       resolved_action, resolved_at
                FROM approvals WHERE episode_id = %s
                """,
                (episode_id,),
            ).fetchone()
            correction = connection.execute(
                """
                SELECT correction_id, human_action, reason, lesson, created_at
                FROM human_corrections WHERE episode_id = %s
                """,
                (episode_id,),
            ).fetchone()
            outcomes = connection.execute(
                """
                SELECT outcome_id, outcome_type, data, verified, verifier, observed_at
                FROM outcomes WHERE episode_id = %s ORDER BY observed_at
                """,
                (episode_id,),
            ).fetchall()
            containment = connection.execute(
                """
                SELECT payload
                FROM audit_events
                WHERE episode_id = %s AND event_type = 'containment_verified'
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (episode_id,),
            ).fetchone()
            mcp_verification = connection.execute(
                """
                SELECT provider, endpoint, cluster_scope, database_name AS database,
                       tool_name, required, verified, episode_id,
                       observed_episode_id, observed_decision, observed_policy_version,
                       vector_check_performed, expected_neighbor_ids,
                       vector_neighbor_ids, matching_neighbor_ids, checked_at,
                       receipt_hash, failure_reason
                FROM mcp_verification_receipts
                WHERE episode_id = %s
                """,
                (episode_id,),
            ).fetchone()
        return {
            "episode": dict(episode),
            "approval": dict(approval) if approval else None,
            "correction": dict(correction) if correction else None,
            "outcomes": [dict(outcome) for outcome in outcomes],
            "containment": dict(containment["payload"]) if containment else None,
            "mcp_verification": dict(mcp_verification) if mcp_verification else None,
        }


class InMemoryMemoryRepository:
    """Credential-free judge/demo adapter with the same repository contract."""

    def __init__(self) -> None:
        self.episodes: dict[UUID, AgentRun] = {}
        self.idempotency_keys: dict[str, UUID] = {}
        self.corrections: dict[UUID, dict[str, Any]] = {}
        self.correction_ids: dict[UUID, UUID] = {}
        self.review_summaries: dict[UUID, dict[str, Any]] = {}
        self.delayed_outcomes: dict[UUID, dict[str, Any]] = {}
        self.outcome_ids: dict[UUID, UUID] = {}
        self.mcp_receipts: dict[UUID, dict[str, Any]] = {}

    def get_customer_context(self, customer_id: str) -> dict[str, Any]:
        stored_context = customer_context(customer_id)
        if stored_context is not None:
            return stored_context
        return {
            "customer": {
                "customer_id": customer_id,
                "display_name": "Unassigned customer",
                "account_type": "standard",
                "region": "US",
                "contract_type": "standard",
            },
            "events": [],
            "payments": [],
        }

    def list_analyst_cases(self) -> list[dict[str, Any]]:
        return analyst_case_records()

    def get_analyst_case(self, case_id: str) -> dict[str, Any] | None:
        return analyst_case_record(case_id)

    def find_similar_experiences(
        self,
        task_type: str,
        embedding: list[float],
        embedding_model: str,
        limit: int = 5,
    ) -> tuple[SimilarExperience, ...]:
        del embedding, embedding_model
        corrected = [
            SimilarExperience(
                episode_id=episode_id,
                summary=self.episodes[episode_id].case.request_text,
                similarity=0.99,
                verified_success=False,
                correction_lesson=str(correction["lesson"]),
            )
            for episode_id, correction in self.corrections.items()
            if self.episodes[episode_id].case.task_type == task_type
        ]
        readable_task = task_type.replace("_", " ")
        seeded_memories = [
            (f"Verified {readable_task} resolved from complete current evidence", 0.97, None),
            (f"Comparable {readable_task} with independently observed outcome", 0.94, None),
            (f"Policy-gated {readable_task} preserving customer and company value", 0.91, None),
        ]
        seeded = [
            SimilarExperience(
                episode_id=uuid4(),
                summary=summary,
                similarity=similarity,
                verified_success=True,
                correction_lesson=lesson,
            )
            for summary, similarity, lesson in seeded_memories
        ]
        return tuple([*corrected, *seeded][:limit])

    def get_historical_stats(self, task_type: str) -> HistoricalStats:
        if task_type == "__memory_ablation_disabled__":
            return HistoricalStats(0, 0, 0, 0, average_similarity=0.0)
        seeded = {
            "warranty_grace_exception": (42, 39, 1, 2),
            "product_safety_incident": (28, 27, 0, 1),
            "freight_damage_high_value": (76, 72, 2, 2),
            "delivery_theft_review": (84, 78, 3, 3),
            "counterfeit_marketplace_claim": (35, 33, 1, 1),
            "repeat_repair_failure": (61, 57, 2, 2),
            "serial_mismatch_return": (112, 109, 1, 2),
        }.get(task_type, (500, 498, 1, 1))
        successes = seeded[1]
        failures = seeded[2]
        overrides = seeded[3]
        for episode_id, run in self.episodes.items():
            if run.case.task_type != task_type:
                continue
            if episode_id in self.delayed_outcomes:
                if bool(self.delayed_outcomes[episode_id]["success"]):
                    successes += 1
                else:
                    failures += 1
            elif episode_id in self.corrections:
                overrides += 1
            elif run.verification is not None:
                if run.verification.success:
                    successes += 1
                else:
                    failures += 1
        verified_cases = successes + failures + overrides
        return HistoricalStats(
            verified_cases=verified_cases,
            successes=successes,
            failures=failures,
            human_overrides=overrides,
            average_similarity=0.94,
            last_verified_at=datetime.now(timezone.utc),
        )

    def get_all_historical_stats(self) -> dict[str, HistoricalStats]:
        task_types = {str(record["task_type"]) for record in self.list_analyst_cases()} | {
            run.case.task_type for run in self.episodes.values()
        }
        return {task_type: self.get_historical_stats(task_type) for task_type in task_types}

    def create_decision_record(
        self,
        run: AgentRun,
        idempotency_key: str,
        embedding: list[float],
        embedding_model: str,
    ) -> DecisionRecord:
        del embedding, embedding_model
        if idempotency_key in self.idempotency_keys:
            return DecisionRecord(
                episode_id=self.idempotency_keys[idempotency_key],
                created=False,
            )
        self.episodes[run.run_id] = run
        self.idempotency_keys[idempotency_key] = run.run_id
        return DecisionRecord(episode_id=run.run_id, created=True)

    def complete_episode(self, run: AgentRun) -> None:
        self.episodes[run.run_id] = run

    def record_mcp_verification(self, run: AgentRun) -> None:
        if run.mcp_verification is None:
            raise ValueError("mcp_verification is required")
        self.episodes[run.run_id] = run
        self.mcp_receipts[run.run_id] = asdict(run.mcp_verification)

    def save_review_summary(self, episode_id: UUID, summary: dict[str, Any]) -> None:
        if episode_id not in self.episodes:
            raise EpisodeNotReviewableError("Episode is not awaiting human review")
        self.review_summaries[episode_id] = summary

    def record_human_correction(
        self,
        episode_id: UUID,
        human_action: dict[str, Any],
        reason: str,
        lesson: str,
        embedding: list[float],
        embedding_model: str,
    ) -> UUID:
        del embedding, embedding_model
        run = self.episodes.get(episode_id)
        if run is None or run.execution is not None:
            raise EpisodeNotReviewableError("Episode is not awaiting human review")
        correction = {
            "proposal": asdict(run.proposal),
            "human_action": human_action,
            "reason": reason,
            "lesson": lesson,
        }
        existing = self.corrections.get(episode_id)
        if existing is not None and existing != correction:
            raise EpisodeNotReviewableError("Episode already has a different correction")
        self.corrections[episode_id] = correction
        correction_id = self.correction_ids.setdefault(episode_id, uuid4())
        return correction_id

    def record_delayed_outcome(
        self,
        episode_id: UUID,
        success: bool,
        reason: str,
    ) -> UUID:
        run = self.episodes.get(episode_id)
        if run is None or run.verification is None:
            raise EpisodeNotReviewableError(
                "Delayed outcomes require a completed, verified episode"
            )
        self.delayed_outcomes[episode_id] = {
            "success": success,
            "reason": reason,
            "source": "chargeback-simulator",
        }
        return self.outcome_ids.setdefault(episode_id, uuid4())

    def get_evidence_receipt(self, episode_id: UUID) -> dict[str, Any]:
        run = self.episodes.get(episode_id)
        if run is None:
            raise KeyError(str(episode_id))
        return {
            "episode": asdict(run),
            "approval": (
                {"status": "PENDING", "review_summary": self.review_summaries[episode_id]}
                if episode_id in self.review_summaries
                else None
            ),
            "correction": (
                {
                    "correction_id": self.correction_ids[episode_id],
                    **self.corrections[episode_id],
                }
                if episode_id in self.corrections
                else None
            ),
            "outcomes": (
                [
                    {
                        "outcome_id": self.outcome_ids[episode_id],
                        "outcome_type": "delayed",
                        "data": self.delayed_outcomes[episode_id],
                    }
                ]
                if episode_id in self.delayed_outcomes
                else []
            ),
            "containment": asdict(run.containment),
            "mcp_verification": self.mcp_receipts.get(episode_id),
        }


def _vector_literal(embedding: list[float]) -> str:
    if len(embedding) != 1_024:
        raise ValueError("Embeddings must contain exactly 1024 dimensions")
    if not all(math.isfinite(value) for value in embedding):
        raise ValueError("Embeddings must contain only finite values")
    return "[" + ",".join(f"{value:.8f}" for value in embedding) + "]"
