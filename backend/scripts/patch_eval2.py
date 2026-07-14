"""Patch eval_golden_real.py to run Phase 2 with RUN_GENERATION=1."""
p = r"D:\MyPrograms\rag-knowledge-platform\backend\scripts\eval_golden_real.py"
with open(p, "r", encoding="utf-8") as f:
    c = f.read()

old = """    print("  [auto] Skipping Phase 2. Set RUN_GENERATION=1 to enable.")"""
new = """    import os
    if os.environ.get("RUN_GENERATION") == "1":
        await run_generation_eval(kb_id, results)
    else:
        print("  [skip] Set RUN_GENERATION=1 to enable generation eval")"""

c = c.replace(old, new)
with open(p, "w", encoding="utf-8") as f:
    f.write(c)
print("OK")
