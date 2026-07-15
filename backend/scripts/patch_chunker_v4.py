"""Remove duplicate SOFT_MAX_MARGIN and fix line 37."""
p = r"D:\MyPrograms\rag-knowledge-platform\backend\app\services\ingestion\chunker.py"
with open(p, "r", encoding="utf-8") as f:
    text = f.read()

# Remove duplicate SOFT_MAX_MARGIN and comment
import re
# The pattern is: the variable + comment + duplicate variable
text = re.sub(
    r"SOFT_MAX_MARGIN = 0\.2\n\n# .+\nSOFT_MAX_MARGIN = 0\.2\n",
    "SOFT_MAX_MARGIN = 0.2\n",
    text,
)

# Fix line 37 style: both _leaf_chunks_for_prose and _split_long_text now use SENTENCE_END
# _leaf_chunks_for_prose's version at line ~36
old = '    sentences = re.split(r"(?<=[\u4e00-\u9fff\uff01\uff1f!?\uff1b;])", text.strip())'
# This might not match due to literal vs escape; try literal match
lines = text.split("\n")
for i, line in enumerate(lines):
    stripped = line.strip()
    if stripped.startswith('sentences = re.split') and 'SENTENCE_END' not in stripped:
        indent = " " * (len(line) - len(line.lstrip()))
        lines[i] = f"{indent}sentences = re.split(SENTENCE_END, text.strip())"

text = "\n".join(lines)

with open(p, "w", encoding="utf-8") as f:
    f.write(text)
print("OK")
