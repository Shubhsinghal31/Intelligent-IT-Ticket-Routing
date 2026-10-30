# Milestone 4 — Interview Preparation: Ticket Module & RBAC

> **Project:** Helpdesk-AI Enterprise ITSM
> **Milestone:** 4 — Ticket CRUD, lifecycle state machine, comments, role-based access
> **Audience:** Technical interviews at mid-to-senior backend roles

---

## Topics Covered

- Clean architecture (API → Service → Repository → Model)
- Finite state machines implemented as explicit guard clauses
- Role-Based Access Control enforced in the service layer
- N+1 query prevention with SQLAlchemy `joinedload`
- Partial updates (PATCH semantics)

---

### Q1. Why split ticket logic into service + repository layers instead of one `TicketService` that also writes SQL?

**Answer:** Single Responsibility Principle — a service answers "is this operation allowed and what should happen," a repository answers "how do I fetch/store this." Splitting them means `TicketService` can be unit-tested with a `MagicMock()` repository (no database needed — see `tests/unit/test_ticket_service.py`), and if a query needs optimizing (e.g. an index, a different join), that's a repository-only change that can't accidentally touch business rules.

**In our project:** `TicketService.get_tickets()` never writes `select(Ticket)...` — it calls `self.ticket_repo.get_paginated(...)`. All SQLAlchemy lives in `backend/repositories/ticket_repository.py`.

**Follow-up:** What would break this separation? → A service method that does `self.db.query(Ticket)...` directly — several early-milestone services do this for lookups outside the primary entity (e.g. `TicketService._validate_department` queries `Department` directly). That's a deliberate, smaller exception: `Department` isn't `TicketService`'s primary entity, so a dedicated repository felt like overkill for one lookup — but it's a tradeoff worth being able to defend, not an accident.

---

### Q2. How is the ticket lifecycle (open → in_progress → resolved → closed → reopened) implemented?

**Answer:** As explicit guard clauses in each transition method, not a generic state-machine library. `resolve_ticket()` checks `if ticket.status not in {IN_PROGRESS, REOPENED}: raise ForbiddenException(...)` before doing anything else.

**Why not a library?** With five states and five transition methods, a formal FSM library (e.g. `transitions`) adds a dependency and an abstraction layer for a problem that's fully expressed in ~30 lines of `if` statements. The guard-clause approach is also what makes each transition trivially unit-testable in isolation (`TestResolveTicket`, `TestCloseTicket`, etc. in `test_ticket_service.py`).

**Follow-up:** When would a library be justified? → If the state graph grew substantially (many more states, conditional transitions based on multiple factors, need to visualize/audit the graph itself) or if the same state machine needed to be reused across several entities.

---

### Q3. Where does RBAC actually get enforced — the endpoint or the service?

**Answer:** The service. Endpoints only handle *authentication* (who are you — `get_current_active_user`) and, for the two purely role-gated actions, a `require_roles(...)` dependency. Everything conditional on *data* (is this your own ticket?) lives in the service, because that check needs the ticket loaded first — a dependency can't know that ahead of the route handler running.

**In our project:** `_assert_can_view()` / `_assert_can_modify()` in `TicketService` implement "employees see only their own tickets; engineers/admins see all" — called from `get_ticket`, `update_ticket`, `get_history`, etc. `assign_ticket`/`close_ticket`/`resolve_ticket` check role directly (`if user.role.name not in ("engineer", "admin")`) since those have no ownership dimension at all.

**Follow-up:** Why not put all RBAC in dependencies for consistency? → Because "is engineer or admin" is static (true regardless of which ticket), but "is this your ticket" is data-dependent — a dependency would have to re-fetch the ticket, duplicating the service's own fetch. Two different problems, two different layers.

---

### Q4. Why can't `PATCH /tickets/{id}` change status?

**Answer:** Separation between "edit metadata" (title, description, priority, department) and "advance the lifecycle" (assign/resolve/close/reopen). A generic PATCH that accepted `status` would need to re-implement every transition's guard clauses inline, duplicating `resolve_ticket`/`close_ticket`/etc. Dedicated endpoints keep each transition's rules in exactly one place.

**Follow-up:** What's the API design cost of this choice? → More endpoints (`POST /assign`, `/resolve`, `/close`, `/reopen` vs. one `PATCH`), but each one has a narrow, auditable contract. This mirrors how `TicketHistory` tracks `status` changes distinctly from field edits.

---

### Q5. How do you avoid N+1 queries when listing tickets with reporter/assignee/department names?

**Answer:** `TicketRepository._base_query()` bakes in `joinedload(Ticket.reporter)`, `joinedload(Ticket.assignee)`, `joinedload(Ticket.department)` — one SQL query with JOINs instead of 1 (list tickets) + N (fetch each ticket's reporter) + N (assignee) + N (department).

**Follow-up:** Why `joinedload` and not `selectinload`? → `joinedload` is a good fit here because the joined tables (users, departments) are small and the relationship is many-to-one from the ticket's perspective (each ticket has exactly one reporter/assignee/department row to attach) — a single JOIN doesn't multiply result rows in a way that bloats the resultset. `selectinload` would be preferable for a one-to-many relationship being eagerly loaded (e.g., loading all comments for a page of tickets), where a JOIN would duplicate the parent row per child.

---

### Q6. Why is `ticket_number` set *after* the insert, not before?

**Answer:** The format is `TKT-{year}-{id:05d}` — it embeds the DB-generated primary key. `TicketRepository.add()` calls `db.flush()`, which sends the INSERT and gets the assigned `id` back without committing the transaction, so `ticket.id` is available to build the ticket number before the final commit. The row is briefly inserted with a placeholder (`"PENDING"`), then updated in the same transaction.

**Follow-up:** What's the alternative? → A separate sequence/counter table queried before insert, but that adds a second table to keep in sync and a race-condition risk under concurrent ticket creation that `flush()`-then-`update` inside one transaction avoids entirely.
