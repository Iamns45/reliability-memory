#!/usr/bin/env python3
from __future__ import annotations

import argparse
import math
import os
import random
import sys
import time
from pathlib import Path
from typing import Any, Protocol

from migrate_and_seed import database_url_from_secret

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "services" / "api"))

from app.bedrock import TitanEmbeddingProvider  # noqa: E402

EPISODE_INPUT_VERSION = "episode-summary-v1"
CORRECTION_INPUT_VERSION = "human-correction-v1"


class Embeddings(Protocol):
    model_id: str

    def embed(self, text: str) -> list[float]: ...


class RateLimiter:
    def __init__(self, requests_per_second: float) -> None:
        if requests_per_second <= 0:
            raise ValueError("requests_per_second must be positive")
        self.minimum_interval = 1.0 / requests_per_second
        self.last_request_at: float | None = None

    def wait(self) -> None:
        now = time.monotonic()
        if self.last_request_at is not None:
            remaining = self.minimum_interval - (now - self.last_request_at)
            if remaining > 0:
                time.sleep(remaining)
        self.last_request_at = time.monotonic()


def _is_throttled(error: Exception) -> bool:
    response = getattr(error, "response", None)
    if not isinstance(response, dict):
        return False
    details = response.get("Error", {})
    return isinstance(details, dict) and details.get("Code") in {
        "ThrottlingException",
        "TooManyRequestsException",
        "ServiceUnavailableException",
    }


def embed_with_retry(
    provider: Embeddings,
    text: str,
    rate_limiter: RateLimiter,
    max_attempts: int = 7,
) -> list[float]:
    for attempt in range(max_attempts):
        rate_limiter.wait()
        try:
            return provider.embed(text)
        except Exception as error:
            if not _is_throttled(error) or attempt == max_attempts - 1:
                raise
            delay = min(30.0, (2**attempt) + random.uniform(0.0, 1.0))
            time.sleep(delay)
    raise RuntimeError("embedding retry budget exhausted")


def vector_literal(embedding: list[float]) -> str:
    if len(embedding) != 1_024:
        raise ValueError("Embeddings must contain exactly 1024 dimensions")
    if not all(math.isfinite(value) for value in embedding):
        raise ValueError("Embeddings must contain only finite values")
    return "[" + ",".join(f"{value:.8f}" for value in embedding) + "]"


def reindex_table(
    connection: Any,
    provider: Embeddings,
    rate_limiter: RateLimiter,
    table: str,
    input_version: str,
    batch_size: int,
    remaining: int | None,
    progress_every: int,
) -> int:
    if table == "episodes":
        identifier = "episode_id"
        text_expression = "summary"
    elif table == "human_corrections":
        identifier = "correction_id"
        text_expression = "'human correction | ' || reason || ' | ' || lesson"
    else:  # pragma: no cover - only module constants call this function
        raise ValueError(f"Unsupported embedding table: {table}")

    updated = 0
    embedding_cache: dict[str, list[float]] = {}
    while remaining is None or updated < remaining:
        limit = batch_size if remaining is None else min(batch_size, remaining - updated)
        rows = connection.execute(
            f"""
            SELECT {identifier}, {text_expression} AS embedding_text
            FROM {table}
            WHERE embedding IS NOT NULL
              AND (
                embedding_model IS DISTINCT FROM %s
                OR embedding_input_version IS DISTINCT FROM %s
              )
            ORDER BY {identifier}
            LIMIT %s
            """,
            (provider.model_id, input_version, limit),
        ).fetchall()
        if not rows:
            break

        for record_id, embedding_text in rows:
            text = str(embedding_text)
            embedding = embedding_cache.get(text)
            if embedding is None:
                embedding = embed_with_retry(provider, text, rate_limiter)
                embedding_cache[text] = embedding
            result = connection.execute(
                f"""
                UPDATE {table}
                SET embedding = %s::VECTOR,
                    embedding_model = %s,
                    embedding_input_version = %s,
                    embedded_at = now()
                WHERE {identifier} = %s
                  AND (
                    embedding_model IS DISTINCT FROM %s
                    OR embedding_input_version IS DISTINCT FROM %s
                  )
                """,
                (
                    vector_literal(embedding),
                    provider.model_id,
                    input_version,
                    record_id,
                    provider.model_id,
                    input_version,
                ),
            )
            if result.rowcount > 0:
                updated += 1
                if updated % progress_every == 0:
                    print(f"Re-indexed {updated} {table} records")

    return updated


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Resume-safe CockroachDB memory re-indexing with Amazon Titan embeddings"
    )
    parser.add_argument("--secret-arn")
    parser.add_argument("--region", default=os.getenv("AWS_REGION", "us-east-1"))
    parser.add_argument("--batch-size", type=int, default=100)
    parser.add_argument("--max-records", type=int, default=0)
    parser.add_argument("--progress-every", type=int, default=100)
    parser.add_argument("--requests-per-second", type=float, default=10.0)
    args = parser.parse_args()
    if args.batch_size <= 0 or args.progress_every <= 0 or args.max_records < 0:
        raise SystemExit(
            "batch-size and progress-every must be positive; max-records cannot be negative"
        )

    database_url = os.getenv("DATABASE_URL") or database_url_from_secret(
        args.secret_arn,
        args.region,
    )
    if not database_url:
        raise SystemExit("DATABASE_URL or --secret-arn is required")

    try:
        import psycopg
    except ImportError as exc:
        raise SystemExit("Install services/api/requirements.txt first") from exc

    provider = TitanEmbeddingProvider(region=args.region)
    limiter = RateLimiter(args.requests_per_second)
    remaining = args.max_records or None
    with psycopg.connect(database_url, autocommit=True) as connection:
        episodes = reindex_table(
            connection,
            provider,
            limiter,
            "episodes",
            EPISODE_INPUT_VERSION,
            args.batch_size,
            remaining,
            args.progress_every,
        )
        if remaining is not None:
            remaining -= episodes
        corrections = reindex_table(
            connection,
            provider,
            limiter,
            "human_corrections",
            CORRECTION_INPUT_VERSION,
            args.batch_size,
            remaining,
            args.progress_every,
        )

    print(
        "Titan vector re-index ready: "
        f"{episodes} episodes and {corrections} corrections updated with {provider.model_id}"
    )


if __name__ == "__main__":
    main()
