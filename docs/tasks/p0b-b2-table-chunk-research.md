# P0-B · B2 Research — 大表 / 跨页表格切分

> **日期**：2026-07-21  
> **对标**：architecture-optimization-map **B2**  
> **状态**：✅ Research 完成 · ✅ Plan/Implement 见 [`p0b-b2-table-chunk-plan.md`](p0b-b2-table-chunk-plan.md)  
> **前置**：F1 xlsx ✅ · F3 PDF 表格 ✅ · R2-2 表格独立 chunk + Parent-Child ✅ · B1 版式降噪 ✅

---

## 1. 问题一句话

企业台账 / 制度附录里，**一张表常常比散文块大很多**，且 **PDF 表经常跨页断行**。  
现状是「每页/每 sheet 一整块 → 一个 table chunk」，检索与嵌入都会吃亏。

---

## 2. 现状摸底（代码事实）

| 路径 | 今天怎么做 | 缺口 |
|------|------------|------|
| **PDF 表（F3）** | `extract_tables()` **按页**各出 1 个 `block_kind=table`；F3 plan 写明 **不合并跨页表** | 续页无表头 / 同表被拆成两块 → 问续页行易 miss |
| **XLSX（F1）** | `parse_xlsx`：**整 sheet → 1 个 MD 表 block** | 几百行 sheet 变成超长单 chunk |
| **MD/DOCX 表（R2-2）** | 识别 pipe 表 → 独立 table chunk | 超长表同样 **不按行窗切** |
| **chunker** | `block_kind=="table"` → **原样 1 个 `chunk_kind=table`**，**绕过** `max_chars`（1200）句号切分 | 大表稀释向量；也可能触嵌入长度上限 |
| **Parent-Child** | 仅 prose 同节多 leaf 时建 parent | 表拆窗后是否建 parent **未定义** |
| **检索** | 已有 table chunk 可被 hybrid 命中 | B2 **不应改** RRF / multi-query / rerank 默认 |

**夹具与题**：`test_pdf_table_ingestion` 只有「每页一张小表」；Advanced AQ-6 等是 **小 MD 表计算题**，盖不住「大表 / 跨页」回归。

---

## 3. 根因（面试可讲）

1. **大表**：嵌入模型对超长文本会截断或平均语义变糊；问「第 N 行某列」时，整表向量不如「表头+附近行窗」稳。  
2. **跨页**：pdfplumber 按页抽表；续页往往只有数据行或重复表头。不拼、不带表头 → 续页 chunk **丢列语义**。

---

## 4. 方案对比（Research 结论）

| 方案 | 做法 | 利 | 弊 | 选用 |
|------|------|----|----|------|
| **A. 仅 chunker 按行窗切** | 任意 table MD：保留表头+分隔行，数据行按 `max_chars`（或略松的 table soft）切窗 | 一处改动覆盖 xlsx/PDF/MD/DOCX | 不解决跨页丢表头 | **必做** |
| **B. PDF 相邻页启发式合并** | 列数一致 + 续页首行像数据（或重复表头则去重）→ 合并后再走 A | 直接打跨页痛点 | 误合并风险；需安全闸 | **必做（保守启发式）** |
| **C. 表格也建 parent 全文** | 多窗 table leaf + 一个 parent 全文 | 生成侧可读全表 | 超大表 parent 巨大、入库内存 | **可选轻量**：仅窗数 2～N 且总长 ≤ 某上限才建；超限只留 leaf |
| **D. 换 DeepDoc / 表格 OCR** | 版面模型 | 扫描表更强 | Wave 2+；与 B3/F5 纠缠 | **不做** |
| **E. 改检索默认** | 表题加权 / 专路 | 可能抬 Hit | 越界地图 B2；回归面大 | **不做** |

**推荐组合**：**B（PDF 合并）→ A（统一行窗切）→ C 轻量（有条件 parent）**。

---

## 5. 启发式草案（Implement 细化）

### 5.1 跨页合并（仅 PDF table blocks，批内按页序）

对相邻 `table` block（页码连续）：

| 条件 | 动作 |
|------|------|
| 列数相同，且续页首行 ≈ 上页表头（归一化比） | 去掉续页表头行后拼接数据行 |
| 列数相同，续页首行 **不像** 表头（单元格与表头差异大） | 直接拼接（认定续页无表头） |
| 列数不同 / 中间插散文页 | **不合并** |
| 合并后仍可再与下一页试合并（同表跨多页） | 链式合并 |

合并后：`page_number` = 首页；`section_title`/`heading_path` 可标 `第{p}–{q}页表格`（或保留首页标题 + meta 注释在 content 外——优先简单字符串）。

### 5.2 大表行窗（chunker，所有来源）

| 参数（建议默认） | 值 | 说明 |
|------------------|----|------|
| 触发 | `len(content) > max_chars`（与 prose 同 1200，或 `table_max_chars` 可配置，默认= `max_chars`） | 小表不切 |
| 窗内容 | **表头行 + 分隔行 + 数据行子集** | 每窗自洽 |
| 切点 | 按 **数据行** 累加字符，不超过预算 | 不在单元格中间切开 |
| overlap | 上一窗末 **1～2 行**数据（可选，默认 1 行） | 边界行可检索 |
| parent | 窗数 ≥2 且合并全文 ≤ `table_parent_max_chars`（建议 8000）→ 建 `chunk_kind=parent`；否则仅 leaf | 防 OOM |

开关建议：`TABLE_CHUNK_SPLIT_ENABLED` 默认 `true`（与 B1 风格一致，可一键回退）。

---

## 6. 风险与安全闸

| 风险 | 闸 |
|------|----|
| 两张无关表同列数被合并 | 要求页码连续；列数+表头相似度；单测「同列数不同表」不合并 |
| 切窗后 Hit 变差（小表被误切） | 仅超 `max_chars` 才切；既有小表 fixture 行为不变 |
| parent 过大 | 上限跳过 parent |
| 嵌入维度/长度 | 行窗对齐 `max_chars`，贴近 prose 预算 |
| 回归 | 既有 `test_pdf_table_ingestion` / `test_chunker` 表用例 / golden 表题不掉 |

---

## 7. 验收信号（对齐地图）

| 信号 | 怎么验 |
|------|--------|
| **表格题 Hit 或人工抽检改善** | 新增夹具：① 跨页同表 PDF（续页无表头）问续页单元格；② 超长 xlsx/MD 表问靠后行 → 命中含该行的窗；或 Advanced/自建表题子集 Hit 不掉且跨页题从 miss→hit |
| **零回归** | `test_chunker` + `test_pdf_table_ingestion` + 相关 ingestion 绿；**不改** `retrieval.py` 默认；CI golden Hit@3 门禁不破 |

---

## 8. 明确不做（本叶）

- B3 OCR 失败可观测  
- B4 中英双嵌入  
- 检索默认 / RRF / multi-query / rerank  
- DeepDoc、扫描件表格 OCR、F5  
- 散文路径 / B1 降噪逻辑改动  

---

## 9. 建议动哪些文件（预估 · plan 锁定）

| 文件 | 角色 |
|------|------|
| `ingestion/parser_pdf.py` 或新建 `table_merge.py` | 跨页 table block 合并 |
| `ingestion/chunker.py` + 可能 `table_split.py` | 行窗切分 + 可选 parent |
| `ingestion/types.py` / `config.py` | 开关与限额 |
| `tests/test_table_chunk_b2.py`（新建）+ 夹具 | 跨页合并 + 大表切窗 |
| TECH-4.2 / 4.3 · 地图 B2 · remaining-plan | 文档同步（Implement 窗） |

**行数**：若 `chunker.py` 将超 300 行软上限 → Implement 前把表逻辑拆到 `table_split.py`（plan 写死）。
