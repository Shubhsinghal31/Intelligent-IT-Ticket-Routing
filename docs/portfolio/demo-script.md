# Demo Script — Helpdesk-AI

A spoken walkthrough for a 3-5 minute demo video or a live interview screen-share.
Written to be read almost verbatim; adjust pacing to fit your audience.

**Live URLs** (free tier — first request after ~15 min idle can take 30-60s to wake up, mention this if it happens):
- Frontend: https://helpdesk-ai-frontend-retv.onrender.com/
- API docs: https://helpdesk-ai-backend-0o3i.onrender.com/docs

---

## 0. Cold open (10s)

> "This is Helpdesk-AI — an ITSM ticketing system like ServiceNow, but with the
> triage automated by machine learning instead of manual rules. I built the
> whole stack: FastAPI backend, Streamlit frontend, Postgres, three ML models,
> and it's deployed live on Render."

## 1. Login & roles (20s)

- Open the frontend, show the login page.
- Log in as an **employee** account.

> "There are three roles — employee, engineer, and admin — enforced with JWT
> and role-based access control on every API endpoint, not just hidden in the
> UI. An employee literally cannot call the admin endpoints even if they guess
> the URL — I have integration tests that assert on that."

## 2. Create a ticket — the ML moment (60s)

- Go to **Create Ticket**. Fill in a realistic title/description, e.g.
  "Production database connection pool exhausted — outage."
- Submit.
- On the ticket detail page, point at the **predicted priority**,
  **predicted department**, and **SLA due date**.

> "The moment this ticket is submitted, three ML models run: a priority
> classifier, a department router, and an SLA breach predictor — all
> scikit-learn, trained on synthetic-but-realistic ticket data at Docker build
> time so the models ship inside the image. No manual triage step. This one
> got auto-classified as [say the actual result] and routed to
> [department] with an SLA due date of [X hours] out."

## 3. Lifecycle (30s)

- Show comment, then transition the ticket (assign → resolve, or similar)
  logged in as an engineer/admin account if you have one handy.

> "Tickets move through a state machine — open, assigned, in-progress,
> resolved, closed, reopened — and every transition is logged to a history
> table for audit purposes, not just the current status."

## 4. Admin dashboard (45s)

- Log in as admin, go to **Dashboard**.
- Point at: open vs. closed tickets, average resolution time, the
  department/priority heatmap, monthly trend chart.

> "This is all Plotly, driven by real aggregation queries — nothing here is
> pre-computed and cached, it's live off Postgres. The heatmap is department
> vs. priority, so you can see at a glance where tickets are piling up."

## 5. SLA breach view (20s)

> "This column tracks SLA breaches specifically — tickets that blew past
> their predicted resolution window. That's the fourth ML model, resolution
> time prediction, feeding directly into an operational metric, not just
> sitting in a notebook somewhere."

## 6. Reports (20s)

- Go to **Reports**, generate an Excel or PDF export.

> "Reports export to Excel, CSV, or PDF — for anyone who needs this data
> outside the app, e.g. for a stakeholder update."

## 7. Under the hood — close on engineering depth (30s)

- Switch tabs to `/docs` (Swagger UI).

> "Every endpoint is documented via OpenAPI/Swagger automatically from
> FastAPI's type hints — this isn't hand-written. The whole thing is tested:
> 128 unit tests, 44 integration tests against a real Postgres instance, and
> GitHub Actions runs lint plus the full suite on every push. It's deployed
> on Render as two Docker services plus a managed Postgres, wired together
> with Infrastructure-as-Code — a single render.yaml file, no manual
> dashboard clicking."

## Closing line

> "So — full-stack, ML-integrated, tested, containerized, CI/CD'd, and
> actually deployed and reachable right now, not just running on localhost."

---

## If something goes wrong live

- **Backend is cold (slow first request):** "This is on Render's free tier,
  so it spins down after 15 minutes idle — give it a few seconds to wake up.
  In a paid tier this wouldn't happen." (Then narrate something else while
  you wait, or show the architecture diagram instead.)
- **Asked "why isn't X live-updating without refresh":** Streamlit reruns the
  script top-to-bottom on interaction by design — mention it's a deliberate
  trade-off (fast to build a data-heavy internal tool) vs. a React SPA (more
  work, better UX for consumer-facing products).
