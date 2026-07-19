# BGE 嵌入模型接入计划（2026-07-18）

>环境：有 GPU，选型 BGE-large-zh-v1.5（1024维）
>策略：先对比评测，数据驱动决策后再做生产切换

---

## 1. Phase 1：搭建 BGE 推理服务

**目标**：跑通 BGE-large-zh-v1.5，暴露 HTTP API 供 embedder 调用。

   - **1.1** 用 `xinference` 启动 BGE-large-zh-v1.5 模型服务
     ```
     xinference launch --model-name bge-large-zh-v1.5 --model-type embedding
     ```
     验证：`curl http://localhost:9997/v1/embeddings -d '{"model":"bge-large-zh-v1.5","input":"你好"}'`
   - **1.2** 确认 API 地址（默认 `http://localhost:9997`）、模型名、请求/响应格式
   - **1.3** 确认向量维度为 1024，记录在案

## 2. Phase 2：代码接入 + 对比评测

**目标**：不改 production 配置，只在评测环境验证 BGE 效果。

   - **2.1** `config.py` 增加 BGE 配置项：
     - `bge_api_url: str = "http://localhost:9997/v1/embeddings"`
     - `bge_model_name: str = "bge-large-zh-v1.5"`
     - `embedding_dim` 改为配置可切换（当前 1536 硬编码，需改为 dynamic）
   - **2.2** `embedder.py` 实现 `_embed_bge()` 函数：
     - 调用 Xinference 兼容的 OpenAI embedding API 格式
     - 加入 `_validate_vectors()` 校验
     - 加入 `_embedding_cache`（LRU）——和通义共用
   - **2.3** `embedder.py` 的 `embed_texts()` 增加 `provider == "bge"` 分支
   - **2.4** 评测脚本：
     - 在测试环境跑 golden QA 50 题，分别记录：
       - BGE-large 的 Hit@3 / MRR / 平均延迟
       - 通义 text-embedding-v2 的 Hit@3 / MRR（已有基线 86.49%）
     - 格式：`"bge":{"hit_at_k":0.88,"mrr":0.97,"latency_ms":{"p50":45}}`
   - **验证**：BGE 评测结果写入 `benchmark_results/` 目录

## 3. Phase 3：生产切换（仅当 BGE 效果不差于通义时执行）

**目标**：正式将 embedding provider 切为 BGE，重建索引。

   - **3.1** 新建 DB migration（`035_add_bge_embedding.sql`）：
     - 新增 `document_chunk.embedding_bge` 列（VECTOR(1024)）
     - 或直接修改 `embedding` 列类型为 VECTOR(1024)——**锁表操作，需维护窗口**
   - **3.2** 重建 pgvector HNSW 索引：
     ```sql
     DROP INDEX IF EXISTS idx_chunk_embedding_hnsw;
     CREATE INDEX CONCURRENTLY idx_chunk_embedding_hnsw 
       ON document_chunk USING hnsw (embedding vector_cosine_ops) 
       WITH (m = 16, ef_construction = 200);
     ```
   - **3.3** 重跑全量 embedding 的脚本：
     - 遍历所有 `document_chunk` 行，用 BGE 重新生成 embedding
     - 或增量式：新入库文档用 BGE，旧文档后台异步重算
   - **3.4** `config.py` 默认 `embedding_provider` 改为 `"bge"`
   - **3.5** 回归验证：
     - CI golden QA 门禁更新为 BGE 基线
     - 人工抽测 5-10 道典型企业问题，确认回答质量
   - **验证**：`/health` 端点显示当前 embedding provider

---

## 决策决策树

```
Phase 2 完成后：
  BGE Hit@3 ≥ 通义 Hit@3 (86.49%)？
  ├── 是 → Phase 3 生产切换（性能更好 + 离线 + 可控）
  └── 否 → 保持通义，BGE 作为 fallback 保留代码
```

## 风险

| 风险 | 缓解措施 |
|------|----------|
| 维度 1536→1024 需重建索引 | Phase 3 在维护窗口执行，CONCURRENTLY 建索引 |
| BGE 对长文本切片效果未知 | golden QA 中有长文本题（制度条款），Phase 2 可验证 |
| Xinference 服务稳定性 | 加 healthcheck + 熔断器（复用已有 `retry.py`） |
| 新旧 embedding 共存 | 用列式隔离或 provider 标签区分 |
