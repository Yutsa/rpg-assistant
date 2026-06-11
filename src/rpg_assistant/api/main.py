from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from rpg_assistant.api.routers import campaigns, chunks, documents, entities, pages, stat_blocks


def create_app() -> FastAPI:
    app = FastAPI(
        title="RPG Assistant API",
        version="0.1.0",
        description="HTTP API for campaign PDF ingestion (raw + semantic read layer).",
    )
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
    app.include_router(campaigns.router)
    app.include_router(documents.router)
    app.include_router(chunks.router)
    app.include_router(stat_blocks.router)
    app.include_router(entities.router)
    app.include_router(pages.router)
    return app


def main() -> None:
    import uvicorn

    uvicorn.run(
        "rpg_assistant.api.main:create_app",
        factory=True,
        host="127.0.0.1",
        port=8000,
    )


if __name__ == "__main__":
    main()
