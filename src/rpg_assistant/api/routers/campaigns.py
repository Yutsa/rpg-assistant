from __future__ import annotations

from fastapi import APIRouter, Depends

from rpg_assistant.api.deps import get_db
from rpg_assistant.api.errors import not_found
from rpg_assistant.api.schemas import CampaignSummary, document_to_summary
from rpg_assistant.models.raw import CampaignRecord, DocumentRecord
from rpg_assistant.storage.db import DatabaseConnection
from rpg_assistant.storage.repositories.raw import RawRepository
from rpg_assistant.storage.repositories.semantic import SemanticRepository

router = APIRouter(tags=["campaigns"])


@router.get("/campaigns", response_model=list[CampaignRecord])
def list_campaigns(conn: DatabaseConnection = Depends(get_db)) -> list[CampaignRecord]:
    return RawRepository(conn).list_campaigns()


@router.get("/campaigns/{campaign_id}/documents", response_model=list[DocumentRecord])
def list_campaign_documents(
    campaign_id: str,
    conn: DatabaseConnection = Depends(get_db),
) -> list[DocumentRecord]:
    repo = RawRepository(conn)
    if not repo.campaign_exists(campaign_id):
        raise not_found("campaign", campaign_id)
    return repo.list_documents(campaign_id)


@router.get("/campaigns/{campaign_id}/summary", response_model=CampaignSummary)
def get_campaign_summary(
    campaign_id: str,
    conn: DatabaseConnection = Depends(get_db),
) -> CampaignSummary:
    raw_repo = RawRepository(conn)
    if not raw_repo.campaign_exists(campaign_id):
        raise not_found("campaign", campaign_id)
    semantic = SemanticRepository(conn).get_semantic_summary(campaign_id)
    documents = [
        document_to_summary(doc) for doc in raw_repo.list_documents(campaign_id)
    ]
    return CampaignSummary(**semantic, documents=documents)
