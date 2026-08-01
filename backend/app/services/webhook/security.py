"""Webhook secret 加密/解密（P1-A：at rest 加密）。"""

from cryptography.fernet import Fernet
import base64
import hashlib

from app.core.config import settings


def _get_fernet() -> Fernet:
    """从 jwt_secret 派生 Fernet 密钥（32 bytes → base64）。

    不引入额外密钥管理：派生密钥与 jwt_secret 绑定，
    变更 jwt_secret 会使已有 webhook secret 无法解密。
    """
    key = hashlib.sha256(settings.jwt_secret.encode()).digest()
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
        cryptography.fernet.InvalidToken: jwt_secret 不匹配或数据损坏。
    """
    return _get_fernet().decrypt(encrypted.encode()).decode()
