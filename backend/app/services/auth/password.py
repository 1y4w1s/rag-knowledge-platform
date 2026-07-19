"""密码哈希（bcrypt，TECH-SEC SEC-1）。"""

import bcrypt

BCRYPT_ROUNDS = 12


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt(rounds=BCRYPT_ROUNDS)).decode(
        "utf-8"
    )


def verify_password(plain: str, password_hash: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), password_hash.encode("utf-8"))
