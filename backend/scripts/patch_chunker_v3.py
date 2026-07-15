"""Fix chunker.py: add SOFT_MAX_MARGIN, use SENTENCE_END in splitter, soft max limit."""
p = r"D:\MyPrograms\rag-knowledge-platform\backend\app\services\ingestion\chunker.py"
with open(p, "r", encoding="utf-8") as f:
    lines = f.readlines()

result = []
in_function = False
for i, line in enumerate(lines):
    stripped = line.strip()
    # Add SOFT_MAX_MARGIN after SENTENCE_END line
    if stripped.startswith("SENTENCE_END = re.compile") and not any("SOFT_MAX" in l for l in lines[max(0,i-2):i+2]):
        result.append(line)
        result.append("SOFT_MAX_MARGIN = 0.2\n")
        continue
    
    # Fix _split_long_text
    if 'def _split_long_text' in stripped:
        in_function = True
    if in_function and 'return parts' in stripped:
        in_function = False
    
    if in_function and 'sentences = re.split' in stripped and 'SENTENCE_END' not in stripped:
        # Replace inline regex with SENTENCE_END
        indent = " " * (len(line) - len(line.lstrip()))
        result.append(f"{indent}soft_max = int(max_chars * (1 + SOFT_MAX_MARGIN))\n")
        result.append(f"{indent}sentences = re.split(SENTENCE_END, text.strip())\n")
        continue
    
    if in_function and 'if len(current) + len(sentence) <= max_chars:' in stripped:
        indent = " " * (len(line) - len(line.lstrip()))
        result.append(f"{indent}if len(current) + len(sentence) <= soft_max:\n")
        continue
    
    # Fix _leaf_chunks_for_prose (the other split location at line 36 area)
    if '_leaf_chunks_for_prose' in stripped:
        in_function = True
    
    result.append(line)

with open(p, "w", encoding="utf-8") as f:
    f.writelines(result)
print("OK")
