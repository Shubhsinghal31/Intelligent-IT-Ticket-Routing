"""
Rate limiting — brute-force protection for authentication endpoints.

Problem this solves: without a limit, an attacker (or a buggy client
retry loop) can hit /auth/login thousands of times per second, either
password-spraying every account in the system or just taking the
database down. JWT verification and RBAC don't help here — the request
never gets past login because it's the login endpoint itself being
attacked.

Library choice: slowapi, a thin FastAPI/Starlette adapter around the
`limits` package. It tracks request counts per key (here, client IP)
in an in-memory store and raises RateLimitExceeded once a window's
quota is used up.

Alternative considered: enforcing this at the infrastructure layer
(nginx `limit_req`, a cloud load balancer, or Render's own edge
throttling) instead of in application code. That's a valid and common
production choice, and the two aren't mutually exclusive — but an
app-level limiter (a) works identically in local dev with no
extra infra, (b) can key on more than just IP (e.g. per-account in a
later iteration), and (c) is easier to unit test and to explain here.

Known limitation: the default in-memory storage means limits reset if
the process restarts, and aren't shared across multiple uvicorn
worker processes. Production multi-worker deployments would point
slowapi at Redis (`storage_uri="redis://..."`) instead — noted here
rather than implemented, since this project runs a single worker.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

# A single shared Limiter instance — imported by main.py (to register
# the exception handler and middleware) and by any endpoint module
# that wants to decorate a route with @limiter.limit(...).
limiter = Limiter(key_func=get_remote_address)
