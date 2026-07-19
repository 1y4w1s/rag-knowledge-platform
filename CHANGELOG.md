# 睿阁（Ruige）变更日志

## [Unreleased]

### 修复
- FTS 全文检索：过滤 tsquery 中的特殊字符（& | ! ( )），修复英文查询因符号报错的问题
- Citation Accuracy：engine.py 事件名 `citations`→`citation` 修复前后端事件名不匹配

### 新增
- 统一评测入口：`scripts/run_benchmark.py`，支持 `--dataset` / `--mode` / `--output`
- 上传进度条：XMLHttpRequest 用于前端跟踪文档上传进度
- 帮助/关于页：`/about` 路由 + 侧边栏入口

### 变更
- 嵌入模型：切换至 BGE-small-zh (512-dim via fastembed)，移除通义千问依赖
- 切片参数：`min_chars` 80→400, `max_chars` 1000→1200
- Rerank 关闭：移除通义 qwen3-rerank API 依赖，检索链路纯本地
- Docker 构建：移除 sentence-transformers + torch，构建时间从 ~10min 降至 ~84s
- Docker 内存限制：768MB→2GB
- 运行环境：`ENVIRONMENT=production`

### 评测
- Expense QA 断言修正：41%→92%
- Enterprise QA 校准：56%→98%
- Faithfulness 评测：94%（50 题抽样）
- Golden QA 扩展：50 题→110 题，新增 domain/difficulty/question_type 字段
- evaluation_runs 表：评测结果自动落库
- NDCG 指标：已在 benchmark runner 中实现

### 工程
- `.env` 中固化 `HF_ENDPOINT` 和 `HF_HUB_DISABLE_XET`
- `requirements.txt` 添加 `fastembed`，移除 `sentence-transformers`
- Dockerfile 添加 pip fallback 源（PyPI）
- 统一评测入口（替代 20+ 个独立脚本）
