from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from rpg_ingest.raw.layout import LayoutBlock


class BlockRef(BaseModel):
    page_number: int
    block_index: int


class StatAbility(BaseModel):
    title: str
    text: str


class StatAttack(BaseModel):
    name: str
    attack_bonus: int
    damage: str


class RulebookReference(BaseModel):
    profile_name: str
    source_label: str = "Livre de règles, COF"


class ParsedStatBlock(BaseModel):
    name: str
    subtitle: str | None = None
    nc: int | str | None = None
    attributes: dict[str, int] = Field(default_factory=dict)
    defense: int | None = None
    vigor: int | None = None
    initiative: int | None = None
    mana: int | None = None
    attacks: list[StatAttack] = Field(default_factory=list)
    abilities: list[StatAbility] = Field(default_factory=list)
    rulebook_reference: RulebookReference | None = None
    raw_text: str = ""
    block_refs: list[BlockRef] = Field(default_factory=list)
    game_system: str = ""


class StatBlockSpan(BaseModel):
    id: str
    blocks: list[LayoutBlock] = Field(default_factory=list)
    page_start: int = 0
    page_end: int = 0

    model_config = {"arbitrary_types_allowed": True}


class StatBlockAnnotationResult(BaseModel):
    pages: list[Any]
    spans: list[StatBlockSpan] = Field(default_factory=list)
    profile_id: str = ""

    model_config = {"arbitrary_types_allowed": True}
