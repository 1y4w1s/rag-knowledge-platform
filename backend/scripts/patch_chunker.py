"""Patch chunker.py: better sentence splitting, soft max chunk size."""
p = r"D:\MyPrograms\rag-knowledge-platform\backend\app\services\ingestion\chunker.py"
with open(p, "r", encoding="utf-8") as f:
    c = f.read()

# 1. Fix SENTENCE_END to handle English period + space
old_re = 'SENTENCE_END = re.compile(r"[\u3000-\u9fa5\uff01\uff1f!?\uff1b;]")'
# The file has literal CJK chars, let me find the exact line
import re as re_mod
match = re_mod.search(r'SENTENCE_END = re\.compile\(r"[^"]+"\)', c)
if match:
    old_line = match.group()
    # Keep the original content but add English period support
    new_line = old_line.replace('")', r'|(?<=\\.) (?=[A-Z0-9])")')
    c = c.replace(old_line, new_line)

# 2. Add SOFT_MAX_MARGIN after the SENTENCE_END line
c = c.replace(new_line, new_line + "\n\nSOFT_MAX_MARGIN = 0.2")

# 3. Update _split_long_text
old_split = "    sentences = re.split(r\"(?<=[\u3000-\u9fa5\uff01\uff1f!?\uff1b;])\", text.strip())"
# Harder: find the actual split line
split_match = re_mod.search(r"    sentences = re\.split\(r\"[^\"]+\", text\.strip\(\)\)", c)
if split_match:
    old = split_match.group()
    new = "    soft_max = int(max_chars * (1 + SOFT_MAX_MARGIN))\n    " + old.replace('re.split(r"', 're.split(SENTENCE_END, "')
    c = c.replace(old, new)

# 4. Update the max_chars check in the loop
c = c.replace("if len(current) + len(sentence) <= max_chars:", "if len(current) + len(sentence) <= soft_max:")

with open(p, "w", encoding="utf-8") as f:
    f.write(c)
print("OK")
