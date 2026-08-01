"""NW-36 / M13：格式样例包可被 parse_document 抽出验收码（不测检索/OCR）。"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.services.ingestion.parser import parse_document

_FIXTURES = Path(__file__).resolve().parent / "fixtures" / "m13_format"

_CASES = (
    ("m13_plain.txt", "txt", "M13-NEEDLE-TXT-8841"),
    ("m13_notes.md", "md", "M13-NEEDLE-MD-8842"),
    ("m13_handbook.docx", "docx", "M13-NEEDLE-DOCX-8843"),
    ("m13_text_layer.pdf", "pdf", "M13-NEEDLE-PDF-8844"),
    ("m13_ledger.xlsx", "xlsx", "M13-NEEDLE-XLSX-8845"),
    ("m13_deck.pptx", "pptx", "M13-NEEDLE-PPTX-8846"),
)


@pytest.mark.parametrize("filename,file_type,needle", _CASES, ids=[c[1] for c in _CASES])
def test_m13_fixture_parse_contains_needle(
    filename: str, file_type: str, needle: str
) -> None:
    path = _FIXTURES / filename
    assert path.is_file(), f"missing fixture {path}; run scripts/gen_m13_format_fixtures.py"
    blocks = parse_document(path, file_type)
    joined = "\n".join(b.content for b in blocks)
    assert needle in joined, f"{file_type}: needle not in parse output"
