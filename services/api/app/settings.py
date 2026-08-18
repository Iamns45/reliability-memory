from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class Settings:
    """Validated runtime configuration loaded once per Lambda container."""

    database_url: str | None
    use_bedrock: bool
    aws_region: str
    bedrock_model_id: str
    cors_origins: tuple[str, ...]
    mcp_api_key: str | None = None
    mcp_cluster_id: str | None = None
    mcp_endpoint: str = "https://cockroachlabs.cloud/mcp"
    mcp_database: str = "reliability_memory"
    mcp_required: bool = False
    mcp_timeout_seconds: float = 12.0

    @property
    def mcp_configured(self) -> bool:
        return bool(self.mcp_api_key and self.mcp_cluster_id)

    @classmethod
    def from_environment(cls, environment: Mapping[str, str] | None = None) -> "Settings":
        values = os.environ if environment is None else environment
        database_url = values.get("DATABASE_URL") or _database_url_from_secret(values)
        mcp_api_key = values.get("COCKROACH_MCP_API_KEY") or _mcp_api_key_from_secret(values)
        mcp_cluster_id = values.get("COCKROACH_MCP_CLUSTER_ID")
        mcp_required = _read_boolean(values.get("COCKROACH_MCP_REQUIRED", "false"))
        if mcp_required and (not mcp_api_key or not mcp_cluster_id):
            raise ValueError(
                "COCKROACH_MCP_REQUIRED needs a service-account API key and cluster ID"
            )
        return cls(
            database_url=database_url,
            use_bedrock=_read_boolean(values.get("USE_BEDROCK", "false")),
            aws_region=values.get("AWS_REGION", "us-east-1"),
            bedrock_model_id=values.get("BEDROCK_MODEL_ID", "amazon.nova-lite-v1:0"),
            cors_origins=_read_origins(values.get("CORS_ORIGINS", "http://localhost:3000")),
            mcp_api_key=mcp_api_key,
            mcp_cluster_id=mcp_cluster_id,
            mcp_endpoint=values.get(
                "COCKROACH_MCP_ENDPOINT",
                "https://cockroachlabs.cloud/mcp",
            ),
            mcp_database=values.get("COCKROACH_MCP_DATABASE", "reliability_memory"),
            mcp_required=mcp_required,
            mcp_timeout_seconds=_read_positive_float(
                values.get("COCKROACH_MCP_TIMEOUT_SECONDS", "12")
            ),
        )


def _database_url_from_secret(environment: Mapping[str, str]) -> str | None:
    secret_arn = environment.get("DATABASE_SECRET_ARN")
    if not secret_arn:
        return None

    import boto3

    client = boto3.client(
        "secretsmanager",
        region_name=environment.get("AWS_REGION", "us-east-1"),
    )
    response: dict[str, Any] = client.get_secret_value(SecretId=secret_arn)
    secret = response.get("SecretString")
    if not isinstance(secret, str) or not secret:
        raise RuntimeError("CockroachDB secret does not contain SecretString")

    try:
        payload = json.loads(secret)
    except json.JSONDecodeError:
        return secret

    if not isinstance(payload, dict):
        raise RuntimeError("CockroachDB secret must be a URL or JSON object")

    database_url = payload.get("DATABASE_URL") or payload.get("database_url")
    if not isinstance(database_url, str) or not database_url:
        raise RuntimeError("CockroachDB secret is missing DATABASE_URL")
    return database_url


def _mcp_api_key_from_secret(environment: Mapping[str, str]) -> str | None:
    secret_arn = environment.get("COCKROACH_MCP_SECRET_ARN")
    if not secret_arn:
        return None
    secret = _secret_string(secret_arn, environment)
    try:
        payload = json.loads(secret)
    except json.JSONDecodeError:
        return secret
    if not isinstance(payload, dict):
        raise RuntimeError("CockroachDB Managed MCP secret must be a key or JSON object")
    api_key = payload.get("COCKROACH_MCP_API_KEY") or payload.get("api_key")
    if not isinstance(api_key, str) or not api_key:
        raise RuntimeError("CockroachDB Managed MCP secret is missing its API key")
    return api_key


def _secret_string(secret_arn: str, environment: Mapping[str, str]) -> str:
    import boto3

    client = boto3.client(
        "secretsmanager",
        region_name=environment.get("AWS_REGION", "us-east-1"),
    )
    response: dict[str, Any] = client.get_secret_value(SecretId=secret_arn)
    secret = response.get("SecretString")
    if not isinstance(secret, str) or not secret:
        raise RuntimeError("AWS secret does not contain SecretString")
    return secret


def _read_boolean(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"true", "1", "yes"}:
        return True
    if normalized in {"false", "0", "no"}:
        return False
    raise ValueError(f"Invalid boolean configuration value: {value!r}")


def _read_origins(value: str) -> tuple[str, ...]:
    origins = tuple(origin.strip() for origin in value.split(",") if origin.strip())
    return origins or ("http://localhost:3000",)


def _read_positive_float(value: str) -> float:
    number = float(value)
    if number <= 0:
        raise ValueError("Timeout configuration must be greater than zero")
    return number
