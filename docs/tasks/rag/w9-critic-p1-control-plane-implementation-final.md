# W9 P1 — Critic 控制面实施设计

> 对应规划：`docs/tasks/rag/w9-critic-p1-control-plane-plan-final.md`
> 本文只覆盖 P1，不扩展 W9 P2。

## Owner 与顺序

Agent critic 推荐动作的唯一 owner 是 `agent/stream.py::_stream_generation_phase`，它只在 `_stream_agent_core` 的单 turn 编排下运行。Fast Chat 没有 recovery loop，由 `ChatEngine._generate` 负责最终候选冻结。

```text
run_react_loop(defer_finish whenever critic is enabled)
→ freeze scoped AgentGenerationPlan evidence
→ generate buffered candidate
→ deterministic mutation/preflight
→ run_critic (advisory only)
→ outer owner executes at most one named action
→ if revised: deterministic + semantic re-check once
→ output safety / citation alignment
→ publish and persist the same candidate
→ finalize message + run once
```

Legacy E2 与 L3/W6b 由 planner type 互斥；critic 不进入 runtime loop。

## 文件与接口

- `agent/types.py`：`AgentRunOutcome` 携带 EvidenceState、absolute deadline、critic usage 与有序 `critic_actions`。
- `agent/runtime.py`：accounted recovery 统一 create/execute/finish/audit/reducer/hooks/steps；`max_retries=0`；deadline timeout 记录真实 latency/metric。
- `agent/matcher_runtime.py`：复用 EvidenceState matcher reducer，不建立平行 state。
- `agent/tools/semantic_search.py` + `agent/state.py`：保留 `document_id`，形成 run/step/kb/chunk/document provenance。
- `audit/agent.py`：新增无原文载荷的 `agent.recovery_action`。
- `rag/generation.py`：分离 pure judgment 与显式 revision；保留 `verify_answer` 兼容 wrapper，prompt 不变。
- `rag/critic.py`：返回 `recommended_action`；deterministic rules 先于 semantic LLM；critic 不生成 correction。
- `rag/engine.py`：critic ON 绕过 early cache、缓冲 draft、先完成 citation regeneration；degraded/exception/self-verify/interruption 均不能旁路最终边界。
- `agent/stream.py`：retrieval、revision、post-revision validation 共用 step/deadline/次数预算；所有 action 结果写入 trajectory + audit；只发布最终 token。

Contract：

- `backend/tests/fixtures/l4_critic/w9-critic-control-plane-p1.json`
- `backend/tests/test_critic_w9_control_plane.py`
- `backend/tests/test_critic_w9_recovery.py`
- `backend/tests/test_critic_w9_actions.py`
- `backend/tests/test_critic_w9_scope.py`
- `backend/tests/test_critic_w9_terminal.py`

不修改 `w9-critic-cases.json` 或 `golden_agent_qa.json`。

## 预算 ownership map

| 动作 | owner | 预算 | 隐藏重试 |
|---|---|---|---|
| normal tool / E2 / W6b | Agent runtime | `steps_used/max_steps` + deadline + 原有 reflection/replan limit | 保持现状 |
| critic initial validation | outer turn owner | 1 | 不执行 action |
| critic retrieval | outer owner → runtime | 同一 agent step + absolute deadline + max 1 | `max_retries=0` |
| critic revision | outer owner | max 1 + absolute deadline | 失败也消费并记录 |
| post-revision validation | outer owner | max 1 + remaining deadline | 无第三轮 |
| citation regeneration | Fast Chat owner | `citation_density_regenerate_limit` | critic 之前完成 |

## 验收命令

```powershell
cd D:\MyPrograms\rag-knowledge-platform\backend
$taskJwt=(Get-Content -LiteralPath ..\.env | Where-Object { $_ -like 'JWT_SECRET=*' } | Select-Object -First 1).Substring(11)
$env:JWT_SECRET=$taskJwt
.\.venv\Scripts\python.exe -m pytest tests\test_critic_w9_contract.py tests\test_critic_g1w1.py tests\test_g1_critic_falsekill.py tests\test_agent_l3_critic.py tests\test_critic_w9_control_plane.py tests\test_critic_w9_recovery.py tests\test_critic_w9_actions.py tests\test_critic_w9_scope.py tests\test_critic_w9_terminal.py tests\test_agent_e2_reflection.py tests\test_agent_l4_reflection_recovery.py tests\test_agent_l4_recovery_runtime.py tests\test_agent_l3_evidence.py tests\test_agent_finalize.py tests\test_generation_verify_fail_closed_p2_04.py tests\test_citation_align.py tests\test_citation_section_coverage.py tests\test_defense_layers.py tests\test_agent_audit.py -q
.\.venv\Scripts\python.exe -m ruff check app\services\agent app\services\rag tests\test_critic_w9_control_plane.py tests\test_critic_w9_recovery.py tests\test_critic_w9_actions.py
git diff --check
```

本里程碑跨越 runtime state、canonical trajectory/EvidenceState、critic judgment/action separation 与 final-output SSE boundary；拆开会暂时保留 hidden recovery 或 stale validation。未新增依赖、模型、迁移、API 或默认开关。
