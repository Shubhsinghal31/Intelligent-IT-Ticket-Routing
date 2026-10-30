# Milestone 9 (+ SLA engine) — Interview Preparation: Reports & SLA Policies

> **Project:** Helpdesk-AI Enterprise ITSM
> **Milestone:** 9 — Report export (CSV/Excel/PDF); SLA due-date and breach logic (built earlier, tested here)
> **Audience:** Technical interviews touching data export, file streaming, business-rule design

---

## Topics Covered

- Sharing one data-shaping step across multiple export formats
- Streaming file responses vs. writing to temp files
- SLA due-date computation timing
- Resolve-time breach detection vs. background jobs

---

### Q1. How do CSV, Excel, and PDF exports share logic instead of each reimplementing ticket-row shaping?

**Answer:** `ReportService.get_ticket_rows(...)` does all the filtering and flattening (ticket → flat dict with human-readable status/priority/breach flag) exactly once. `to_csv_bytes()`, `to_excel_bytes()`, `to_pdf_bytes()` each take that same list of rows and only handle format-specific rendering. If the "breached" column's display logic changed (e.g. "Yes"/"No" → "⚠"/"✓"), that's a one-line change in `get_ticket_rows()`, not three.

**Follow-up:** What's the risk of NOT sharing this? → Format-specific drift — e.g. the PDF export silently using a different filter than the CSV export because someone updated one and forgot the other.

---

### Q2. Why does the reports endpoint use `StreamingResponse` instead of writing a file to disk and returning a path?

**Answer:** No filesystem cleanup problem to manage (a temp file written per request would need a cleanup mechanism — cron, TTL, or manual deletion — to avoid unbounded disk growth), no risk of concurrent requests colliding on the same filename, and no latency from an extra disk round-trip. `StreamingResponse(io.BytesIO(content), ...)` serves the bytes directly from memory.

**Follow-up:** When would writing to disk make more sense? → If report generation were slow/expensive enough to want to cache and reuse the same report across requests (e.g. a nightly report many people download), disk (or object storage) caching would be the right call — this project's reports are generated fresh per request because ticket data changes constantly and staleness would be misleading.

---

### Q3. When is a ticket's `sla_due_at` actually calculated?

**Answer:** At ticket creation time, in `TicketService.create_ticket()` — it looks up the `SlaPolicy` row matching the ticket's priority and sets `sla_due_at = ticket.created_at + timedelta(hours=policy.resolution_time_hours)`. It's a fixed target set once, not recomputed later even if the ticket's priority changes.

**Follow-up:** What happens if priority is edited after creation via `PATCH /tickets/{id}`? → `sla_due_at` is *not* recalculated — `update_ticket()` only changes `ticket.priority`, leaving the original due date. This is a real, honest gap: a ticket escalated from low to critical priority keeps its original (looser) SLA deadline. Worth flagging as a candidate fix, not something to gloss over.

---

### Q4. How is an SLA breach detected — polling, a background job, or something else?

**Answer:** Neither — it's computed inline, at the moment a ticket is resolved. `resolve_ticket()` compares `ticket.resolved_at > ticket.sla_due_at` and sets `sla_breached = True` if so. There's no scheduled job continuously checking open tickets against their due dates.

**Follow-up:** What's the limitation of resolve-time-only breach detection? → An *open* ticket that has already blown past its SLA due date shows `sla_breached = False` right up until someone resolves it — the flag only reflects breaches that have already been confirmed at resolution, not "at risk right now." A dashboard wanting to surface "currently breaching" tickets would need a computed comparison (`now() > sla_due_at AND status not in (resolved, closed)`) done at query time, not read from the stored `sla_breached` column.

**Follow-up 2:** Why not build the background job anyway? → Added complexity (a scheduler, idempotency handling, what happens if the job is down) for a signal that's also derivable on-demand from existing columns via a query — a reasonable scope call for this project's size, but the kind of design decision that should be stated explicitly rather than assumed.

---

### Q5. `sla_policies` has one row per priority level — what does that constrain?

**Answer:** SLA targets are the same for every ticket of a given priority, regardless of department, customer tier, or anything else. There's exactly one active resolution-time target for "critical," period.

**Follow-up:** How would you support per-department or per-customer SLA policies? → Add a `department_id` (nullable, meaning "applies to all departments") to `sla_policies`, and change the lookup in `create_ticket()` to prefer a department-specific policy over the priority-only fallback — a small, backward-compatible schema change.
