from __future__ import annotations

import sys
import tempfile
import unittest
from contextlib import nullcontext
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from migrate_and_seed import (
    _baseline_legacy_schema,
    discover_migrations,
    pending_migrations,
    split_sql_statements,
)


class FakeResult:
    def __init__(self, row: tuple[Any, ...]) -> None:
        self.row = row

    def fetchone(self) -> tuple[Any, ...]:
        return self.row


class FakeLegacyConnection:
    def __init__(self) -> None:
        self.baselined: list[tuple[str, str]] = []

    def execute(
        self,
        query: str,
        parameters: tuple[str, str] | None = None,
    ) -> FakeResult:
        if "SELECT count(*)" in query:
            return FakeResult((0,))
        if "information_schema.columns" in query:
            return FakeResult((True,))
        if "INSERT INTO reliability_schema_migrations" in query:
            assert parameters is not None
            self.baselined.append(parameters)
            return FakeResult(())
        raise AssertionError(f"Unexpected SQL: {query}")

    def transaction(self) -> Any:
        return nullcontext()


class MigrationRunnerTests(unittest.TestCase):
    def test_sql_splitter_preserves_semicolons_in_literals_and_comments(self) -> None:
        statements = split_sql_statements(
            """
            -- comment with a semicolon;
            INSERT INTO sample (value) VALUES ('customer''s; value');
            /* another ; comment */
            UPDATE sample SET value = "quoted;identifier";
            """
        )

        self.assertEqual(len(statements), 2)
        self.assertIn("customer''s; value", statements[0])
        self.assertIn('"quoted;identifier"', statements[1])

    def test_sql_splitter_rejects_unterminated_literals(self) -> None:
        with self.assertRaisesRegex(ValueError, "unterminated"):
            split_sql_statements("SELECT 'unfinished;")

    def test_legacy_baseline_uses_psycopg_connection_execute(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for number in range(1, 9):
                (root / f"{number:03d}_migration.sql").write_text(
                    f"SELECT {number};",
                    encoding="utf-8",
                )
            (root / "009_customer_resolution_evidence.sql").write_text(
                "SELECT 9;",
                encoding="utf-8",
            )
            (root / "010_embedding_provenance.sql").write_text(
                "SELECT 10;",
                encoding="utf-8",
            )
            connection = FakeLegacyConnection()

            _baseline_legacy_schema(connection, discover_migrations(root))

            self.assertEqual(len(connection.baselined), 9)
            self.assertEqual(connection.baselined[0][0], "001_migration.sql")
            self.assertEqual(
                connection.baselined[-1][0],
                "009_customer_resolution_evidence.sql",
            )

    def test_only_unrecorded_migrations_are_pending(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "001_initial.sql").write_text("SELECT 1;", encoding="utf-8")
            (root / "002_next.sql").write_text("SELECT 2;", encoding="utf-8")
            migrations = discover_migrations(root)

            pending = pending_migrations(
                migrations,
                {migrations[0].name: migrations[0].checksum},
            )

            self.assertEqual([migration.name for migration in pending], ["002_next.sql"])

    def test_modified_applied_migration_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            migration_path = root / "001_initial.sql"
            migration_path.write_text("SELECT 1;", encoding="utf-8")
            original = discover_migrations(root)
            migration_path.write_text("SELECT 2;", encoding="utf-8")
            modified = discover_migrations(root)

            with self.assertRaisesRegex(RuntimeError, "Applied migration was modified"):
                pending_migrations(
                    modified,
                    {original[0].name: original[0].checksum},
                )

    def test_unknown_database_migration_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "001_initial.sql").write_text("SELECT 1;", encoding="utf-8")
            migrations = discover_migrations(root)

            with self.assertRaisesRegex(RuntimeError, "unknown migrations"):
                pending_migrations(migrations, {"999_unknown.sql": "checksum"})


if __name__ == "__main__":
    unittest.main()
