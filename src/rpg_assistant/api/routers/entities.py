from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from rpg_assistant.api.deps import get_db
from rpg_assistant.api.errors import not_found
from rpg_assistant.api.schemas import (
    EntityIndexEntry,
    EntityRelationsResponse,
    entity_to_index_entry,
)
from rpg_assistant.models.semantic import EntityRecord
from rpg_assistant.storage.db import DatabaseConnection
from rpg_assistant.storage.repositories.raw import RawRepository
from rpg_assistant.storage.repositories.semantic import SemanticRepository

router = APIRouter(tags=["entities"])


@router.get(
    "/campaigns/{campaign_id}/entities",
    response_model=list[EntityIndexEntry],
)
def list_campaign_entities(
    campaign_id: str,
    type: str | None = None,
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    conn: DatabaseConnection = Depends(get_db),
) -> list[EntityIndexEntry]:
    raw_repo = RawRepository(conn)
    if not raw_repo.campaign_exists(campaign_id):
        raise not_found("campaign", campaign_id)
    entities = SemanticRepository(conn).list_entities(
        campaign_id,
        entity_type=type,
        limit=limit,
        offset=offset,
    )
    return [entity_to_index_entry(e) for e in entities]


@router.get("/entities/{entity_id}", response_model=EntityRecord)
def get_entity(
    entity_id: str,
    conn: DatabaseConnection = Depends(get_db),
) -> EntityRecord:
    entity = SemanticRepository(conn).get_entity(entity_id)
    if not entity:
        raise not_found("entity", entity_id)
    return entity


@router.get(
    "/entities/{entity_id}/relations",
    response_model=EntityRelationsResponse,
)
def get_entity_relations(
    entity_id: str,
    conn: DatabaseConnection = Depends(get_db),
) -> EntityRelationsResponse:
    sem_repo = SemanticRepository(conn)
    entity = sem_repo.get_entity(entity_id)
    if not entity:
        raise not_found("entity", entity_id)
    relations = sem_repo.list_relations_for_entity(entity_id)
    return EntityRelationsResponse(**relations)
