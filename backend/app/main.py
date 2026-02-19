import logging
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

from .config import settings
from .logging_config import configure_logging, reset_request_id, set_request_id
from .rate_limit import RateLimitExceeded, SLOWAPI_AVAILABLE, limiter
from .routes import router
from .services import directions, scoring, weather
from .services.cache import route_cache

try:
    import sentry_sdk
    from sentry_sdk.integrations.fastapi import FastApiIntegration
except ModuleNotFoundError:  # pragma: no cover
    sentry_sdk = None
    FastApiIntegration = None

try:
    from prometheus_fastapi_instrumentator import Instrumentator
except ModuleNotFoundError:  # pragma: no cover
    Instrumentator = None

configure_logging(settings.log_format)
logger = logging.getLogger(__name__)

if not SLOWAPI_AVAILABLE:  # pragma: no cover
    logger.warning("slowapi not installed; rate limiting is disabled.")

if settings.sentry_dsn_backend and sentry_sdk and FastApiIntegration:
    sentry_sdk.init(
        dsn=settings.sentry_dsn_backend,
        environment=settings.sentry_environment,
        release=settings.sentry_release,
        integrations=[FastApiIntegration()],
        traces_sample_rate=0.0,
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    route_cache.configure()
    yield
    route_cache.close()
    await directions.client.aclose()
    await weather.client.aclose()
    await scoring.geocode_client.aclose()


app = FastAPI(title="Route Weather API", lifespan=lifespan)
app.state.limiter = limiter

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_methods=["POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)

if Instrumentator:
    Instrumentator().instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)
else:  # pragma: no cover
    @app.get("/metrics", include_in_schema=False)
    async def metrics_fallback():
        return PlainTextResponse("http_requests_total 0\n")


@app.exception_handler(RateLimitExceeded)
async def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded):
    logger.warning(
        "Rate limit exceeded",
        extra={"path": request.url.path, "method": request.method, "status_code": 429},
    )
    return JSONResponse(status_code=429, content={"detail": "Rate limit exceeded"})


@app.middleware("http")
async def request_context_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    token = set_request_id(request_id)
    start = time.perf_counter()
    response = None
    try:
        response = await call_next(request)
    finally:
        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        status_code = response.status_code if response is not None else 500
        logger.info(
            "Request completed",
            extra={
                "path": request.url.path,
                "method": request.method,
                "status_code": status_code,
                "duration_ms": duration_ms,
            },
        )
        reset_request_id(token)

    if response is None:  # pragma: no cover
        return JSONResponse(status_code=500, content={"detail": "Internal server error"})

    response.headers["X-Request-ID"] = request_id
    return response


@app.get("/health")
async def health():
    return {"status": "ok"}


app.include_router(router)

# Serve frontend static files in production.
# The Dockerfile copies the built frontend to /app/static.
# In local dev, this directory doesn't exist so the catch-all is never registered.
STATIC_DIR = Path(__file__).resolve().parent.parent / "static"

if STATIC_DIR.is_dir():
    app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="static-assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        file_path = STATIC_DIR / full_path
        if full_path and file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(STATIC_DIR / "index.html")
