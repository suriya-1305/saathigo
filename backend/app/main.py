import logging
from pathlib import Path

from fastapi import APIRouter, FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.routes import agents, auth, meta, payments, requests, shipments, trips
from app.core.config import settings
from app.db import Base, engine, ensure_columns

logging.basicConfig(level=logging.INFO)


def create_app() -> FastAPI:
    Base.metadata.create_all(bind=engine)
    ensure_columns()

    app = FastAPI(title=f"{settings.app_name} API", version="1.0.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    api = APIRouter(prefix="/api")
    for module in (auth, meta, trips, requests, shipments, payments, agents):
        api.include_router(module.router)

    @api.get("/health", tags=["meta"])
    def health():
        return {"status": "ok"}

    app.include_router(api)

    uploads = Path(settings.upload_dir)
    uploads.mkdir(parents=True, exist_ok=True)
    app.mount("/uploads", StaticFiles(directory=uploads), name="uploads")

    # Production: serve the built React app (frontend/dist) from the same origin.
    static_dir = Path(settings.static_dir) if settings.static_dir else None
    if static_dir and (static_dir / "index.html").is_file():
        app.mount("/assets", StaticFiles(directory=static_dir / "assets"), name="assets")
        index = static_dir / "index.html"

        @app.get("/{path:path}", include_in_schema=False)
        def spa(path: str):
            if path.startswith(("api/", "uploads/")):
                raise HTTPException(status_code=404)
            candidate = (static_dir / path).resolve()
            if path and candidate.is_file() and static_dir.resolve() in candidate.parents:
                return FileResponse(candidate)
            return FileResponse(index)

    return app


app = create_app()
