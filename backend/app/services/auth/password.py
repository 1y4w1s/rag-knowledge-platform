"""密码哈希与强度策略（TECH-SEC SEC-1 · NW-37）。"""

from __future__ import annotations

import re

import bcrypt

from app.core.exceptions import ValidationError

BCRYPT_ROUNDS = 12
MIN_PASSWORD_LEN = 8

# 与前端 PasswordRequirements / auth-form-validation 对齐：非字母数字即特殊字符
_SPECIAL_RE = re.compile(r"[^A-Za-z0-9]")

# M5：常见弱密码黑名单（大小写不敏感匹配）
_COMMON_WEAK_PASSWORDS: frozenset[str] = frozenset({
    "123456", "password", "12345678", "qwerty", "admin123", "abc123",
    "123456789", "11111111", "123123123", "admin888", "password123",
    "P@ssw0rd", "Passw0rd!", "Admin123!", "Qwerty123!", "Test123!@",
    "Welcome1!", "Password1", "Changeme1", "Letmein1", "Passw0rd!",
})


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt(rounds=BCRYPT_ROUNDS)).decode(
        "utf-8"
    )


def verify_password(plain: str, password_hash: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), password_hash.encode("utf-8"))


def validate_password_strength(password: str) -> None:
    """注册 / 改密 / 重置共用。失败抛 ValidationError（422 · 中文）。"""
    if len(password) < MIN_PASSWORD_LEN:
        raise ValidationError(detail=f"密码至少 {MIN_PASSWORD_LEN} 位")
    if not re.search(r"[A-Z]", password):
        raise ValidationError(detail="密码须包含大写字母")
    if not re.search(r"[a-z]", password):
        raise ValidationError(detail="密码须包含小写字母")
    if not re.search(r"[0-9]", password):
        raise ValidationError(detail="密码须包含数字")
    if not _SPECIAL_RE.search(password):
        raise ValidationError(detail="密码须包含特殊字符（如 ! @ # $）")
    if password.lower() in _COMMON_WEAK_PASSWORDS:
        raise ValidationError(detail="密码过于常见，请更换")
