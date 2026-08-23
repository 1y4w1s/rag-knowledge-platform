# W9 P0 — Critic Architecture Audit & Hardening Contract

> 日期：2026-08-23
> Base SHA：`33e7c551081eaa22db2eb5c7f9fec1f0585f4976`
> 状态：**PARTIAL**
> 边界：仅 CPU / deterministic audit、合同、fixture、evaluator 与测试；不运行模型，不改产品 runtime。

## 1. 结论

| 项目 | 结论 |
|---|---|
| `EXISTING_CRITIC_PRESENT` | **YES** |
| `W9_SEMANTIC_CLAIM_CRITIC_CAPABILITY` | **PARTIAL** |
| `DUPLICATE_REFLECTION_RISK` | **HIGH** |
| `CAPABILITY_VALID_DENOMINATOR` | **12** |
| Product experiment | **NO** |
| Real-local measurement | **NO** |
| Runtime rollout | **NO** |

仓库已经存在 rules/LLM critic、自验证、citation regeneration，以及 Agent 侧 critic-directed retrieve → revise → re-critic。因此 W9 不能再新增一套独立 reflection loop。P0 的正确产物是冻结现状、定义唯一 owner 与严格输入/动作合同，并用确定性 evaluator 防止退化策略“刷分”。

## 2. 当前架构事实

### 2.1 Runtime reflection owners

- Legacy E2：`LLMPlanner` 路径中的 low-recall rewrite、complex decomposition、failure replan。
- L3/W6b：`NextActionPlanner` 路径中的 observation loop、EvidenceState gate、ReflectionRecovery。
- 两条 runtime reflection 路径由 planner factory 选择，同一个 run 内互斥。

### 2.2 Generation revision owner

- Agent generation 已有 critic fail → direct semantic search → regenerate → re-critic 的一次闭环。
- 该 recovery 发生在 `AgentRunOutcome` 已形成之后，未进入 `outcome.steps`、EvidenceState、正常 step audit、`retrieval_duration_ms` 或统一 budget accounting。
- Fast Chat 的 critic/self-verify 位于 citation-density/section regeneration 之前，因此被检查的 draft 不一定是最终输出。

### 2.3 不能误认的机制

- EvidenceState 的 hit/score/diversity/doc coverage 只表示检索充分性，不表示 claim 被 evidence 语义支持。
- `_has_shallow_evidence` 的词面重叠是 heuristic semantic signal，不是 deterministic support proof。
- `verify_answer` 的缺 Key、解析失败、异常 fail-open 行为，在未来合同中必须映射为 `UNVERIFIABLE/degraded`，不能记为 semantic pass。
- `prepare_agent_generation` 当前不消费 outcome 的 terminal/refuse/clarify/low-confidence 语义；不能假设 runtime terminal decision 已约束最终生成。

完整机制清单与文件/函数证据见：

- `backend/tests/fixtures/l4_critic/w9-critic-architecture-audit.json`

## 3. Target Reflection Architecture

唯一 orchestration owner 按以下顺序负责：

1. 在共享 agent `steps_used/max_steps` 下完成 scoped retrieval/runtime correction。
2. 冻结本次 run 真正 prompt-visible 的 evidence snapshot。
3. 完成所有答案内容 mutation。
4. deterministic layer 先检查 citation syntax/id、workspace/kb/run provenance、missing citation、known conflict、required fact missing。
5. semantic critic 只处理仍 eligible 的 claim/evidence entailment、semantic contradiction、unsupported、unverifiable。
6. critic 只返回有限动作建议，不执行 retrieve/revise/clarify/refuse/accept。
7. 若外层 owner 使用一次显式预算的 revision，修订稿必须再走同一 deterministic + semantic boundary 一次。
8. 最后执行 citation alignment、output safety，再 persist/cache/finalize。

预算合同：首次 critic invocation 最多 1 次；只允许额外 1 次明确标记的 post-revision validation；hidden retry 为 0；retrieval 不得重置原 agent step budget。

## 4. Critic 输入与报告合同

合法输入仅限：

- 当前 run 的 query；
- 所有内容 mutation 后的完整 buffered draft；
- `AgentGenerationPlan.gated_chunks`；
- 与 gated chunks 同步的 citations；
- 可选的同 run、只读 EvidenceState 元数据。

禁止：critic 自查数据库、扩大 workspace/kb scope、静默 web retrieval、把 memory 当事实权威、接收 oracle 字段、直接执行建议动作。

Finding 状态：

- `SUPPORTED`
- `UNSUPPORTED`
- `CONFLICTED`
- `INSUFFICIENT_EVIDENCE`
- `UNVERIFIABLE`

动作：

- `ACCEPT`
- `REVISE_FROM_EXISTING_EVIDENCE`
- `RETRIEVE_MISSING_EVIDENCE`
- `CLARIFY`
- `REFUSE`

deterministic 阻断时，finding 使用 `evaluation_state=BLOCKED_BY_DETERMINISTIC`、`decision_owner=DETERMINISTIC`、`status=null`，从 semantic denominator 排除。

## 5. Capability-valid evaluator

P0 冻结 12 个独立 case；model input 与 oracle 物理分文件，并用每个 input 的 canonical SHA-256 绑定。loader 递归拒绝 oracle/status/action/reason/denominator 字段，测试再用 nested sentinel 防泄漏。

Case 覆盖：

- exact support；
- low-lexical paraphrase support；
- supported + unsupported；
- valid citation but wrong evidence；
- known conflict；
- required fact missing；
- correct insufficiency/refusal；
- non-assertive preface exclusion；
- supported + unverifiable future assertion；
- multi-claim/multi-citation support；
- citation-format-only deterministic blocker；
- out-of-workspace/kb provenance blocker。

动作分布为 `ACCEPT=5 / REVISE=3 / RETRIEVE=2 / CLARIFY=1 / REFUSE=1`。正确的 insufficiency/refusal 回答期望 `ACCEPT`；`REFUSE` 只用于当前答案不安全且 scope 已耗尽的 case。

Evaluator 输出九个有序 stage 的 `eligible/attempted/passed/reason` 与 `first_failed_stage`。每项 metric 单独报告 numerator/denominator/rate/N-A reason，不允许 weighted aggregate。12 是 case denominator，不会被错误复用为 semantic claim denominator；当前 semantic claim denominator 为 10。

ALWAYS_ACCEPT / ALWAYS_REVISE / ALWAYS_RETRIEVE / ALWAYS_CLARIFY / ALWAYS_REFUSE 均为 evaluator sanity control，不进入主 denominator，且每一种都必须触发至少一个 hard gate failure。

## 6. P0 DoD 与停止条件

- [x] 架构 audit 固化现有 loops、budget owner、flag、audit、测试与 failure semantics。
- [x] `EXISTING_CRITIC_PRESENT=YES` 与完整语义能力 `PARTIAL` 分开报告。
- [x] 定义 deterministic/semantic layer ownership。
- [x] 定义 12-case capability-valid contract 与硬负例。
- [x] 确定性 evaluator 与 first-failed-stage 测试落地。
- [x] 产品 runtime diff = 0。
- [x] Golden diff = 0。
- [x] Workflow diff = 0。
- [x] LM Studio/model run = 0。

P0 到此停止。现有 hidden retrieve/revise/recritic 的预算与 provenance 缺口、final-output boundary、cache/settings isolation 均未修复，因此不能进入 product experiment、real-local measurement 或 rollout。

## 7. 下一原子任务

仅进入 **W9 P1 — Critic Adapter Interface & Deterministic Preflight**：定义 eval-only adapter interface 和 deterministic preflight 的实现文档/测试，不接产品 runtime，不执行本地模型，不实现 retrieve/revise owner。

验收命令：

```powershell
cd D:\MyPrograms\rag-knowledge-platform\backend
$taskJwt=(Get-Content -LiteralPath ..\.env | Where-Object { $_ -like 'JWT_SECRET=*' } | Select-Object -First 1).Substring(11)
$env:JWT_SECRET=$taskJwt
.\.venv\Scripts\python.exe -m pytest tests\test_critic_w9_contract.py -q
.\.venv\Scripts\python.exe -m ruff check app\eval\critic_capability tests\test_critic_w9_contract.py
```
