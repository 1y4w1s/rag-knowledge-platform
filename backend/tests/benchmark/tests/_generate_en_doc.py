"""用 DeepSeek 生成 Python 语言 Wikipedia 文章"""
import asyncio, os
from pathlib import Path

os.environ["RAG_RATE_LIMIT_MODE"] = "bypass"
TARGET = Path("/app/tests/fixtures") / "python_language.md"

async def main():
    from app.services.rag.generation import stream_deepseek_tokens
    prompt = """Generate the complete text of a Wikipedia article about "Python (programming language)" in English. Include:
- History (created by Guido van Rossum, first released 1991)
- Design philosophy (PEP 20, Zen of Python)
- Features (dynamic typing, garbage collection, etc.)
- Versions (Python 2 vs 3, current stable 3.12, 3.8 walrus operator)
- Uses (web development, data science, AI)
- Community (PSF, PyPI, BDFL/Steering Council)
- Syntax examples (brief, 2-3 lines)

Format as proper Wikipedia article with sections. About 3000-4000 words."""
    
    parts = []
    async for token in stream_deepseek_tokens([{"role": "user", "content": prompt}]):
        parts.append(token)
    content = "".join(parts)
    TARGET.write_text(f"# Python (programming language)\n\n{content}", encoding="utf-8")
    print(f"Generated: {len(content)} chars")

asyncio.run(main())
