# Milestone 13-14 — Interview Preparation: CI/CD & Render Deployment

> **Project:** Helpdesk-AI Enterprise ITSM
> **Milestones:** 13 (GitHub Actions CI/CD) and 14 (Render deployment)
> **Audience:** Technical interviews touching CI/CD, deployment, and platform-specific debugging

---

## Topics Covered

- Two-stage CI design (lint job + test job) and why they're separate
- Why `Settings()`'s required fields broke even the *unit* suite in CI
- A Python-version-specific `datetime.fromisoformat` bug CI caught that local dev couldn't
- Render Blueprints as Infrastructure-as-Code, and why over manual dashboard clicking
- `preDeployCommand` being a paid-tier-only feature, and the free-tier workaround
- A real dockerCommand shell-parsing failure, and why a script file fixed it
- A pydantic-settings JSON-decoding gotcha with the `CORS_ORIGINS` env var
- Deliberate, disclosed limitations of the current deployment (not hidden)

---

### Q1. Why split CI into two separate jobs (`lint` and `test`) instead of one job running everything sequentially?

**Answer:** Fail-fast feedback and parallelism. GitHub Actions runs independent jobs concurrently by default, so a lint failure and a test failure are both visible within the same total wall-clock time as the slower one alone, not summed. It's also a clearer signal to a reviewer glancing at the checks: "lint" red means style/correctness issues (fast, cheap to fix), "test" red means actual behavior broke — collapsing them into one job means a lint failure could mask whether the tests even ran.

**Follow-up:** Why give the `test` job a full `postgres:16-alpine` service container instead of mocking the database entirely for CI? → Because the integration suite's entire purpose is verifying real SQL behavior — RBAC boundaries, SLA due-date math, cascading deletes — against an actual Postgres instance, not a mock that could silently diverge from Postgres's real behavior. The service container is configured identically to `docker/docker-compose.test.yml` (same image, credentials, port `5433`), so `tests/integration/conftest.py` needs zero CI-specific configuration to find it.

---

### Q2. The first CI run failed with `pydantic_core.ValidationError: 3 validation errors for Settings` — on the *unit* tests, which are supposed to be fully mocked and not touch a real database. Why did they fail at all?

**Answer:** `backend/core/config.py`'s `Settings` class has three required fields with no defaults — `DB_PASSWORD`, `DATABASE_URL`, `JWT_SECRET_KEY` — deliberately, so the app can never silently boot with a placeholder secret. Locally, a gitignored `.env` satisfies them automatically. The CI runner has no such file. The reason this broke *unit* tests specifically, not just integration tests, is import-time coupling: `tests/unit/conftest.py` imports `backend.models`, which imports the full config chain, which constructs `Settings()` at module load — before a single test function runs or a single mock gets used. A missing env var crashes the entire test *file* at collection time, not a specific assertion. Fixed with a job-level `env:` block in the workflow supplying CI-only dummy values (real ones, structurally, just never used anywhere else).

**Follow-up:** Isn't a required field with no default a design smell if it can break unrelated tests? → No — it's the validator working exactly as designed; the coupling is the real thing to notice. The lesson isn't "loosen the validation," it's "know your import graph": any module-level side effect (settings construction, DB connection, file I/O) that happens on `import` rather than inside a function will run during test *collection*, before any fixture or mock has a chance to intervene.

---

### Q3. Second CI failure: `ValueError: Invalid isoformat string: '2026-07-03T15:15:10.648714Z'` in an SLA breach integration test — but this same test passed locally. What was actually going on?

**Answer:** `datetime.fromisoformat()` only started accepting a trailing `Z` (Zulu/UTC) suffix in Python 3.11. This project targets Python 3.10 — that's both the CI runner's pinned version and `pyproject.toml`'s declared `requires-python`. My local development Python happened to be a newer version where the trailing-`Z` string parsed without complaint, which masked the incompatibility until it ran on a runner actually pinned to the target version. The API's `Z`-suffixed timestamp is correct, standard ISO-8601 — the fix belonged in the *test*, normalizing with `.replace("Z", "+00:00")` before parsing, not in the API.

**Follow-up:** How would you catch this kind of thing before CI does? → Match your local interpreter to the project's declared minimum version (a `.python-version` file plus `pyenv`, or running tests inside the same Docker image CI/prod use) rather than trusting whatever version happens to be on your machine. CI is the backstop, not the first line of defense.

---

### Q4. Why use a Render Blueprint (`render.yaml`) instead of just clicking through Render's dashboard to create the database and two services?

**Answer:** It's Infrastructure-as-Code: the entire cloud footprint — one Postgres instance, two Docker web services, every environment variable and how it's wired — lives in a single reviewable, version-controlled file. Anyone can read exactly what's deployed without dashboard access, it's reproducible (spin up an identical staging environment by importing the same file into a new Render project), and secrets never get typed into a UI by hand: `JWT_SECRET_KEY` uses `generateValue: true` (Render generates and stores it), and the frontend/backend URLs cross-reference each other via `fromService`/`fromDatabase` rather than being copy-pasted between two dashboard tabs.

**Follow-up:** What's the tradeoff? → A YAML file's declarative model can't express every dashboard toggle, and Render's own documented constraints (no variable interpolation, `preDeployCommand` gated by plan tier — see Q5) sometimes force workarounds that a manual click-through wouldn't need. It's a worthwhile tradeoff for reproducibility and review-ability, but it does mean occasionally hitting a platform limitation the dashboard UI would have silently handled for you.

---

### Q5. The Blueprint's backend service originally used `preDeployCommand: python -m database.bootstrap` to run migrations before the app started serving. Render rejected it with "pre-deploy command is not supported for free tier services." What did you do?

**Answer:** `preDeployCommand` runs once, after build, before `startCommand` — the textbook-correct spot for a migration, since it guarantees the migration finishes before any replica starts serving, and before a second/third replica could race the same migration concurrently. It turned out to be a paid-plan-only feature. The free tier only ever runs a single instance anyway, so the multi-replica race concern doesn't apply there — I moved the identical logic into the container's own start command (`dockerCommand`) instead, preserving the same ordering guarantee (migration completes, *then* `uvicorn` starts) just without a separate deploy phase.

**Follow-up:** Is running the migration on every container start safe, or does it need the "once, before serving" guarantee specifically? → `database/bootstrap.py` is deliberately idempotent — Alembic tracks its own applied-migrations state, and the seed data uses `ON CONFLICT ... DO NOTHING` — so rerunning it is safe, and this is the exact same command `docker-compose.yml`'s backend service already runs on every local dev container start. The "once, before serving" property matters for *concurrent replicas*, not for idempotency; single-instance free tier doesn't have that risk at all.

---

### Q6. That first fix (`dockerCommand: sh -c "python -m database.bootstrap && uvicorn ..."`) then failed too — with exit 127 and Render's log showing it tried to run the *entire literal string*, quotes and `&&` included, as one unfound command. What was happening, and how did you fix it?

**Answer:** `docker-compose.yml`'s `command:` field does full shell-aware tokenization when parsing a quoted string like that — the quotes correctly group everything after `sh -c` into one argument. Render's `dockerCommand` field doesn't do the same parsing; empirically, it appears to pass the string through without respecting the quoting, so the shell ends up trying to execute the whole thing — including the literal `&&` — as a single command name, which obviously doesn't exist. Rather than reverse-engineer Render's exact tokenization rules through trial and error, I sidestepped the ambiguity entirely: I wrote the two commands into a real script file (`docker/start-backend.sh`, `set -e`, bootstrap then `exec uvicorn ...`), baked it into the image, made it executable in the Dockerfile, and pointed `dockerCommand` at the bare script path. A path has no spaces or shell metacharacters left for anything to mis-tokenize.

**Follow-up:** Why the explicit `RUN chmod +x` in the Dockerfile instead of relying on the file's permission bit from the git commit? → Because the file was authored and committed on Windows, where the filesystem has no native concept of a Unix executable bit — `git` may or may not preserve `+x` faithfully depending on the exact tooling and settings. An explicit `chmod +x` at build time guarantees the script is executable inside the Linux container regardless of what bit survived the Windows→git→Linux round trip — a small defensive step against a real, easy-to-miss cross-platform failure mode.

---

### Q7. `CORS_ORIGINS` needed to accept the frontend's Render URL, which is only known *after* deploy — how does a Blueprint hand one service's URL to another, and what broke the first time?

**Answer:** Render Blueprints explicitly don't support variable interpolation in the YAML file, so the mechanism is `fromService`/`envVarKey: RENDER_EXTERNAL_URL` — a declarative "wire this env var to that other service's auto-injected public URL" reference resolved by Render at provision time, not a string template. The first attempt typed `CORS_ORIGINS` as `list[str]` with a `@field_validator(mode="before")` meant to split an incoming comma-separated string into a list. It broke at startup with a `SettingsError` from a failed JSON decode — it turns out pydantic-settings tries to JSON-parse any `list`-typed field's raw env var value in its settings *source* layer, a step that runs before any field validator of any mode. A plain URL string like `https://helpdesk-ai-frontend.onrender.com` isn't valid JSON, so it never reached my validator at all.

**Follow-up:** How did you fix it, concretely? → Stopped fighting that earlier layer: `CORS_ORIGINS` is now typed as a plain `str` (raw, comma-separated), with a `cors_origins_list` `@property` that does the splitting whenever the value is actually consumed (in `main.py`'s CORS middleware setup). No JSON decoding happens on this field at all anymore, so there's no earlier layer to conflict with. I verified the fix with three concrete scenarios before considering it done: a single Render-style URL, a genuine multi-origin comma-separated string, and the default with no env var set at all (confirming local/native dev behavior was unaffected).

---

### Q8. What limitations of this deployment are you deliberately *not* hiding?

**Answer:** Two, both documented in the codebase itself rather than only in my head: (1) ticket attachments are stored on local disk, and Render's free-tier filesystem is ephemeral across redeploys — an uploaded file won't survive the next deploy. Moving to S3-compatible object storage is the real fix, tracked as explicit future work, not silently swept under the rug. (2) the free tier spins a service down after ~15 minutes idle, and the first request after that takes 30-60 seconds to wake it back up. I made the frontend's request timeout configurable via `API_TIMEOUT_SECONDS` (60s in production, 10s default locally) specifically so that cold start doesn't get misreported to a user as "the backend is down" — but the multi-second wait itself is still real and visible, not eliminated.

**Follow-up:** Why surface these instead of just not mentioning them? → Because an interviewer (or a real production reviewer) who clicks around a live demo *will* notice the slow first load or a vanished attachment after a redeploy — disclosing it upfront, with the actual tracked fix, reads as engineering judgment. Silently hoping nobody notices reads as either not knowing or hiding it, and both are worse than an honest "here's the tradeoff and here's what fixes it properly."
