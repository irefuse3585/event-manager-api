# app/main.py

import asyncio
import contextlib
import logging
from contextlib import asynccontextmanager

import msgpack
from fastapi import Depends, FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import HTTPException as StarletteHTTPException
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from starlette.types import ASGIApp, Receive, Scope, Send

from app.api.auth import router as auth_router
from app.api.events import router as events_router
from app.api.history import router as history_router
from app.api.permissions import router as permissions_router
from app.api.ws_notifications import redis_listener
from app.api.ws_notifications import router as ws_notifications_router
from app.core.logging import init_logging
from app.db.redis import redis_client
from app.db.session import engine
from app.models.user import User, UserRole
from app.schemas.user import UserRead
from app.utils.deps import get_current_user, require_role
from app.utils.exceptions import ServiceUnavailableError


class MessagePackMiddleware:
    """
    If client requests Accept: application/x-msgpack,
    converts all JSON responses to MessagePack.
    """

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = {k: v for k, v in scope.get("headers", [])}
        accept = headers.get(b"accept", b"").decode()
        if "application/x-msgpack" not in accept:
            await self.app(scope, receive, send)
            return

        responder = _MsgpackResponder(self.app, scope, receive, send)
        await responder.run()


class _MsgpackResponder:
    """
    Intercepts JSON response and converts it to MessagePack.
    """

    def __init__(self, app, scope, receive, send):
        self.app = app
        self.scope = scope
        self.receive = receive
        self.send = send

    async def run(self):
        # Buffer to capture response body
        self.body = b""

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                # Replace Content-Type with msgpack
                headers = []
                for name, value in message["headers"]:
                    if name == b"content-type":
                        value = b"application/x-msgpack"
                    headers.append((name, value))
                message["headers"] = headers
                await self.send(message)
            elif message["type"] == "http.response.body":
                # Convert JSON body to MessagePack if possible
                try:
                    import json

                    data = json.loads(message["body"].decode())
                    packed = msgpack.packb(jsonable_encoder(data), use_bin_type=True)
                    message["body"] = packed
                except Exception:
                    pass  # fallback, send as-is
                await self.send(message)
            else:
                await self.send(message)

        await self.app(self.scope, self.receive, send_wrapper)


def add_global_exception_handlers(app: FastAPI):
    """
    Register global exception handlers for various error types.
    """

    @app.exception_handler(ServiceUnavailableError)
    async def db_unavailable_handler(request: Request, exc: ServiceUnavailableError):
        logger = logging.getLogger("app.errors")
        logger.warning(
            "Service unavailable: %s %s -> %s",
            request.method,
            request.url,
            exc.status_code,
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": exc.status_code, "message": exc.detail}},
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        logger = logging.getLogger("app.errors")
        logger.warning(
            "HTTP exception: %s %s -> %s",
            request.method,
            request.url,
            exc.status_code,
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": exc.status_code, "message": exc.detail}},
        )

    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception):
        logger = logging.getLogger("app.errors")
        logger.error(
            "Unhandled exception on %s %s",
            request.method,
            request.url,
            exc_info=True,
        )
        return JSONResponse(
            status_code=500,
            content={"error": {"code": 500, "message": "Internal Server Error"}},
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    On startup: init logging, check Redis/Postgres, start Redis listener.
    On shutdown: stop Redis listener and log shutdown.
    """
    # initialize logging configuration
    init_logging()
    logger = logging.getLogger("app.main")
    logger.info("Starting FastAPI application")

    # check Redis connectivity
    try:
        await redis_client.ping()
        logger.info("Successfully connected to Redis.")
    except Exception as exc:
        logger.critical("Failed to connect to Redis: %s", exc, exc_info=True)
        raise ServiceUnavailableError("Redis temporarily unavailable")

    # check Postgres connectivity
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        logger.info("Successfully connected to Postgres database.")
    except SQLAlchemyError as exc:
        logger.critical("Failed to connect to DB: %s", exc, exc_info=True)
        raise ServiceUnavailableError("Database temporarily unavailable")

    # start background Redis listener for WebSocket notifications
    app.state.redis_task = asyncio.create_task(redis_listener())

    # yield control to FastAPI to start serving requests
    yield

    # shutdown: cancel Redis listener task
    task = app.state.redis_task
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task

    logger.info("Redis listener stopped")
    logger.info("Shutting down FastAPI application.")


def create_app() -> FastAPI:
    app = FastAPI(
        title="NeoFi Event Manager API",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # register global exception handlers
    add_global_exception_handlers(app)

    # Register MessagePack middleware
    app.add_middleware(MessagePackMiddleware)

    # Rate limiting middleware
    limiter = Limiter(key_func=get_remote_address, default_limits=["200/minute"])
    app.state.limiter = limiter
    app.add_middleware(SlowAPIMiddleware)

    # health check endpoint
    @app.get("/health", tags=["Health"])
    async def health_check() -> dict:
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

    # admin-area endpoint
    @app.get("/admin-area", tags=["Admin"])
    async def admin_area(current_user: User = Depends(require_role(UserRole.ADMIN))):
        logger = logging.getLogger("app.main")
        logger.info("Admin-area accessed by user: %s", current_user.username)
        return {"msg": f"Hello, admin {current_user.username}!"}

    # user self-info endpoint
    @app.get("/me", response_model=UserRead, tags=["User"])
    async def read_current_user(current_user: User = Depends(get_current_user)):
        """
        Returns information about the current authenticated user.
        """
        return current_user

    # include routers
    app.include_router(auth_router)
    app.include_router(events_router)
    app.include_router(permissions_router)
    app.include_router(ws_notifications_router)
    app.include_router(history_router)

    return app


app = create_app()
