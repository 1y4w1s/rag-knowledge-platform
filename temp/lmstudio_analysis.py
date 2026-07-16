"""Analyze dashboard layout via LM Studio vision model"""
import httpx, json

layout_text = """You are a professional UI/UX designer reviewing a dashboard. The viewport is 1707x769px.

=== SECTION 1: KEY METRICS RIBBON ===
Three KPI cards in a row (each ~280px, gap 40px):
- "资料库 / scope 可见"
- "已入库文件 / 可提问 9"
- "近 7 日提问 / 含引用溯源"

=== SECTION 2: INGESTION PIPELINE ===
Title "入库态势 Ingestion Pipeline"
Two columns split 1.2fr | 1px | 1fr:
LEFT: Pipeline bar (排队1/处理中0/已完成9/失败4) + 3 mini metrics (成功率69.23%, 耗时0.4s, 切片数)
RIGHT: 4 key-value rows (近7日重试0✓/清理失败累计0✓/待处理队列1/最近活跃库xxx)

=== SECTION 3: RAG PROOF & LATENCY === 
Title "可信与性能 RAG Proof & Latency"
Two equal columns:
LEFT: "检索可证明性·Golden Hit@3" with large 100% score + progress bar
RIGHT: "检索性能" with 3 metrics (平均检索延迟664ms/样本数/P95延迟)

=== SECTION 4: ACTIVITY ===
Title "活跃度 Activity"
LEFT: 7-day calendar heatmap with daily click counts
RIGHT: Format distribution bars + doc/chunk counts

=== SECTION 5: RECENT ACTIVITY ===
Title "最近对话与动态 Threads & Audit"
LEFT: Recent conversations list
RIGHT: Audit log entries

Analyze: (1) spatial balance between left/right columns, (2) visual hierarchy, (3) any cards that look sparse, (4) specific improvement suggestions.
"""

payload = {
    "model": "qwen/qwen3.5-9b",
    "messages": [
        {"role": "system", "content": "You are a professional UI/UX designer. Provide concise, actionable feedback."},
        {"role": "user", "content": layout_text}
    ],
    "max_tokens": 1500,
}

try:
    resp = httpx.post("http://localhost:1234/v1/chat/completions", json=payload, timeout=60)
    result = resp.json()
    print(result["choices"][0]["message"]["content"])
except Exception as e:
    print(f"Error: {e}")
