"""Add raw_layout_json to pages for PyMuPDF fidelity.

Revision ID: 002
Revises: 001
Create Date: 2026-06-21

"""

from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        op.execute(text("ALTER TABLE pages ADD COLUMN raw_layout_json TEXT"))
    else:
        op.execute(
            text("ALTER TABLE pages ADD COLUMN raw_layout_json JSONB NOT NULL DEFAULT '{}'::jsonb")
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        # SQLite cannot drop columns easily; recreate without column is out of scope for MVP.
        pass
    else:
        op.execute(text("ALTER TABLE pages DROP COLUMN raw_layout_json"))
