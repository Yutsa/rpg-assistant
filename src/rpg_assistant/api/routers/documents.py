from __future__ import annotations

from fastapi import APIRouter, Depends

from rpg_assistant.api.deps import get_db
from rpg_assistant.models.raw import SectionRecord
from rpg_assistant.storage.db import DatabaseConnection
from rpg_assistant.storage.repositories.raw import RawRepository

router = APIRouter(tags=["documents"])


@router.get("/documents/{document_id}/sections", response_model=list[SectionRecord])
def list_document_sections(
    document_id: str,
    conn: DatabaseConnection = Depends(get_db),
) -> list[SectionRecord]:
    return RawRepository(conn).list_sections(document_id)
