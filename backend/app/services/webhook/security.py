"""Webhook secret 加密/解密（P1-A：at rest 加密；P1-S2：独立专用密钥）。"""

from cryptography.fernet import Fernet
import base64
import hashlib

from app.core.config import settings

_WEBHOOK_DEFAULT_KEYS = frozenset({"", "replace-with-a-long-random-string", "changeme"})


def _get_fernet() -> Fernet:
    """从独立 WEBHOOK_ENCRYPTION_SECRET 派生 Fernet 密钥（32 bytes → base64）。

    P1-S2：webhook 密钥必须使用专用配置，不回退/不继承 jwt_secret 等
    其它凭证体系；未配置、强度不足或与 JWT 串用时 fail-closed。
    """
    secret = settings.webhook_encryption_secret
    if (
        not secret
        or secret in _WEBHOOK_DEFAULT_KEYS
        or len(secret) < 32
        or secret == settings.jwt_secret
    ):
        raise RuntimeError(
            "WEBHOOK_ENCRYPTION_SECRET 未配置、强度不足或与 JWT_SECRET 相同："
            "webhook 密钥加密需要独立的 32+ 字符随机密钥，且禁止复用 JWT 密钥"
        )
    key = hashlib.sha256(secret.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(key))


def encrypt_secret(plain: str) -> str:
    """加密 webhook secret（AES-GCM）。

    Args:
        plain: 明文 secret。

    Returns:
        base64 编码的密文字符串。
    """
    return _get_fernet().encrypt(plain.encode()).decode()


def decrypt_secret(encrypted: str) -> str:
    """解密 webhook secret。

    Args:
        encrypted: 密文字符串。

    Returns:
        原始明文 secret。

    Raises:
        cryptography.fernet.InvalidToken: 加密密钥不匹配或数据损坏。
    """
    return _get_fernet().decrypt(encrypted.encode()).decode()
