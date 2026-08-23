"""Local DATABASE_URL bootstrap for adversarial P4 CLI (eval harness only)."""

from __future__ import annotations

import os
from pathlib import Path


def bootstrap_local_database_url() -> None:
    if os.environ.get("DATABASE_URL"):
        return
    root = Path(__file__).resolve().parents[4]
    env_file = root / ".env"
    if not env_file.is_file():
        return
    for line in env_file.read_text(encoding="utf-8", errors="ignore").splitlines():
        if line.startswith("POSTGRES_PASSWORD=") and not line.startswith("#"):
            pw = line.split("=", 1)[1].strip()
            if pw:
                os.environ["DATABASE_URL"] = (
                    f"postgresql+asyncpg://ruige:{pw}@localhost:5432/ruige"
                )
            break


bootstrap_local_database_url()
