"""M9-P1-4: api_keys.key_hash UNIQUE index (P1-35)."""

import pytest
from httpx import AsyncClient
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from uuid import UUID

from app.core.database import SessionLocal, engine
from app.models.api_key import ApiKey
from tests.conftest import RegisterAndLogin


@pytest.mark.asyncio
async def test_api_keys_key_hash_unique_index_exists() -> None:
    async with engine.connect() as conn:
        index_name = (
            await conn.execute(
                text(
                    """
                    SELECT i.relname
                    FROM pg_class i
                    JOIN pg_index ix ON ix.indexrelid = i.oid
                    JOIN pg_class t ON t.oid = ix.indrelid
                    WHERE t.relname = 'api_keys'
                      AND i.relname = 'uq_api_keys_key_hash'
                      AND ix.indisunique
                    """
                )
            )
        ).scalar_one_or_none()
    assert index_name == "uq_api_keys_key_hash"


@pytest.mark.asyncio
async def test_api_keys_duplicate_key_hash_rejected(
    client: AsyncClient,
    register_and_login: RegisterAndLogin,
) -> None:
    headers, _user = await register_and_login(
        prefix="api-key-hash-index",
        account_type="enterprise",
        org_name="API Key Hash Index Org",
    )
    resp = await client.post(
        "/api/v1/api-keys",
        json={"name": "base-key"},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text

    async with SessionLocal() as db:
        existing = (
            await db.execute(
                select(ApiKey).where(
                    ApiKey.user_id == UUID(_user["id"]),
                    ApiKey.name == "base-key",
                )
            )
        ).scalar_one()
        duplicate = ApiKey(
            user_id=existing.user_id,
            key_hash=existing.key_hash,
            prefix="dup00001",
            name="duplicate-hash-key",
        )
        db.add(duplicate)
        with pytest.raises(IntegrityError):
            await db.commit()
        await db.rollback()
