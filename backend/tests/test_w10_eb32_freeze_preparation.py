"""W10 E-B32 freeze preparation — tests-only deterministic doc validation."""

from __future__ import annotations

from pathlib import Path
import re

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
EB32_DIR = REPO_ROOT / "docs" / "research" / "w10-eb32-freeze-preparation"

REQUIRED_FILES = (
    "README.md",
    "01-source-identity-freeze-template.md",
    "02-capture-mode-freeze-template.md",
    "03-runtime-and-reproducibility-freeze-template.md",
    "04-human-freeze-checklist.md",
    "05-freeze-execution-entry-gate.md",
)

FORBIDDEN_STATUS_VARS = (
    "OWNER_AUTHORIZATION_ISSUED",
    "SOURCE_APPROVED",
    "AFTER_SOURCE_APPROVED",
    "E-B_FORMAL_READY",
)

PROHIBITION_MARKERS = (
    "DO NOT",
    "MUST NOT",
    "禁止",
    "⇏",
    "non-goal",
    "Does not",
    "不得",
    "unchanged",
    "remain",
    "still NO",
    "not flip",
    "∧",
    "only where",
    "future",
    "later human",
    "human freeze",
    "predicate",
)

SEPARATION_PATTERNS = (
    re.compile(r"candidate\s*≠\s*approved", re.IGNORECASE),
    re.compile(r"template\s*≠\s*frozen", re.IGNORECASE),
    re.compile(r"Preparation\s*≠\s*Freeze", re.IGNORECASE),
)

REAL_STAMP_MARKERS = (
    re.compile(r"authorization_status\s*=\s*APPROVED"),
    re.compile(r"freeze_status\s*=\s*FROZEN(?!\s*\()"),  # achieved FROZEN, not prose
)

SHA_LIKE = re.compile(r"\b[a-f0-9]{40}\b")  # git sha-1


def _package_text() -> str:
    parts: list[str] = []
    for name in REQUIRED_FILES:
        parts.append((EB32_DIR / name).read_text(encoding="utf-8"))
    return "\n".join(parts)


def _lines_declaring_forbidden_yes(text: str) -> list[str]:
    violations: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if any(marker in line for marker in PROHIBITION_MARKERS):
            continue
        for var in FORBIDDEN_STATUS_VARS:
            if re.search(rf"{re.escape(var)}\s*=\s*YES\b", line):
                violations.append(stripped)
                break
    return violations


@pytest.mark.parametrize("filename", REQUIRED_FILES)
def test_eb32_required_files_exist(filename: str) -> None:
    path = EB32_DIR / filename
    assert path.is_file(), f"missing {path.relative_to(REPO_ROOT)}"


def test_eb32_forbidden_status_gates_not_flipped_yes() -> None:
    text = _package_text()
    violations = _lines_declaring_forbidden_yes(text)
    assert not violations, "forbidden YES gates found:\n" + "\n".join(violations)


def test_eb32_candidate_not_approved_separation_present() -> None:
    text = _package_text()
    assert any(p.search(text) for p in SEPARATION_PATTERNS[:1]), (
        "expected candidate ≠ approved separation language"
    )


def test_eb32_template_not_frozen_separation_present() -> None:
    text = _package_text()
    assert any(p.search(text) for p in SEPARATION_PATTERNS[1:]), (
        "expected template ≠ frozen / Preparation ≠ Freeze separation language"
    )


def _lines_with_real_stamp_markers(text: str) -> list[str]:
    violations: list[str] = []
    for line in text.splitlines():
        if any(marker in line for marker in PROHIBITION_MARKERS):
            continue
        for pattern in REAL_STAMP_MARKERS:
            if pattern.search(line):
                violations.append(line.strip())
                break
    return violations


def test_eb32_no_real_stamp_artifact_markers() -> None:
    text = _package_text()
    violations = _lines_with_real_stamp_markers(text)
    assert not violations, "real stamp marker found:\n" + "\n".join(violations)


def test_eb32_no_real_git_sha_filled() -> None:
    text = _package_text()
    # Allow only if inside prohibition/example context — none expected in E-B32
    shas = SHA_LIKE.findall(text)
    assert not shas, f"unexpected real sha-like values: {shas}"


def test_eb32_primary_candidate_source_a_inherited() -> None:
    text = _package_text()
    assert "PRIMARY_CANDIDATE_SOURCE = A" in text


def test_eb32_preparation_designed_and_gates_remain_no() -> None:
    readme = (EB32_DIR / "README.md").read_text(encoding="utf-8")
    assert "E-B32_FREEZE_PREPARATION_DESIGNED   = YES" in readme
    assert "SOURCE_IDENTITY_COMPLETE            = NO" in readme
    assert "CAPTURE_MODE_FROZEN                 = NO" in readme
    assert "OWNER_AUTHORIZATION_ISSUED          = NO" in readme
