"""NW-16 / NW-35：值班四件套包装脚本须保持干跑契约（源码不含 apply 开关）。"""

from __future__ import annotations

from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_WRAPPERS = (
    _REPO_ROOT / "scripts" / "ops-duty-dry-run.ps1",
    _REPO_ROOT / "scripts" / "ops-duty-dry-run.sh",
)
_EXPECTED_CLIS = (
    "scan_orphans.py",
    "scan_stale_ingestion.py",
    "purge_trash.py",
    "purge_chat_threads.py",
)


@pytest.mark.parametrize("path", _WRAPPERS, ids=[p.name for p in _WRAPPERS])
def test_ops_duty_wrapper_exists(path: Path) -> None:
    assert path.is_file(), f"missing wrapper: {path}"


@pytest.mark.parametrize("path", _WRAPPERS, ids=[p.name for p in _WRAPPERS])
def test_ops_duty_wrapper_never_contains_apply_flag(path: Path) -> None:
    text = path.read_text(encoding="utf-8-sig")
    assert "--apply" not in text, (
        f"{path.name} must not contain '--apply' (dry-run contract)"
    )


@pytest.mark.parametrize("path", _WRAPPERS, ids=[p.name for p in _WRAPPERS])
def test_ops_duty_wrapper_invokes_all_duty_clis(path: Path) -> None:
    text = path.read_text(encoding="utf-8-sig")
    for name in _EXPECTED_CLIS:
        assert name in text, f"{path.name} must invoke {name}"
