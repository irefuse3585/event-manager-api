# app/main.py

import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from slowapi import Limiter
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.api.auth import router as auth_router
from app.core.logging import init_logging
from app.db.redis import redis_client
from app.db.session import engine
from app.models.user import User, UserRole
from app.utils.deps import require_role


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan handler for FastAPI.
    Initializes logging and verifies external services (DB, Redis) on startup.
    """
    init_logging()
    logger = logging.getLogger("app.main")
    logger.info("Starting FastAPI application")

    # Startup checks for Redis and Postgres
    try:
        await redis_client.ping()
        logger.info("Successfully connected to Redis.")
    except Exception as exc:
        logger.critical("Failed to connect to Redis: %s", exc, exc_info=True)
        raise
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        logger.info("Successfully connected to Postgres database.")
    except SQLAlchemyError as exc:
        logger.critical("Failed to connect to DB: %s", exc, exc_info=True)
        raise

    yield  # Application runs here

    # Shutdown logic if needed
    logger.info("Shutting down FastAPI application.")


def create_app() -> FastAPI:
    """
    Create and configure FastAPI application instance with lifespan.
    """
    app = FastAPI(
        title="NeoFi Event Manager API",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # Initialize rate limiting
    limiter = Limiter(key_func=get_remote_address, default_limits=["200/minute"])
    app.state.limiter = limiter
    app.add_middleware(SlowAPIMiddleware)

    @app.get("/health", tags=["Health"])
    async def health_check() -> dict:
        """
        Health check endpoint for API, Redis, and PostgreSQL.
        """
        logger = logging.getLogger("app.main")
        redis_status = "ok"
        db_status = "ok"
        try:
            await redis_client.ping()
        except Exception as exc:
            logger.error("Health check failed: Redis unavailable (%s)", exc)
            redis_status = "unavailable"
        try:
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
        except SQLAlchemyError as exc:
            logger.error("Health check failed: DB unavailable (%s)", exc)
            db_status = "unavailable"
        status_code = 200 if (redis_status == "ok" and db_status == "ok") else 503
        return {
            "status": "ok" if status_code == 200 else "degraded",
            "redis": redis_status,
            "db": db_status,
        }

    @app.get("/admin-area", tags=["Admin"])
    async def admin_area(current_user: User = Depends(require_role(UserRole.ADMIN))):
        logger = logging.getLogger("app.main")
        logger.info("Admin-area accessed by user: %s", current_user.username)
        return {"msg": f"Hello, admin {current_user.username}!"}

    # Include authentication routes
    app.include_router(auth_router)

    return app


app = create_app()
