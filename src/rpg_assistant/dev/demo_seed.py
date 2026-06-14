from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pymupdf

from rpg_assistant.models.raw import (
    BBox,
    ChunkRecord,
    IngestionRunRecord,
    PageBlockRecord,
    PageRecord,
    SectionRecord,
    SourceSpan,
)
from rpg_assistant.models.semantic import ChunkClassification, EntityRecord, EntitySourceRef
from rpg_assistant.storage.db import DatabaseConnection, get_connection
from rpg_assistant.storage.repositories.raw import RawRepository
from rpg_assistant.storage.repositories.semantic import SemanticRepository

DEMO_PDF_DIR = Path("data/demo")
DEMO_PDF_PATH = DEMO_PDF_DIR / "mondanites-momie.pdf"
CAMPAIGN_MOMIE = "momie"
DOCUMENT_MOMIE = "doc_demo_momie"
INGESTION_RUN_ID = "run_demo_seed"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _write_demo_pdf(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = pymupdf.open()
    pages = [
        "Mondanités et Momie — Introduction\n\n"
        "Les aventuriers pénètrent dans la crypte enfumée. "
        "L'odeur de myrrhe et de poussière ancienne leur brûle les narines.",
        "La crypte\n\n"
        "Un gobelin embusqué bondit depuis une alcôve. "
        "Plus loin, le sarcophage de la momie animée pulse d'une lueur verdâtre.",
        "Mondanités\n\n"
        "Le village voisin murmure des légendes sur la momie. "
        "Les villageois évitent le sentier nord après la tombée de la nuit.",
    ]
    for text in pages:
        page = doc.new_page()
        page.insert_text((72, 72), text, fontsize=11)
    doc.save(path)
    doc.close()


def _clear_demo_campaign(conn: DatabaseConnection, campaign_id: str) -> None:
    with conn.cursor() as cur:
        cur.execute("DELETE FROM campaigns WHERE id = %s", (campaign_id,))


def seed_demo_data(*, reset: bool = True) -> dict[str, str]:
    """Insère une campagne de démo exploitable par le front Replicant."""
    pdf_path = DEMO_PDF_PATH.resolve()
    _write_demo_pdf(pdf_path)

    with get_connection() as conn:
        if reset:
            _clear_demo_campaign(conn, CAMPAIGN_MOMIE)

        raw = RawRepository(conn)
        semantic = SemanticRepository(conn)

        raw.ensure_campaign(
            CAMPAIGN_MOMIE,
            title="Mondanités et Momie",
            game_system="cof2",
        )
        raw.upsert_document(
            DOCUMENT_MOMIE,
            campaign_id=CAMPAIGN_MOMIE,
            filename="Mondanités et Momie.pdf",
            page_count=3,
            content_hash="demo-momie-v1",
        )
        raw.create_ingestion_run(
            IngestionRunRecord(
                id=INGESTION_RUN_ID,
                campaign_id=CAMPAIGN_MOMIE,
                document_id=DOCUMENT_MOMIE,
                stage="raw",
                status="completed",
                stats={"source_pdf_path": str(pdf_path)},
                started_at=_utcnow(),
            )
        )

        raw.insert_sections(
            [
                SectionRecord(
                    id="sec_intro",
                    campaign_id=CAMPAIGN_MOMIE,
                    document_id=DOCUMENT_MOMIE,
                    parent_section_id=None,
                    title="Introduction",
                    level=1,
                    page_start=1,
                    page_end=1,
                ),
                SectionRecord(
                    id="sec_crypte",
                    campaign_id=CAMPAIGN_MOMIE,
                    document_id=DOCUMENT_MOMIE,
                    parent_section_id="sec_intro",
                    title="La crypte",
                    level=2,
                    page_start=2,
                    page_end=2,
                ),
                SectionRecord(
                    id="sec_mondanites",
                    campaign_id=CAMPAIGN_MOMIE,
                    document_id=DOCUMENT_MOMIE,
                    parent_section_id=None,
                    title="Mondanités",
                    level=1,
                    page_start=3,
                    page_end=3,
                ),
            ]
        )

        raw.insert_pages(
            [
                PageRecord(
                    id="page_demo_1",
                    document_id=DOCUMENT_MOMIE,
                    page_number=1,
                    text="Introduction",
                    text_coverage_ratio=1.0,
                    width=595.0,
                    height=842.0,
                ),
                PageRecord(
                    id="page_demo_2",
                    document_id=DOCUMENT_MOMIE,
                    page_number=2,
                    text="La crypte",
                    text_coverage_ratio=1.0,
                    width=595.0,
                    height=842.0,
                ),
                PageRecord(
                    id="page_demo_3",
                    document_id=DOCUMENT_MOMIE,
                    page_number=3,
                    text="Mondanités",
                    text_coverage_ratio=1.0,
                    width=595.0,
                    height=842.0,
                ),
            ]
        )

        raw.insert_page_blocks(
            [
                PageBlockRecord(
                    id="blk_intro",
                    document_id=DOCUMENT_MOMIE,
                    page_id="page_demo_1",
                    page_number=1,
                    block_index=0,
                    text="Les aventuriers pénètrent dans la crypte enfumée.",
                    bbox=BBox(x0=72, y0=72, x1=480, y1=120),
                ),
                PageBlockRecord(
                    id="blk_gobelin",
                    document_id=DOCUMENT_MOMIE,
                    page_id="page_demo_2",
                    page_number=2,
                    block_index=0,
                    text="Un gobelin embusqué bondit depuis une alcôve.",
                    bbox=BBox(x0=72, y0=72, x1=460, y1=110),
                ),
                PageBlockRecord(
                    id="blk_momie",
                    document_id=DOCUMENT_MOMIE,
                    page_id="page_demo_2",
                    page_number=2,
                    block_index=1,
                    text="Le sarcophage de la momie animée pulse d'une lueur verdâtre.",
                    bbox=BBox(x0=72, y0=130, x1=500, y1=170),
                ),
                PageBlockRecord(
                    id="blk_village",
                    document_id=DOCUMENT_MOMIE,
                    page_id="page_demo_3",
                    page_number=3,
                    block_index=0,
                    text="Le village voisin murmure des légendes sur la momie.",
                    bbox=BBox(x0=72, y0=72, x1=470, y1=110),
                ),
            ]
        )

        raw.insert_chunks(
            [
                ChunkRecord(
                    id="chunk_intro",
                    campaign_id=CAMPAIGN_MOMIE,
                    document_id=DOCUMENT_MOMIE,
                    section_id="sec_intro",
                    page_start=1,
                    page_end=1,
                    text=(
                        "Les aventuriers pénètrent dans la crypte enfumée. "
                        "L'odeur de myrrhe et de poussière ancienne leur brûle les narines. "
                        "Des torches vacillantes dessinent des ombres longues sur les murs de pierre."
                    ),
                    chunk_type_hint="narrative",
                    token_count=42,
                    source_spans=[
                        SourceSpan(
                            page=1,
                            page_block_ids=["blk_intro"],
                            bbox=BBox(x0=72, y0=72, x1=480, y1=120),
                        )
                    ],
                ),
                ChunkRecord(
                    id="chunk_gobelin_scene",
                    campaign_id=CAMPAIGN_MOMIE,
                    document_id=DOCUMENT_MOMIE,
                    section_id="sec_crypte",
                    page_start=2,
                    page_end=2,
                    text=(
                        "Un gobelin embusqué bondit depuis une alcôve et hurle : "
                        "« À vos places, mortels ! » Les héros sentent le métal froid de la lame."
                    ),
                    chunk_type_hint="narrative",
                    token_count=28,
                    source_spans=[
                        SourceSpan(
                            page=2,
                            page_block_ids=["blk_gobelin"],
                            bbox=BBox(x0=72, y0=72, x1=460, y1=110),
                        )
                    ],
                ),
                ChunkRecord(
                    id="chunk_gobelin_stat",
                    campaign_id=CAMPAIGN_MOMIE,
                    document_id=DOCUMENT_MOMIE,
                    section_id="sec_crypte",
                    page_start=2,
                    page_end=2,
                    text="Gobelin\nNC 1\nFOR 10 · DEX 14 · CON 8\nCoup sournois : +2 dégâts si avantage.",
                    chunk_type_hint="stat_block",
                    token_count=18,
                    source_spans=[
                        SourceSpan(
                            page=2,
                            page_block_ids=["blk_gobelin"],
                            bbox=BBox(x0=72, y0=72, x1=460, y1=110),
                        )
                    ],
                    metadata={
                        "stat_block": {
                            "name": "Gobelin",
                            "nc": 1,
                            "attributes": {"FOR": "10", "DEX": "14", "CON": "8"},
                            "abilities": [
                                {
                                    "title": "Coup sournois",
                                    "text": "Inflige +2 dégâts lorsqu'il attaque avec avantage.",
                                }
                            ],
                        }
                    },
                ),
                ChunkRecord(
                    id="chunk_momie_stat",
                    campaign_id=CAMPAIGN_MOMIE,
                    document_id=DOCUMENT_MOMIE,
                    section_id="sec_crypte",
                    page_start=2,
                    page_end=2,
                    text="Momie animée\nNC 3\nImmunité poison. Résistance nécrotique.",
                    chunk_type_hint="stat_block",
                    token_count=16,
                    source_spans=[
                        SourceSpan(
                            page=2,
                            page_block_ids=["blk_momie"],
                            bbox=BBox(x0=72, y0=130, x1=500, y1=170),
                        )
                    ],
                    metadata={
                        "stat_block": {
                            "name": "Momie animée",
                            "subtitle": "Gardienne du sarcophage",
                            "nc": 3,
                            "attributes": {"FOR": "16", "DEX": "8", "CON": "14"},
                            "abilities": [
                                {
                                    "title": "Regard pétrifiant",
                                    "text": "La cible doit réussir un jet de Volonté ou être ralentie.",
                                }
                            ],
                        }
                    },
                ),
                ChunkRecord(
                    id="chunk_mondanites",
                    campaign_id=CAMPAIGN_MOMIE,
                    document_id=DOCUMENT_MOMIE,
                    section_id="sec_mondanites",
                    page_start=3,
                    page_end=3,
                    text=(
                        "Le village voisin murmure des légendes sur la momie. "
                        "Les villageois évitent le sentier nord après la tombée de la nuit. "
                        "Une vieille prêtresse propose aux héros une amulette de protection."
                    ),
                    chunk_type_hint="narrative",
                    token_count=35,
                    source_spans=[
                        SourceSpan(
                            page=3,
                            page_block_ids=["blk_village"],
                            bbox=BBox(x0=72, y0=72, x1=470, y1=110),
                        )
                    ],
                ),
            ]
        )

        semantic.submit_chunk_classifications(
            ingestion_run_id=INGESTION_RUN_ID,
            campaign_id=CAMPAIGN_MOMIE,
            submitted_by="demo-seed",
            classifications=[
                ChunkClassification(chunk_id="chunk_intro", chunk_type="narrative", confidence=0.95),
                ChunkClassification(
                    chunk_id="chunk_gobelin_scene", chunk_type="narrative", confidence=0.9
                ),
                ChunkClassification(
                    chunk_id="chunk_gobelin_stat", chunk_type="stat_block", confidence=0.98
                ),
                ChunkClassification(
                    chunk_id="chunk_momie_stat", chunk_type="stat_block", confidence=0.98
                ),
                ChunkClassification(
                    chunk_id="chunk_mondanites", chunk_type="narrative", confidence=0.92
                ),
            ],
        )
        semantic.submit_entities(
            ingestion_run_id=INGESTION_RUN_ID,
            campaign_id=CAMPAIGN_MOMIE,
            submitted_by="demo-seed",
            entities=[
                EntityRecord(
                    entity_id="ent_momie",
                    type="npc",
                    name="Momie animée",
                    summary="Antagoniste principale de la crypte.",
                    confidence=0.9,
                    source_refs=[
                        EntitySourceRef(
                            document_id=DOCUMENT_MOMIE,
                            page=2,
                            chunk_id="chunk_momie_stat",
                            page_block_ids=["blk_momie"],
                        )
                    ],
                ),
                EntityRecord(
                    entity_id="ent_village",
                    type="location",
                    name="Village des Mondanités",
                    summary="Hameau voisin de la crypte.",
                    confidence=0.85,
                    source_refs=[
                        EntitySourceRef(
                            document_id=DOCUMENT_MOMIE,
                            page=3,
                            chunk_id="chunk_mondanites",
                            page_block_ids=["blk_village"],
                        )
                    ],
                ),
            ],
        )

        conn.commit()

    return {
        "campaign_id": CAMPAIGN_MOMIE,
        "document_id": DOCUMENT_MOMIE,
        "pdf_path": str(pdf_path),
    }
