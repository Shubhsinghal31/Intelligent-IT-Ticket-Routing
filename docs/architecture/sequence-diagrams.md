# Sequence Diagrams

Three flows chosen to cover the system's most interesting behavior: auth
(security-critical), ticket creation (ML integration), and the lifecycle
transitions (state machine + audit trail interaction).

## 1. Login

```mermaid
sequenceDiagram
    actor U as User
    participant FE as Streamlit Frontend
    participant API as POST /auth/login
    participant Svc as AuthService
    participant DB as PostgreSQL

    U->>FE: Enter email + password
    FE->>API: form-encoded credentials
    API->>Svc: authenticate(email, password)
    Svc->>DB: SELECT * FROM users WHERE email = ?
    DB-->>Svc: user row (or none)

    alt user not found
        Svc->>Svc: run dummy bcrypt verify anyway
        Note over Svc: constant-time response —<br/>prevents timing attacks that reveal<br/>which emails are registered
        Svc-->>API: raise UnauthorizedException
        API-->>FE: 401 "Invalid email or password"
    else password does not match
        Svc-->>API: raise UnauthorizedException
        API-->>FE: 401 "Invalid email or password"
    else account inactive
        Svc-->>API: raise UnauthorizedException
        API-->>FE: 401 "Account is disabled"
    else valid credentials
        Svc->>DB: UPDATE users SET last_login_at = now()
        Svc-->>API: user
        API->>Svc: issue_tokens(user)
        Svc-->>API: access_token, refresh_token (JWT)
        API-->>FE: 200 { access_token, refresh_token, expires_in }
        FE->>FE: store tokens in st.session_state
        FE-->>U: redirect to dashboard
    end
```

## 2. Create ticket (with ML prediction + SLA due date)

```mermaid
sequenceDiagram
    actor U as Employee
    participant FE as Streamlit Frontend
    participant API as POST /tickets
    participant Svc as TicketService
    participant ML as ml_service
    participant DB as PostgreSQL

    U->>FE: Fill title/description/priority, submit
    FE->>API: ticket payload + Bearer JWT
    API->>Svc: create_ticket(reporter, data)
    Svc->>DB: INSERT ticket (status=OPEN, ticket_number="PENDING")
    DB-->>Svc: ticket.id (from flush)
    Svc->>Svc: ticket_number = f"TKT-{year}-{id:05d}"

    Svc->>ML: predict(title, description)
    ML-->>Svc: priority_score, sla_breach_prob,<br/>resolution_hours, department_name

    Note over Svc: ML failure never blocks creation —<br/>caught and logged, prediction fields stay null

    opt reporter did not choose a department
        Svc->>DB: SELECT department WHERE name = predicted_department_name
        Svc->>Svc: auto-assign department_id if found and active
    end

    Svc->>DB: SELECT sla_policy WHERE priority = ticket.priority
    Svc->>Svc: sla_due_at = created_at + resolution_time_hours

    Svc->>DB: COMMIT
    Svc-->>API: ticket (with predictions + sla_due_at)
    API-->>FE: 201 { ticket }
    FE-->>U: show ticket detail with AI predictions panel
```

## 3. Assign → resolve (state machine + audit trail)

```mermaid
sequenceDiagram
    actor E as Engineer
    participant FE as Streamlit Frontend
    participant API as FastAPI
    participant Svc as TicketService
    participant DB as PostgreSQL

    E->>FE: Pick engineer, click "Assign"
    FE->>API: POST /tickets/{id}/assign { assignee_id }
    API->>Svc: assign_ticket(id, engineer, assignee_id)
    Svc->>DB: SELECT ticket, SELECT assignee (must be active)
    Svc->>Svc: _record_history("assigned_to_id", old, new)
    Svc->>Svc: ticket.assigned_to_id = assignee_id
    alt status was OPEN
        Svc->>Svc: _record_history("status", "open", "in_progress")
        Svc->>Svc: ticket.status = IN_PROGRESS
    end
    Svc->>DB: COMMIT (ticket row + up to 2 ticket_history rows,<br/>same transaction)
    Svc-->>API: ticket
    API-->>FE: 200 ticket (in_progress)

    E->>FE: Click "Mark Resolved"
    FE->>API: POST /tickets/{id}/resolve
    API->>Svc: resolve_ticket(id, engineer)
    Svc->>DB: SELECT ticket
    alt status not in {IN_PROGRESS, REOPENED}
        Svc-->>API: raise ForbiddenException (invalid transition)
        API-->>FE: 403
    else valid transition
        Svc->>Svc: _record_history("status", "in_progress", "resolved")
        Svc->>Svc: ticket.status = RESOLVED, resolved_at = now()
        alt resolved_at > sla_due_at
            Svc->>Svc: sla_breached = true
        end
        Svc->>DB: COMMIT
        Svc-->>API: ticket
        API-->>FE: 200 ticket (resolved, sla_breached?)
    end
```

**Why the assign step matters for the audit trail design:** two
`ticket_history` rows can be written inside the *same* commit (assignee +
status). Postgres's `CURRENT_TIMESTAMP` default is transaction-time, so
both rows get an identical `changed_at` — `TicketHistoryRepository`
breaks that tie with `id` as a secondary sort key, not timestamp alone.
See the repository docstring for the full explanation; this bit an
integration test before it was caught.
