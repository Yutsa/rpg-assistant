from __future__ import annotations

from fastapi import APIRouter, Depends

from rpg_api.deps import get_raw_repo, get_semantic_repo
from rpg_api.schemas import CampaignOut, CampaignSummaryOut, DocumentOut
from rpg_core.storage.repositories.raw import RawRepository
from rpg_core.storage.repositories.semantic import SemanticRepository

router = APIRouter(prefix="/campaigns", tags=["campaigns"])


@router.get("", response_model=list[CampaignOut])
def list_campaigns(repo: RawRepository = Depends(get_raw_repo)) -> list[CampaignOut]:
    return [CampaignOut(**c.model_dump()) for c in repo.list_campaigns()]


@router.get("/{campaign_id}/documents", response_model=list[DocumentOut])
def list_documents(
    campaign_id: str,
    repo: RawRepository = Depends(get_raw_repo),
) -> list[DocumentOut]:
    return [DocumentOut(**d.model_dump()) for d in repo.list_documents(campaign_id)]


@router.get("/{campaign_id}/summary", response_model=CampaignSummaryOut)
def campaign_summary(
    campaign_id: str,
    raw_repo: RawRepository = Depends(get_raw_repo),
    semantic_repo: SemanticRepository = Depends(get_semantic_repo),
) -> CampaignSummaryOut:
    documents = raw_repo.list_documents(campaign_id)
    section_count = sum(d.section_count for d in documents)
    chunk_count = sum(d.chunk_count for d in documents)
    semantic = semantic_repo.get_semantic_summary(campaign_id)
    return CampaignSummaryOut(
        campaign_id=campaign_id,
        document_count=len(documents),
        section_count=section_count,
        chunk_count=chunk_count,
        chunks_total=semantic["chunks_total"],
        chunks_classified=semantic["chunks_classified"],
        entities=semantic["entities"],
        relations=semantic["relations"],
        low_confidence_entities=semantic["low_confidence_entities"],
        needs_review=semantic["needs_review"],
    )
