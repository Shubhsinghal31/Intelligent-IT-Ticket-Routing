# Milestone 12 — Interview Preparation: Dockerization

> **Project:** Helpdesk-AI Enterprise ITSM
> **Milestone:** 12 — Containerizing backend, frontend, and a dev database
> **Audience:** Technical interviews touching Docker/deployment fundamentals

---

## Topics Covered

- Base image choice and layer-caching order
- Why ML models are trained at build time, and why that's safe
- Running as a non-root user
- Container-to-container networking vs. localhost
- The idempotent database bootstrap script (born from a real incident this session)
- Why two separate `docker-compose` files exist
- What's deliberately deferred to Render (Milestone 14)

---

### Q1. Why `python:3.11-slim` instead of the full `python:3.11` image or an Alpine variant?

**Answer:** It's the middle ground that actually works for this dependency set. The full image includes a complete Debian userland (compilers, docs, etc.) that this app never uses at runtime — pure bloat. Alpine is smaller still, but it uses musl libc instead of glibc, and several pinned dependencies here (`psycopg2-binary`, `numpy`, `pandas`, `scikit-learn`) publish prebuilt wheels for `manylinux` (glibc), not musl — Alpine would force pip to compile them from source, which is slow and needs a full build toolchain installed anyway, eroding Alpine's size advantage while adding build time. `slim` gets prebuilt wheels for every dependency here with no compiler needed, while staying far smaller than the full image.

**Follow-up:** What's the actual size difference? → Roughly `python:3.11` (~1GB) vs. `python:3.11-slim` (~150MB) vs. `python:3.11-alpine` (~50MB) as base layers, before any dependencies are installed — but the wheel-availability problem makes Alpine's raw size number misleading for this specific dependency set.

---

### Q2. Why does the Dockerfile `COPY requirements.txt` and run `pip install` *before* copying the rest of the source code, instead of copying everything at once?

**Answer:** Docker layer caching. Each instruction in a Dockerfile produces a cached layer, invalidated only when its inputs change. If `COPY . .` happened first, editing a single line in `backend/services/ticket_service.py` would invalidate that layer *and every layer after it*, including `pip install` — forcing a full ~20-package reinstall on every rebuild, even though none of the dependencies actually changed. Copying `requirements.txt` alone first means that layer (and the expensive `pip install` layer after it) only gets invalidated when `requirements.txt` itself changes — a routine code edit reuses both layers from cache and rebuilds in seconds instead of minutes.

**Follow-up:** Does this project's shared `requirements.txt` (both backend and frontend dependencies in one file) cost anything here? → Yes — a change to any dependency, even a frontend-only one like `plotly`, invalidates the backend image's `pip install` layer too, and vice versa. Splitting into `requirements-backend.txt`/`requirements-frontend.txt` (with a shared base file for genuinely common packages) would tighten that, at the cost of two files to keep in sync. Deliberately not done yet — the project has one `requirements.txt` from Milestone 0, and reworking it wasn't necessary to get Docker working; noted here as a real, scoped follow-up rather than silently ignored.

---

### Q3. The backend Dockerfile trains all four ML models at build time (`RUN python -m ml.training.train_priority`, etc.) instead of shipping the `.pkl` files or training them at container startup. Why is that safe, and why do it at all?

**Answer:** It's safe because the whole pipeline is deterministic — `ml/data/generate_training_data.py` seeds both `random` and `numpy.random` with `42`, and every script in `ml/training/` passes `random_state=42` to its models. The exact same training run happens on every `docker build`, so there's no "the image I built differs from the one you built" risk. It's worth doing (rather than training at container *startup*) because `.pkl` files are gitignored — they're build artifacts, not source — so the image needs to either generate them itself or start without them. `MLService._safe_load()` already degrades gracefully or predictions fall back to safe defaults, so this isn't a hard requirement) — but baking them into the image at build time means every container starts instantly with real predictions, rather than a ~10-second training delay on first boot (or a `MLService` running in relegated to defaults until that finishes).

**Follow-up:** Isn't training in a `RUN` step wasteful if it happens on every build? → It's cached like any other layer — as long as `ml/data/`, `ml/training/`, and `requirements.txt` haven't changed, Docker reuses the cached layer instead of re-training. It only actually re-runs when the training code or data-generation logic changes, which is exactly when you'd want fresh models anyway.

---

### Q4. Why does the frontend's `api_client.py` need `BASE_URL` to come from an environment variable, when it worked fine hardcoded to `http://localhost:8000` for the entire project up to this point?

**Answer:** Container networking. `localhost` inside a container refers to *that container itself*, not its host machine or any sibling container — this is true regardless of OS or Docker Desktop version. When the frontend and backend run as two separate containers (`docker/docker-compose.yml`), the frontend container's `http://localhost:8000` request would try to reach port 8000 on the frontend container, where nothing is listening, producing a connection-refused error that has nothing to do with the actual application code. Docker Compose's internal DNS resolves service names instead — `http://backend:8000` reaches the actual backend container. `api_client.py` now reads `API_BASE_URL` from the environment (`os.environ.get("API_BASE_URL", "http://localhost:8000")`), defaulting to the original hardcoded value for native (non-Docker) dev, while `docker-compose.yml`'s frontend service overrides it to `http://backend:8000`.

**Follow-up:** Why wasn't this needed for the *backend* talking to Postgres? → It was — the exact same pattern applies. `DB_HOST`/`DATABASE_URL` get overridden from `localhost` to `postgres` (the Compose service name for the database) in the backend service's `environment:` block, for the identical reason.

---

### Q5. What is `database/bootstrap.py`, and why did this milestone need it?

**Answer:** It's an idempotent script that brings a Postgres database from completely empty to fully migrated and seeded in one call — `python -m database.bootstrap`. It exists because of a real bug hit earlier in this same session: this project's schema has 10 hand-written SQL files (`database/migrations/001-010`) that predate Alembic, and Alembic's baseline revision is a deliberate no-op that *assumes* those 10 files already ran. Running `alembic upgrade head` alone against a brand-new database does nothing useful — which is exactly what happened when the local dev database was accidentally reset earlier tonight, producing `relation "users" does not exist`. That was recoverable by hand (run the 10 files, then `alembic stamp` + `upgrade head`, then the 4 seed files) — but a container can't "recover by hand." `docker compose up` needs the backend to bring its own database up from nothing, unattended, every time. `bootstrap.py` automates that exact manual sequence: check if `users` exists (via `to_regclass`) to decide whether the legacy files need to run at all, then always run `alembic upgrade head` (naturally idempotent — it tracks its own version), then always re-apply the 4 seed files (safe because every one uses `ON CONFLICT ... DO NOTHING`).

**Follow-up:** Why not just fix the Alembic baseline to actually contain the schema, instead of keeping this two-step dance? → That's the more thorough long-term fix, and worth doing — a single `alembic upgrade head` that works from a truly empty database is simpler than a script that knows about two different migration systems. It wasn't done as part of this milestone to keep the change scoped: rewriting a already-applied "baseline" migration touches every environment that's ever run it, and is exactly the kind of change that deserves its own dedicated, carefully-tested step rather than being folded silently into "add Docker support."

---

### Q6. Why does the repo have two `docker-compose` files (`docker-compose.test.yml` and `docker-compose.yml`) instead of one?

**Answer:** They serve genuinely different purposes with different risk profiles. `docker-compose.test.yml` (existing, from Milestone 11) spins up a single throwaway Postgres container — no backend, no frontend — purely so `pytest tests/integration` has a real, disposable database to run against; it uses `tmpfs` storage (never touches disk) and fixed test-only credentials. `docker-compose.yml` (this milestone) runs the *entire application* — Postgres plus backend plus frontend — as a way to develop or demo the app without a `.venv`. Merging them would mean every `pytest` run either depends on backend/frontend images being built (slow, unnecessary for testing the API layer) or the "just run the tests" workflow accidentally shares a database volume with the "run the whole app" workflow — exactly the kind of coupling that caused tonight's `.env`/database confusion, deliberately avoided here by keeping the test database fully separate and disposable.

**Follow-up:** Do the two Postgres containers ever conflict? → No — `docker-compose.test.yml`'s Postgres runs on host port `5433` specifically to avoid colliding with `docker-compose.yml`'s Postgres on the default `5432`, and each uses its own container name and (for the dev one) named volume.

---

### Q7. What's deliberately *not* done in this milestone, and why?

**Answer:** Three things, all pushed to Milestone 14 (Render deployment) on purpose: (1) migrations don't run automatically in the backend image's `CMD` — only in `docker-compose.yml`'s dev `command:` override — because in production, running migrations as part of every container's normal startup risks multiple replicas racing to migrate the same database concurrently; Render's Pre-Deploy Command runs migrations once, before any replica starts serving traffic. (2) No production-grade secrets management — `.env` file injection is fine for local Docker dev, but a real deployment needs a proper secrets store. (3) The attachments' local-disk storage limitation (already documented in `docs/interview/11-attachments.md`) still applies inside a container exactly as it did natively — Render's filesystem is ephemeral, so this remains an explicit, tracked follow-up rather than something Docker incidentally fixes.
