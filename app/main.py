# app/main.py

from fastapi import Depends, FastAPI
from slowapi import Limiter
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address

from app.api.auth import router as auth_router
from app.core.logging import init_logging
from app.models.user import User, UserRole
from app.utils.deps import require_role


def create_app() -> FastAPI:
    """
    Create and configure FastAPI application instance.
    """
    init_logging()

    app = FastAPI(
        title="NeoFi Event Manager API",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    # Initialize rate limiting
    limiter = Limiter(key_func=get_remote_address, default_limits=["200/minute"])
    app.state.limiter = limiter
    app.add_middleware(SlowAPIMiddleware)

    @app.get("/health", tags=["Health"])
    async def health_check() -> dict:
        """
        Health check endpoint.
        """
        return {"status": "ok"}

    @app.get("/admin-area", tags=["Admin"])
    async def admin_area(current_user: User = Depends(require_role(UserRole.ADMIN))):
        """
        Доступ только для админов.
        """
        return {"msg": f"Hello, admin {current_user.username}!"}

    # Include authentication routes
    app.include_router(auth_router)

    return app


app = create_app()
