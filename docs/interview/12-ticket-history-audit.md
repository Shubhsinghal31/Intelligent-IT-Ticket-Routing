# Gap Fill — Interview Preparation: Ticket History / Audit Trail

> **Project:** Helpdesk-AI Enterprise ITSM
> **Feature:** Automatic audit logging of tracked ticket field changes
> **Audience:** Technical interviews touching audit-log / event-sourcing-adjacent design

---

## Topics Covered

- Writing audit rows in the same transaction as the change they document
- The Postgres transaction-timestamp tiebreaker bug (also covered from the testing angle in `09-testing-strategy.md` Q5 — here from the design angle)
- No-op detection to keep the trail meaningful
- Why history is read-only
- Cascade/restrict delete rules for audit integrity

---

### Q1. Why does writing a `TicketHistory` row happen inside the same database transaction as the field change it documents, rather than as a separate step afterward?

**Answer:** Atomicity — an audit row must never exist without its corresponding change actually landing, and a change must never land without being recorded (for fields being tracked). `_record_history()`'s `self.history_repo.add(...)` only calls `flush()` (stages the row, doesn't commit); the actual commit is the *same* `self.ticket_repo.commit()` call the lifecycle method was already going to make for the ticket mutation itself. There's no window where one succeeds and the other doesn't — either both happen or, if something fails first, neither does (the whole transaction rolls back).

**Follow-up:** What would go wrong with a "fire and forget" approach (write history via a separate async call/event)? → A crash or exception between the two writes leaves either an orphaned history row (documenting a change that never actually happened) or a silent, unrecorded change — both are audit-integrity failures. Async/event-based auditing is a legitimate pattern at larger scale, but it requires its own consistency mechanism (outbox pattern, at-least-once delivery + idempotency) that this project's scale doesn't need yet.

---

### Q2. Explain the Postgres transaction-timestamp bug you found while building this.

**Answer:** `TicketHistory.changed_at` defaults to `CURRENT_TIMESTAMP` at the database level. In Postgres, `CURRENT_TIMESTAMP` (and `now()`) is **transaction time** — evaluated once when the transaction begins, not re-evaluated per statement. `assign_ticket()` can write two history rows in one commit (an `assigned_to_id` change and, if the ticket was OPEN, a `status` change to IN_PROGRESS) — both rows get an *identical* `changed_at`, because they're both inserted within the same transaction. An integration test asserting the audit trail came back in true chronological order caught this: `ORDER BY changed_at` alone left same-timestamp rows in an order Postgres wasn't obligated to preserve.

**Fix:** `TicketHistoryRepository.get_by_ticket()` now sorts by `(changed_at, id)` — `id` is autoincrement, so it's a reliable secondary key reflecting true insertion order regardless of timestamp precision or transaction-time semantics.

**Follow-up:** Would using `datetime.now()` in Python instead of a DB-level default have avoided this? → Yes, partially — a Python-side default (evaluated per-object, before the INSERT is sent) would give each row a distinct wall-clock timestamp. But that swaps one subtlety for another: Python's `datetime.now()` calls happen microseconds apart and could still theoretically collide at low enough clock resolution, and mixing "some timestamps are DB-generated, some are app-generated" across the codebase is its own maintenance hazard. The `id`-tiebreaker fix is more robust because it doesn't depend on clock resolution at all.

---

### Q3. Why does `_record_history()` skip writing a row when the old and new values are equal?

**Answer:** An audit trail's value comes from precision — every row should represent something that actually happened. `assign_ticket(ticket_id, user, assignee_id=<current assignee>)` is a legal, no-op call (re-assigning someone to the engineer they're already assigned to), and if that unconditionally wrote a history row, the trail would accumulate misleading "assigned_to_id: 7 → 7" entries that look like changes but aren't. The guard (`if old_value == new_value: return`) keeps every row meaningful.

**Follow-up:** How is this verified? → `test_assigning_to_current_assignee_does_not_duplicate_history` (unit) and `test_no_op_assign_does_not_add_entry` (integration) both assert zero new rows for a genuinely no-op call.

---

### Q4. Why is there no `POST /tickets/{id}/history` endpoint to manually add an audit entry?

**Answer:** An audit log a client could write to arbitrarily isn't trustworthy as an audit log — its entire value is that every row is a guaranteed side effect of a real, service-validated action, not an unverified claim. `TicketHistoryResponse`'s schema docstring states this explicitly: history rows are written exclusively by `TicketService` as a side effect of its own lifecycle/update methods.

**Follow-up:** What if an admin genuinely needs to annotate a ticket's history (e.g. "escalated per phone call")? → That's a different feature — a free-form ticket comment (which already exists, with `is_internal=True` for staff-only notes) is the right tool for human annotation. Conflating "system-verified field change" with "human note" into one audit table would blur exactly the trustworthiness property that makes the audit trail useful.

---

### Q5. Why is `changed_by_id` (and similarly `author_id`, `uploaded_by_id` elsewhere) `ON DELETE RESTRICT` instead of `SET NULL` or `CASCADE`?

**Answer:** Audit integrity again — you cannot delete a user who has ever changed a ticket's field, authored a comment, or uploaded a file. `RESTRICT` makes that deletion fail at the database level rather than silently orphaning the audit record (`SET NULL`, losing who made the change) or silently destroying history (`CASCADE`, deleting the audit trail along with the user). This forces a deliberate decision (deactivate the user instead of deleting, or explicitly handle their historical records first) rather than letting a routine user-deletion quietly corrupt the audit trail.

**Follow-up:** Contrast this with `ticket_id`'s cascade rule. → `ticket_id` foreign keys on `comments`/`attachments`/`ticket_history` are `ON DELETE CASCADE` — deleting a *ticket* (there's no such endpoint today, but the schema is ready) reasonably takes its history with it, since the history only has meaning in the context of that ticket. Deleting a *user*, by contrast, should never retroactively erase what they did — that's the asymmetry the two different cascade rules encode.
