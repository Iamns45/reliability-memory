#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import uuid5, NAMESPACE_URL

PROJECT_ROOT = Path(__file__).resolve().parents[1]
API_ROOT = PROJECT_ROOT / "services" / "api"
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from app.case_catalog import analyst_case_records  # noqa: E402
from app.resolution_selector import select_resolution  # noqa: E402
from seed_memory import normalized_embedding  # noqa: E402

CASE_SHAPED_EPISODES_PER_AUTO_CASE = 150


def seed_case_catalog(connection: Any) -> int:
    records = analyst_case_records()
    customer_ids = [record["customer"]["customer_id"] for record in records]

    for record in records:
        customer = record["customer"]
        evidence_bundle = {
            "issue_type": record["task_type"],
            "customer_segment": record["customer_segment"],
            "evidence_as_of": record["evidence_as_of"],
            "customer_goal": record["customer_goal"],
            "business_guardrail": record["business_guardrail"],
            "evidence_required": record["evidence_required"],
            "evidence_sources": record["evidence_sources"],
            "resolution_options": record["resolution_options"],
            "resolution_constraints": record["resolution_constraints"],
        }
        connection.execute(
            """
            UPSERT INTO customers (
                customer_id, display_name, account_type, region, contract_type, metadata
            ) VALUES (%s, %s, %s, %s, %s, %s::JSONB)
            """,
            (
                customer["customer_id"],
                customer["display_name"],
                customer["account_type"],
                customer["region"],
                customer["contract_type"],
                json.dumps({"synthetic": True, "dataset": "customer-resolution-v2"}),
            ),
        )
        connection.execute(
            """
            UPSERT INTO analyst_cases (
                case_id, customer_id, title, queue_status, priority, task_type,
                request_text, requested_amount, existing_credit, fraud_signal,
                ground_truth_amount, expected_mode, created_at, evidence_bundle
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                now() - (%s * INTERVAL '1 minute'), %s::JSONB
            )
            """,
            (
                record["case_id"],
                customer["customer_id"],
                record["title"],
                record["queue_status"],
                record["priority"],
                record["task_type"],
                record["request_text"],
                record["requested_amount"],
                record["existing_credit"],
                record["fraud_signal"],
                record["ground_truth_amount"],
                record["expected_mode"],
                records.index(record),
                json.dumps(evidence_bundle),
            ),
        )

    connection.execute(
        """
        DELETE FROM customer_events
        WHERE customer_id = ANY(%s)
          AND source IN ('simulator', 'catalog-seed-v2')
        """,
        (customer_ids,),
    )
    for record in records:
        customer_id = record["customer"]["customer_id"]
        for index, event in enumerate(record["events"]):
            event_id = uuid5(
                NAMESPACE_URL,
                f"reliability-memory:{record['case_id']}:{index}:{event['event_type']}",
            )
            connection.execute(
                """
                UPSERT INTO customer_events (
                    event_id, customer_id, event_type, event_at, data, source
                ) VALUES (%s, %s, %s, %s, %s::JSONB, 'catalog-seed-v2')
                """,
                (
                    event_id,
                    customer_id,
                    event["event_type"],
                    event["event_at"],
                    json.dumps(event["data"]),
                ),
            )

    connection.execute(
        """
        DELETE FROM payment_transactions
        WHERE customer_id = ANY(%s)
          AND metadata->>'synthetic' = 'true'
        """,
        (customer_ids,),
    )
    return len(records)


def seed_case_shaped_episodes(connection: Any, per_case: int) -> int:
    """Seed verified memories that use the same semantic shape as runtime retrieval."""

    if per_case < 0:
        raise ValueError("per_case cannot be negative")
    inserted = 0
    seeded_at = datetime.now(timezone.utc) - timedelta(days=1)
    for record in analyst_case_records():
        if record["expected_mode"] != "AUTO":
            continue
        customer = record["customer"]
        semantic_text = " | ".join(
            [
                record["task_type"],
                record["request_text"],
                customer["account_type"],
                customer["region"],
                customer["contract_type"],
                f"amount:{float(record['requested_amount']):.2f}",
            ]
        )
        selection = select_resolution(
            record["resolution_options"], record["resolution_constraints"]
        )
        action = {
            "action_type": selection.option["action"],
            "amount": float(selection.option["amount"]),
        }
        embedding = (
            "[" + ",".join(f"{value:.8f}" for value in normalized_embedding(semantic_text)) + "]"
        )
        for index in range(per_case):
            episode_id = uuid5(
                NAMESPACE_URL,
                f"reliability-memory:case-shaped-v1:{record['case_id']}:{index}",
            )
            created_at = seeded_at - timedelta(minutes=index)
            row = connection.execute(
                """
                INSERT INTO episodes (
                  episode_id, agent_id, customer_id, task_type, summary, context,
                  proposed_action, executed_action, risk_level, autonomy_decision,
                  policy_version, outcome_status, immediate_outcome, verified_success,
                  verification_quality, idempotency_key, embedding, embedding_model,
                  embedding_input_version, embedded_at, created_at, verified_at
                ) VALUES (
                  %s, 'customer-resolution-agent-v2', %s, %s, %s, %s::JSONB,
                  %s::JSONB, %s::JSONB, 'LOW', 'AUTO', 'customer-resolution-v5.0',
                  'VERIFIED_SUCCESS', %s::JSONB, true, 'deterministic', %s,
                  %s::VECTOR, 'deterministic-seed-sha256-v1', 'episode-summary-v1',
                  %s, %s, %s
                )
                ON CONFLICT (idempotency_key) DO NOTHING
                RETURNING episode_id
                """,
                (
                    episode_id,
                    customer["customer_id"],
                    record["task_type"],
                    semantic_text,
                    json.dumps(
                        {
                            "case_id": record["case_id"],
                            "dataset": "case-shaped-autonomy-v1",
                            "evidence_record_ids": [
                                source["source_record_id"] for source in record["evidence_sources"]
                            ],
                            "synthetic": True,
                        }
                    ),
                    json.dumps(action),
                    json.dumps(action),
                    json.dumps(
                        {
                            "expected": action["amount"],
                            "actual": action["amount"],
                            "workflow_verified": True,
                        }
                    ),
                    f"case-shaped-v1-{record['case_id']}-{index}",
                    embedding,
                    created_at,
                    created_at,
                    created_at + timedelta(minutes=2),
                ),
            ).fetchone()
            inserted += row is not None
    return inserted


def main() -> None:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise SystemExit("DATABASE_URL is required")
    try:
        import psycopg
    except ImportError as exc:
        raise SystemExit("Install services/api/requirements.txt first") from exc

    with psycopg.connect(database_url, autocommit=True) as connection:
        count = seed_case_catalog(connection)
    print(f"Customer-resolution catalog ready: {count} cases")


if __name__ == "__main__":
    main()
