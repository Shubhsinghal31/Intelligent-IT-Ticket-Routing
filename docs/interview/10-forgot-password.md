# Gap Fill — Interview Preparation: Forgot Password Flow

> **Project:** Helpdesk-AI Enterprise ITSM
> **Feature:** Password reset via emailed, single-use, expiring tokens
> **Audience:** Technical interviews touching applied auth/security

---

## Topics Covered

- Fast hash vs. slow hash — choosing the right one for the data's entropy
- Single-use token enforcement
- User-enumeration prevention (again, in a second flow)
- Why not a magic login link instead

---

### Q1. Why is the password reset token hashed with SHA-256, while the user's actual password is hashed with bcrypt?

**Answer:** They protect against different threats because they have different entropy. A human password might be `Password123!` — low entropy, guessable, so it needs a *deliberately slow* hash (bcrypt) to make brute-forcing every likely password expensive even if the hash leaks. A reset token is `secrets.token_urlsafe(32)` — 256 bits of cryptographically random entropy. Brute-forcing that is infeasible regardless of hash speed, so a slow hash buys nothing but latency. SHA-256 (fast) is the correct tool here — the token's *randomness* is what makes it secure, not the hash's slowness.

**Follow-up:** What would go wrong if you used bcrypt for the token too? → Nothing security-wise — it'd just be needlessly slow (bcrypt is intentionally ~100ms+ per hash) for zero added protection, since the thing being protected is already unguessable.

---

### Q2. Why does `POST /auth/forgot-password` always return the same response, whether or not the email exists?

**Answer:** User enumeration prevention — the same principle applied to `/login` (see `08-logging-security.md`, Q4). If the endpoint said "no account found" for unregistered emails, an attacker could use it to build a list of valid accounts to target for credential stuffing elsewhere. `AuthService.request_password_reset()` looks up the user, and if not found (or inactive), simply returns `None` without raising — no token is generated, no email sent, but the endpoint's response and status code (202) are identical either way.

**Follow-up:** Doesn't this make debugging "I never got my reset email" harder for support staff? → Yes, and that's the accepted tradeoff — a legitimate user support flow (checking server logs, or a dedicated admin tool) exists separately from the public-facing endpoint's response shape, so the security property doesn't get compromised for UX convenience.

---

### Q3. How is single-use enforced?

**Answer:** A nullable `used_at` timestamp on `PasswordResetToken`, set atomically the moment the token is redeemed. `is_valid` (a computed property) checks `used_at is None and now() < expires_at`. `reset_password()` sets `reset_token.used_at = now()` in the same transaction as the password update — so even if someone captured the raw token and tried to reuse it a second later, `is_valid` would already be `False`.

**Follow-up:** What's the race condition risk here? → Two near-simultaneous requests with the same valid token could both pass the `is_valid` check before either commits. This project's traffic profile makes that vanishingly unlikely, but a hardened version would add a unique constraint or `SELECT ... FOR UPDATE` row lock on redemption to close that window entirely.

---

### Q4. Why an emailed reset-token flow instead of just emailing a magic login link?

**Answer:** They solve different problems. A magic login link authenticates you directly — convenient, but means anyone with access to that email (now or later, if the email is ever compromised/forwarded) can log in as you indefinitely until the link expires. A reset-token flow forces you to *set a new password* as part of redemption — it revokes whatever the old (possibly compromised) password was, which is the actual point of "I think my account is compromised, help."

**Follow-up:** Could you support both? → Yes — many products do (passwordless magic-link login is a legitimate, separate feature) — but conflating them into one mechanism would blur two different security postures (login convenience vs. credential recovery) into one token type with unclear semantics.

---

### Q5. What happens if SMTP isn't configured in local dev?

**Answer:** `backend/core/email.py`'s `send_email()` checks `settings.SMTP_HOST` — if empty, it logs the email's subject/body instead of attempting to send, and never raises. This keeps `request_password_reset()` fully functional in dev (you can read the reset link straight from the server logs) without requiring a real mail provider to be configured, and — just as importantly — a broken/misconfigured SMTP server in production can't take down the reset-request endpoint, since sending is best-effort by design.

**Follow-up:** Is silently not sending an email in production ever a bug risk? → Yes — if `SMTP_HOST` were accidentally left empty in a real deployment, users would never receive reset emails and support would have no obvious error to point to (no exception is raised). Worth pairing with a startup-time check or monitoring alert that SMTP is actually configured before going live, not just relying on the dev-mode fallback being safe.
