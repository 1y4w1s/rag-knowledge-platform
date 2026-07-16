"""Analyze dashboard layout via LM Studio"""
import httpx

layout = """Dashboard layout (viewport 1707x825px):

SECTION 1 - KPI RIBBON (y=163):
Three cards: KB count, Files processed(9 askable), Questions this week

SECTION 2 - INGESTION PIPELINE (y=261-570):
Title: Ingestion Pipeline
Left 1.2fr: Pipeline bar (queued1/processing0/completed9/failed4) + legend + 3 mini-metrics
Right 1fr (x=979-1397): Storage Health + 4 rows (retry7d 0/cleanFailure 0/queue 1/activeKb)

SECTION 3 - RAG PROOF (y=634-825):
Title: RAG Proof & Latency
Grid 2 cols: Left=Golden Hit@3 (100%+gauge), Right=Retrieval latency(664ms/samples)

Analyze visual balance between left/right columns in Section 2.
Is the 1.2fr:1fr ratio appropriate? Is right column still sparse?
Provide 2-3 specific measurable improvements."""

try:
    r = httpx.post("http://localhost:1234/v1/chat/completions", json={
        "model": "google/gemma-4-e4b",
        "messages": [
            {"role": "system", "content": "You are a UI/UX designer. Provide concise, data-driven feedback."},
            {"role": "user", "content": layout}
        ],
        "max_tokens": 2000,
    }, timeout=120)
    data = r.json()
    content = data["choices"][0]["message"]["content"] or "(模型思考中，content为空)"
    print(content)
except Exception as e:
    print(f"Error: {e}")
