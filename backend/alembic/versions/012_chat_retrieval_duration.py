"""012 — chat_messages.retrieval_duration_ms

Revision ID: 012
Revises: 011
Create Date: 2026-07-06

EW-C3: 记录 assistant 消息的 hybrid 检索耗时（毫秒），供 Dashboard 聚合。
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "012"
down_revision: Union[str, None] = "011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "chat_messages",
        sa.Column("retrieval_duration_ms", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("chat_messages", "retrieval_duration_ms")
