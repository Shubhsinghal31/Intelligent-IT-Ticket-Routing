"""
Shared fixtures for integration tests.

Unlike tests/unit (services tested in isolation with MagicMock models),
integration tests exercise the real stack: HTTP request -> FastAPI
routing -> dependency injection -> service -> repository -> a real
Postgres database -> response. The trade-off is setup cost, which is
why this file exists — every integration test file reuses these
fixtures instead of wiring the database up itself.

Requires a running test Postgres instance:
    docker compose -f docker/docker-compose.test.yml up -d

Points at it via TEST_DATABASE_URL (defaults to the docker-compose.test.yml
service). Override the env var if you're running Postgres somewhere else.
"""

import os
from collections.abc import Generator

TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql://postgres:test_password@localhost:5433/helpdesk_ai_test",
)

# Must happen BEFORE any `backend.*` import. backend/core/config.py builds
# its Settings singleton (and backend/core/database.py builds its module-
# level `engine` from it) at import time — if those imports run first,
# nothing below can change what database the app thinks it's talking to.
# Without this, dependency_overrides on get_db would isolate most of the
# app correctly, but anything that bypasses DI and touches the global
# `engine` directly (health check's check_db_connection(), for one) would
# silently hit the dev database instead of the disposable test one.
os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ["DB_HOST"] = "localhost"
os.environ["DB_PORT"] = "5433"
os.environ["DB_NAME"] = "helpdesk_ai_test"
os.environ["DB_USER"] = "postgres"
os.environ["DB_PASSWORD"] = "test_password"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.dialects.postgresql import ENUM as PGEnum  # noqa: E402
from sqlalchemy.dialects.postgresql import insert as pg_insert  # noqa: E402
from sqlalchemy.orm import Session, sessionmaker  # noqa: E402

# Import backend.models BEFORE anything touches Base.metadata — this is
# what registers every table (User, Ticket, Role, ...) onto the shared
# declarative base. Forgetting this import is the single most common
# reason create_all() silently creates zero tables.
import backend.models  # noqa: F401,E402
from backend.api.deps import get_db  # noqa: E402
from backend.core.database import Base  # noqa: E402
from backend.core.rate_limit import limiter  # noqa: E402
from backend.core.security import hash_password  # noqa: E402
from backend.main import create_app  # noqa: E402
from backend.models.department import Department  # noqa: E402
from backend.models.role import Role  # noqa: E402
from backend.models.user import User  # noqa: E402

# Shared password for every user created via create_active_user() below —
# fine for test fixtures where the point is exercising RBAC/lifecycle
# logic, not password security itself.
TEST_PASSWORD = "TestPass123!"


@pytest.fixture(scope="session")
def test_engine():
    """
    One engine for the whole test session.

    Creates every table at the start of the run and drops them all at
    the end — each test run starts from a clean, known schema rather
    than accumulating leftover state across runs.
    """
    engine = create_engine(TEST_DATABASE_URL, future=True)

    _create_enum_types(engine)
    Base.metadata.create_all(engine)
    _seed_reference_data(engine)

    yield engine

    Base.metadata.drop_all(engine)
    engine.dispose()


def _create_enum_types(engine) -> None:
    """
    Explicitly create the Postgres ENUM types that Ticket.status,
    Ticket.priority, and SlaPolicy.priority reference.

    Those columns are declared with create_type=False (see
    backend/models/ticket.py, backend/models/sla_policy.py) — that flag
    tells SQLAlchemy "assume this type already exists, created by an
    Alembic migration; don't try to CREATE or DROP it yourself." That's
    the right call for the real app (multiple tables share the same
    enum type name, and letting more than one Enum() column try to
    create it would conflict), but it means Base.metadata.create_all()
    alone can never bootstrap a genuinely fresh test database — it'll
    fail with `type "ticket_status" does not exist` the first time
    CREATE TABLE tickets runs. Using PGEnum(...).create(engine,
    checkfirst=True) here does what create_type=False deliberately
    doesn't: create the type if missing, and do nothing if it's already
    there (safe to call on every test run).
    """
    ticket_status = PGEnum(
        "open",
        "in_progress",
        "resolved",
        "closed",
        "reopened",
        name="ticket_status",
    )
    ticket_priority = PGEnum(
        "low",
        "medium",
        "high",
        "critical",
        name="ticket_priority",
    )
    ticket_status.create(bind=engine, checkfirst=True)
    ticket_priority.create(bind=engine, checkfirst=True)


def _seed_reference_data(engine) -> None:
    """
    Insert the same reference rows database/seeds/*.sql provides in a
    real deployment (roles, departments) — ticket/user creation depends
    on these foreign keys existing. Kept minimal and idempotent
    (ON CONFLICT DO NOTHING) so re-running against an already-seeded
    database is harmless.

    Uses SQLAlchemy Core insert() against the mapped Table objects
    rather than raw SQL text. This is not just style — Role.created_at
    and Department.created_at/updated_at are defined as Python-side
    defaults (`mapped_column(default=datetime.utcnow)`), which only
    fire when SQLAlchemy itself builds the INSERT. A raw `INSERT INTO
    roles (name, description) VALUES (...)` bypasses that entirely and
    Postgres has no server-side DEFAULT on the column, so it happily
    tries to insert NULL into a NOT NULL column — this is exactly the
    bug that showed up as `NotNullViolation: null value in column
    "created_at"` the first time this ran against a real Postgres.
    """
    with engine.begin() as conn:
        conn.execute(
            pg_insert(Role.__table__)
            .values(
                [
                    {"name": "admin", "description": "Full system access"},
                    {
                        "name": "engineer",
                        "description": "Resolves tickets within assigned department",
                    },
                    {
                        "name": "employee",
                        "description": "Raises tickets and tracks their progress",
                    },
                ]
            )
            .on_conflict_do_nothing(index_elements=["name"])
        )
        conn.execute(
            pg_insert(Department.__table__)
            .values(
                [
                    {"name": "IT Support", "description": "Hardware, OS, general IT issues"},
                    {"name": "Network", "description": "Connectivity, VPN, firewall, Wi-Fi"},
                ]
            )
            .on_conflict_do_nothing(index_elements=["name"])
        )


@pytest.fixture
def db_session(test_engine) -> Generator[Session, None, None]:
    """
    A DB session scoped to a single test, wrapped in a transaction that
    is always rolled back at the end — even if the code under test
    calls db.commit(). This keeps every test's writes invisible to
    every other test without needing to truncate tables between runs.

    Technique: open a connection and an outer transaction ourselves,
    bind the session to that connection, and start a SAVEPOINT
    (begin_nested). Application code calling commit() only closes the
    savepoint, not the outer transaction — so rolling back the outer
    transaction at teardown discards everything regardless of how many
    times the code under test committed.
    """
    connection = test_engine.connect()
    outer_transaction = connection.begin()

    TestSessionLocal = sessionmaker(bind=connection, expire_on_commit=False)
    session = TestSessionLocal()
    session.begin_nested()

    @__import__("sqlalchemy").event.listens_for(session, "after_transaction_end")
    def _restart_savepoint(sess, transaction):
        if transaction.nested and not transaction._parent.nested:
            sess.begin_nested()

    try:
        yield session
    finally:
        session.close()
        outer_transaction.rollback()
        connection.close()


@pytest.fixture
def client(db_session) -> Generator[TestClient, None, None]:
    """
    A TestClient wired to the real FastAPI app, but with the database
    dependency swapped for the transactional test session above — every
    other piece of the app (routing, middleware, exception handlers,
    RBAC) runs exactly as it would in production.
    """
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db_session

    # Auth endpoints are rate-limited (Milestone 10, Step 10.2). An
    # integration suite that calls /auth/register or /auth/login more
    # than a few times would start tripping 429s unrelated to whatever
    # the test is actually checking — reset before each test so the
    # limiter's quota doesn't leak across tests.
    limiter.reset()

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


# =====================================================
# Shared test helpers
# =====================================================
# Plain functions, not fixtures — every integration test file that needs
# to provision a non-employee user or authenticate does the same three
# things, so they live here once instead of being copy-pasted per file.


def create_active_user(db_session, role_name: str, email: str, username: str) -> User:
    """
    Provision a user directly against the test database session.

    POST /users (admin-only, see backend/api/v1/endpoints/users.py) can
    now create engineer/admin accounts too, but using it here would mean
    every test needing a non-employee token first has to bootstrap an
    admin through that same endpoint — extra HTTP round-trips for what
    is fixture setup, not the thing under test. This bypasses the API
    and writes the row directly, which also means tests for POST /users
    itself (see test_user_provisioning.py) aren't implicitly depending
    on the endpoint they're supposed to be testing.
    """
    role = db_session.query(Role).filter(Role.name == role_name).one()
    user = User(
        email=email,
        username=username,
        password_hash=hash_password(TEST_PASSWORD),
        full_name=username.replace("_", " ").title(),
        role_id=role.id,
        is_active=True,
    )
    db_session.add(user)
    db_session.flush()
    return user


def login(client, email: str) -> str:
    """POST /auth/login for a user created via register() or create_active_user(), return its access token."""
    response = client.post(
        "/api/v1/auth/login",
        data={"username": email, "password": TEST_PASSWORD},
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def register(client, email: str, username: str, full_name: str) -> None:
    """POST /auth/register with the shared TEST_PASSWORD — always creates an 'employee'."""
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "username": username,
            "password": TEST_PASSWORD,
            "full_name": full_name,
        },
    )
    assert response.status_code == 201, response.text
