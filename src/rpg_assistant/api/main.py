from __future__ import annotations

from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from rpg_assistant.api.errors import ApiError, api_error_handler
from rpg_assistant.api.routers import campaigns, chunks, documents, pages, stat_blocks

WEB_DIST = Path(__file__).resolve().parents[3] / "web" / "dist"


def create_app() -> FastAPI:
    app = FastAPI(title="RPG Assistant", version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.add_exception_handler(ApiError, api_error_handler)

    app.include_router(campaigns.router)
    app.include_router(documents.router)
    app.include_router(chunks.router)
    app.include_router(stat_blocks.router)
    app.include_router(pages.router)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    if WEB_DIST.is_dir():
        assets_dir = WEB_DIST / "assets"
        if assets_dir.is_dir():
            app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

        @app.get("/{full_path:path}")
        async def spa_fallback(full_path: str) -> FileResponse:
            if full_path.startswith(("campaigns", "documents", "chunks", "health")):
                raise HTTPException(status_code=404, detail="Not found")
            candidate = WEB_DIST / full_path
            if full_path and candidate.is_file():
                return FileResponse(candidate)
            index = WEB_DIST / "index.html"
            if not index.is_file():
                raise HTTPException(status_code=404, detail="Frontend not built")
            return FileResponse(index)

    return app


app = create_app()


def run() -> None:
    uvicorn.run(
        "rpg_assistant.api.main:app",
        host="127.0.0.1",
        port=8000,
        reload=False,
    )


if __name__ == "__main__":
    run()
