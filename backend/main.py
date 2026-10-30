"""
FastAPI application entry point.

Defines the application factory (create_app) following clean architecture:
- Configuration loading
- Middleware registration
- Router mounting
- Exception handlers
- Lifecycle events (startup/shutdown)
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from loguru import logger
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

# ⭐ CRITICAL: Force-import all models so SQLAlchemy registers them
import backend.models  # noqa: F401
from backend.api.v1.router import api_router
from backend.core.config import settings
from backend.core.exceptions import AppException
from backend.core.logging_config import setup_logging
from backend.core.middleware import RequestIDMiddleware
from backend.core.rate_limit import limiter


# =====================================================
# Lifespan: runs at startup and shutdown
# =====================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Startup and shutdown logic.

    Use this for:
    - Initializing connections (DB, Redis, ML models)
    - Cleanup on shutdown
    """
    # ----- Startup -----
    setup_logging()
    logger.info(f"🚀 Starting {settings.APP_NAME} v{settings.APP_VERSION} ({settings.APP_ENV})")
    logger.info(f"📚 API docs available at http://{settings.API_HOST}:{settings.API_PORT}/docs")

    yield  # Application runs here

    # ----- Shutdown -----
    logger.info(f"👋 Shutting down {settings.APP_NAME}")


# =====================================================
# Application factory
# =====================================================
def create_app() -> FastAPI:
    """
    Build and configure the FastAPI application.

    Returns:
        Configured FastAPI instance.
    """
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description=(
            "🛠️ **Enterprise ITSM Assistant** — AI-powered helpdesk system "
            "with ML-based ticket routing, priority prediction, and SLA breach detection."
        ),
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        debug=settings.APP_DEBUG,
        lifespan=lifespan,
    )

    # -----------------------------------------------
    # Rate limiting: attach the shared Limiter to app.state
    # -----------------------------------------------
    # slowapi's @limiter.limit(...) decorator (used on individual routes
    # in backend/api/v1/endpoints/auth.py) looks up the limiter via
    # request.app.state.limiter at call time — it has to be registered
    # here before any request comes in.
    app.state.limiter = limiter
    app.add_middleware(SlowAPIMiddleware)

    # -----------------------------------------------
    # Middleware: CORS
    # -----------------------------------------------
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # -----------------------------------------------
    # Middleware: request correlation ID
    # -----------------------------------------------
    # Registered after CORSMiddleware so it ends up outermost (Starlette
    # treats the most-recently-added middleware as outermost) — the request
    # ID needs to exist for the entire request, including inside CORS
    # handling, and needs to make it onto every response, including ones
    # produced by the exception handlers below.
    app.add_middleware(RequestIDMiddleware)

    # -----------------------------------------------
    # Routers
    # -----------------------------------------------
    app.include_router(api_router, prefix=settings.API_V1_PREFIX)

    # -----------------------------------------------
    # Exception handler: AppException (and all its subclasses)
    # -----------------------------------------------
    # Without this, FastAPI's default HTTPException handling still returns
    # the correct status code and {"detail": ...} — but drops error_code
    # and request_id, and never logs the error at all. Business-logic
    # errors (404s from a bad ticket ID, 403s from RBAC) are expected,
    # routine traffic, so this logs at INFO rather than ERROR/exception —
    # reserving stack traces for the truly unexpected case below.
    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
        request_id = getattr(request.state, "request_id", None)
        logger.info(f"{exc.error_code} on {request.method} {request.url.path}: {exc.detail}")
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "detail": exc.detail,
                "error_code": exc.error_code,
                "request_id": request_id,
            },
        )

    # -----------------------------------------------
    # Exception handler: request validation (Pydantic / query params)
    # -----------------------------------------------
    # FastAPI already returns a well-formed 422 for these without any
    # handler — this doesn't change that response shape (clients already
    # depend on FastAPI's standard {"detail": [...]} field-error format).
    # What was missing is visibility: these failures previously left zero
    # trace in the logs, so a client sending malformed requests was
    # invisible to anyone watching the server.
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        request_id = getattr(request.state, "request_id", None)
        logger.warning(
            f"Request validation failed on {request.method} {request.url.path}: {exc.errors()}"
        )
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "detail": exc.errors(),
                "error_code": "VALIDATION_ERROR",
                "request_id": request_id,
            },
        )

    # -----------------------------------------------
    # Exception handler: rate limit exceeded
    # -----------------------------------------------
    # slowapi ships its own default handler (_rate_limit_exceeded_handler)
    # that returns a plain-text 429. Overriding it here keeps the error
    # response shape consistent with every other error in this API
    # (detail/error_code/request_id) instead of a client having to special-
    # case one endpoint's error format.
    @app.exception_handler(RateLimitExceeded)
    async def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
        request_id = getattr(request.state, "request_id", None)
        logger.warning(
            f"Rate limit exceeded on {request.method} {request.url.path} "
            f"from {request.client.host if request.client else 'unknown'}: {exc.detail}"
        )
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={
                "detail": f"Rate limit exceeded: {exc.detail}",
                "error_code": "RATE_LIMIT_EXCEEDED",
                "request_id": request_id,
            },
        )

    # -----------------------------------------------
    # Global exception handler — truly unexpected errors only
    # -----------------------------------------------
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        """
        Catch-all for unhandled exceptions — never leak stack traces to clients.

        Starlette routes generic Exception to a separate, outer
        ServerErrorMiddleware — unlike AppException/RequestValidationError,
        which are caught *inside* RequestIDMiddleware's call_next() and so
        get the X-Request-ID response header attached automatically on the
        way back out. An exception that reaches this handler instead skips
        that return path entirely, so the header has to be set explicitly
        here or every 500 response would be missing it.
        """
        request_id = getattr(request.state, "request_id", None)
        logger.exception(
            f"Unhandled exception on {request.method} {request.url.path} "
            f"[request_id={request_id}]: {exc}"
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "detail": "An internal server error occurred",
                "error_code": "INTERNAL_SERVER_ERROR",
                "request_id": request_id,
            },
            headers={"X-Request-ID": request_id} if request_id else None,
        )

    # -----------------------------------------------
    # Root endpoint
    # -----------------------------------------------
    @app.get("/", tags=["Root"], include_in_schema=False)
    async def root():
        return {
            "app": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "docs": "/docs",
            "health": f"{settings.API_V1_PREFIX}/health",
        }

    return app


# =====================================================
# Module-level app instance (used by uvicorn)
# =====================================================
app = create_app()
