from __future__ import annotations

import uvicorn
from fastapi import FastAPI

from rpg_assistant.api.errors import ApiError, api_error_handler
from rpg_assistant.api.routers import campaigns, chunks, documents, pages, stat_blocks


def create_app() -> FastAPI:
    app = FastAPI(title="RPG Assistant", version="0.1.0")

    app.add_exception_handler(ApiError, api_error_handler)

    app.include_router(campaigns.router)
    app.include_router(documents.router)
    app.include_router(chunks.router)
    app.include_router(stat_blocks.router)
    app.include_router(pages.router)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

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
