"""
Unit tests for database/bootstrap.py.

The two things that touch the outside world — psycopg2.connect and
subprocess.run (for `alembic upgrade head`) — are mocked throughout.
File-selection logic (which .sql files get picked up, and in what
order) is exercised against real temporary files via pytest's tmp_path
fixture instead of mocking Path.glob, the same approach
test_attachment_service.py uses for filesystem-facing code: it's
closer to what actually runs than mocking the filesystem API itself.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from database import bootstrap

# =====================================================
# _schema_already_bootstrapped
# =====================================================


class TestSchemaAlreadyBootstrapped:

    def test_returns_true_when_users_table_exists(self):
        conn = MagicMock()
        conn.cursor.return_value.__enter__.return_value.fetchone.return_value = (12345,)

        assert bootstrap._schema_already_bootstrapped(conn) is True

    def test_returns_false_when_users_table_missing(self):
        conn = MagicMock()
        # to_regclass() returns NULL (None) for a table that doesn't exist.
        conn.cursor.return_value.__enter__.return_value.fetchone.return_value = (None,)

        assert bootstrap._schema_already_bootstrapped(conn) is False


# =====================================================
# _run_sql_file
# =====================================================


class TestRunSqlFile:

    def test_executes_file_contents_and_commits(self, tmp_path):
        sql_file = tmp_path / "001_test.sql"
        sql_file.write_text("CREATE TABLE foo (id int);", encoding="utf-8")
        conn = MagicMock()

        bootstrap._run_sql_file(conn, sql_file)

        cursor = conn.cursor.return_value.__enter__.return_value
        cursor.execute.assert_called_once_with("CREATE TABLE foo (id int);")
        conn.commit.assert_called_once()


# =====================================================
# _apply_legacy_migrations
# =====================================================


class TestApplyLegacyMigrations:

    def test_skips_entirely_when_already_bootstrapped(self, monkeypatch):
        monkeypatch.setattr(bootstrap, "_schema_already_bootstrapped", lambda c: True)
        run_mock = MagicMock()
        monkeypatch.setattr(bootstrap, "_run_sql_file", run_mock)

        bootstrap._apply_legacy_migrations(MagicMock())

        run_mock.assert_not_called()

    def test_applies_only_001_through_010_in_order(self, tmp_path, monkeypatch):
        # Mirrors the real migrations/ directory: legacy files 001-010,
        # plus 011/012 which are superseded by Alembic revisions and
        # must NOT be picked up by this function.
        for name in (
            "002_create_roles_table.sql",
            "010_create_indexes.sql",
            "001_create_enums.sql",
            "011_fix_tickets_timestamp_timezones.sql",
            "012_create_password_reset_tokens_table.sql",
        ):
            (tmp_path / name).write_text("-- noop", encoding="utf-8")

        monkeypatch.setattr(bootstrap, "MIGRATIONS_DIR", tmp_path)
        monkeypatch.setattr(bootstrap, "_schema_already_bootstrapped", lambda c: False)

        applied: list[str] = []
        monkeypatch.setattr(bootstrap, "_run_sql_file", lambda c, p: applied.append(p.name))

        bootstrap._apply_legacy_migrations(MagicMock())

        assert applied == [
            "001_create_enums.sql",
            "002_create_roles_table.sql",
            "010_create_indexes.sql",
        ]


# =====================================================
# _apply_seeds
# =====================================================


class TestApplySeeds:

    def test_applies_every_seed_file_in_sorted_order(self, tmp_path, monkeypatch):
        for name in ("003_seed_sla_policies.sql", "001_seed_roles.sql", "002_seed_departments.sql"):
            (tmp_path / name).write_text("-- noop", encoding="utf-8")

        monkeypatch.setattr(bootstrap, "SEEDS_DIR", tmp_path)
        applied: list[str] = []
        monkeypatch.setattr(bootstrap, "_run_sql_file", lambda c, p: applied.append(p.name))

        bootstrap._apply_seeds(MagicMock())

        assert applied == [
            "001_seed_roles.sql",
            "002_seed_departments.sql",
            "003_seed_sla_policies.sql",
        ]


# =====================================================
# bootstrap() — full sequence
# =====================================================


class TestBootstrapSequence:

    def test_runs_legacy_migrations_then_alembic_then_seeds_in_order(self, monkeypatch):
        order: list[str] = []

        monkeypatch.setattr(bootstrap.psycopg2, "connect", lambda dsn: MagicMock())
        monkeypatch.setattr(bootstrap, "_apply_legacy_migrations", lambda c: order.append("legacy"))
        monkeypatch.setattr(bootstrap, "_apply_seeds", lambda c: order.append("seeds"))
        monkeypatch.setattr(
            bootstrap.subprocess,
            "run",
            lambda *args, **kwargs: order.append("alembic"),
        )

        bootstrap.bootstrap()

        assert order == ["legacy", "alembic", "seeds"]

    def test_alembic_runs_as_upgrade_head(self, monkeypatch):
        captured = {}

        monkeypatch.setattr(bootstrap.psycopg2, "connect", lambda dsn: MagicMock())
        monkeypatch.setattr(bootstrap, "_apply_legacy_migrations", lambda c: None)
        monkeypatch.setattr(bootstrap, "_apply_seeds", lambda c: None)

        def fake_run(cmd, check):
            captured["cmd"] = cmd
            captured["check"] = check

        monkeypatch.setattr(bootstrap.subprocess, "run", fake_run)

        bootstrap.bootstrap()

        assert captured["cmd"][-2:] == ["upgrade", "head"]
        assert captured["check"] is True
