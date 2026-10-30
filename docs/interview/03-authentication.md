# Milestone 3 — Interview Preparation: Authentication & Authorization

> **Project:** Helpdesk-AI Enterprise ITSM  
> **Milestone:** 3 — JWT Authentication, RBAC, Repository/Service Layer  
> **Audience:** Technical interviews at mid-to-senior backend / full-stack roles

---

## Topics Covered

- JWT (JSON Web Tokens)
- OAuth2 Password Flow
- Access Tokens vs Refresh Tokens
- Stateless Authentication
- bcrypt & Password Salting
- Role-Based Access Control (RBAC)
- Dependency Injection in FastAPI
- Repository Pattern
- Service Layer Architecture
- Security Best Practices (OWASP)

---

## Interview Questions & Answers

---

### Q1. What is JWT and how does it work?

**Question (Conceptual):** Explain what a JSON Web Token is and describe its three parts.

**Answer:**

A JWT is a compact, URL-safe token used to securely transmit claims between parties. It has three Base64URL-encoded parts separated by dots:

```
header.payload.signature
```

- **Header**: Declares the token type (`JWT`) and signing algorithm (e.g., `HS256`).
- **Payload**: Contains claims — `sub` (subject/user ID), `exp` (expiry), `iat` (issued at), and custom claims like `role`.
- **Signature**: `HMAC_SHA256(base64(header) + "." + base64(payload), SECRET_KEY)`. This proves the token hasn't been tampered with.

**Why stateless?** The server doesn't store tokens. Every request is self-contained — the server verifies the signature and reads the claims directly from the token. This makes JWT ideal for distributed/microservice architectures.

**In our project:** We use `python-jose` to encode/decode JWTs. The secret key lives in `.env` and is read via Pydantic `Settings`. We embed `sub` (user ID), `type` (access/refresh), `role`, and `exp` in the payload.

**Follow-up questions:**
- What happens if the JWT secret key is leaked? → All tokens signed with that key must be considered compromised. Rotate the key immediately (invalidating all tokens) and add the old key to a revocation list.
- Can you read the payload of a JWT without the secret? → Yes. JWTs are Base64-encoded, not encrypted. Never put sensitive data (passwords, PII) in the payload unless you use JWE (JSON Web Encryption).

---

### Q2. Why did you choose JWT over session-based authentication?

**Question (Architecture):** Compare JWT and session-based auth. When would you choose each?

**Answer:**

| Aspect | JWT (Stateless) | Sessions (Stateful) |
|---|---|---|
| Storage | Token on client (header/cookie) | Session ID on client, data on server |
| Server memory | None — no server-side state | Redis/DB required per user |
| Scalability | Horizontal scaling trivial | Sticky sessions or shared store needed |
| Revocation | Hard — must use blocklist or short TTL | Easy — delete session from store |
| Microservices | Ideal — each service verifies independently | Harder — shared session store required |

**Our choice:** JWT because Helpdesk-AI is designed as a stateless REST API that will eventually scale horizontally. The trade-off is token revocation complexity, which we mitigate with short-lived access tokens (30 min) and long-lived refresh tokens (7 days).

**Follow-up:** How do you handle logout with JWT? → You can't truly invalidate a JWT without a blocklist. Approach: on logout, add the token's `jti` (JWT ID) to a Redis set with TTL equal to remaining token lifetime.

---

### Q3. What is the OAuth2 Password Flow and why is it appropriate here?

**Question (Protocol):** Explain the OAuth2 Password Grant. What are its security trade-offs?

**Answer:**

The OAuth2 Password Flow (Resource Owner Password Credentials) works like this:

1. Client sends `username` + `password` to `/auth/login` as `application/x-www-form-urlencoded`
2. Server verifies credentials, returns `access_token` + `refresh_token`
3. Client sends `Authorization: Bearer <access_token>` on subsequent requests

**Why we use it:** FastAPI's `OAuth2PasswordRequestForm` is built for this flow and integrates with Swagger UI automatically. For an internal enterprise tool where the client (our own Streamlit frontend) is trusted, this flow is acceptable.

**Security trade-off:** This flow requires the client to handle raw passwords — appropriate only for first-party (trusted) clients. For third-party apps, use Authorization Code Flow with PKCE instead.

**OWASP note:** Always use HTTPS. Never send credentials over HTTP.

---

### Q4. What is the difference between access tokens and refresh tokens?

**Question (Design):** Why do we use two tokens? What problem does the refresh token solve?

**Answer:**

| | Access Token | Refresh Token |
|---|---|---|
| Lifetime | Short (30 min in our app) | Long (7 days) |
| Purpose | Authorizes API requests | Obtains new access tokens |
| Sent to | Every protected endpoint | Only `/auth/refresh` |
| Exposure risk | Higher (sent frequently) | Lower (sent rarely) |

**The problem:** If the access token is long-lived, a stolen token gives an attacker extended access. If it's short-lived, the user must re-authenticate every 30 minutes, which is bad UX.

**The solution:** Short-lived access token (minimizes damage if stolen) + long-lived refresh token (held more securely, used infrequently to get new access tokens).

**In our project:** `create_access_token()` produces a 30-minute token with `type: "access"`. `create_refresh_token()` produces a 7-day token with `type: "refresh"`. `decode_token()` enforces the type check to prevent a refresh token from being used as an access token.

---

### Q5. How does bcrypt work? Why did we choose cost factor 12?

**Question (Security):** Explain bcrypt's mechanism. What is a salt and why is it critical?

**Answer:**

bcrypt is an adaptive password hashing function designed to be slow by design. It:

1. Generates a **random salt** (16 bytes) automatically
2. Uses the salt + password to run the Blowfish cipher in a key setup loop
3. The number of rounds = `2^cost_factor` — at cost 12, that's 4,096 rounds

**Why salting matters:** Without a salt, identical passwords produce identical hashes. An attacker with a rainbow table (precomputed hash→password lookup) cracks your entire database in seconds. With a unique salt per password, each hash is unique even for the same password — rainbow tables become useless.

**Why cost factor 12?** It produces ~100ms per hash on modern hardware. That's imperceptible to users but makes brute-force attacks 10,000x slower than a cheap hash like MD5. OWASP recommends minimum cost factor 10; we use 12 for defense in depth.

**In our code:**
```python
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12)
```
`passlib` handles salt generation, hash formatting (`$2b$12$...`), and verification automatically.

**Follow-up:** What is `deprecated="auto"` in passlib? → It means if we ever upgrade the hash scheme, passlib will automatically re-hash old passwords on next login using the new scheme. Zero-downtime hash algorithm migration.

---

### Q6. Explain Role-Based Access Control (RBAC) and how you implemented it.

**Question (Design + Code):** What is RBAC? Walk me through your implementation.

**Answer:**

RBAC restricts system access based on a user's assigned role rather than their individual identity. Roles bundle permissions, and users are assigned roles.

**Our roles:**
- `employee` — can create and view their own tickets
- `engineer` — can view/update/resolve assigned tickets
- `admin` — full access including user management and reports

**Implementation pattern — FastAPI Dependency Injection:**

```python
# api/deps.py
def require_role(*roles: str):
    async def _dependency(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role.name not in roles:
            raise ForbiddenException("Insufficient permissions")
        return current_user
    return _dependency

# Usage in router
@router.get("/admin/users", dependencies=[Depends(require_role("admin"))])
async def list_users(): ...
```

The dependency chain: `OAuth2PasswordBearer` → `get_current_user` → `require_role`. FastAPI resolves these automatically before the route handler runs.

**Enterprise perspective:** In a larger system, you'd implement PBAC (Permission-Based Access Control) where roles map to fine-grained permissions (`ticket:create`, `ticket:delete`, etc.) stored in the database. RBAC is appropriate at our scale.

---

### Q7. What is Dependency Injection and why is it used in FastAPI?

**Question (Framework):** Explain DI. How does FastAPI implement it and what are the benefits?

**Answer:**

Dependency Injection means a function/class declares what it needs, and a framework provides those dependencies automatically — the consumer doesn't instantiate them.

**FastAPI's `Depends()`:**

```python
async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
) -> User:
    ...
```

FastAPI builds a dependency graph, resolves all dependencies, and injects them before calling the route handler.

**Benefits:**
1. **Testability** — swap real DB with mock by overriding `app.dependency_overrides`
2. **Reusability** — `get_current_user` is written once, used across all protected routes
3. **Single Responsibility** — routes only handle HTTP concerns, not auth logic
4. **Lifecycle management** — `yield`-based dependencies handle resource cleanup (DB sessions)

**In our code:** `get_db` yields an `AsyncSession` and closes it after the request. This ensures the connection is always returned to the pool, even if an exception occurs.

---

### Q8. Explain the Repository Pattern. Why is it used here?

**Question (Architecture):** What problem does the Repository Pattern solve?

**Answer:**

The Repository Pattern creates an abstraction layer between your business logic and your data access logic. Instead of writing SQL or ORM queries directly in your service or route handler, you call methods like `user_repo.get_by_email(email)`.

**Problem it solves:**
- Service layer doesn't know or care whether data comes from PostgreSQL, MongoDB, or a test fixture
- If you change from SQLAlchemy to another ORM, only the repository changes — not the service
- Easier to mock in unit tests

**Our structure:**
```
BaseRepository          ← generic CRUD: get, get_multi, create, update, delete
  └── UserRepository    ← domain-specific: get_by_email, get_by_username
```

`BaseRepository` uses Python generics (`Generic[ModelType]`) so the type system catches errors at development time.

**Key insight:** The repository takes a `db: AsyncSession` as a constructor argument (injected via `Depends`). This means the same DB session is shared across the request lifecycle, enabling transactions that span multiple repository calls.

---

### Q9. What is the Service Layer and what belongs in it?

**Question (Architecture):** Distinguish between a Service and a Repository.

**Answer:**

| Layer | Responsibility | Example |
|---|---|---|
| Repository | Data access — CRUD operations | `user_repo.get_by_email(email)` |
| Service | Business logic — orchestration | `auth_service.login(email, password)` |
| Route/Controller | HTTP concerns — request/response | Parse request, call service, return JSON |

The Service Layer contains business rules. `AuthService.login()` does: find user → verify password → check active status → create tokens → return result. None of that is HTTP logic; none of it is raw SQL. It's pure business logic.

**Why separate?** The service can be called from a REST API today, a CLI script tomorrow, or a Celery background task next week — no HTTP concerns leak into the logic.

---

### Q10. What security vulnerabilities did you protect against?

**Question (Security):** Walk me through the OWASP considerations in your auth implementation.

**Answer:**

| Threat | Our Mitigation |
|---|---|
| Broken Authentication | bcrypt cost 12 + short-lived tokens + refresh rotation |
| Broken Access Control | RBAC enforced at dependency level, not in business logic |
| Injection | SQLAlchemy ORM with parameterized queries — no raw SQL |
| Security Misconfiguration | Secrets in `.env` (never committed), `python-dotenv`, `.gitignore` |
| Sensitive Data Exposure | Never log passwords or tokens; JWT payload avoids PII |
| Brute Force | Short bcrypt time makes enumeration expensive |
| Token Theft | Short access token TTL (30 min) limits damage window |
| Username Enumeration | `authenticate_user()` returns generic `UnauthorizedException` regardless of whether email exists or password is wrong |

**The last point is often missed in interviews:** Always return the same error for "email not found" and "wrong password". Different errors let attackers enumerate valid accounts.

---

### Q11. How does the token type check prevent token misuse?

**Question (Security):** Why do you check `token.type` in `decode_token()`?

**Answer:**

Without the type check, a refresh token (which lives for 7 days) could be submitted to a protected API endpoint as if it were an access token. Since both are valid JWTs signed with the same secret, the signature check would pass.

The `type` claim (`"access"` or `"refresh"`) is embedded in the payload and signed. `decode_token(token, expected_type="access")` explicitly rejects any token where `payload["type"] != "access"`. This means:

- Access tokens can only be used at protected resource endpoints
- Refresh tokens can only be used at `/auth/refresh`

This is defense in depth: even if an attacker intercepts a refresh token and tries to use it directly on `/me`, they'll get a `401 Expected access token, got refresh`.

---

### Q12. How would you scale this authentication system for 100,000 users?

**Question (System Design):** What are the bottlenecks and how would you address them?

**Answer:**

**Current bottlenecks at scale:**

1. **bcrypt at login** — 100ms per hash is correct for security, but 1,000 concurrent logins = 100 CPU-seconds. Mitigation: run FastAPI with Uvicorn workers + async handling. bcrypt is CPU-bound, so run it in a thread pool: `await asyncio.to_thread(pwd_context.verify, ...)`.

2. **No token revocation** — if an admin deactivates a user, their existing access token is valid for up to 30 more minutes. Mitigation: Redis blocklist keyed on `jti` (JWT ID) with TTL = remaining token lifetime.

3. **Database connection pooling** — at high concurrency, DB connections become the bottleneck. Mitigation: `asyncpg` + SQLAlchemy async engine + PgBouncer in transaction mode.

4. **Single JWT secret** — all tokens signed with one key. Mitigation: implement key rotation with versioned keys (`kid` header claim); validate against the correct key version.

5. **Stateless refresh** — refresh tokens aren't stored server-side, so we can't revoke them individually. Mitigation: refresh token rotation (invalidate old, issue new on each use) + family detection to catch token theft.

---

## STAR Interview Story

**Situation:** I was building an enterprise ITSM backend that needed to support three distinct user roles — employees raising tickets, engineers resolving them, and admins managing everything — with each role having different API access levels.

**Task:** Design and implement a production-grade authentication system with JWT, refresh tokens, bcrypt password hashing, and RBAC, following OWASP security guidelines and clean architecture principles.

**Action:** I implemented a layered system using FastAPI's Dependency Injection. The `security.py` module handles all cryptographic operations (bcrypt with cost factor 12, JWT encoding/decoding). The `AuthService` contains business logic (credential verification, token creation). The `UserRepository` abstracts all database access using SQLAlchemy 2.0 async. RBAC is enforced via `require_role()` FastAPI dependencies, keeping authorization concerns entirely separate from business logic.

**Result:** A stateless, horizontally scalable authentication system with access tokens (30 min TTL), refresh tokens (7 days), type-claim enforcement to prevent token misuse, and generic error responses to prevent username enumeration. The architecture allows the auth layer to be unit-tested in complete isolation from the database by overriding FastAPI's dependency injection.

---

## Common Interview Mistakes to Avoid

- Saying "JWT is encrypted" — it is **signed**, not encrypted. The payload is readable by anyone.
- Suggesting MD5 or SHA-256 for password hashing — these are fast hash functions, never use them for passwords.
- Not knowing the difference between authentication (who you are) and authorization (what you can do).
- Saying JWTs can be revoked by "just deleting them" — you need a blocklist or token rotation.
- Confusing OAuth2 (authorization framework) with JWT (token format) — JWT is often used as the token format within an OAuth2 flow, but they are separate concepts.

---

## Recruiter Talking Points

> "I built the authentication foundation of an enterprise ITSM application using JWT with refresh token rotation, bcrypt at cost factor 12, and FastAPI's dependency injection for RBAC. The system is stateless and horizontally scalable by design. I followed OWASP guidelines throughout — from generic error messages to prevent user enumeration, to short-lived access tokens to minimize breach windows."

---

*Part of the Helpdesk-AI Enterprise ITSM project — Milestone 3 closeout.*
