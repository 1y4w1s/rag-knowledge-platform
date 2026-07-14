"""023 — agent_mode ENUM 扩展 edit (G4-0.2)

Revision ID: 023
Revises: 022
Create Date: 2026-07-10

G4-0.2: agent_runs.mode 扩展 edit 值，支持编辑模式。
"""

from typing import Sequence, Union

from alembic import op

revision: str = "023"
down_revision: Union[str, None] = "022"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE agent_mode ADD VALUE 'edit'")


def downgrade() -> None:
    # PostgreSQL 不支持从 ENUM 中移除值；不做回退操作
    pass