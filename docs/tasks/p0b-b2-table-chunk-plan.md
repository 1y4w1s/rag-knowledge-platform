# P0-B · B2 大表 / 跨页表格切分 · Plan

> **日期**：2026-07-21  
> **对标**：architecture-optimization-map **B2**  
> **状态**：✅ **Implement 完成**  
> **Research**：[`p0b-b2-table-chunk-research.md`](p0b-b2-table-chunk-research.md)  
> **前置**：F1/F3/R2-2/B1 ✅

---

## 做 / 不做

| 做 | 不做 |
|----|------|
| PDF **相邻页同表启发式合并**（列数一致 + 续页表头去重/无表头拼接） | B3 OCR 可观测 · B4 双嵌入 |
| 所有来源 **超长 MD 表按行窗切**（每窗保留表头+分隔行） | 改正文检索默认 / A* / RRF / multi-query / rerank |
| 窗数≥2 且全文 ≤ parent 上限 → **table parent** | DeepDoc / 扫描表 OCR / F5 |
| 开关 `TABLE_CHUNK_SPLIT_ENABLED`（默认开）+ 安全闸 | 改散文 `parse_pdf` / B1 降噪 |

---

## 验收结果（2026-07-21）

| 项 | 结果 |
|----|------|
| B2 单测 | `test_table_chunk_b2` **7 passed** |
| chunker 回归 | `test_chunker` **11 passed**（含小表隔离） |
| 检索 | 未改 `retrieval.py` / RRF / multi-query / rerank |

---

## 落地设计

1. `table_md.py`：pipe 表解析/重建 · 表头相似 · 强数据行判定  
2. `table_merge.py`：页码连续 + 同列数 → 重复表头去重或数据行续拼  
3. `table_split.py`：超 `max_chars` 按数据行切窗（overlap 默认 1）+ 短 parent  
4. `parser_pdf` 抽表后 merge；`chunker` table 分支调 split；pipeline 读 settings  

---

## 文件清单

| 文件 | 变更 |
|------|------|
| `app/services/ingestion/table_md.py` | **新建** |
| `app/services/ingestion/table_merge.py` | **新建** |
| `app/services/ingestion/table_split.py` | **新建** |
| `app/services/ingestion/parser_pdf.py` | 抽表后 merge |
| `app/services/ingestion/chunker.py` | table → split |
| `app/services/ingestion/pipeline.py` | IngestionConfig 对齐 settings |
| `app/services/ingestion/types.py` | B2 字段；`min_chars` 回对齐 TECH=80 |
| `app/core/config.py` | 开关与限额 |
| `tests/test_table_chunk_b2.py` | **新建** |
| `.env.example` / `.env.production.example` | 开关说明 |
| TECH-4.2 / 4.2.3 · 地图 B2 · remaining-plan · AGENTS | ✅ |
| 本文 | ✅ |

---

## 验收清单

- [x] 跨页同表：重复表头合并；续页数据行拼上；异表头不合并  
- [x] 大表多 leaf 且每窗有表头；靠后行在后窗；短 parent  
- [x] 小表仍 1 chunk；开关 off 整表保留  
- [x] 不改正文检索；不动 B3/B4  
- [x] 地图 B2 → ✅  

---

## 面试 30 秒口播

「F3 按页抽表、chunker 又整表进一个向量，大表和跨页续页都会丢。B2 先保守合并相邻同列表并带上表头，再按行窗切分且每窗自带表头；短 parent 有上限。开关可关。不动检索默认，也不碰 OCR。」
