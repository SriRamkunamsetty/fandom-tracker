"""FastAPI application factory for FandomWatch Enterprise Platform."""
import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from fandomwatch.config import settings
from fandomwatch.logging import get_logger
from fandomwatch.metrics import HTTP_REQUEST_DURATION, HTTP_REQUESTS_TOTAL
from .routes import router

logger = get_logger("fandomwatch.api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle event manager for startup and graceful shutdown."""
    logger.info(f"FandomWatch API v{settings.version} starting in {settings.app_env} mode")
    yield
    logger.info("FandomWatch API shutting down gracefully")


def create_app() -> FastAPI:
    """Builds and configures the production FastAPI instance."""
    app = FastAPI(
        title="FandomWatch API",
        description=(
            "Enterprise Fan-Conversation Intelligence Platform: Aspect-Based Sentiment Analysis, "
            "Semantic Narrative Clustering, Time-Series Backlash Anomaly Detection, Holt-Winters "
            "Forecasting, and Autonomous PR Crisis Response."
        ),
        version="2.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # CORS configuration
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Observability & Request Duration Middleware
    @app.middleware("http")
    async def observability_middleware(request: Request, call_next):
        start_time = time.time()
        endpoint = request.url.path
        method = request.method

        try:
            response = await call_next(request)
            status_code = str(response.status_code)
        except Exception as exc:
            status_code = "500"
            logger.error(f"Unhandled exception on {method} {endpoint}: {exc}", exc_info=True)
            response = JSONResponse(
                status_code=500,
                content={"detail": "Internal server error", "path": endpoint},
            )

        duration = time.time() - start_time

        # Track Prometheus metrics
        try:
            HTTP_REQUESTS_TOTAL.labels(method=method, endpoint=endpoint, status=status_code).inc()
            HTTP_REQUEST_DURATION.labels(method=method, endpoint=endpoint).observe(duration)
        except Exception:
            pass

        return response

    # Mount API routes
    app.include_router(router)

    return app
