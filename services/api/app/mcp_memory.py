from __future__ import annotations

import asyncio
import hashlib
import json
from collections.abc import Iterable, Mapping, Sequence
from datetime import datetime, timezone
from typing import Any, Protocol, cast

from .domain import AgentRun, McpVerificationReceipt


class McpReadGateway(Protocol):
    """Minimal boundary around the Managed MCP transport."""

    endpoint: str
    cluster_id: str
    database: str

    def execute_selects(self, statements: Sequence[str]) -> tuple[Any, ...]: ...


class McpVerifier(Protocol):
    provider: str
    required: bool

    def verify(
        self,
        run: AgentRun,
        expected_neighbor_ids: Sequence[str],
    ) -> McpVerificationReceipt: ...


class CockroachCloudMcpGateway:
    """Cluster-scoped, read-only client for CockroachDB Cloud Managed MCP."""

    TOOL_NAME = "select_query"

    def __init__(
        self,
        *,
        endpoint: str,
        api_key: str,
        cluster_id: str,
        database: str,
        timeout_seconds: float = 12.0,
    ) -> None:
        if not endpoint.startswith("https://"):
            raise ValueError("CockroachDB Managed MCP endpoint must use HTTPS")
        if not api_key.strip():
            raise ValueError("CockroachDB Managed MCP API key is required")
        if not cluster_id.strip():
            raise ValueError("CockroachDB Managed MCP cluster ID is required")
        self.endpoint = endpoint.rstrip("/")
        self.api_key = api_key.strip()
        self.cluster_id = cluster_id.strip()
        self.database = database.strip()
        self.timeout_seconds = timeout_seconds

    def execute_selects(self, statements: Sequence[str]) -> tuple[Any, ...]:
        for statement in statements:
            if statement.lstrip().split(maxsplit=1)[0].upper() not in {"SELECT", "WITH"}:
                raise ValueError("Managed MCP gateway accepts read-only SELECT statements")
        try:
            return asyncio.run(self._execute_selects(statements))
        except Exception as exc:
            safe_message = _exception_message(exc).replace(self.api_key, "[redacted]")
            raise RuntimeError(
                f"Managed MCP read failed ({type(exc).__name__}): {safe_message[:300]}"
            ) from exc

    async def _execute_selects(self, statements: Sequence[str]) -> tuple[Any, ...]:
        from mcp import ClientSession
        from mcp.client.streamable_http import streamablehttp_client

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "mcp-cluster-id": self.cluster_id,
        }
        async with streamablehttp_client(
            self.endpoint,
            headers=headers,
            timeout=self.timeout_seconds,
            sse_read_timeout=self.timeout_seconds,
        ) as (read_stream, write_stream, _session_id):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                tools_result = await session.list_tools()
                tool = next(
                    (
                        candidate
                        for candidate in tools_result.tools
                        if candidate.name == self.TOOL_NAME
                    ),
                    None,
                )
                if tool is None:
                    available = ", ".join(
                        sorted(candidate.name for candidate in tools_result.tools)
                    )
                    raise RuntimeError(
                        f"Managed MCP did not expose {self.TOOL_NAME}; available tools: {available}"
                    )
                outputs: list[Any] = []
                for statement in statements:
                    arguments = _select_arguments(
                        cast(Mapping[str, Any], tool.inputSchema),
                        statement,
                        database=self.database,
                    )
                    result = await session.call_tool(self.TOOL_NAME, arguments=arguments)
                    if result.isError:
                        raise RuntimeError(_tool_error_message(result.content))
                    outputs.append(_tool_payload(result))
                return tuple(outputs)


class DisabledMcpVerifier:
    """Local-development verifier that makes the disabled state explicit in results."""

    provider = "cockroachdb-cloud-managed-mcp"
    required = False

    def verify(
        self,
        run: AgentRun,
        expected_neighbor_ids: Sequence[str],
    ) -> McpVerificationReceipt:
        return _receipt(
            provider=self.provider,
            endpoint="not-configured",
            cluster_scope="not-configured",
            database="reliability_memory",
            required=False,
            verified=False,
            episode_id=run.run_id,
            observed_episode_id=None,
            observed_decision=None,
            observed_policy_version=None,
            vector_check_performed=False,
            expected_neighbor_ids=tuple(expected_neighbor_ids),
            vector_neighbor_ids=(),
            matching_neighbor_ids=(),
            failure_reason="Managed MCP verification is disabled for this local runtime.",
        )


class McpMemoryVerifier:
    """Verifies persistence and vector-memory evidence through Managed MCP."""

    provider = "cockroachdb-cloud-managed-mcp"

    def __init__(self, gateway: McpReadGateway, *, required: bool) -> None:
        self.gateway = gateway
        self.required = required

    def verify(
        self,
        run: AgentRun,
        expected_neighbor_ids: Sequence[str],
    ) -> McpVerificationReceipt:
        expected = tuple(dict.fromkeys(str(item) for item in expected_neighbor_ids))
        vector_check_performed = run.case.memory_enabled
        statements = [_episode_query(run)]
        if vector_check_performed:
            statements.append(_vector_query(run))

        try:
            payloads = self.gateway.execute_selects(statements)
            episode_rows = _records(payloads[0])
            observed = next(
                (row for row in episode_rows if str(row.get("episode_id", "")) == str(run.run_id)),
                None,
            )
            vector_rows = _records(payloads[1]) if vector_check_performed else []
            vector_ids = tuple(
                dict.fromkeys(
                    str(row["episode_id"])
                    for row in vector_rows
                    if row.get("episode_id") is not None
                    and str(row["episode_id"]) != str(run.run_id)
                )
            )
            matching = tuple(item for item in expected if item in set(vector_ids))
            persisted_match = bool(
                observed
                and str(observed.get("autonomy_decision")) == run.permission.mode.value
                and str(observed.get("policy_version")) == run.permission.policy_version
            )
            vector_match = not expected or bool(matching)
            verified = persisted_match and (not vector_check_performed or vector_match)
            failure_reason: str | None = None
            if not persisted_match:
                failure_reason = "Persisted episode, permission, or policy version did not match."
            elif vector_check_performed and not vector_match:
                failure_reason = (
                    "Managed MCP vector neighbors did not overlap direct vector memory."
                )
            return _receipt(
                provider=self.provider,
                endpoint=self.gateway.endpoint,
                cluster_scope=self.gateway.cluster_id,
                database=self.gateway.database,
                required=self.required,
                verified=verified,
                episode_id=run.run_id,
                observed_episode_id=(
                    str(observed.get("episode_id")) if observed is not None else None
                ),
                observed_decision=(
                    str(observed.get("autonomy_decision")) if observed is not None else None
                ),
                observed_policy_version=(
                    str(observed.get("policy_version")) if observed is not None else None
                ),
                vector_check_performed=vector_check_performed,
                expected_neighbor_ids=expected,
                vector_neighbor_ids=vector_ids,
                matching_neighbor_ids=matching,
                failure_reason=failure_reason,
            )
        except Exception as exc:
            return _receipt(
                provider=self.provider,
                endpoint=self.gateway.endpoint,
                cluster_scope=self.gateway.cluster_id,
                database=self.gateway.database,
                required=self.required,
                verified=False,
                episode_id=run.run_id,
                observed_episode_id=None,
                observed_decision=None,
                observed_policy_version=None,
                vector_check_performed=vector_check_performed,
                expected_neighbor_ids=expected,
                vector_neighbor_ids=(),
                matching_neighbor_ids=(),
                failure_reason=str(exc)[:500],
            )


def _episode_query(run: AgentRun) -> str:
    episode_id = _sql_literal(str(run.run_id))
    return (
        "SELECT episode_id::STRING AS episode_id, autonomy_decision, policy_version "
        f"FROM episodes WHERE episode_id = {episode_id}::UUID LIMIT 1"
    )


def _vector_query(run: AgentRun) -> str:
    episode_id = _sql_literal(str(run.run_id))
    task_type = _sql_literal(run.case.task_type)
    return f"""
        SELECT candidate.episode_id::STRING AS episode_id,
               1 - (candidate.embedding <=> target.embedding) AS similarity
        FROM episodes AS candidate
        CROSS JOIN (
            SELECT embedding, embedding_model
            FROM episodes
            WHERE episode_id = {episode_id}::UUID
        ) AS target
        WHERE candidate.episode_id != {episode_id}::UUID
          AND candidate.task_type = {task_type}
          AND candidate.outcome_status IN ('VERIFIED_SUCCESS', 'VERIFIED_FAILURE')
          AND candidate.embedding IS NOT NULL
          AND candidate.embedding_model = target.embedding_model
        ORDER BY candidate.embedding <-> target.embedding
        LIMIT 5
    """.strip()


def _sql_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _select_arguments(
    schema: Mapping[str, Any],
    statement: str,
    *,
    database: str,
) -> dict[str, Any]:
    properties = schema.get("properties")
    if not isinstance(properties, Mapping):
        raise RuntimeError("Managed MCP select_query has no inspectable input schema")
    query_key = next(
        (key for key in ("query", "sql", "statement") if key in properties),
        None,
    )
    if query_key is None:
        raise RuntimeError("Managed MCP select_query schema has no SQL argument")
    arguments: dict[str, Any] = {query_key: statement}
    for key in ("database", "database_name", "databaseName"):
        if key in properties:
            arguments[key] = database
            break
    # The gateway always scopes the session with the mcp-cluster-id header.
    # Managed MCP rejects a duplicate cluster_id tool argument in this mode.
    return arguments


def _exception_message(exc: BaseException) -> str:
    """Return actionable leaf errors from async exception groups."""

    if isinstance(exc, BaseExceptionGroup):
        messages = [_exception_message(nested) for nested in exc.exceptions]
        return "; ".join(message for message in messages if message)
    return str(exc)


def _tool_payload(result: Any) -> Any:
    structured = getattr(result, "structuredContent", None)
    if structured is not None:
        return structured
    values: list[Any] = []
    for item in getattr(result, "content", []):
        text = getattr(item, "text", None)
        if not isinstance(text, str):
            continue
        normalized = text.strip()
        if normalized.startswith("```") and normalized.endswith("```"):
            normalized = normalized.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
        try:
            values.append(json.loads(normalized))
        except json.JSONDecodeError:
            values.append({"text": normalized})
    return values


def _tool_error_message(content: Iterable[Any]) -> str:
    messages = [str(getattr(item, "text", "")) for item in content]
    return "Managed MCP tool error: " + " ".join(message for message in messages if message)[:300]


def _records(value: Any) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []

    def visit(item: Any) -> None:
        if isinstance(item, Mapping):
            columns = item.get("columns")
            rows = item.get("rows")
            tabular_payload = (
                isinstance(columns, Sequence)
                and not isinstance(columns, (str, bytes, bytearray))
                and isinstance(rows, Sequence)
                and not isinstance(rows, (str, bytes, bytearray))
            )
            if tabular_payload:
                assert isinstance(columns, Sequence)
                assert isinstance(rows, Sequence)
                names = [
                    str(column.get("name", "")) if isinstance(column, Mapping) else str(column)
                    for column in columns
                ]
                for row in rows:
                    if isinstance(row, Mapping):
                        visit(row)
                    elif isinstance(row, Sequence) and not isinstance(row, (str, bytes, bytearray)):
                        visit(dict(zip(names, row, strict=False)))
            if "episode_id" in item:
                records.append(dict(item))
            for key, nested in item.items():
                if tabular_payload and key in {"columns", "rows"}:
                    continue
                visit(nested)
        elif isinstance(item, Sequence) and not isinstance(item, (str, bytes, bytearray)):
            for nested in item:
                visit(nested)

    visit(value)
    return records


def _receipt(
    *,
    provider: str,
    endpoint: str,
    cluster_scope: str,
    database: str,
    required: bool,
    verified: bool,
    episode_id: Any,
    observed_episode_id: str | None,
    observed_decision: str | None,
    observed_policy_version: str | None,
    vector_check_performed: bool,
    expected_neighbor_ids: tuple[str, ...],
    vector_neighbor_ids: tuple[str, ...],
    matching_neighbor_ids: tuple[str, ...],
    failure_reason: str | None,
) -> McpVerificationReceipt:
    checked_at = datetime.now(timezone.utc)
    public_payload = {
        "provider": provider,
        "endpoint": endpoint,
        "cluster_scope": cluster_scope,
        "database": database,
        "tool_name": CockroachCloudMcpGateway.TOOL_NAME,
        "required": required,
        "verified": verified,
        "episode_id": str(episode_id),
        "observed_episode_id": observed_episode_id,
        "observed_decision": observed_decision,
        "observed_policy_version": observed_policy_version,
        "vector_check_performed": vector_check_performed,
        "expected_neighbor_ids": expected_neighbor_ids,
        "vector_neighbor_ids": vector_neighbor_ids,
        "matching_neighbor_ids": matching_neighbor_ids,
        "checked_at": checked_at.isoformat(),
        "failure_reason": failure_reason,
    }
    receipt_hash = hashlib.sha256(
        json.dumps(public_payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    receipt = McpVerificationReceipt(
        provider=provider,
        endpoint=endpoint,
        cluster_scope=cluster_scope,
        database=database,
        tool_name=CockroachCloudMcpGateway.TOOL_NAME,
        required=required,
        verified=verified,
        episode_id=episode_id,
        observed_episode_id=observed_episode_id,
        observed_decision=observed_decision,
        observed_policy_version=observed_policy_version,
        vector_check_performed=vector_check_performed,
        expected_neighbor_ids=expected_neighbor_ids,
        vector_neighbor_ids=vector_neighbor_ids,
        matching_neighbor_ids=matching_neighbor_ids,
        checked_at=checked_at,
        receipt_hash=receipt_hash,
        failure_reason=failure_reason,
    )
    return receipt
