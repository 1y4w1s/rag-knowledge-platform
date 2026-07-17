# 睿阁 — RAG Hybrid Retrieval 检索流程

> 交接对象：后端开发者
> 更新日期：2026-07-17

---

## 1. 整体流程

```
用户输入查询 → stream_chat_events()
    │
    ├── 安全过滤 → [input_safety_check]
    ├── 降级评估 → [assess_degradation]
    ├── 短查询跳过 → [是否问候/闲聊？]
    │                    ├── 是 → 直接 LLM，跳过检索
    │                    └── 否 → 继续
    │
    ▼
[retrieve_chunks(db, kb_id, query, top_k=5)]
    │
    ├── 1. embed_texts([query]) → 向量 [1536]           ← 通义 text-embedding-v2
    ├── 2. _vector_recall() → Top-20                     ← pgvector cosine_distance
    ├── 3. _fts_recall() → Top-20                        ← ts_rank_cd(plainto_tsquery)
    ├── 4. reciprocal_rank_fusion() → RRF Top-20         ← k=60, weights=[1.0, 1.2]
    ├── 5. _merge_recall_rows() → [RetrievedChunk]       ← 向量+FTS 字段融合
    │
    ├── 6. 条件 Rerank 决策                              ← 4 信号决策树
    │       ├── 高置信度 → 跳过 Rerank，RRF 顺序直接返回
    │       └── 低置信度 → [rerank_chunks()]             ← 通义 qwen3-rerank
    │
    ├── 7. 自适应 chunk 数量                              ← _adaptive_top_k()
    │       ├── max_sim > 0.85  → 2 chunks
    │       ├── max_sim > 0.70  → 3 chunks
    │       └── 其他          → 5 chunks
    │
    └── 8. 跨段 Query Rewrite                            ← 复合问题拆子查询
            ├── 检测关键词：和/与/以及/还是/或/同时/如果
            └── → decompose_query() → 多路检索 → RRF 再融合
```

---

## 2. 关键函数

### `retrieve_chunks(db, *, kb_id, query, top_k=5) -> list[RetrievedChunk]`
- **位置**: `app/services/rag/retrieval.py:230`
- **功能**: 单知识库检索（向量 + FTS + RRF + 条件 Rerank）

### `stream_chat_events(db, *, kb_id, user_id, message, ...) -> AsyncIterator[SSE Event]`
- **位置**: `app/services/rag/chat.py:73`
- **功能**: 完整对话编排：检索 → citations SSE → token SSE → done SSE → 落库

---

## 3. RRF 融合配置

| 参数 | 值 | 说明 |
|------|-----|------|
| `rrf_k` | 60 | RRF 平滑常数（越小 weight 差异越大）|
| `rrf_vector_weight` | 1.0 | 向量检索权重 |
| `rrf_fts_weight` | 1.2 | 全文检索权重（略高于向量）|

```
RRF score = Σ (1 / (k + rank(r, i)))
```

---

## 4. 条件 Rerank 决策树

**文件**: `app/services/rag/retrieval.py:_should_skip_rerank()`

| 条件 | 决策 | 预计触发比例 |
|------|------|------------|
| `len(candidates) <= 1` | 跳过 Rerank | ~10% |
| `max_sim > 0.85` | 跳过 Rerank | ~30% |
| `max_sim > 0.70 AND fts_high` | 跳过 Rerank | ~30% |
| `fts_high AND query_len < 10` | 跳过 Rerank | ~15% |
| 其他 | 保留 Rerank | ~15% |

**信号说明**：
- `max_sim`: 最高向量余弦相似度（1 - cosine_distance）
- `fts_rank`: FTS 第一名的 ts_rank_cd 值（> 0.1 表示关键词命中）
- `query_len`: 查询字符数

---

## 5. 跨段 Query Rewrite（decompose_query）

对于含多个知识点的复合问题（如"年假和加班费怎么算"），自动拆分为子查询并行检索：

```
"培训完不到一年就离职，需要赔培训费吗？"
    │
    ├── 子查询 1: "培训 离职 赔钱"
    └── 子查询 2: "培训不到一年 离职 培训费"
            │
            ▼ 各自调用 retrieve_chunks()
            │
            ▼ RRF 再融合 + Rerank
```

**触发条件**: `rerank_enabled=True` AND（含"和/与/以及/还是/或/同时/如果" OR 多问号 OR query > 15 字）

---

## 6. 向量检索

| 项目 | 详情 |
|------|------|
| 引擎 | pgvector（PostgreSQL 扩展）|
| 索引类型 | HNSW（`ix_document_chunks_embedding_hnsw`）|
| 距离函数 | cosine_distance（内积归一化）|
| 维度 | 1536（通义 text-embedding-v2）|
| 召回量 | Top-20（`VECTOR_RECALL`）|

---

## 7. 全文检索（FTS）

| 项目 | 详情 |
|------|------|
| 引擎 | PostgreSQL tsvector |
| 分词配置 | `simple` + `segment_cjk()`（CJK 字符间加空格）|
| 排名函数 | `ts_rank_cd` |
| 查询构建 | `plainto_tsquery('simple', segment_cjk(query))` |
| 召回量 | Top-20（`FTS_RECALL`）|
| 特殊字符回退 | 含特殊字符时追加 ILIKE 查询 |

---

## 8. 重排序（Rerank）

| 项目 | 详情 |
|------|------|
| 提供商 | 通义千问 qwen3-rerank |
| 输入 | Top-20（RRF 融合后）|
| 输出 | Top-5（重排序后）|
| 回落 | API 失败时使用 RRF 顺序 |
| 条件 | 仅低置信度查询触发 |

---

## 9. 安全控制

| 检查 | 函数 | 位置 |
|------|------|------|
| kb_id 隔离 | `_enforce_kb_scope()` | retrieval.py:395 |
| 向量召回范围过滤 | `_exclude_admin_only()` + `visible_kb_ids` | retrieval.py:106 |
| FTS 召回范围过滤 | 同上的 WHERE 条件 | retrieval.py:143 |
| 相关性门禁 | `filter_relevant_chunks()` | chat.py:162 |
| 输入安全 | `input_safety_check()` | chat.py:97 |
| 输出安全 | `output_safety_check()` | chat.py:205 |
