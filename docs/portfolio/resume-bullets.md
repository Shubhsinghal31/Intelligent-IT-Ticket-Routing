# Resume Bullet Points — Helpdesk-AI

Several variants at different lengths/emphases. Pick 3-5 depending on how
much space you have; don't use all of them at once. Swap in real numbers
where you have better ones (e.g. if you add more tests later).

## Project header line

**Helpdesk-AI — Enterprise ITSM Assistant** | Python, FastAPI, Streamlit,
PostgreSQL, scikit-learn, Docker, GitHub Actions, Render
[github.com/Shubhsinghal31/Intelligent-IT-Ticket-Routing](https://github.com/Shubhsinghal31/Intelligent-IT-Ticket-Routing)

## Full-stack / architecture

- Designed and built a full-stack ITSM ticketing platform (FastAPI +
  Streamlit + PostgreSQL) with clean-architecture layering (API → service →
  repository) and JWT-based role authentication across 3 roles (employee,
  engineer, admin), enforced at the endpoint level via RBAC middleware.

- Built a REST API of 30+ endpoints with FastAPI, auto-documented via
  OpenAPI/Swagger, covering ticket lifecycle management, user administration,
  SLA policy configuration, and reporting.

## ML integration

- Integrated 3 scikit-learn models (priority classification, department
  routing, SLA-breach prediction) directly into the ticket-creation flow,
  automating triage that would otherwise require manual routing — models
  train deterministically (seeded) at Docker build time so predictions are
  reproducible across every deploy.

- Designed a graceful-degradation path for the ML layer: if a trained model
  is ever missing or fails to load, the service falls back to safe defaults
  instead of blocking ticket creation — no single point of failure between
  ML and the core CRUD flow.

## Testing / quality

- Wrote a 191-test suite (134 unit tests with mocked dependencies + 57
  integration tests against a real Postgres instance) covering auth, RBAC
  boundaries, ticket lifecycle, SLA breach logic, and attachment handling;
  enforced on every push via a two-stage GitHub Actions pipeline (lint +
  full suite).

- Debugged and resolved two CI-only failures invisible in local
  development — a Pydantic settings validation gap (missing env vars on a
  clean CI runner) and a Python-version-specific `datetime.fromisoformat`
  incompatibility — hardening the test suite against environment drift.

## DevOps / deployment

- Containerized the application (separate backend/frontend Docker images,
  docker-compose for local dev and a distinct compose file for isolated test
  runs) and deployed to Render via a declarative Blueprint (`render.yaml`)
  provisioning a managed Postgres instance and two web services with
  zero secrets committed to source control (Render-generated JWT secret,
  cross-service URL wiring via env var references).

- Diagnosed and fixed two platform-specific deployment failures on Render's
  free tier (an unsupported pre-deploy command, and a shell-parsing
  mismatch in the container start command) by reading build/deploy logs and
  iterating — resulting in a documented, repeatable Infrastructure-as-Code
  deployment.

## Short, single-line versions (for a compressed resume)

- Built and deployed a full-stack ML-powered ITSM platform (FastAPI,
  Streamlit, PostgreSQL, scikit-learn) with JWT/RBAC auth, 191 automated
  tests, GitHub Actions CI/CD, and a live Render deployment.

- Automated ticket triage with 3 integrated ML models (priority, department,
  SLA-breach prediction), reducing what would be manual routing to an
  automatic classification step on ticket creation.

- Shipped a two-stage CI/CD pipeline (lint + 191 tests) and an
  Infrastructure-as-Code Render deployment (Blueprint YAML, managed
  Postgres, zero manually-entered secrets).
