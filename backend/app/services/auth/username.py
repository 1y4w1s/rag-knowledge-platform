"""用户名校验（Wave 4.2.2）。"""

import re

from fastapi import status
from app.core.exceptions import ValidationError

USERNAME_PATTERN = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_]{2,31}$")
RESERVED_USERNAMES = frozenset(
    {"admin", "root", "system", "support", "help", "api", "null", "undefined"}
)


def normalize_username(username: str) -> str:
    return username.strip().lower()


def validate_username(username: str) -> str:
    raw = username.strip()
    if not USERNAME_PATTERN.fullmatch(raw):
        raise ValidationError("用户名须为 3～32 位字母、数字或下划线，且以字母或数字开头")
    normalized = raw.lower()
    if normalized in RESERVED_USERNAMES:
        raise ValidationError("该用户名不可用")
    return normalized


def normalize_nickname(nickname: str | None) -> str | None:
    if nickname is None:
        return None
    trimmed = nickname.strip()
    return trimmed or None
