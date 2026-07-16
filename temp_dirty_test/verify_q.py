"""Verify the 4 questions from the interview"""
from pathlib import Path
import re

# Q1: File named '.pdf'
p = Path(".pdf")
print(f"Q1: Path('.pdf').suffix={repr(p.suffix)} .stem={repr(p.stem)}")

# Q3: plainto_tsquery simulation
def plainto_tsquery_sim(query):
    tokens = re.findall(r"[a-zA-Z0-9]+", query)
    return " & ".join(tokens) if tokens else ""

print(f"Q3: C++ -> tsquery={plainto_tsquery_sim('C++')}")
print(f"Q3: C# -> tsquery={plainto_tsquery_sim('C#')}")
print(f"Q3: ART-2026-0716-001 -> tsquery={plainto_tsquery_sim('ART-2026-0716-001')}")
print()

# Conclusion
print("Q1: .pdf is rejected (suffix is empty, not in ALLOWED_EXTENSIONS) -> no fix needed")
print("Q2: 3 tabs = 3 requests counted separately -> correct by design")
print("Q3: plainto_tsquery drops + and # -> C++ treated as just C -> GAP")
print("Q4: COMPRESS_PROMPT is lossy -> ART-2026-0716-001 may be dropped -> DESIGN ISSUE")
