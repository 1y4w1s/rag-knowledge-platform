"""007 — users.username / users.nickname

Revision ID: 007
Revises: 006
Create Date: 2026-07-03

Wave 4.2.2: display name fields; login by username or email.
"""

import re
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _derive_username(email: str, user_id: str) -> str:
    local = email.split("@", 1)[0].lower()
    base = re.sub(r"[^a-z0-9_]", "", local) or "user"
    if len(base) < 3:
        base = f"user{base}"
    suffix = user_id.replace("-", "")[:6]
    return f"{base[:24]}_{suffix}"


def upgrade() -> None:
    op.add_column("users", sa.Column("username", sa.String(32), nullable=True))
    op.add_column("users", sa.Column("nickname", sa.String(64), nullable=True))

    conn = op.get_bind()
    rows = conn.execute(sa.text("SELECT id, email FROM users")).fetchall()
    for user_id, email in rows:
        username = _derive_username(email, str(user_id))
        conn.execute(
            sa.text("UPDATE users SET username = :username WHERE id = :id"),
            {"username": username, "id": user_id},
        )

    op.alter_column("users", "username", nullable=False)
    op.create_index("ix_users_username", "users", ["username"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_users_username", table_name="users")
    op.drop_column("users", "nickname")
    op.drop_column("users", "username")
