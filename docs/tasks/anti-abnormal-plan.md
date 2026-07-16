# 抗异常改进计划

## 优先级评估矩阵

| # | 问题 | 影响面 | 修复难度 | 优先级 |
|---|------|--------|---------|--------|
| P0‑1 | **parse_txt Unicode 正则写死** → 所有中文文本被丢弃 | 核心功能损坏 | 1 行 | **🔴 CRITICAL** |
| P0‑2 | **Markdown 预览 XSS** → 任意 JS 执行 | 安全漏洞 | 低（加 dompurify） | **🔴 CRITICAL** |
| P0‑3 | **parse_txt 死代码** → 段落分割逻辑未生效 | 核心功能损坏 | 删多余代码 | **🔴 CRITICAL** |
| P1‑1 | OCR 路径未捕获加密 PDF | 500 报错 | 1 行 catch | 🟡 HIGH |
| P1‑2 | 零宽/不可见 Unicode 未过滤 | 存储浪费 | 2 行 regex | 🟡 HIGH |
| P1‑3 | Prompt 注入无防护 | LLM 被操纵 | 加 system prompt | 🟡 HIGH |
| P1‑4 | display_name 特殊字符未清理 | 响应头注入 | 2 行 strip | 🟡 HIGH |
| P2‑1 | 纯符号/emoji 提问浪费额度 | API 浪费 | 3 行 | 🟢 MED |
| P2‑2 | 提问限流 30/h 偏紧（已有） | 误伤正常用户 | 不改（已有配置） | ⏭️ SKIP |

## 各文件改动

### P0‑1+P0‑3: `backend/app/services/ingestion/parser.py`
- 修复正则：`r'[\\u4e00-\\u9fff\\w]'` → `r'[\u4e00-\u9fff\w]'`
- 删除第 55 行 `return blocks` 之后的全部死代码
- 在段落分割中保留原有的 heading 追踪和 table 检测逻辑

### P0‑2: `frontend/` 
- `npm install dompurify @types/dompurify`
- `DocumentPreviewViewer.tsx` — `MarkdownRenderer` 中 `marked.parse()` 后加 `DOMPurify.sanitize()`

### P1‑1: `backend/app/services/ingestion/parser_pdf.py`
- OCR 路径 `parse_pdf_ocr` / `ocr_pdf_pages` 加 try/except PDFEncryptionError

### P1‑2: `backend/app/services/ingestion/parser.py`
- `_read_text_with_fallback()` 后加一步：用 regex 移除零宽字符

### P1‑3: `backend/app/services/rag/`
- 在发给 LLM 的 system prompt 末尾追加注入防护指令

### P1‑4: `backend/app/services/documents/upload.py`
- `display_name` 入库前 strip 控制字符和空字节

### P2‑1: `frontend/src/pages/AskPage.tsx` 或 `ChatPage.tsx`
- 提交前检测提问是否仅含 emoji/符号，拦截并给提示

## 自审

### 风险评估
- P0‑1 修复后所有之前的 .txt 测试数据需要重新 ingestion 吗？**是**，但只有新上传的文档会走新代码，历史数据已入库的不受影响。
- P0‑2 加 DOMPurify 后 XSS 防护 ✅ 不会破坏正常 Markdown 渲染。
- P1‑2 零宽字符过滤在 encoding fallback 之后做，不会干扰正常文本 ✅
- P1‑3 prompt 注入防护：加在 system prompt 尾巴上，不会影响 RAG 的检索召回 ✅
- 无破坏性改动，不改 schema、不改 API 签名、不改路由。

### 屎山风险检查
- ✅ 不新增外部依赖（除了 dompurify — 标准前端安全库）
- ✅ 每个文件改动量 ≤20 行
- ✅ 不引入新抽象层
- ✅ 不改测试套件

## 实施顺序
1. P0‑1 + P0‑3（parse_txt 修复）
2. P0‑2（XSS 防护）
3. P1‑1（加密 PDF OCR）
4. P1‑2（零宽字符）
5. P1‑3（prompt 注入）
6. P1‑4（display_name）
7. P2‑1（纯符号提问拦截）
