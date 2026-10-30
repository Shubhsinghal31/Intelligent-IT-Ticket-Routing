# Milestone 10 — Interview Preparation: Logging, Error Handling & Rate Limiting

> **Project:** Helpdesk-AI Enterprise ITSM
> **Milestone:** 10 — Structured error handling, logging, brute-force protection
> **Audience:** Technical interviews touching API reliability/security hygiene

---

## Topics Covered

- Custom exception hierarchies vs. raw `HTTPException`
- Preventing stack-trace/internal-detail leaks
- Rate limiting design (what to limit, and why)
- Structured logging vs. `print()`
- User-enumeration prevention as a logging/response-shape concern

---

### Q1. Why a custom exception hierarchy (`NotFoundException`, `ForbiddenException`, etc.) instead of raising `HTTPException(status_code=404, ...)` everywhere?

**Answer:** Three reasons, all in `backend/core/exceptions.py`: (1) a stable `error_code` string (`"NOT_FOUND"`, `"FORBIDDEN"`) that a frontend or API consumer can branch on without parsing message text, which varies per raise site; (2) the status code is baked into the exception class, so `raise NotFoundException(f"Ticket {id} not found")` can't accidentally use the wrong HTTP status; (3) a single exception handler in `backend/main.py` can log every `AppException` consistently by type, without each raise site remembering to log.

**Follow-up:** Isn't this just `HTTPException` with extra steps? → It's `HTTPException` with a contract: every subclass declares its status/error_code once, at the class level, so 40+ raise sites across the service layer can't drift on what "not found" means in terms of status code.

---

### Q2. How does the app avoid leaking internal details (stack traces, SQL errors) to API clients?

**Answer:** The global exception handler in `backend/main.py` catches unhandled exceptions and returns a generic `ErrorResponse` with a fixed message, logging the real exception (with traceback) server-side via loguru. Only `AppException` subclasses' `detail` messages (which are always written to be safe for clients to see — "Ticket 5 not found," never a raw DB error) reach the response body.

**Follow-up:** What's the risk if this handler didn't exist? → An unhandled `IntegrityError` or similar would propagate to FastAPI's default handler, which in debug mode can include a full traceback in the response — directly useful to an attacker probing the app's internals.

---

### Q3. How is rate limiting implemented, and why only on auth endpoints?

**Answer:** `slowapi`, configured per-endpoint via `@limiter.limit(settings.RATE_LIMIT_LOGIN)` etc. (`"5/minute"` for login, `"3/minute"` for register and forgot-password). It's scoped to auth endpoints specifically because those are the ones where an attacker gains from brute force — credential stuffing against `/login`, account-enumeration or spam via repeated `/register` or `/forgot-password` calls. Ticket CRUD endpoints don't have the same brute-force incentive structure.

**Follow-up:** What's rate-limited *by* — IP, user, something else? → By client IP (slowapi's default `get_remote_address`), which is imperfect behind NAT (many users, one IP) but is the standard first line of defense; a production deployment behind a load balancer would need to configure the real-IP header correctly or this silently rate-limits an entire office/NAT'd network as one client.

---

### Q4. Why does a failed login for an unknown email log the same outcome (401, generic message) as a wrong password for a real account?

**Answer:** User enumeration prevention. If "unknown email" returned a different message ("no account with that email") than "wrong password" ("incorrect password"), an attacker could use the login endpoint to build a list of valid registered emails one guess at a time. `AuthService.authenticate()` runs a dummy `verify_password()` call even when the user isn't found (to keep response *timing* similar too — bcrypt is slow, and skipping it for "not found" would make that branch measurably faster, itself a signal).

**Follow-up:** Where else does this project apply the same principle? → `request_password_reset()` — `POST /auth/forgot-password` always returns the same 202 response and generic message whether or not the email is registered, for exactly the same reason.

---

### Q5. Why loguru instead of Python's built-in `logging` module or `print()`?

**Answer:** `print()` has no levels, no structured output, and can't be redirected/filtered per environment. Built-in `logging` is fully capable but verbose to configure correctly (handlers, formatters, propagation gotchas). loguru gives sensible defaults (readable formatting, easy file rotation via `LOG_FILE_PATH`) with almost no setup, and every log call in this codebase (`logger.info(...)`, `logger.warning(...)`) carries structured context (user IDs, ticket IDs) directly in the message — making log lines greppable/traceable back to a specific request without a separate correlation-ID system.

**Follow-up:** What's missing for production-grade observability? → Structured (JSON) log output for ingestion into a log aggregator (Datadog, ELK), and a request-correlation ID threaded through each request's log lines — this project's logs are human-readable but not yet machine-parseable at scale.
