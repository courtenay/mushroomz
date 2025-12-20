"""FastAPI server for the lighting controller web interface."""

from pathlib import Path
from typing import TYPE_CHECKING

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

if TYPE_CHECKING:
    from main import LightingController


def create_app(controller: "LightingController") -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="Mushroom Lighting Controller",
        description="Web interface for controlling DMX lighting",
        version="1.0.0",
    )

    # Store controller reference for API routes
    app.state.controller = controller

    # Import and include API routes
    from .api import router
    app.include_router(router, prefix="/api")

    # Serve static files
    static_dir = Path(__file__).parent / "static"
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    @app.get("/")
    async def index() -> FileResponse:
        """Serve the main HTML page."""
        return FileResponse(static_dir / "index.html")

    return app
