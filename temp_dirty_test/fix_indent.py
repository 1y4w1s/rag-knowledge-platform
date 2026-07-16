"""Fix indentation in pipeline.py after adding _INGESTION_SEMAPHORE block"""
path = r"D:\MyPrograms\rag-knowledge-platform\backend\app\services\ingestion\pipeline.py"
with open(path, "r", encoding="utf-8") as f:
    lines = f.readlines()

# Find the function start
func_start = -1
session_start = -1
for i, line in enumerate(lines):
    if "async def process_document_ingestion" in line:
        func_start = i
    if func_start >= 0 and "async with SessionLocal() as db:" in line:
        session_start = i
        break

if session_start < 0:
    print("ERROR: Cannot find SessionLocal() line")
    exit(1)

# Indent everything between session_start+1 and matching dedent by 4 more spaces
# The session block continues until the indentation drops back to 8 spaces (the semaphore level)
# Current: lines after session_start have 8 spaces (should be 12)
fixed = 0
for i in range(session_start + 1, len(lines)):
    line = lines[i]
    if line.startswith("        ") and not line.startswith("            "):
        # Line at 8 spaces under session should be at 12 spaces
        if line.strip() and not line.startswith("        #") and "async with" not in line and "try:" not in line and "except" not in line:
            lines[i] = "    " + line
            fixed += 1
    
    # Stop when we hit a line that's at 4 spaces (outside the semaphore)
    if line.startswith("    ") and not line.startswith("        "):
        if line.strip():
            break

with open(path, "w", encoding="utf-8") as f:
    f.writelines(lines)
print(f"Fixed {fixed} lines")
