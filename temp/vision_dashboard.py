"""Analyze dashboard layout via Qwen-VL-Plus"""
import os, httpx, json

API_KEY = ""
env_path = r"D:\MyPrograms\rag-knowledge-platform\.env"
for line in open(env_path, encoding="utf-8"):
    if line.startswith("TONGYI_API_KEY="):
        API_KEY = line.strip().split("=", 1)[1].strip().strip("\"'")
        break

layout_text = """You are a professional UI/UX designer reviewing a dashboard layout. Below is the actual rendered page data with exact X,Y coordinates of every element. The viewport is 1707x769px. Evaluate the visual layout, space utilization, and hierarchy.

=== SECTION 1: KEY METRICS RIBBON (y=163) ===
Three KPI cards in a horizontal row:
- [x=452,y=163] "资料库" / "scope 可见" (link to /knowledge-bases)
- [x=736,y=163] "已入库文件" / "可提问 9" (link to KB)
- [x=1020,y=163] "近 7 日提问" / "含引用溯源" (link to /ask)
Each card spans about 280px wide with 40px gap between them.
Total ribbon width ~960px, centered in 1180px container.

=== SECTION 2: INGESTION PIPELINE (y=261~537) ===
Title "入库态势 Ingestion Pipeline" at x=357,y=261

The panel is split into left (1.7fr) and right (1fr):
LEFT side (x~367-560):
- Header "文档流转" + badge "实时四态"
- Pipeline bar: 4 colored segments (排队1 / 处理中0 / 已完成9 / 失败4), h=46px
- Legend row: 4 color dots with labels
- 3 mini metrics at bottom: "69.23% 成功率" / "0.4s 平均耗时" / "切片数" (serif font, large)

RIGHT side (x~1074-1397):
- Header "存储健康" + badge "Plan-3E"
- 4 key-value rows: "近7日重试 0✓" / "清理失败累计 0✓" / "待处理队列 1" / "最近活跃库 xxx"
- Each row: label on left, value on right, border-bottom separation
- Total height of all rows: about 200px

=== SECTION 3: RAG PROOF & LATENCY (y=610~878) ===
Title "可信与性能 RAG Proof & Latency" at x=366,y=610
Two-column grid:
LEFT card "检索可证明性·Golden Hit@3" centered at x=593:
- 100% score in large 46px green serif font
- Gauge/progress bar (7px height)
- Note text below

RIGHT card "检索性能" centered at x=933:
- 3 metric rows: "平均检索延迟 664ms" / "样本数" / "P95延迟"
- Each key-value pair in a table format

=== SECTION 4: ACTIVITY (y=964~1204) ===
Title "活跃度 Activity" at x=349,y=964
Two-column:
LEFT: "近7日提问趋势" with 7-day calendar heatmap at x=376-902
- Each day button labeled with date and count
- "7日合计 1次" at x=907,y=1201

RIGHT: "知识构成" / "格式分布" at x=1025,y=1024
- Format distribution bars
- "文档总数" / "切片颗粒" at y=1204

=== SECTION 5: RECENT ACTIVITY (y=1275~1651) ===
Title "最近对话与动态 Threads & Audit" at x=383,y=1275
Two-column:
LEFT: "最近对话" - 1 conversation entry
RIGHT: "操作动态" - 5 audit log entries

=== QUESTIONS ===
1. Analyze the spatial balance: is the left-right split in Section 2 (1.7fr vs 1fr) visually balanced?
2. Section 3's right card only has 3 data points - does it look sparse compared to the left card?
3. How is the overall vertical rhythm between the 5 sections?
4. Any issues with the KPI ribbon at the top? Are the 3 cards balanced?
5. Would you recommend any layout ratio changes?
6. Specific spacing or alignment issues you notice?
"""

headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
payload = {
    "model": "qwen-vl-plus",
    "messages": [{"role": "user", "content": [{"type": "text", "text": layout_text}]}],
    "max_tokens": 2000,
}

resp = httpx.post("https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
    headers=headers, json=payload, timeout=60)
result = resp.json()
if "choices" in result:
    print(result["choices"][0]["message"]["content"])
else:
    print("ERROR:", json.dumps(result, indent=2, ensure_ascii=False))
