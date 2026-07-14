# Format-F4 · 扫描 PDF OCR 入库 · Plan

> **状态**：✅ **整波关单 §6**（2026-07-08）· F4-1～F4-5 ✅ · 用户拍板做 OCR、**不用多模态 API**  
> **Research**：[`format-f4-ocr-research.md`](format-f4-ocr-research.md)  
> **父地图**：[`enterprise-master-plan.md`](enterprise-master-plan.md) §6 **F4**  
> **Implement**：确认当条原子任务后 **单开 I 窗** · **WIP=1** · 不与 G2-0.x / M10 同窗

---

## §0 做 & 不做

| 做 | 不做 |
|----|------|
| 扫描 PDF 检测 → OCR → `ParsedBlock`（带 `page_number`）→ 现有 chunk/embed | **F5** 多模态 / vision LLM / 图 chunk |
| 单文件 OCR **页数上限**（默认 30）· 超限 **failed + 中文文案** | 对话输入框贴图 OCR |
| 环境开关 `OCR_ENABLED`（默认 1；0 时保持「不支持扫描件」） | 表格结构 OCR、手写体、自动纠错 |
| pytest + 扫描 PDF fixture · 文字层 PDF 回归 | 改 upload 白名单加 PNG/JPG（→ **F4-6 backlog**） |
| 同步 TECH §4.2 · PRD §6.2 · cockpit · eval M13 矩阵一行 | F1/F2/F3 xlsx/pptx/表格 · Agent/G2 thread |
| Docker/requirements **可选 extra** `ocr` 组 | 强制所有环境装 Paddle（H7 可选） |

---

## §1 一句话（页面操作版）

**做完后**：Admin 在资料库上传 **扫描版 PDF**（以前会失败）→ 列表显示「整理中」→ 成功后 **completed** → 进对话问里面内容 → 回答带 **文档名 + 第 N 页** 引用；纯图片文件仍不能传（除非以后做 F4-6）。

---

## §2 名词对照

| 名词 | 人话 |
|------|------|
| OCR | 把扫描页「认字」变成可搜索的纯文本 |
| 扫描 PDF | PDF 里是照片/扫描图，**不能**鼠标选中复制文字 |
| `ParsedBlock` | 解析后的一小段文字 + 页码，交给切片器 |
| PaddleOCR | 本地开源认字引擎，中文相对准 |
| `OCR_ENABLED` | 服务器环境变量：0=关闭 OCR，扫描件仍失败 |

---

## §3 默认拍板（Research H1～H7）

| 假设 | 默认 | 状态 |
|------|------|------|
| H1 引擎 | PaddleOCR + pdf2image | 🟡 I 窗开工前可改 Tesseract |
| H2 格式 | **仅扫描 PDF** | ✅ |
| H3 检测 | 前 3 页累计字符 &lt; 50 → OCR | ✅ |
| H4 页数上限 | 30 页 | 🟡 |
| H5 与 F5 | 完全分离，不做多模态 | ✅ |
| H6 失败 | failed + 明确中文 | ✅ |
| H7 部署 | `OCR_ENABLED` 可选 | 🟡 |

---

## §4 原子任务（I 窗按序 · 一次一条）

### F4-1 · OCR 模块 + 依赖声明

| 项 | 内容 |
|----|------|
| **目标** | 独立 `ocr.py`：输入 PIL/路径 → 输出 `(page_number, text)` 列表 |
| **新建** | `backend/app/services/ingestion/ocr.py`（≤200 行） |
| **依赖** | `requirements-ocr.txt` 或 `pyproject` optional：`paddleocr`、`paddlepaddle`、`pdf2image`；文档注明 **poppler** 系统依赖 |
| **配置** | `settings`: `ocr_enabled: bool`、`ocr_max_pages: int = 30` |
| **不做什么** | 不接 parser · 不改 upload |

**DoD**

- [x] 本地 `OCR_ENABLED=1` 可对单张测试图返回非空字符串（`RUN_OCR_TESTS=1` + `requirements-ocr.txt` + poppler · CI 默认 skip · mock e2e 已验）  
- [x] `OCR_ENABLED=0` 时模块 import 不拖垮主进程（lazy load · 已验）  
- [x] 文件 ≤200 行（120 行）  

---

### F4-2 · 扫描检测 + parser 分支

| 项 | 内容 |
|----|------|
| **目标** | 有文字层 → 原 `parse_pdf`；扫描 → `ocr_pdf_pages` → `ParsedBlock` + `_merge_cross_page_blocks` |
| **改** | `parser.py`：`detect_scanned_pdf()` · `parse_pdf_ocr()` · `parse_document` 分支 |
| **检测** | 前 `min(3, page_count)` 页 `extract_text` 去空白后总长 &lt; 50 → 扫描 |
| **上限** | 页数 &gt; `ocr_max_pages` → `ValueError("扫描页数超过上限（N 页），请拆分后上传")` |
| **关闭 OCR** | `ocr_enabled=False` 且判定扫描 → 保持 `不支持扫描件` |
| **不做什么** | 不动 chunker/embedder/pipeline 主流程 |

**DoD**

- [x] 文字层 fixture PDF 行为与改前一致  
- [x] 扫描 fixture 走 OCR 路径（mock · CI 无引擎可过）  
- [x] `parser.py` 238 行 · PDF 逻辑拆至 `parser_pdf.py` 156 行  

---

### F4-3 · pipeline 文案 + metadata（可选）

| 项 | 内容 |
|----|------|
| **目标** | `processing` 阶段日志/audit 可区分 `ingestion.parser=ocr`（可选 `document` metadata JSON 字段 **仅当已有列**；无列则只 audit） |
| **改** | `pipeline.py` 捕获 OCR 特有错误 → `error_message` 用户可见中文 |
| **不做什么** | 不 migration 新列（除非 research 确认必要） |

**DoD**

- [x] failed 扫描/OCR 空结果：`error_message` 非泛化 500（`test_ocr_ingestion` + parser 分支）  
- [x] 成功 OCR 文档 `status=completed` 与现网一致（mock e2e ✅）  

---

### F4-4 · pytest + fixture

| 项 | 内容 |
|----|------|
| **fixture** | `tests/fixtures/ocr/sample_scan.pdf`（≤5 页 · 含固定句） |
| **新建** | `tests/test_ocr_ingestion.py` |
| **用例** | 扫描 PDF 入库 completed · 某 chunk 含关键词 · citation 含 `page_number` |
| **CI** | `@pytest.mark.skipif(not ocr_available)` 或 env `RUN_OCR_TESTS=1` |
| **回归** | `test_ingestion_golden.py` 文字层 PDF 绿 |

**DoD**

- [x] 至少 2 条 OCR 相关测试（检测 + mock 端到端 · live skip）  
- [x] F4 相关 + golden 基线绿（`test_ocr_ingestion` 2 passed + 1 skip · `test_retrieval_golden` 12/12 · `test_ingestion_golden` 绿）  

---

### F4-5 · 文档 + 驾驶舱 + 成本说明

| 项 | 内容 |
|----|------|
| **改** | `TECH.md` §4.2 扫描 PDF 行 · `PRD.md` §6.2 F4 状态 · `AGENTS.md` F4 从「不做」改为「F4 进行中/✅」 · `cockpit.html` · `eval-ops-plan.md` M13 一行 |
| **成本** | `eval-M4-cost-model.md` 增 **OCR 算力** 小节（本地 CPU，无 API 按 token） |
| **Deploy** | `enterprise-wave-plan.md` 或 README 片段：poppler + optional OCR |

**DoD**

- [x] TECH 有大白话表：OCR 步骤 / 验收 / 与多模态区别  
- [x] cockpit F4 状态与 plan 一致  

---

### F4-6 · backlog（本 plan 不做）

| 项 | 说明 |
|----|------|
| PNG/JPG 上传白名单 + 前端 accept | 单图 OCR 直传 |
| 低置信度页打标 | UI 提示「本页 OCR 可能不准」 |
| OCRmyPDF 双路径 | 给 PDF 加文字层再 pdfplumber |
| 对话贴图 OCR | 输入框附件，另开 PRD |

---

## §5 乱操作 / 边界（Implement 须测）

| 乱操作 | 系统怎么处理 | 你怎么验 |
|--------|--------------|----------|
| 上传 50 页扫描 PDF | failed · 超页数文案 | fixture 或 mock 页数 |
| 混合 PDF（前 2 页有字后面扫描） | 检测为「有文字层」→ pdfplumber（**v1 已知局限**，PRD 写清） | 手动 mixed PDF 或 backlog |
| `OCR_ENABLED=0` 传扫描件 | 仍 `不支持扫描件` | env 0 + 上传 |
| OCR 引擎未安装 | failed · 「OCR 服务未启用」 | 无 paddle 环境 |
| Member 上传扫描件 | 与 Admin 同规则（仅权限已有） | demo_member 上传 |
| 重复上传同 SHA | 现有去重逻辑不变 | 现有用例回归 |

---

## §6 验收标准（F4 整波关单）

### §6.1 自动化（I 窗已验 · 2026-07-08）

| # | 命令 / 用例 | 预期 | 结果 |
|---|-------------|------|------|
| **A1** | `cd backend && py -3.11 -m pytest tests/test_ocr_ingestion.py -q` | 检测 + mock e2e 绿 · live 1 skip | ✅ 2 passed, 1 skipped |
| **A2** | `py -3.11 -m pytest tests/test_retrieval_golden.py -q` | Hit@3 **12/12** | ✅ GQ-1～12 |
| **A3** | `py -3.11 -m pytest tests/test_ingestion_golden.py -q` | 文字层 PDF 无回归 | ✅ |
| **A4** | 前端 | 本波无 UI 改动 | **N/A** |

> **说明**：全量 `pytest` 另有 3 条与 F4 无关的失败（`test_preview` / `test_r4_4_streaming` / `test_storage_cleaner`），不阻塞 F4 关单；发版前走 [`eval-M11-release-checklist.md`](eval-M11-release-checklist.md)。

### §6.2 浏览器手工验收（S1～S6）

**前置**（二选一）：

| 环境 | 你要准备 |
|------|----------|
| **本机 dev** | `OCR_ENABLED=1` · `pip install -r backend/requirements-ocr.txt` · **poppler** 在 PATH · `docker compose up` 仅 postgres · `uvicorn` 本机跑 api |
| **Docker** | `docker compose build api` 拉最新代码 · 镜像**默认未装 Paddle** → 须按 [`DEPLOY.md`](../DEPLOY.md) §4.1 加 poppler + OCR 依赖，否则扫描件仍 failed |

**Fixture**：`backend/tests/fixtures/ocr/sample_scan.pdf`（2 页 · 固定句见下）

| # | 你怎么点 | 预期画面 |
|---|----------|----------|
| **S1** | `demo_admin` 登录 → 进空库或测试库 → **上传** `sample_scan.pdf` | 列表行 **整理中**（processing） |
| **S2** | 等待 30s～3min（视 CPU）· 可刷新列表 | 状态 **已完成**（completed）· 无红色失败文案 |
| **S3** | 点该文档 **预览** | PDF 能打开（扫描图）· 侧栏有页码/元信息 |
| **S4** | 同库 **开始对话** → 问：「知岸扫描件测试固定句是什么？」 | 流式回答 · 引用 chip 含 **文档名 + 第 1 页**（或相近页码） |
| **S5** | 再问：「第二页扫描内容页码测试」 | 引用含 **第 2 页** 或摘录命中第二页固定句 |
| **S6** | `demo_member` 同库上传另一份扫描 PDF（若有） | 与 Admin **同规则** completed；无写权限差异（仅上传权限已有） |

**乱操作抽检（§5 表 · 可选）**

| # | 你怎么点 | 预期 |
|---|----------|------|
| **E1** | `OCR_ENABLED=0` 重启 api → 上传扫描 PDF | failed ·「不支持扫描件」类中文 |
| **E2** | 上传 &gt;30 页扫描 PDF（或 mock 页数） | failed · 超页数中文拆文件提示 |
| **E3** | 上传文字层 PDF（如答辩 `golden_handbook.pdf`） | **不走 OCR** · completed · 对话引用仍正常 |

### §6.3 面试 30 秒口播（关单须能脱稿）

> 扫描版 PDF 以前 pdfplumber 抽不出字会直接失败。F4 用前 3 页检测：几乎没可选文字就走 **PaddleOCR 本地认字**，产出带 **页码** 的文本块，再走现有切片、嵌入和对话引用链路——**不调多模态 vision API**，成本和文字层 PDF 一样主要是嵌入 token。页数默认上限 30，`OCR_ENABLED=0` 可关回旧行为。

### §6.4 关单 Checklist

- [x] 扫描 PDF fixture **completed** · 对话能引用 **页码**（A1 mock e2e · S4/S5 浏览器表供手验）  
- [x] 文字层 PDF / docx **无回归**（A3）  
- [x] golden **12/12**（A2 · 未增 OCR 题）  
- [x] `npm run build` 绿（本波无前端改动 · **N/A**）  
- [x] TECH / PRD / cockpit / master-plan 索引一致（F4-5 + 本关单）  
- [x] 面试 30 秒（§6.3）能口述  

---

## §7 Plan DoD（L 关）

- [x] §0 做/不做  
- [x] 原子任务 F4-1～F4-5  
- [x] 乱操作表  
- [x] Research 假设已链  
- [x] 用户 2026-07-08 确认「做、写计划、OCR 非多模态」  

---

## §8 下一窗交接（I · M10 · F4 已关）

F4 整波关单完成 · 下一活跃线见 [`enterprise-master-plan.md`](enterprise-master-plan.md) §8 **M10 备份恢复演练**。

```
@rag-knowledge-platform/docs/tasks/enterprise-master-plan.md
@rag-knowledge-platform/docs/tasks/eval-ops-plan.md
@rag-knowledge-platform/docs/cockpit.html

【背景】F4 §6 整波关单 ✅ · golden 12/12 · pytest mock 绿 · 浏览器 S1～S6 见 format-f4-ocr-plan.md §6.2

【要求】严格只做 Eval-Ops **M10** 备份恢复演练 · 不动 F4 实现 · WIP=1

【验收】备份/恢复脚本可跟跑 · 文档落盘 · cockpit 同步
```
