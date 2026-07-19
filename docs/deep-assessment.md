# 睿阁 RAG 系统 · 底层完整评估

> 内部文档，非 README。从底层到上层逐层审视，不贴金不隐瞒。

---

## L0 嵌入层

### 亮点

**选型决策有数据支撑。** 通义 text-embedding-v3（1,536 维，API）、BGE-small-zh（512 维，本地 ONNX）、BGE-large-zh（1,024 维，本地 PyTorch）三组模型在 Golden QA 110 题上跑过完整基线。Hit@3 完全一致（86%），但延迟差了一个数量级。最终选 BGE-small-zh 不是因为「小模型够用」，而是因为增加 3 倍参数量没有带来任何检索质量提升。

**零外部依赖。** BGE-small-zh 通过 fastembed 加载 ONNX 模型，纯 CPU 推理，单条查询 9ms。不需要 GPU，不需要 API Key，不需要联网。docker-compose up 后即可用。

**首次加载问题已解决。** 之前 OOM 原因是 sentence-transformers 加载 PyTorch 模型占用 2GB+ 内存。切换到 fastembed 后，模型加载内存 < 200MB。

### 缺陷

**英文泛化能力未经量化验证。** 9/9 HIT 的轻量测试不能代替完整基线。BGE-small-zh 的训练数据以中文为主，英文检索的召回边界未知。

**512 维的信息密度上限。** BGE-small-zh 的 512 维在文档量级达到数万级时，向量区分度可能不足。当前测试集只有 6 份文档（约 400 chunks），无法验证这一点。

---

## L1 切片层

### 亮点

**算法逻辑清晰，非简单定长切割。** 切片器按章节边界（heading-path）分割，同节内合并（min_chars=400），长段按句边界拆分（。！？；），chunk 间保留 150 字 overlap。表格独立标记 `chunk_kind="table"`，避免表行被切散。

**Parent-Child 结构。** 每节同时生成 parent chunk（全文）和 child chunk（片段），检索命中 child 后通过 `parent_group` 回溯到 parent。实现方式是一个 parent_group 的 UUID 关联。

**参数可配置。** `max_chars=1200`、`min_chars=400`、`overlap_max_chars=150`、`SOFT_MAX_MARGIN=0.2` 都在 `IngestionConfig` 中集中管理，不需要改核心代码。

### 缺陷

**跨页内容断裂。** PDF 解析后的 page_number 字段仅用于引用标注，切片器不会「感知」跨页内容。如果一个段落被 PDF 解析器切成两个 block（分布在两页），切片器会当成两个独立 prose 块处理。

**句子边界正则不够全面。** `SENTENCE_END = re.compile(r"[。！？!?；;]|(?<=\.) (?=[A-Z0-9])")` —— 中文省略号（……）、破折号（——）、英文逗号分隔的长句没有被覆盖。长句可能因为找不到拆分点而被整个截断。

**合并阈值是经验值。** `min_chars=400` 和 `max_chars=1200` 是基于当前测试集调出来的，没有对不同类型文档（法律合同、技术文档、FAQ）做分类型消融。

---

## L2 检索层

### 亮点

**双路召回 + RRF 融合。** 向量检索（余弦相似度，Top-30）和全文检索（ts_rank_cd，Top-30）通过 reciprocal_rank_fusion 合并。RRF 参数经过消融：`w_v=1.0, w_f=1.2` 是实验确定的最优点，`w_f` 超过 1.5 时跨章节查询开始掉点。

**全文检索的 CJK 分词。** 使用 jieba 做中文分词，英文按空格分割。FTS 的 `tsquery` 中使用 `|`（OR）连接每个 token，不要求精准匹配。对 `&` 等 tsquery 保留字符做了过滤，防止 PostgreSQL 报错。

**查询缓存。** LRU 缓存（`max_size=5000, TTL=3600s`），命中率约 40%（来自 /health/detailed 数据）。缓存失效策略是定时过期，不是基于内容变更。

**熔断降级。** BGE 嵌入连续失败 2 次后自动降级为纯 FTS 检索。从 /health/detailed 可观测熔断器状态（`bge_embed: closed/open`）。

### 缺陷

**rerank 被关闭但没有消融数据。** rerank_enabled=False，因为之前用通义 qwen3-rerank 有延迟和依赖问题。但关闭前/后的 Hit@3 差异从未被量化——不知道这个决策损失了多少检索质量。

**向量召回的死角。** 余弦相似度对数值接近的短文本区分度差（如 `金额 ≤ 1,000 元` vs `金额 ≤ 5,000 元`）。这类信息靠 FTS 的 ts_rank_cd 区分，但如果 FTS 召回没覆盖，向量侧也无法弥补。

**缓存一致性。** 文档更新后缓存不会自动失效。LRU 的 TTL=3600s 意味着文档更新后最多一小时才能被检索到。

---

## L3 生成层

### 亮点

**引用强制。** System prompt 中明确要求「每个结论必须标注来源片段编号」，有明确的 few-shot 示例。实测 10/10 生成包含 `[片段N]` 引用。Citation Accuracy（SSE 事件）100%。

**无依据拒答。** 当检索结果为空或置信度低于阈值时，返回固定拒答话术「知识库中未找到相关内容，无法根据文档回答您的问题」。中文/英文 query 自动切换。

**自验证。** 生成完成后调用 `verify_answer` 检查回答每个事实是否能在检索片段中找到原文支持。验证失败时保留原答案（不修改）。

### 缺陷

**引用是「要求」不是「验证」。** 虽然 prompt 要求 `[片段N]`，但 DeepSeek 不一定每次都遵守。没有 post-processing 来检查引用有效性。如果 LLM 产生了一个不存在的 `[片段5]`，没有校验环节。

**Faithfulness 89% 有水分。** Judge 评估时给 DeepSeek 看的检索片段和生成时 LLM 看到的片段是同一批数据，Judge 倾向于判"忠实"。更严谨的做法是让独立 judge 模型（不相关 prompt）评估。

**verify_answer 不修改回答。** 发现不忠实时只返回原答案，没有纠错机制。正确的做法是对不忠实部分重新生成。

---

## L4 评测层

### 亮点

**三套自建测试集。** Golden QA 110 题（9 领域，L1-L4 分层）、Expense QA 105 题（财务专用）、Enterprise QA 108 题（6 份模拟文档）。每套都有领域分解和难度分层。

**外部验证测试集。** 3 份真实中文文档（员工手册 + 报销制度 + README）30 题，Hit@3=70%。低于自建测试集 25 个百分点——这个差距是清楚的。

**评测管道。** `scripts/run_benchmark.py` 支持 `--dataset` 和 `--mode`，结果自动写入 `evaluation_runs` 表。趋势 API `GET /trends` 返回历史基线，前端看板 `eval-trends.html` 展示趋势图表。

**可复现。** 每次评测创建独立的 KB，不依赖已有数据。`run_id` 包含时间戳，可回溯。

### 缺陷

**测试集质量「自己教自己」。** 文档是 DeepSeek 生成的，题目是 DeepSeek 出的，答案是从 chunk 里取的。这是闭环自我验证，不是独立审查。70% 真实文档测试集分数差距 25 个百分点就是直接证据。

**LLM-as-Judge 的信噪比未知。** 同一份回答用不同 prompt 让 DeepSeek 打分，结果可能波动。没有做 Judge 的 inter-rater reliability 测试。

**评测入口不全。** `run_benchmark.py` 的 generation 模式已实现但使用率低。Faithfulness 评测和 Citation 评测仍然是独立脚本，未统一集成到 run_benchmark.py 中。

---

## L5 工程层

### 亮点

**构建可重复。** Dockerfile 移除 sentence-transformers 后构建时间 84 秒。fastembed 写入 requirements.txt。pip 有阿里云 + PyPI 双源 fallback。

**安全体系完整。** JWT 认证 + RBAC（admin/member）+ kb_id 隔离 + 审计日志 + 登录限流 + API rate limit。三层限流：登录（5次/15min）、API（100/min）、chat（30/h）。

**可观测性。** OpenTelemetry 追踪 + Loki 日志 + Tempo 链路 + Grafana 看板。每个检索操作有耗时分解（embed/vector_recall/fts_recall/rerank）。

**工程基建。** .pre-commit-config.yaml、CHANGELOG.md、CONTRIBUTING.md（提交规范）。

### 缺陷

**Docker 镜像 >1GB。** 即使移除了 torch，fastembed 的 onnxruntime 和 jieba 分词模型仍然占空间。没有做多阶段构建优化。

**无 CI pipeline 验证记录。** `.github/workflows/ci.yml` 配置了 GitHub Actions，但从未确认过是否能完整跑通。pytest 不在容器中（正常），但 CI 环境的依赖安装步骤可能过时。

**测试脚本碎片问题未根除。** 统一评测入口 `run_benchmark.py` 已建，但 `tests/benchmark/tests/` 下仍有 15+ 个独立调试脚本未清理。

---

## L6 产品层

### 亮点

**引用溯源是真实功能，不是前端贴标签。** 后端 SSE 事件 + 前端 CitationChip + CitationPreview 浮层，完整的引用查看体验。

**权限隔离有设计。** kb_id 级别的数据隔离、admin/member 角色、admin_only 文档可见性控制。不是只有一个 open API。

**评测体系可展示。** `eval-trends.html` 看板 + `evaluation_runs` 表 + 趋势 API，在面对技术评审时可以直接打开浏览器看趋势图。

### 缺陷

**无 i18n。** 所有 UI 文案硬编码中文。

**无 Forget Password 页面。** 后端 API 已实现但前端没有入口。

**多轮对话前端体验未打磨。** thread 侧边栏、历史列表、会话切换均已实现，但首次使用的用户引导（empty state）没有设计。

**单机部署，无高可用。** Docker Compose 单节点部署，PostgreSQL 单实例。数据库挂了整个系统不可用。

---

## 能力边界清单

| 能力 | 当前状态 | 可信度 |
|------|----------|--------|
| 中文单文档检索 | Hit@3 95%+ | 高（自建+外验证） |
| 数字密集文档检索 | Hit@3 ~92% | 中高（修复后稳定） |
| 跨文档检索 | 2/3 领域 100%，1/3 67% | 中 |
| 英文检索 | 9/9 HIT（轻量） | 低（未完整验证） |
| 生成忠实度 | 89% | 中（Judge bias） |
| 引用准确率 | 100%（SSE） | 高 |
| 多轮对话 | contextualize 正确 | 中（3轮测试） |
| 并发能力 | 50 req/s health 正常 | 中（无完整压测） |
| 容错能力 | 嵌入降级→FTS | 高 |
