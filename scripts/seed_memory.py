#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import random
from datetime import datetime, timedelta, timezone
from uuid import uuid4


TASKS = [
    ("damaged_item_keep_offer", "partial_refund", 0.982, (20, 90)),
    ("delivery_not_found", "reship", 0.971, (35, 160)),
    ("early_product_failure", "replacement", 0.989, (30, 180)),
    ("freight_damage_high_value", "replacement", 0.963, (300, 900)),
    ("wrong_variant_exchange", "exchange", 0.992, (8, 40)),
    ("missing_component", "ship_missing_part", 0.991, (10, 80)),
    ("late_delivery_recovery", "store_credit", 0.987, (10, 40)),
    ("product_safety_incident", "safety_escalation", 0.975, (60, 300)),
    ("delivery_theft_review", "reship", 0.952, (50, 250)),
    ("fit_dissatisfaction", "store_credit", 0.966, (40, 180)),
    ("serial_mismatch_return", "deny", 0.984, (300, 900)),
    ("empty_box_claim", "replacement", 0.981, (40, 250)),
    ("counterfeit_marketplace_claim", "seller_investigation", 0.968, (150, 700)),
    ("warranty_grace_exception", "warranty_repair", 0.934, (30, 200)),
    ("partial_shipment", "reship", 0.991, (20, 140)),
    ("guided_product_recovery", "guided_troubleshooting", 0.993, (0, 10)),
    ("repeat_claim_known_defect", "partial_refund", 0.961, (15, 60)),
]


def normalized_embedding(text: str, dimensions: int = 1024) -> list[float]:
    values: list[float] = []
    counter = 0
    while len(values) < dimensions:
        digest = hashlib.sha256(f"{counter}:{text}".encode()).digest()
        values.extend((byte / 127.5) - 1.0 for byte in digest)
        counter += 1
    values = values[:dimensions]
    norm = math.sqrt(sum(value * value for value in values)) or 1.0
    return [value / norm for value in values]


def seed_episodes(connection: object, episode_count: int, seed: int) -> int:
    rng = random.Random(seed)
    now = datetime.now(timezone.utc)
    inserted = 0
    for index in range(episode_count):
        task_type, action_type, success_rate, value_range = TASKS[index % len(TASKS)]
        amount = round(rng.uniform(*value_range), 2)
        outcome_roll = rng.random()
        success = outcome_roll < success_rate
        corrected = not success and outcome_roll < success_rate + 0.02
        outcome_status = (
            "VERIFIED_SUCCESS"
            if success
            else "HUMAN_CORRECTED" if corrected else "VERIFIED_FAILURE"
        )
        summary = (
            f"Synthetic {task_type.replace('_', ' ')} using {action_type} "
            f"for ${amount:.2f} under customer-resolution-v5.0"
        )
        embedding = "[" + ",".join(f"{value:.8f}" for value in normalized_embedding(summary)) + "]"
        episode_id = uuid4()
        created_at = now - timedelta(days=rng.randint(0, 365))
        context = {
            "amount": amount,
            "synthetic": True,
            "seed": seed,
            "evidence_model": "issue-specific-resolution",
        }
        autonomy_decision = (
            "AUTO"
            if success
            and amount <= 150
            and task_type
            not in {
                "product_safety_incident",
                "counterfeit_marketplace_claim",
                "serial_mismatch_return",
            }
            else "VERIFY" if success and amount <= 500 else "HUMAN"
        )
        row = connection.execute(  # type: ignore[attr-defined]
            """
            INSERT INTO episodes (
              episode_id, agent_id, customer_id, task_type, summary, context,
              proposed_action, executed_action, risk_level, autonomy_decision,
              policy_version, outcome_status, immediate_outcome, verified_success,
              verification_quality, idempotency_key, embedding, embedding_model,
              embedding_input_version, embedded_at, created_at, verified_at
            ) VALUES (
              %s, 'customer-resolution-agent-v2', NULL, %s, %s, %s::JSONB, %s::JSONB, %s::JSONB,
              %s, %s, 'customer-resolution-v5.0', %s, %s::JSONB, %s, 'deterministic',
              %s, %s::VECTOR, %s, 'episode-summary-v1', %s, %s, %s
            )
            ON CONFLICT (idempotency_key) DO NOTHING
            RETURNING episode_id
            """,
            (
                episode_id,
                task_type,
                summary,
                json.dumps(context),
                json.dumps({"action_type": action_type, "amount": amount}),
                json.dumps({"action_type": action_type, "amount": amount}) if success else None,
                "LOW" if amount <= 100 else "MEDIUM" if amount <= 1000 else "HIGH",
                autonomy_decision,
                outcome_status,
                json.dumps({"expected": amount, "actual": amount if success else 0}),
                success,
                f"seed-{seed}-{index}",
                embedding,
                "deterministic-seed-sha256-v1",
                created_at,
                created_at,
                created_at + timedelta(minutes=2),
            ),
        ).fetchone()
        inserted += row is not None
    return inserted


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Seed synthetic verified Reliability Memory episodes"
    )
    parser.add_argument("--episodes", type=int, default=5000)
    parser.add_argument("--seed", type=int, default=184)
    args = parser.parse_args()
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise SystemExit("DATABASE_URL is required")

    try:
        import psycopg
    except ImportError as exc:
        raise SystemExit("Install services/api/requirements.txt first") from exc

    with psycopg.connect(database_url, autocommit=True) as connection:
        inserted = seed_episodes(connection, args.episodes, args.seed)
    print(f"Seeded {inserted} new deterministic synthetic episodes")


if __name__ == "__main__":
    main()
