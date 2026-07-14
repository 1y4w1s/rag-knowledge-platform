"""Fix KB name to be unique."""
p = r"D:\MyPrograms\rag-knowledge-platform\backend\scripts\eval_golden.py"
with open(p, "r", encoding="utf-8") as f:
    c = f.read()
c = c.replace('"name": "Golden QA Eval"', '"name": f"Golden QA Eval {uuid.uuid4().hex[:8]}"')
with open(p, "w", encoding="utf-8") as f:
    f.write(c)
print("OK")
