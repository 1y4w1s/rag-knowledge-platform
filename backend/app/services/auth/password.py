"""密码哈希与强度策略（TECH-SEC SEC-1 · NW-37）。"""

from __future__ import annotations

import re

import bcrypt

from app.core.exceptions import ValidationError

BCRYPT_ROUNDS = 12
MIN_PASSWORD_LEN = 8

# 与前端 PasswordRequirements / auth-form-validation 对齐：非字母数字即特殊字符
_SPECIAL_RE = re.compile(r"[^A-Za-z0-9]")

# M5 / H2（P0-14）：常见弱密码黑名单（大小写不敏感匹配）。
# 注意：黑名单**必须全小写存储**（匹配时 password.lower() 比较），
# 混合大小写条目会因永不匹配而失效——本窗已归一化（H2 修复）。
# 已知权衡：测试标准口令 `Test123!@` 不在黑名单（全仓测试夹具依赖，
# 且强度规则要求 ≥8 位 + 大小写 + 数字 + 特殊字符，仍是强口令）。
_COMMON_WEAK_PASSWORDS: frozenset[str] = frozenset({
    # 纯数字 / 纯字母（强度规则先拦，黑名单兜底）
    "123456", "12345678", "123456789", "1234567890", "11111111", "00000000",
    "123123123", "66666666", "88888888", "99999999", "12121212",
    "qwerty", "qwerty123", "qwertyuiop", "abc123", "abc12345", "abc123456",
    "password", "password1", "password123", "password1234", "passw0rd",
    "iloveyou", "letmein", "letmein1", "welcome", "welcome1", "monkey",
    "dragon", "football", "baseball", "sunshine", "master", "superman",
    "whatever", "princess", "admin", "admin123", "admin888", "admin1234",
    "administrator", "root", "guest", "test", "test123", "test1234",
    "adminadmin", "changeme", "changeme1", "changeit", "temp1234",
    "qazwsx", "1q2w3e4r", "1qaz2wsx", "zaq12wsx", "asdfghjkl", "zxcvbnm",
    "a123456", "a123456789",
    # 能过强度规则的常见弱口令（黑名单必须拦；任意大小写变体均命中）
    "passw0rd!", "password1!", "password123!", "password@123", "password!123",
    "admin123!", "admin888!", "changeme1!", "welcome1!", "letmein1!",
    "qwerty123!", "p@ssw0rd", "pass@123", "admin@123", "admin!@#",
    "ruige123!", "postgres1!", "grafana1!", "1qaz2wsx!",
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
