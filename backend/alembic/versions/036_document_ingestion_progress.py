"""036 — documents 入库进度字段（NW-4）

processing_stage / progress_percent / progress_detail
供列表轮询展示阶段与百分比；100 仅 completed。
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "036"
down_revision: Union[str, None] = "035"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "documents",
        sa.Column("processing_stage", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "documents",
        sa.Column("progress_percent", sa.SmallInteger(), nullable=True),
    )
    op.add_column(
        "documents",
        sa.Column("progress_detail", sa.String(length=64), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("documents", "progress_detail")
    op.drop_column("documents", "progress_percent")
    op.drop_column("documents", "processing_stage")
