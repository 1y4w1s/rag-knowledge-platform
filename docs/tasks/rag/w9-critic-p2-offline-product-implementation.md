# W9 P2 — Offline Critic Product Experiment

## 范围

本任务只测量既有 W9 P1 控制面如何消费冻结 critic 输出。不得调用模型、调优提示词、修改产品运行时或启用默认开关。

## 实施边界

- 以 P0 的 12 个 case ID、输入哈希与动作分布作为不可变分母；
- 注入数据与 P0 oracle 物理分离；生产侧只接收 `CriticResult`，不读取 oracle；
- 覆盖 `_stream_generation_phase` 的 outer-owner 分发；外部 token/provider 可以固定 stub，但不能替换该 owner；
- 指标按 L0–L8 与首个失败阶段记录，P2 不解释为本地模型能力；
- P2 发现运行时语义缺口时只记录 PARTIAL，不在本任务修复。

## 改动文件与测试策略

- `backend/tests/fixtures/l4_critic/w9-critic-p2-injected-reports.json`：独立、无 oracle 字段的冻结 transport；
- `backend/tests/fixtures/l4_critic/w9-critic-p2-offline-product.json`：一次已执行的 PARTIAL 观测工件；
- `backend/tests/test_critic_w9_offline_product.py`：分母/泄漏校验，并通过真实 outer owner 复现 C11 的 first-failed-stage；
- `docs/tasks/rag/w9-critic-p2-offline-product-plan.md` 与本文：范围、停止条件和验收记录。

无 API 或运行时接口变更。测试仅 stub 初始 token/provider 和冻结 critic transport；不替换 `_stream_generation_phase`。

## 已知判定

C11 是 deterministic citation blocker，冻结动作为 `REVISE_FROM_EXISTING_EVIDENCE`。当前产品只允许 `METHOD_LLM_VERIFY_V1` 进入 revision 分支；`rules_v1` C11 因而被记录为 `skipped_unavailable`，随后 fail-closed。这是产品控制面结果，不能通过修改冻结方法字段掩盖。

该结果命中 P2 的“需要改运行时语义即停止”条件。因此本轮工件明确标为 `PARTIAL`：只报告已经执行的 C11 分子，不将未执行的其余 11 个 case、恒定策略控制或 P3 readiness 伪报为通过。

## 验收

```powershell
cd D:\MyPrograms\rag-knowledge-platform\backend
$taskJwt=(Get-Content -LiteralPath ..\.env | Where-Object { $_ -like 'JWT_SECRET=*' } | Select-Object -First 1).Substring(11)
$env:JWT_SECRET=$taskJwt
.\.venv\Scripts\python.exe -m pytest tests\test_critic_w9_contract.py tests\test_critic_w9_offline_product.py -q
.\.venv\Scripts\python.exe -m ruff check tests\test_critic_w9_offline_product.py
```

## 不做

- 不改 `agent/stream.py`、`agent/runtime.py` 或 RAG runtime；
- 不修改 P0 frozen cases、P0 oracle 或 golden；
- 不启动 LM Studio 或外部模型服务。
