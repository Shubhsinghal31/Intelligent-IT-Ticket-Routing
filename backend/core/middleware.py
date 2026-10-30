"""
Request correlation ID middleware.

Problem this solves: a single request can log multiple lines across
multiple services (e.g. POST /tickets logs "Ticket created", then
"ML auto-assigned department", then a warning if ML failed). Without a
shared identifier, those lines are indistinguishable from lines produced
by other concurrent requests in the same log file — there's no way to
say "these three log lines all belong to the same API call."

This middleware generates one UUID per incoming request, stores it on
`request.state` for handlers/exception handlers to read, binds it into
every loguru call made during that request via `logger.contextualize()`,
and echoes it back as the X-Request-ID response header so a client (or
a bug report) can hand it back to correlate with server logs.
"""

import uuid

from loguru import logger
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Attaches a unique request_id to every request's state, logs, and response headers."""

    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id

        # logger.contextualize() injects request_id into `extra` for every
        # log call made anywhere during this request — including in services
        # several layers down — without threading request_id through every
        # function signature.
        with logger.contextualize(request_id=request_id):
            response = await call_next(request)

        response.headers["X-Request-ID"] = request_id
        return response
