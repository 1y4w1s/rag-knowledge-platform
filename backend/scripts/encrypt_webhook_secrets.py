"""P1-A backfill：将数据库中已有的明文 webhook secret 加密存储。

用法：
    python -m scripts.encrypt_webhook_secrets

安全：
    - 加密密钥由 settings.jwt_secret 派生（SHA-256 → Fernet）
    - 如果 secret 已加密（decrypt_secret 不抛异常），则跳过
    - 幂等：可多次运行，已加密的不再处理
"""

import asyncio
import logging

from sqlalchemy import select

from app.core.database import SessionLocal
from app.models.webhook import Webhook
from app.services.webhook.security import decrypt_secret, encrypt_secret

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


async def encrypt_existing_secrets() -> int:
    """加密所有明文 webhook secret。返回处理数。"""
    processed = 0

    async with SessionLocal() as db:
        result = await db.execute(select(Webhook))
        webhooks = result.scalars().all()

        for wh in webhooks:
            try:
                # 尝试解密 → 如果成功说明已加密，跳过
                decrypt_secret(wh.secret)
                continue  # 已加密
            except Exception:
                pass  # 明文，需要加密

            wh.secret = encrypt_secret(wh.secret)
            processed += 1

        await db.commit()

    return processed


def main() -> None:
    count = asyncio.run(encrypt_existing_secrets())
    logger.info("已加密 %d 个 webhook secret", count)


if __name__ == "__main__":
    main()
