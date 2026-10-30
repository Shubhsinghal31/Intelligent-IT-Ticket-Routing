# Entity-Relationship Diagram

Supersedes `docs/architecture/er_diagram.png` (Milestone 1 draft), which
predates the `comments.user_id → author_id` / `comments.content → body`
rename and the `password_reset_tokens` table added later. This file is now
the source of truth — kept in Mermaid so it lives in version control and
updates in the same PR as the migration that changes the schema, rather
than needing a separate diagramming tool to regenerate a PNG.

```mermaid
erDiagram
    ROLES ||--o{ USERS : "has"
    DEPARTMENTS ||--o{ USERS : "has"
    DEPARTMENTS ||--o{ TICKETS : "handles"
    USERS ||--o{ TICKETS : "reports (created_by_id)"
    USERS ||--o{ TICKETS : "is assigned (assigned_to_id)"
    USERS ||--o{ COMMENTS : "authors"
    USERS ||--o{ ATTACHMENTS : "uploads"
    USERS ||--o{ TICKET_HISTORY : "changes"
    USERS ||--o{ PASSWORD_RESET_TOKENS : "requests"
    TICKETS ||--o{ COMMENTS : "has"
    TICKETS ||--o{ ATTACHMENTS : "has"
    TICKETS ||--o{ TICKET_HISTORY : "has"

    ROLES {
        int id PK
        string name "admin / engineer / employee"
        string description
        datetime created_at
    }
    DEPARTMENTS {
        int id PK
        string name
        string description
        bool is_active
        datetime created_at
        datetime updated_at
    }
    USERS {
        int id PK
        string email UK
        string username UK
        string password_hash
        string full_name
        int role_id FK
        int department_id FK
        bool is_active
        datetime created_at
        datetime updated_at
        datetime last_login_at
    }
    TICKETS {
        int id PK
        string ticket_number UK "TKT-YYYY-NNNNN"
        string title
        text description
        enum status "open/in_progress/resolved/closed/reopened"
        enum priority "low/medium/high/critical"
        int created_by_id FK
        int assigned_to_id FK
        int department_id FK
        int sla_policy_id "not a real FK, see note below"
        datetime created_at
        datetime updated_at
        datetime resolved_at
        datetime closed_at
        datetime sla_due_at
        bool sla_breached
        decimal predicted_priority_score "ML output"
        decimal predicted_sla_breach_prob "ML output"
        decimal predicted_resolution_hours "ML output"
    }
    COMMENTS {
        int id PK
        int ticket_id FK
        int author_id FK
        text body
        bool is_internal "staff-only note"
        datetime created_at
        datetime updated_at
    }
    ATTACHMENTS {
        int id PK
        int ticket_id FK
        int uploaded_by_id FK
        string file_name "client-supplied, display only"
        string file_path "UUID-based, relative to storage root"
        string mime_type
        bigint file_size_bytes
        datetime uploaded_at
    }
    TICKET_HISTORY {
        int id PK
        int ticket_id FK
        int changed_by_id FK
        string field_changed
        text old_value
        text new_value
        datetime changed_at
    }
    SLA_POLICIES {
        int id PK
        enum priority UK "one row per priority level"
        int response_time_hours
        int resolution_time_hours
        text description
        datetime created_at
        datetime updated_at
    }
    PASSWORD_RESET_TOKENS {
        int id PK
        int user_id FK
        string token_hash UK "SHA-256 of the raw token"
        datetime expires_at
        datetime used_at "null until redeemed"
        datetime created_at
    }
```

## Notes worth knowing

- **`tickets.sla_policy_id` is currently unused.** `TicketService.create_ticket()`
  looks up the applicable `SlaPolicy` by matching `SlaPolicy.priority ==
  ticket.priority.value` at creation time — it never writes
  `ticket.sla_policy_id`. The column exists in the schema but nothing
  populates it, and the model doesn't even declare it as a real
  `ForeignKey`. Flagging this here rather than quietly fixing it: it's a
  reasonable simplification (SLA policies are looked up by priority, not
  a specific policy version, so there's no "which policy applied"
  ambiguity to resolve) but it is schema debt worth a deliberate decision
  — either wire it up for historical accuracy (a policy's hours could
  change after a ticket was created) or drop the column.
- **Cascade rules**: `ticket_id` foreign keys are all `ON DELETE CASCADE`
  (deleting a ticket deletes its comments/attachments/history — there's no
  ticket delete endpoint today, but the schema is ready for one).
  `changed_by_id` / `author_id` / `uploaded_by_id` are `ON DELETE
  RESTRICT` — you cannot delete a user who has ever authored a comment,
  uploaded a file, or changed a ticket, which is exactly what you want for
  audit integrity.
