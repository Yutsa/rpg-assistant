from __future__ import annotations

import json
from typing import Any

from sqlalchemy.engine import make_url

DEFAULT_SQLITE_URL = "sqlite:///./data/rpg_assistant.db"


def get_database_url_from_env(env_value: str | None) -> str:
    if env_value:
        return env_value
    return DEFAULT_SQLITE_URL


def detect_dialect(database_url: str) -> str:
    return make_url(database_url).get_backend_name()


def parse_json(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        return json.loads(value)
    return value


def dump_json(value: Any) -> str:
    return json.dumps(value, default=str)


class Dialect:
    def __init__(self, name: str) -> None:
        self.name = name

    @property
    def is_sqlite(self) -> bool:
        return self.name == "sqlite"

    @property
    def is_postgresql(self) -> bool:
        return self.name == "postgresql"

    def json_param(self, placeholder: str = "%s") -> str:
        if self.is_postgresql:
            return f"{placeholder}::jsonb"
        return placeholder

    def now_expr(self) -> str:
        return "CURRENT_TIMESTAMP" if self.is_sqlite else "NOW()"

    def merge_chunk_metadata_sql(self) -> str:
        if self.is_postgresql:
            return """
                metadata_json = COALESCE(metadata_json, '{}'::jsonb) ||
                    jsonb_build_object(
                        'classification_confidence', %s,
                        'ingestion_run_id', %s,
                        'submitted_by', %s
                    )
            """
        return """
            metadata_json = json_patch(
                COALESCE(metadata_json, '{}'),
                json_object(
                    'classification_confidence', %s,
                    'ingestion_run_id', %s,
                    'submitted_by', %s
                )
            )
        """

    def classified_chunks_expr(self) -> str:
        if self.is_postgresql:
            return "COUNT(*) FILTER (WHERE chunk_type IS NOT NULL)"
        return "SUM(CASE WHEN chunk_type IS NOT NULL THEN 1 ELSE 0 END)"

    def in_list_clause(self, column: str, values: list[Any]) -> tuple[str, list[Any]]:
        if not values:
            return "0 = 1", []
        if self.is_postgresql:
            return f"{column} = ANY(%s)", [values]
        placeholders = ", ".join(["%s"] * len(values))
        return f"{column} IN ({placeholders})", list(values)

    def stat_block_json_path(self, field: str) -> str:
        if self.is_postgresql:
            return f"metadata_json->'stat_block'->>'{field}'"
        return f"json_extract(metadata_json, '$.stat_block.{field}')"

    def stat_block_name_expr(self) -> str:
        return f"{self.stat_block_json_path('name')} AS stat_block_name"

    def stat_block_nc_expr(self) -> str:
        return f"{self.stat_block_json_path('nc')} AS stat_block_nc"

    def stat_block_uses_rulebook_expr(self) -> str:
        if self.is_postgresql:
            return (
                "(metadata_json->'stat_block'->'rulebook_reference' IS NOT NULL "
                "AND metadata_json->'stat_block'->'rulebook_reference' != 'null'::jsonb) "
                "AS uses_rulebook"
            )
        return (
            "(json_extract(metadata_json, '$.stat_block.rulebook_reference') IS NOT NULL) "
            "AS uses_rulebook"
        )

    def stat_block_lookup_match_sql(self) -> str:
        name_key = self.stat_block_json_path("_lookup_name")
        subtitle_key = self.stat_block_json_path("_lookup_subtitle")
        return f"({name_key} = %s OR {subtitle_key} = %s)"
