#!/usr/bin/env python3
"""Validate the cluster-scoped Managed MCP read and vector-query path safely."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "services" / "api"))

from app.mcp_memory import CockroachCloudMcpGateway  # noqa: E402
from app.settings import Settings  # noqa: E402


def main() -> None:
    settings = Settings.from_environment()
    if not settings.mcp_configured:
        raise SystemExit(
            "Set COCKROACH_MCP_CLUSTER_ID and COCKROACH_MCP_API_KEY, or configure "
            "COCKROACH_MCP_SECRET_ARN."
        )
    assert settings.mcp_api_key is not None
    assert settings.mcp_cluster_id is not None
    gateway = CockroachCloudMcpGateway(
        endpoint=settings.mcp_endpoint,
        api_key=settings.mcp_api_key,
        cluster_id=settings.mcp_cluster_id,
        database=settings.mcp_database,
        timeout_seconds=settings.mcp_timeout_seconds,
    )
    metadata_query = """
        SELECT current_database() AS database_name,
               count(*)::INT AS episode_count,
               count(*) FILTER (WHERE embedding IS NOT NULL)::INT AS embedded_episode_count
        FROM episodes
    """.strip()
    vector_query = """
        SELECT candidate.episode_id::STRING AS episode_id,
               1 - (candidate.embedding <=> target.embedding) AS similarity
        FROM episodes AS candidate
        CROSS JOIN (
            SELECT episode_id, embedding, embedding_model
            FROM episodes
            WHERE embedding IS NOT NULL
            ORDER BY created_at DESC
            LIMIT 1
        ) AS target
        WHERE candidate.episode_id != target.episode_id
          AND candidate.embedding IS NOT NULL
          AND candidate.embedding_model = target.embedding_model
        ORDER BY candidate.embedding <-> target.embedding
        LIMIT 3
    """.strip()
    metadata, neighbors = gateway.execute_selects((metadata_query, vector_query))
    report: dict[str, Any] = {
        "status": "verified",
        "endpoint": settings.mcp_endpoint,
        "cluster_scope": f"{settings.mcp_cluster_id[:8]}…",
        "database": settings.mcp_database,
        "tool": gateway.TOOL_NAME,
        "metadata_result": metadata,
        "vector_result": neighbors,
    }
    print(json.dumps(report, indent=2, default=str))


if __name__ == "__main__":
    main()
