# Format-F1/F2/F3 · Plan — 格式扩展（xlsx / pptx / PDF 表格）

> **父计划**：`enterprise-master-plan.md` §6 Format-F · `eval-ops-plan.md` §2 M13  
> **状态**：待开工 · **WIP=1**（依次 F1 → F2 → F3）  
> **基线**：现有 4 格式 pdf/md/docx/txt + OCR ✅；docker compose build api 可运行  
> **风险**：低（不改造 chunker 核心逻辑；纯扩展）

---

## §0 做什么 / 不做什么

### 做

| # | 格式 | 后端引擎 | 输出 | 白名单 | 前端展示 | 测试 fixture |
|---|------|----------|------|--------|----------|-------------|
| **F1** | Excel `.xlsx` | `openpyxl` → 逐 sheet/表 → MD table chunk | `ParsedBlock(block_kind="table")` | 加 `.xlsx` | 文件类型大写展示 | `fixtures/golden_ledger.xlsx` |
| **F2** | PPT `.pptx` | `python-pptx` → 标题+正文+备注 → prose/table mixed | `ParsedBlock(block_kind="prose")` | 加 `.pptx` | 文件类型大写展示 | `fixtures/golden_deck.pptx` |
| **F3** | PDF 表格 | `pdfplumber.extract_tables()` → MD table chunk | `ParsedBlock(block_kind="table")` | **已有** `.pdf` | 失败态中文文案 | `fixtures/golden_table_report.pdf` |

### 不做

- 不改 chunker 核心逻辑（`structure_chunk()` 保持原样——`"table"` block 自动原子化）
- 不改 embedder / pipeline 流程
- 不改数据库模型 / migration
- 不改 AGENTS.md / PRD / TECH（完成后同步）
- **F5 多模态**（已确认不做）
- 前端加文件类型图标（保持纯文本大写展示）
- 不做大表拆分策略（P2，暂不触发）

---

## §1 改动手册

### F1 — Excel `.xlsx` 解析

#### 后端改动

| 文件 | 操作 | 内容 |
|------|------|------|
| `app/services/ingestion/parser.py` | **modify** | 新增 `parse_xlsx(path)` 函数 + `parse_document()` 分支 |
| `app/services/documents/upload.py` | **modify** | `ALLOWED_EXTENSIONS` 加 `".xlsx"` |
| `app/services/documents/filters.py` | **modify** | `ALLOWED_FILE_TYPES` 加 `"xlsx"` |
| `app/services/documents/preview.py` | **modify** | `_CONTENT_TYPES` 加 xlsx MIME |
| `requirements.txt` | **modify** | 加 `openpyxl` |

#### `parse_xlsx()` 设计

```python
def parse_xlsx(path: Path) -> list[ParsedBlock]:
    """Excel: 每 sheet 的每张表输出为 table block，sheet 名作 section_title。"""
    import openpyxl
    wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
    blocks: list[ParsedBlock] = []
    for sheet_name in wb.sheetnames:
        ws = wb[sheet_name]
        rows = list(ws.iter_rows(values_only=True))
        if not rows:
            continue
        # 转 MD 管道表格
        md_lines = _rows_to_markdown_table(rows)
        blocks.append(ParsedBlock(
            content="\n".join(md_lines),
            section_title=sheet_name,
            heading_path=sheet_name,
            block_kind="table",
        ))
    wb.close()
    return blocks
```

- `_rows_to_markdown_table(rows)`：将二维数组转为 MD 管道表格（首行为表头，后续为数据行，行间 `|` 分隔）
- **不处理合并单元格**（遇到 `None` 留空即可）
- 每张 sheet 的输出作为一个独立 table block（元数据表不需要散文 chunk）

#### 测试文件

| 文件 | 操作 | 内容 |
|------|------|------|
| `tests/fixtures/golden_ledger.xlsx` | **create** | 小台账：2 sheets（"部门预算"、"项目支出"），每表 3-5 行 |
| `tests/test_xlsx_ingestion.py` | **create** | 解析→入库→检索 Hit@? |

---

### F2 — PPT `.pptx` 解析

#### 后端改动

| 文件 | 操作 | 内容 |
|------|------|------|
| `app/services/ingestion/parser.py` | **modify** | 新增 `parse_pptx(path)` 函数 + `parse_document()` 分支 |
| `app/services/documents/upload.py` | **modify** | `ALLOWED_EXTENSIONS` 加 `".pptx"` |
| `app/services/documents/filters.py` | **modify** | `ALLOWED_FILE_TYPES` 加 `"pptx"` |
| `app/services/documents/preview.py` | **modify** | `_CONTENT_TYPES` 加 pptx MIME |
| `requirements.txt` | **modify** | 加 `python-pptx` |

#### `parse_pptx()` 设计

```python
def parse_pptx(path: Path) -> list[ParsedBlock]:
    """PPT: 每 slide = 1 prose block，标题作 section_title，备注追加到正文。"""
    from pptx import Presentation
    prs = Presentation(path)
    blocks: list[ParsedBlock] = []
    for i, slide in enumerate(prs.slides, start=1):
        title = ""
        body_parts: list[str] = []
        for shape in slide.shapes:
            if not shape.has_text_frame:
                continue
            text = shape.text_frame.text.strip()
            if not text:
                continue
            if shape == slide.shapes.title:
                title = text
            else:
                body_parts.append(text)
        # 备注
        if slide.has_notes_slide:
            notes = slide.notes_slide.notes_text_frame.text.strip()
            if notes:
                body_parts.append(f"【备注】{notes}")
        content = "\n\n".join(body_parts) if body_parts else ""
        heading_path = title or f"Slide {i}"
        blocks.append(ParsedBlock(
            content=content or heading_path,
            section_title=title or None,
            heading_path=heading_path,
            page_number=i,
            block_kind="prose",
        ))
    return blocks
```

- 每张 slide = 1 个 prose block（不视为 table）
- `page_number` = slide 编号
- 备注追到正文末尾
- 标题作为 `section_title`，空标题时用 `"Slide N"` 作 heading_path

#### 测试文件

| 文件 | 操作 | 内容 |
|------|------|------|
| `tests/fixtures/golden_deck.pptx` | **create** | 培训课件：3 slides（封面→正文→Q&A），含标题和正文 |
| `tests/test_pptx_ingestion.py` | **create** | 解析→入库→检索 Hit@? |

---

### F3 — PDF 表格解析

#### 后端改动

| 文件 | 操作 | 内容 |
|------|------|------|
| `app/services/ingestion/parser_pdf.py` | **modify** | 新增 `_parse_pdf_tables_only(path)` + 在 `parse_pdf()` 或 `parse_document()` 中集成 |
| `app/services/ingestion/parser.py` | **modify** | `parse_document()` 中 PDF 路径新增表提取通道 |
| `app/services/documents/upload.py` | **无需改** | `.pdf` 已在白名单 |
| `app/services/documents/filters.py` | **无需改** | `"pdf"` 已在白名单 |
| `app/services/documents/preview.py` | **无需改** | PDF 已有 MIME |
| `requirements.txt` | **无需改** | `pdfplumber` 已存在 |

#### `_parse_pdf_tables_only()` 设计

```python
def _parse_pdf_tables_only(path: Path, *, batch_pages: int = 10) -> list[ParsedBlock]:
    """从 PDF 中提取表格区块（用 pdfplumber.extract_tables()），每个表格输出为独立 table block。"""
    import pdfplumber
    blocks: list[ParsedBlock] = []
    with pdfplumber.open(path) as pdf:
        for page_num, page in enumerate(pdf.pages, start=1):
            tables = page.extract_tables()
            for table in tables:
                if not table or len(table) < 2:
                    continue
                md_lines = _table_to_markdown(table)
                blocks.append(ParsedBlock(
                    content="\n".join(md_lines),
                    page_number=page_num,
                    section_title=f"第{page_num}页表格",
                    heading_path=f"第{page_num}页表格",
                    block_kind="table",
                ))
    return blocks
```

**集成策略**：在 `parse_pdf()` 中，先用现有逻辑提取散文，然后追加 `_parse_pdf_tables_only()` 提取的表格 block（按页码排序合并）。

**失败态中文文案**：当 `extract_tables()` 在页面中未找到表格时不做特殊处理；如果整 PDF 无表格，`_parse_pdf_tables_only()` 返回空列表，不影响散文解析。

#### 测试文件

| 文件 | 操作 | 内容 |
|------|------|------|
| `tests/fixtures/golden_table_report.pdf` | **create** | 含 2-3 张表格的 PDF（用 python 生成） |
| `tests/test_pdf_table_ingestion.py` | **create** | 表提取→入库→检索 Hit@? |

---

## §2 执行顺序（WIP=1）

**三个格式依次独立开窗，每个窗完成后再开下一条。**

```
F1 (xlsx)  →  验收 ✅  →  F2 (pptx)  →  验收 ✅  →  F3 (PDF表)  →  验收 ✅
```

### F1 步骤

1. **加依赖**：`openpyxl` → `requirements.txt`
2. **写解析器**：`parser.py` 新增 `parse_xlsx()` + `_rows_to_markdown_table()`
3. **注册**：`parse_document()` 加 `ext == "xlsx"` 分支
4. **白名单**：`upload.py` `ALLOWED_EXTENSIONS` + `filters.py` `ALLOWED_FILE_TYPES` + `preview.py` `_CONTENT_TYPES`
5. **重建容器**：`docker compose build api && docker compose up -d api`
6. **上传测试**：手动上传 xlsx 文件验证入库
7. **写 pytest**：`test_xlsx_ingestion.py` + 生成 fixture `golden_ledger.xlsx`

### F2 步骤

1. **加依赖**：`python-pptx` → `requirements.txt`
2. **写解析器**：`parser.py` 新增 `parse_pptx()`
3. **注册**：`parse_document()` 加 `ext == "pptx"` 分支
4. **白名单**：同 F1 模式
5. **重建容器** + 上传测试 + **写 pytest**

### F3 步骤

1. **写解析器**：`parser_pdf.py` 新增 `_parse_pdf_tables_only()` + `_table_to_markdown()`
2. **集成**：修改 `parse_pdf()` 追加表格 block
3. **无需改白名单**（PDF 已有）
4. **重建容器** + 上传测试 + **写 pytest**

---

## §3 边界 & 异常

| 场景 | 处理 |
|------|------|
| **xlsx 空 sheet** | 跳过，不输出 block |
| **xlsx 无表头** | 首行作表头，后续全作数据行 |
| **xlsx 合并单元格** | 非首格返回 `None` → markdown 中留空 |
| **xlsx 超大文件** | `read_only=True` 流式读取 |
| **pptx 无标题** | `section_title=None`，`heading_path="Slide N"` |
| **pptx 空 slide** | 输出 slide 标题（或无标题时只输出 heading_path） |
| **pptx 无备注** | 跳过 notes 追加 |
| **pptx 图片/图表** | `has_text_frame=False` → 跳过 |
| **PDF 整篇无表格** | `extract_tables()` 返回空列表 → 表格 block 为空，不影响散文解析 |
| **PDF 表格跨页** | 两页各输出独立 table block（不合并跨页表） |
| **PDF 内含扫描页（有表格）** | 受 OCR 路径处理——F3 暂不解决扫描件表格提取 |

---

## §4 验收门禁

```
┌─────────────────────────────────────────────────────┐
│            ┏━━━┓  验收强门禁 — Format-F1/F2/F3     │
│            ┃   ┃                                    │
│            ┗━━━┛                                    │
│                                                     │
│  ▢ F1/F2/F3 各自：                                  │
│  ▢   解析器返回 list[ParsedBlock]，block_kind 准确  │
│  ▢   parse_document() 新分支生效                    │
│  ▢   upload/filter/preview 白名单已扩展 (F3 除外)   │
│  ▢   python -m pytest tests/test_*_ingestion.py -q 绿│
│  ▢   手动 upload + 对话引用验证（F1/F2 浏览器）     │
│  ▢   不改现有 4 格式解析逻辑                        │
│  ▢   不改 chunker / embedder / pipeline             │
│  ▢   不改 DB schema / migration                     │
│  ▢   不改 AGENTS.md / PRD / TECH（如有需要再同步）  │
│  ▢   docker compose build api 无报错                │
│                                                     │
│  回退：git checkout -- 改动的文件                    │
│                                                     │
│  ── F1 验收人签名：___________  日期：___________  ──│
│  ── F2 验收人签名：___________  日期：___________  ──│
│  ── F3 验收人签名：___________  日期：___________  ──│
└─────────────────────────────────────────────────────┘
```

---

## §5 回退指令

每个格式独立回退：
- **F1**：`parser.py` 删除 `parse_xlsx` 和 xlsx 分支；`upload.py`/`filters.py`/`preview.py` 删 xlsx 条目；`requirements.txt` 删 `openpyxl`；删 `test_xlsx_ingestion.py` 和 `golden_ledger.xlsx`
- **F2**：同 F1 模式
- **F3**：`parser_pdf.py` 删除 `_parse_pdf_tables_only`；`parser.py` 撤销 PDF 分支改动；删测试文件

---

## §6 依赖安装

两个新依赖（F1 + F2 各需一个）：

```txt
# requirements.txt 追加
openpyxl>=3.1.2
python-pptx>=1.0.0
```

`pdfplumber` 已在 `requirements.txt` 中（PDF 现有解析依赖），F3 不需要新增包。
