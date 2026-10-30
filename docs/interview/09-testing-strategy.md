# Milestone 11 — Interview Preparation: Testing Strategy

> **Project:** Helpdesk-AI Enterprise ITSM
> **Milestone:** 11 — Unit + integration test suite (114 unit, 44 integration as of this writing)
> **Audience:** Technical interviews touching test architecture and real production-bug stories

---

## Topics Covered

- Unit vs. integration test boundaries and why both exist
- Transactional test isolation (SAVEPOINT pattern) against a real Postgres
- Mocking repositories vs. hitting a real database
- Testing RBAC without duplicating per-endpoint logic
- A real bug the test suite caught (STAR-story material)

---

### Q1. What's the actual difference between this project's unit and integration suites?

**Answer:** Unit tests (`tests/unit/`) instantiate a service with `MagicMock()` standing in for its repository and DB session — no network, no database, runs in milliseconds. They verify *business logic in isolation*: does `resolve_ticket()` reject an OPEN ticket, does `_record_history()` skip no-op changes. Integration tests (`tests/integration/`) spin up the real FastAPI app via `TestClient`, against a real (disposable) Postgres container, and drive everything through actual HTTP requests — verifying that routing, dependency injection, RBAC, and the database schema all actually work together, not just that the service's Python logic is correct in isolation.

**Follow-up:** Why not just integration tests, since they're more "real"? → Speed and precision. The full unit suite runs in ~3 seconds; a single integration test needs a running Postgres and pays connection/transaction overhead. Unit tests also pinpoint failures more precisely — a broken `resolve_ticket()` guard clause fails one focused unit test instantly, versus an integration test failure that could stem from routing, auth, the service, or the DB schema.

---

### Q2. How do integration tests get a clean, isolated database per test without wiping and reseeding Postgres for every single test?

**Answer:** The `db_session` fixture (`tests/integration/conftest.py`) opens one real transaction per test, then a `SAVEPOINT` inside it. When application code calls `db.commit()`, that only releases the savepoint — it doesn't end the real transaction. At test teardown, the fixture rolls back the *outer* transaction, discarding everything written during the test regardless of how many times the app "committed." A `test_engine` fixture (session-scoped) creates all tables once at the start of the whole test run and drops them at the end.

**Follow-up:** What's a gotcha this pattern introduces? → Anything that depends on genuine transaction-boundary behavior (like `CURRENT_TIMESTAMP`, which is frozen per Postgres *transaction*, not per statement) behaves differently under this pattern than in production, where each request typically gets its own real transaction. This exact gotcha caused a real bug — see Q5.

---

### Q3. Why mock the repository in unit tests instead of using a real (test) database directly, like the integration suite does?

**Answer:** A unit test's job is to verify the *service's decision logic* — given this ticket state and this user, does the service allow/reject the action, and what does it mutate. Whether the repository's SQL is correct is a separate concern, verified by integration tests exercising the real schema. Mocking the repository means a unit test for "employee cannot resolve a ticket" doesn't need a real ticket row, a real user row, or a database connection at all — it constructs a `MagicMock(spec=Ticket)` with just the attributes the test cares about.

**Follow-up:** Doesn't mocking risk testing something that doesn't match reality? → Yes, if the mock's shape drifts from the real model. This is mitigated by `spec=Ticket`/`spec=User` on the mocks (raises `AttributeError` if code touches an attribute the real model doesn't have) and by the integration suite independently verifying the same behaviors end-to-end.

---

### Q4. How do you test RBAC across many endpoints without writing near-identical test code 20 times?

**Answer:** Shared helpers in `tests/integration/conftest.py` — `register()`, `login()`, `create_active_user(db_session, role_name, email, username)`, `auth_headers(token)` — so every test file provisions users and tokens the same three-line way. Individual test files (`test_comments.py`, `test_attachments.py`, `test_ticket_history.py`) then each write focused RBAC assertions specific to their feature ("employee cannot list attachments on someone else's ticket") rather than reimplementing user setup.

**Follow-up:** What's NOT shared, and why? → The actual assertions (what status code, what error_code, what response shape) stay per-test — RBAC rules differ subtly enough per feature (e.g. comments have an `is_internal` dimension attachments don't) that a fully generic "assert RBAC" helper would either be too loose to catch real bugs or too complex to be simpler than just writing the assertion.

---

### Q5. Tell me about a real bug your tests caught.

**Answer (STAR-shaped):**

- **Situation:** Building the ticket audit trail (`TicketHistory`), `assign_ticket()` can write two history rows in one call — one for the assignee change, one for the resulting status change (OPEN → IN_PROGRESS) — both committed together.
- **Task:** An integration test asserted the full lifecycle's history came back in true chronological order (`ORDER BY changed_at`).
- **Action:** The test failed — `assigned_to_id` and `status` came back in an order that didn't match insertion order. Root cause: Postgres's `CURRENT_TIMESTAMP` (used as `changed_at`'s default) is *transaction-time*, not statement-time — it's frozen once at the start of the enclosing transaction. Both rows, written in the same commit, got byte-identical timestamps. `ORDER BY changed_at` alone left that tie in arbitrary DB-decided order.
- **Result:** Fixed by adding `id` (autoincrement, so always reflects true insertion order) as a secondary sort key: `ORDER BY changed_at ASC, id ASC`. This wasn't just a test-flakiness fix — it was a real correctness bug that would have shown an inconsistent audit trail ordering in production too, for any lifecycle action that writes multiple history rows in one transaction.

**Follow-up:** What's the general lesson? → Never rely on a database-default timestamp alone to order rows that can be written within the same transaction — always have a tiebreaker (an autoincrement ID, or an explicit application-generated sequence number) for anything resembling an audit log or event stream.
