# 睿阁 — Ingestion 入库管道流程

> 交接对象：后端开发者
> 更新日期：2026-07-17

---

## 1. 整体流程

```
用户上传文件 → upload_documents()
    │
    ▼
[validate_file_list] → 扩展名校验 + 内容去重 + 同名检测
    │
    ▼
[build_document_record] → 写磁盘文件 → 创建 Document 记录
    │
    ├── 同名文件 → 保存 DocumentVersion（旧版本）→ 更新 Document
    └── 新文件   → 创建新 Document
    │
    ▼
[ingest_document_task.delay(doc_id)]  ← Celery 异步（redis broker）
 或 process_document_ingestion(doc_id)  ← 本地开发（BackgroundTasks）
    │
    ▼
───────────────── Celery Worker ─────────────────
    │
    ▼
[process_document_ingestion]  ← 入口函数（pipeline.py）
    │
    ├── 1. 加载 Document → 校验状态
    ├── 2. 标记 processing_started_at
    ├── 3. 选择解析器
    │       ├── PDF 扫描件 → OCR（pypdfium2 → 通义千问 OCR API）
    │       ├── PDF 文本   → pdfplumber（表格检测 + 文本提取）
    │       ├── DOCX       → python-docx
    │       ├── XLSX       → openpyxl
    │       ├── PPTX       → python-pptx
    │       └── TXT/MD     → 直接读取
    ├── 4. parse_document() → [ParsedBlock]
    ├── 5. structure_chunk() → [ChunkDraft]（结构优先切片）
    ├── 6. embed_texts() → vector[1536]（通义 text-embedding-v2）
    ├── 7. write_chunks() → document_chunks 表 + pgvector
    ├── 8. 标记 completed + chunk_count
    └── 9. _trigger_webhooks() → POST 回调
```

---

## 2. 关键函数

### `process_document_ingestion(document_id: UUID) -> None`
- **位置**: `app/services/ingestion/pipeline.py:259`
- **入参**: document_id（UUID）
- **返回**: None（所有副作用通过独立 `SessionLocal()` 提交）
- **异常**: 全部捕获 → `_mark_failed()` → 中文错误信息 + 状态=failed

### `upload_documents(db, current_user, kb_id, files, ...) -> list[DocumentResponse]`
- **位置**: `app/services/documents/upload.py:92`
- **功能**: 上传文档入口。同名文件→创建 DocumentVersion 版本记录→复用 doc_id

---

## 3. 版本管理

当上传同名文件时（`_assert_filename_available()` 返回已存在 doc_id）:

```
1. 保存旧版本记录 → DocumentVersion(version_number=current_version, storage_path=...)
2. 审计日志 → action="document.version.create"
3. 更新 Document → current_version += 1, storage_path=新文件, status=queued
4. 触发 ingestion（同一 doc_id，新内容）
```

---

## 4. 并发控制

| 环境 | 机制 | 说明 |
|------|------|------|
| 生产（Docker） | Celery worker `--concurrency=5` | Redis broker，最多 5 个并发任务 |
| 本地/测试 | `background_tasks.add_task()` | 同步执行，无并发限制 |

选择逻辑：
```python
if settings.celery_task_always_eager_local:
    background_tasks.add_task(process_document_ingestion, doc.id)
else:
    ingest_document_task.delay(str(doc.id))
```

---

## 5. 解析器分支

| 文件类型 | 解析器 | 特殊处理 |
|---------|--------|---------|
| `.pdf` + 扫描件 | OCR（pypdfium2 → 通义 OCR API） | 页数上限：ocr_max_pages=30 |
| `.pdf` + 文本 | pdfplumber | 表格检测（`table_detection.py`） |
| `.docx` | python-docx | 标题层级 → heading_path |
| `.xlsx` | openpyxl | 每 sheet 作为一个独立表格 chunk |
| `.pptx` | python-pptx | 每 slide 文本拼接 |
| `.txt` / `.md` | 直接读取 | 纯文本 |
| `.png` / `.jpg` / `.jpeg` | 不支持（白名单有但无解析器） | 会进入 OCR 分支 |

---

## 6. 切片策略（structure_chunk）

**文件**: `app/services/ingestion/chunker.py`

| 配置 | 默认值 | 说明 |
|------|--------|------|
| `max_chars` | 1000 | 单 chunk 上限字符数 |
| `soft_max_margin` | 0.2 | 软上限：1000 * 1.2 = 1200 字符 |
| `min_chars` | 80 | 小于此值的相邻 chunk 合并 |
| `overlap_max_chars` | 150 | 交叉重叠字符数 |
| `SENTENCE_END` | `[。！？!?；;]` | 中文 + 英文句子分隔符 |

**切片规则**：
- 按章节标题分块（`heading_path`）
- 超过 `max_chars + soft_max_margin` 的块按句子分割
- 表格内容独立为 `chunk_kind="table"` 的块
- Parent-Child：父子块关联（`parent_chunk_id`）

---

## 7. Webhook 触发

Ingestion 完成后自动触发 kb_id 关联的 webhook：

```
条件: Webhook.is_active = True AND events LIKE '%document.completed%'
请求: POST {url}
Header:
  X-Webhook-Event: document.completed
  X-Webhook-Signature: HMAC-SHA256(body, secret)
Body:
  {
    "event": "document.completed",
    "kb_id": "...",
    "document_id": "...",
    "filename": "...",
    "status": "completed",
    "chunk_count": 11,
    "timestamp": "2026-07-17T12:00:00Z"
  }
重试: 3 次，指数退避（1s, 2s, 4s）
```

---

## 8. 异常处理

| 异常 | 用户可见错误 | 状态 |
|------|-------------|------|
| 扫描件 OCR 失败 | "OCR 处理失败，请确认文件为清晰扫描件或稍后重试" | failed |
| OCR 服务未启用 | "OCR 服务未启用" | failed |
| 不支持的文件类型 | "不支持的文件类型" | failed |
| 文件不存在 | "文件不存在" | failed |
| Embedding 5xx | 降级为 FTS-only（标记 completed）| completed |
| 其他异常 | "文档处理失败，请稍后重试" | failed |
