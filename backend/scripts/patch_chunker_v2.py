"""Patch chunker.py with improved sentence splitting and soft max chunk size."""
p = r"D:\MyPrograms\rag-knowledge-platform\backend\app\services\ingestion\chunker.py"
with open(p, "r", encoding="utf-8") as f:
    text = f.read()

# 1. Update SENTENCE_END to handle English period + space
text = text.replace(
    'SENTENCE_END = re.compile(r"\u3000-\u9fa5\uff01\uff1f!?\uff1b;]")',
    'SENTENCE_END = re.compile(r"[\u3000-\u9fa5\uff01\uff1f!?\uff1b;]|(?<=\\.) (?=[A-Z0-9])")',
)
# The file uses literal Chinese chars, the above may not match; fallback: direct string
text = text.replace(
    'SENTENCE_END = re.compile(r"[',
    'SOFT_MAX_MARGIN = 0.2\n\nSENTENCE_END = re.compile(r"[',
)

# 3. Add SOFT_MAX_MARGIN after the existing SENTENCE_END line
# Actually let me use a simpler approach - add after re import
text = text.replace(
    "import re\n\n\nfrom app",
    "import re\n\nSOFT_MAX_MARGIN = 0.2\n\n\nfrom app",
)

# 4. Fix _split_long_text to use SENTENCE_END and soft_max
old_split = '    sentences = re.split(r"(?<=[\u3000-\u9fa5\uff01\uff1f!?\uff1b;])", text.strip())'
text = text.replace(
    old_split,
    "    soft_max = int(max_chars * (1 + SOFT_MAX_MARGIN))\n    sentences = re.split(SENTENCE_END, text.strip())",
)

# 5. Fix the max_chars check
text = text.replace(
    "if len(current) + len(sentence) <= max_chars:",
    "if len(current) + len(sentence) <= soft_max:",
)

with open(p, "w", encoding="utf-8") as f:
    f.write(text)
print("OK")
