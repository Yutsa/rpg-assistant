"""Drop token_count from chunks.

Revision ID: 003
Revises: 002
Create Date: 2026-06-26

"""

from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_token_count_column(bind) -> bool:
    if bind.dialect.name == "sqlite":
        rows = bind.execute(text("PRAGMA table_info(chunks)")).fetchall()
        return any(row[1] == "token_count" for row in rows)
    row = bind.execute(
        text(
            """
            SELECT 1
            FROM information_schema.columns
            WHERE table_name = 'chunks' AND column_name = 'token_count'
            LIMIT 1
            """
        )
    ).fetchone()
    return row is not None


def upgrade() -> None:
    bind = op.get_bind()
    if _has_token_count_column(bind):
        op.execute(text("ALTER TABLE chunks DROP COLUMN token_count"))


def downgrade() -> None:
    bind = op.get_bind()
    if not _has_token_count_column(bind):
        op.execute(
            text(
                "ALTER TABLE chunks ADD COLUMN token_count INTEGER NOT NULL DEFAULT 0"
            )
        )
