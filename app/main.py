# app/main.py

from fastapi import FastAPI

from app.core.logging import init_logging


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

    @app.get("/health", tags=["Health"])
    async def health_check() -> dict:
        """
        Health check endpoint.
        """
        return {"status": "ok"}

    return app


app = create_app()
