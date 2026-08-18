#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from seed_memory import seed_episodes
from seed_case_catalog import (
    CASE_SHAPED_EPISODES_PER_AUTO_CASE,
    seed_case_catalog,
    seed_case_shaped_episodes,
)

MIGRATION_TABLE = "reliability_schema_migrations"
LEGACY_BASELINE = "009_customer_resolution_evidence.sql"


@dataclass(frozen=True)
class Migration:
    name: str
    path: Path
    checksum: str


def discover_migrations(migration_directory: Path) -> tuple[Migration, ...]:
    return tuple(
        Migration(
            name=path.name,
            path=path,
            checksum=hashlib.sha256(path.read_bytes()).hexdigest(),
        )
        for path in sorted(migration_directory.glob("*.sql"))
    )


def pending_migrations(
    migrations: tuple[Migration, ...],
    applied: dict[str, str],
) -> tuple[Migration, ...]:
    pending: list[Migration] = []
    known_names = {migration.name for migration in migrations}
    unknown = sorted(set(applied) - known_names)
    if unknown:
        raise RuntimeError(f"Database contains unknown migrations: {', '.join(unknown)}")

    for migration in migrations:
        recorded_checksum = applied.get(migration.name)
        if recorded_checksum is None:
            pending.append(migration)
        elif recorded_checksum != migration.checksum:
            raise RuntimeError(
                f"Applied migration was modified: {migration.name}. "
                "Restore the original file and add a new numbered migration."
            )
    return tuple(pending)


def split_sql_statements(script: str) -> tuple[str, ...]:
    """Split a migration without treating semicolons in literals/comments as boundaries."""
    statements: list[str] = []
    current: list[str] = []
    quote: str | None = None
    in_line_comment = False
    in_block_comment = False
    index = 0

    while index < len(script):
        character = script[index]
        following = script[index + 1] if index + 1 < len(script) else ""
        current.append(character)

        if in_line_comment:
            if character == "\n":
                in_line_comment = False
        elif in_block_comment:
            if character == "*" and following == "/":
                current.append(following)
                index += 1
                in_block_comment = False
        elif quote is not None:
            if character == quote:
                if following == quote:
                    current.append(following)
                    index += 1
                else:
                    quote = None
        elif character == "-" and following == "-":
            current.append(following)
            index += 1
            in_line_comment = True
        elif character == "/" and following == "*":
            current.append(following)
            index += 1
            in_block_comment = True
        elif character in {"'", '"'}:
            quote = character
        elif character == ";":
            statement = "".join(current).strip()
            if statement:
                statements.append(statement)
            current = []
        index += 1

    trailing = "".join(current).strip()
    if trailing:
        statements.append(trailing)
    if quote is not None or in_block_comment:
        raise ValueError("Migration contains an unterminated SQL literal or block comment")
    return tuple(statements)


def apply_migrations(connection: Any, migrations: tuple[Migration, ...]) -> None:
    connection.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {MIGRATION_TABLE} (
          version STRING PRIMARY KEY,
          checksum STRING NOT NULL,
          applied_at TIMESTAMPTZ NOT NULL DEFAULT now(),
          application STRING NOT NULL DEFAULT 'migration-runner-v1'
        )
        """
    )
    _baseline_legacy_schema(connection, migrations)
    applied = {
        str(version): str(checksum)
        for version, checksum in connection.execute(
            f"SELECT version, checksum FROM {MIGRATION_TABLE}"
        ).fetchall()
    }

    pending = pending_migrations(migrations, applied)
    pending_names = {migration.name for migration in pending}
    for migration in migrations:
        if migration.name not in pending_names:
            print(f"Verified {migration.name}")
            continue
        # CockroachDB schema changes use their native online/autocommit behavior.
        # Every migration must therefore remain retry-safe; the ledger insert
        # follows only after the complete file succeeds.
        for statement in split_sql_statements(migration.path.read_text()):
            connection.execute(statement, prepare=False)
        connection.execute(
            f"""
            INSERT INTO {MIGRATION_TABLE} (version, checksum)
            VALUES (%s, %s)
            """,
            (migration.name, migration.checksum),
        )
        print(f"Applied {migration.name}")


def _baseline_legacy_schema(connection: Any, migrations: tuple[Migration, ...]) -> None:
    recorded_count = connection.execute(f"SELECT count(*) FROM {MIGRATION_TABLE}").fetchone()[0]
    if int(recorded_count) > 0 or not _legacy_schema_is_complete(connection):
        return

    baseline = tuple(migration for migration in migrations if migration.name <= LEGACY_BASELINE)
    with connection.transaction():
        for migration in baseline:
            connection.execute(
                f"""
                INSERT INTO {MIGRATION_TABLE} (version, checksum, application)
                VALUES (%s, %s, 'legacy-baseline-v9')
                """,
                (migration.name, migration.checksum),
            )
    print(f"Baselined {len(baseline)} existing migrations through {LEGACY_BASELINE}")


def _legacy_schema_is_complete(connection: Any) -> bool:
    row = connection.execute(
        """
        SELECT
          EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'analyst_cases'
              AND column_name = 'evidence_bundle'
          )
          AND EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'approvals'
              AND column_name = 'review_summary'
          )
          AND EXISTS (
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = 'public'
              AND table_name = 'payment_transactions'
          )
          AND EXISTS (
            SELECT 1 FROM policies
            WHERE task_type = 'customer_resolution'
              AND version = 'customer-resolution-v5.0'
          )
        """
    ).fetchone()
    return bool(row and row[0])


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Apply CockroachDB migrations and idempotently seed synthetic episodes"
    )
    parser.add_argument("--secret-arn")
    parser.add_argument("--region", default=os.getenv("AWS_REGION", "us-east-1"))
    parser.add_argument("--episodes", type=int, default=5000)
    parser.add_argument(
        "--case-shaped-per-auto-case",
        type=int,
        default=CASE_SHAPED_EPISODES_PER_AUTO_CASE,
    )
    parser.add_argument("--seed", type=int, default=184)
    args = parser.parse_args()
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

    project_root = Path(__file__).resolve().parents[1]
    migrations = discover_migrations(project_root / "db" / "migrations")
    with psycopg.connect(database_url, autocommit=True) as connection:
        apply_migrations(connection, migrations)
        catalog_count = seed_case_catalog(connection)
        inserted = seed_episodes(connection, args.episodes, args.seed)
        case_shaped_inserted = seed_case_shaped_episodes(connection, args.case_shaped_per_auto_case)
    print(
        f"CockroachDB seed ready: {catalog_count} cases, "
        f"{inserted} base episodes inserted, {args.episodes - inserted} existing, "
        f"{case_shaped_inserted} case-shaped evidence episodes inserted"
    )


def database_url_from_secret(secret_arn: str | None, region: str) -> str | None:
    if not secret_arn:
        return None
    import boto3

    response: dict[str, Any] = boto3.client(
        "secretsmanager",
        region_name=region,
    ).get_secret_value(SecretId=secret_arn)
    secret = response.get("SecretString")
    if not isinstance(secret, str) or not secret:
        raise RuntimeError("CockroachDB secret does not contain SecretString")
    try:
        value = json.loads(secret)
    except json.JSONDecodeError:
        return secret
    if not isinstance(value, dict):
        raise RuntimeError("CockroachDB secret must be a URL or JSON object")
    database_url = value.get("DATABASE_URL") or value.get("database_url")
    if not isinstance(database_url, str) or not database_url:
        raise RuntimeError("CockroachDB secret is missing DATABASE_URL")
    return database_url


if __name__ == "__main__":
    main()
