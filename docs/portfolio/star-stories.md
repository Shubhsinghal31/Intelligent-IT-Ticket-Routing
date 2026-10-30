# STAR Interview Stories — Helpdesk-AI

Four stories, each grounded in something that actually happened while
building this project — not hypotheticals. Practice these out loud; they're
written as prompts to speak from, not a script to recite word-for-word.

---

## 1. Debugging a CI-only failure that never happened locally

**Situation:** After setting up GitHub Actions CI for Helpdesk-AI (lint +
full test suite on every push), the first run failed immediately — every
unit test errored out at import time with a Pydantic `ValidationError`
complaining about three missing settings fields (`DB_PASSWORD`,
`DATABASE_URL`, `JWT_SECRET_KEY`).

**Task:** The suite passed cleanly on my machine. I needed to figure out why
a CI runner behaved differently and fix it without weakening the validation
that was catching the problem in the first place.

**Action:** I traced it to `Settings()` — a Pydantic settings class with
those three fields marked required, no defaults, by design, so the app can
never silently boot with a placeholder secret. Locally, a gitignored `.env`
file satisfied them automatically. The CI runner had no such file. The
subtler part: even the *unit* tests hit this, not just integration —
because `tests/unit/conftest.py` imports `backend.models`, which transitively
imports the full config chain and constructs `Settings()` at module load
time, before a single test or mock actually runs. I fixed it by adding a
job-level `env:` block to the CI workflow supplying CI-only dummy values,
and verified the fix locally first by clearing my own environment
(`env -i PATH=... DATABASE_URL=... python -m pytest`) to reproduce the exact
CI conditions before trusting a re-push to fix it.

**Result:** CI went green, and the fix documents *why* those specific env
vars are needed right in the workflow file — the next person (or me in six
months) doesn't have to re-derive it. More broadly, it reinforced that a
required-field validator doing its job correctly is a feature, not a bug to
work around by loosening it.

---

## 2. A Python version incompatibility hiding in a passing local test suite

**Situation:** Same CI setup, second failure after fixing the first: one
integration test failed with `ValueError: Invalid isoformat string:
'2026-07-03T15:15:10.648714Z'` — a test asserting on an SLA due-date
calculation.

**Task:** Understand why a string my API was correctly returning could fail
to parse, and fix it in the right layer.

**Action:** `datetime.fromisoformat()` only started accepting a trailing `Z`
(Zulu/UTC) suffix in Python 3.11+. This project targets 3.10 (both the CI
runner and `pyproject.toml`'s `requires-python`). My local dev environment
happened to be running a newer Python where the trailing-`Z` string parsed
fine, masking the incompatibility entirely — the bug was invisible until it
hit a runner pinned to the actual target version. The fix belonged in the
*test*, not the API: the API's `Z`-suffixed ISO-8601 timestamp is correct
and standard; I normalized it with `.replace("Z", "+00:00")` before parsing
in the test assertion.

**Result:** Caught a real version-compatibility gap between my dev machine
and the project's declared target Python version — exactly the class of bug
that CI exists to catch, and exactly why I didn't just say "works on my
machine" and move on.

---

## 3. Deploying to a platform with undocumented-to-me free-tier constraints

**Situation:** Deploying to Render via a Blueprint (`render.yaml`), I used
`preDeployCommand` to run the database migration — the textbook-correct
place for it, since it guarantees the migration finishes before the app
starts serving and before any second replica could race it.

**Task:** Render rejected the Blueprint outright: `preDeployCommand` is a
paid-plan-only feature, unsupported on the free tier I was using. I needed
an equivalent that would still run the migration before the app started
accepting traffic, on a plan that only ever runs a single instance.

**Action:** I moved the same logic into the container's start command
instead (`dockerCommand`), reasoning that the free tier's single-instance
guarantee removed the original multi-replica race concern anyway. That
*also* failed — differently this time, with exit 127 and an error showing
Render trying to execute my entire inline `sh -c "cmd1 && cmd2"` string as
one literal, unfound command. Render's `dockerCommand` field doesn't
shell-parse quoted, `&&`-chained strings the way `docker-compose.yml`'s
`command:` field does locally. Rather than keep guessing at Render's exact
tokenization rules, I sidestepped the ambiguity: I wrote the two commands
into an actual shell script file baked into the Docker image, and pointed
`dockerCommand` at that script's bare path — nothing left with spaces or
shell metacharacters for anything to mis-tokenize.

**Result:** Clean deploy, and a more robust pattern than the original
inline string would have been even if it *had* worked — a script file is
easier to test and reason about than an inline shell one-liner buried in
YAML. I also added a defensive `RUN chmod +x` in the Dockerfile rather than
relying on the executable bit surviving a Windows-to-Linux git checkout,
since that's a real, separate way this exact setup could silently break for
someone else.

---

## 4. Deciding how deep to enforce RBAC (and proving it, not just claiming it)

**Situation:** Helpdesk-AI has three roles — employee, engineer, admin —
and I had to decide where "role-based access control" actually lives: only
in what the Streamlit UI shows/hides, or enforced independently at the API
layer.

**Task:** Make the call, and make it defensible — not just "the UI hides
the admin button," which is trivially bypassable by anyone calling the API
directly.

**Action:** I enforced RBAC as a FastAPI dependency at the endpoint level,
independent of anything the frontend does — an employee's JWT literally
cannot authorize a call to an admin-only endpoint, regardless of what URL
they hit. Critically, I didn't just assert this was true — I wrote
integration tests that log in as each role and assert on the specific
403 responses for the endpoints each role shouldn't reach, alongside tests
confirming each role's *allowed* actions still work. That's part of why the
integration suite (57 tests) is meaningfully larger than a typical CRUD
demo's — RBAC boundaries are exactly the kind of thing that's easy to get
right by accident in manual testing and easy to silently regress later
without a test pinning it down.

**Result:** A security boundary that's actually enforced server-side, not
just a UI convenience — and a regression safety net so a future refactor
(say, restructuring the router) can't quietly reopen an access-control gap
without a test failing first.
