from __future__ import annotations

import os

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from rpg_api.errors import ApiError, api_error_handler
from rpg_api.routers import campaigns, chunks, documents, imports, pages, stat_blocks

_DEFAULT_CORS_ORIGINS = "http://localhost:4200,http://127.0.0.1:4200"


def _cors_origins() -> list[str]:
    raw = os.environ.get("CORS_ORIGINS", _DEFAULT_CORS_ORIGINS)
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


def create_app() -> FastAPI:
    app = FastAPI(title="RPG Assistant", version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins(),
        allow_origin_regex=r"https://.*\.agent\.cvm\.dev",
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
    app.include_router(imports.router)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()


def run() -> None:
    host = os.environ.get("API_HOST", "0.0.0.0")
    port = int(os.environ.get("API_PORT", "8000"))
    uvicorn.run(
        "rpg_api.main:app",
        host=host,
        port=port,
        reload=False,
    )


if __name__ == "__main__":
    run()
