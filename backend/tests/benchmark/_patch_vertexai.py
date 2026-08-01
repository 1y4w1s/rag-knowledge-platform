"""Create vertexai stub for langchain_community"""
import langchain_community.chat_models as m
import os
stub = os.path.join(os.path.dirname(m.__file__), "vertexai.py")
if not os.path.exists(stub):
    with open(stub, "w", encoding="utf-8") as f:
        f.write('"""Stub"""\nclass ChatVertexAI:\n    def __init__(self, *a, **kw):\n        raise ImportError("vertexai not available")\n')
    print("Stub created:", stub)
else:
    print("Stub exists")
