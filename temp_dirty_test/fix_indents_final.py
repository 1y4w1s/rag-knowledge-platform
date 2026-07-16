"""Find and fix all indentation bugs in pipeline.py"""
import re

path = r"D:\MyPrograms\rag-knowledge-platform\backend\app\services\ingestion\pipeline.py"
with open(path, "r", encoding="utf-8") as f:
    lines = f.readlines()

# Pattern: an `if X:` line followed by a non-empty line at the SAME indentation
fix_count = 0
fixes = []
for i, line in enumerate(lines):
    stripped = line.strip()
    if not stripped:
        continue
    
    # Check if this line ends with : (block starter: if/for/except/try/with/elif/else)
    if stripped.endswith(":") and not stripped.startswith("#"):
        j = i + 1
        while j < len(lines) and lines[j].strip() == "":
            j += 1
        if j < len(lines):
            line_indent = len(line) - len(line.lstrip())
            next_indent = len(lines[j]) - len(lines[j].lstrip())
            if next_indent == line_indent and lines[j].strip() and not lines[j].strip().startswith("#"):
                fix_count += 1
                lines[j] = "    " + lines[j]
                print(f"  Line {i+1} '{stripped}' => Line {j+1} '{lines[j].strip()}' indented")

with open(path, "w", encoding="utf-8") as f:
    f.writelines(lines)

print(f"\nFixed {fix_count} indentation errors")
