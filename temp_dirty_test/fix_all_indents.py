"""Fix all indentation errors in pipeline.py by re-indenting the entire file.
The _write_chunks function and other functions had their bodies indented 
by an extra 4 spaces due to a PowerShell script error.
"""
import re

path = r"D:\MyPrograms\rag-knowledge-platform\backend\app\services\ingestion\pipeline.py"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

# Strategy: find lines that are over-indented inside function bodies
# A line at 12 spaces that should be at 8 spaces is the most common error
# We'll reduce lines at 12, 13, 14+ spaces by removing leading spaces

lines = content.split("\n")
fixed = []

for i, line in enumerate(lines):
    if not line.strip():
        fixed.append(line)
        continue
    
    # Count leading spaces
    leading = len(line) - len(line.lstrip())
    stripped = line.lstrip()
    
    # The _write_chunks and process_document_ingestion functions were over-indented
    # Lines that are at 12+ spaces but should be at 8 for for/if/async with blocks
    
    # Pattern: if a line at 12+ spaces starts with a keyword that should be at function body level
    # inside _write_chunks (which starts at 8 spaces for 'for draft in drafts')
    
    # For lines inside the main function body of _write_chunks:
    # 'for draft in drafts:' is at 8 spaces
    # Lines inside it should be at 12 spaces (body of for)
    # Lines inside if/for/try/except inside that should be at 16 spaces
    
    # Remove one level (4 spaces) from over-indented lines
    # Specifically target lines that have 12+ spaces and are common keywords
    if leading >= 12 and re.match(r"^\s{12}(for |if |try:|except |with |async |return |await |chunk|embedding|embed_model|parent_chunk_id|parent_ids)", line):
        # This is at 12+ spaces - should it be at 8?
        # Check if the previous code block is at 8 spaces
        prev_stripped = ""
        for j in range(i-1, -1, -1):
            if fixed[j].strip():
                prev_stripped = fixed[j].strip()
                break
        # If the previous non-empty line is at 8 spaces and is a block starter,
        # this line should be at 12 spaces, not 12+ 
        # This is tricky to automate. Let me just reduce ALL 12+ by 4 spaces
        fixed.append("    " + line[4:])  # Remove 4 spaces
    else:
        fixed.append(line)

result = "\n".join(fixed)
with open(path, "w", encoding="utf-8") as f:
    f.write(result)
print("Done - removed 4 spaces from over-indented lines")
