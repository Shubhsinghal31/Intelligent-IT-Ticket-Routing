"""
Tests for rate limiting (Milestone 10, Step 10.2).

Why not test through the real /auth/login route: that route's body
calls AuthService, which needs a real database connection — out of
scope for a unit test. slowapi's rate check runs as part of calling
the route function itself (before the body executes), so the limiting
mechanics can be verified against a throwaway route decorated with the
exact same Limiter instance and exception handler used in
backend/main.py, without needing a database at all.

Gotcha discovered while writing this test: the throwaway app and its
@limiter.limit(...)-decorated route must be built exactly ONCE at
module scope, not freshly inside each test. slowapi's Limiter keeps a
process-wide record of every view function it has ever decorated;
rebuilding the route per-test re-registers a limit each time, so by
the third test a single request would count three times against the
shared limiter. This isn't a production bug — backend/main.py only
imports and decorates its routes once — but it's a real trap when unit
testing anything built on slowapi.
"""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
from slowapi.errors import RateLimitExceeded

from backend.core.rate_limit import limiter

# Built once at import time — mirrors how backend/main.py decorates its
# real routes exactly once when the module loads.
_app = FastAPI()
_app.state.limiter = limiter


@_app.exception_handler(RateLimitExceeded)
async def _rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    return JSONResponse(
        status_code=429,
        content={
            "detail": f"Rate limit exceeded: {exc.detail}",
            "error_code": "RATE_LIMIT_EXCEEDED",
            "request_id": None,
        },
    )


@_app.get("/limited")
@limiter.limit("3/minute")
def _limited_route(request: Request):
    return {"ok": True}


class TestRateLimiting:
    def setup_method(self):
        # slowapi's Limiter keeps hit counts in an in-memory store shared
        # across the whole process — reset before each test so one test's
        # requests don't count against the next test's quota.
        limiter.reset()
        self.client = TestClient(_app)

    def test_requests_within_limit_succeed(self):
        for _ in range(3):
            response = self.client.get("/limited")
            assert response.status_code == 200
            assert response.json() == {"ok": True}

    def test_request_over_limit_returns_429(self):
        for _ in range(3):
            self.client.get("/limited")

        response = self.client.get("/limited")
        assert response.status_code == 429
        body = response.json()
        assert body["error_code"] == "RATE_LIMIT_EXCEEDED"
        assert "detail" in body

    def test_limit_resets_are_isolated_per_test(self):
        """
        Regression guard for the exact bug found while writing this file:
        a fresh TestClient against the same already-decorated app, after
        limiter.reset(), must get a full fresh quota — not leftover counts
        from a previous test.
        """
        results = [self.client.get("/limited").status_code for _ in range(4)]
        assert results == [200, 200, 200, 429]
