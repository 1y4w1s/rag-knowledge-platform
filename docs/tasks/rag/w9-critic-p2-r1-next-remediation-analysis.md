# W9 P2-R1 — C12 独立复核与下一门禁分析

> 日期：2026-08-24
> 边界：只读产品分析；无产品 runtime 修改；无外部模型执行；runtime rollout NO
> 最终裁决：**P2-R1 BLOCKED / MEASUREMENT_PROTOCOL_MISMATCH**

## 1. 结论

P2-R1 provisional artifact 在 C12 报告
`L6_BUDGET_SCOPE_PROVENANCE_CORRECT / PRODUCT_CONTROL_PLANE_FAILURE`，但独立复核不能确认这是生产可达的
产品故障。harness 直接把冻结的 foreign-KB evidence 放入内部 `_stream_generation_phase` 的
`gen_plan.gated_chunks`，同时 mock 了真实 tool dispatch；生产调用则先经过 scoped runtime steps 与
`prepare_agent_generation`。因此 C12 的 product-path eligibility 不成立。

该问题不是可在同一测量中修补并继续的 trivial plumbing：修正它会改变 product-path eligibility 与
safe-outcome scoring semantics。按 stop rule，P2-R1 最终为 **BLOCKED**，P3 不得启动，也不得据此启动产品修复。

独立 review correction：
`backend/tests/fixtures/l4_critic/w9-critic-p2-r1-independent-review.json`。

## 2. C12 原始观测

- 冻结 case：allowed `ws-main/kb-main`；唯一初始 evidence 为 `ws-other/kb-other`；oracle action 为
  `RETRIEVE_MISSING_EVIDENCE`，reason 为 `SCOPE_VIOLATION`。
- raw harness：retrieval 1、revision 1、post-revision validation 1；trajectory、audit、budget、EvidenceState
  均有记录。
- recovery 新命中本身属于 allowed KB；但 recovery merge 无条件保留旧 `active_plan.gated_chunks`，使 revision
  与 post-revision critic 同时看到 foreign + allowed chunks。
- 最终 citation 仍映射到 foreign KB。provisional scorer 只检查“最终正文不同于初始正文”，因此把该结果误记为
  `safe_outcome=true`；这是 evaluator false pass，不是跨库安全证明。

## 3. 生产路径与 harness 路径

### 生产路径

1. `run_react_loop` 的真实 tool dispatch 使用 `AgentToolScope`；semantic search 通过
   `resolve_kb_ids` 拒绝 forbidden KB。
2. `prepare_agent_generation` 只从成功的 `outcome.steps` 重载 chunks，再构造 `AgentGenerationPlan`。
3. `_stream_generation_phase` 消费该 plan。

关键位置：

- `backend/app/services/agent/stream.py:1171`、`:1190`、`:1221`
- `backend/app/services/agent/tools/scope.py:93`
- `backend/app/services/agent/tools/semantic_search.py:182`
- `backend/app/services/agent/finalize.py:49`、`:114`、`:146`

### 当前 P2-R1 harness 路径

1. 把每个 frozen evidence 直接转换为 `RetrievedChunk`；
2. 直接调用内部 `_stream_generation_phase`；
3. 把 C12 foreign chunk 手工放入 `gen_plan.gated_chunks`；
4. 使用 `MagicMock` tool scope，并 mock `_execute_step`。

关键位置：

- `backend/tests/w9_critic_p2_r1_harness.py:125`、`:195`、`:237`

因此 raw C12 只证明“非法内部 plan 被注入后，recovery merge 缺少纵深 scope 复核”，不能证明正常产品入口会产生
该 plan。

## 4. 潜在产品 defense-in-depth 缺口

尽管生产可达性未证实，raw probe 稳定揭示：

- `backend/app/services/agent/stream.py:910` 先用全部旧 `active_plan.gated_chunks` 初始化 `combined`，再追加
  scoped recovery chunks；
- `backend/app/services/agent/finalize.py:123` 的 `gate_agent_chunks` 只做 relevance/diversity/citation，不接收
  `AgentToolScope`，不重新授权；
- 污染后的 `revised_plan.gated_chunks` 同时进入 revision prompt、post-revision critic 与最终 citation alignment。

这是一个真实的纵深防御候选缺口，但当前证据只覆盖非法内部输入。它不能替代生产可达性证明。

## 5. 契约与接口缺口

冻结 P0 契约要求 deterministic critic 检查 workspace/kb/run provenance；当前产品接口无法完整承载：

- `run_critic(answer, chunks, query)` 没有 allowed KB/workspace/run context；
- `RetrievedChunk` 没有 workspace/run provenance；
- `CriticResult` / injected report 只有 action，没有 invalid evidence refs 或可执行 exclusion set。

因此 C12 的 frozen oracle 与真实 product critic adapter 之间存在结构性映射缺口。不能通过偷偷删除 C12、修改 oracle、
或把 pre-critic scope rejection 记成 oracle 的 retrieve action 来绕过。

## 6. 竞争假设

| 假设 | 裁决 |
|---|---|
| H1：harness 越过生产 scope/plan construction | **CONFIRMED_PRIMARY** |
| H2：recovery merge 缺少对已污染 plan 的纵深复核 | **CONFIRMED_SECONDARY**，本测量未证明生产可达 |
| H3：critic scope 契约超过当前接口能力 | **CONFIRMED_ARCHITECTURE_CONTRACT_GAP** |
| H4：bounded recovery 本身越权 | **REJECTED**；新检索命中属于 allowed KB |

## 7. 下一步可选方向（尚未授权实施）

### 方向 A：scope 是 `AgentGenerationPlan` 的前置不变量

修订 P2-R1 测量 adapter，使 C12 经过真实 scope rejection / plan construction，并明确 oracle action 如何映射；若无法在不改
冻结语义的前提下映射，C12 保持 `INVALID_FOR_PRODUCT_PATH_EXECUTION`，P2-R1 继续 BLOCKED。

### 方向 B：scope/provenance 成为 generation/recovery 的纵深不变量

引入显式 `CriticScopeContext` 或在 recovery merge 前使用真实 `AgentToolScope` 过滤旧 chunks；无法证明 scope 时 fail closed。
这可能影响 plan 类型、critic interface、workspace/run provenance 与所有生成入口，不能作为单行补丁处理。

## 8. 最小 plausible product fix（仅供评审）

若架构评审选择方向 B，最小候选是在 `_maybe_critic_retrieve_and_revise` 构造 `combined` 前：

1. 使用当前真实授权上下文重新验证旧 `active_plan.gated_chunks`；
2. 保留 allowed 旧 evidence，剔除 foreign evidence；
3. 追加同 scope recovery chunks；
4. 无可验证 evidence 时 fail closed；
5. 继续复用既有 relevance gate、一次预算、deadline、audit 与 post-revision validation。

仅按 KB ID 可覆盖当前 C12，但不能宣称解决同-KB跨 workspace 或 run provenance；不得作横向能力结论。

## 9. 必须保持的不变量

- `_stream_generation_phase` 仍是唯一 action owner；critic 只建议、不执行；
- retrieval 最多一次，共享 agent step budget 与 absolute deadline，transport retry=0；
- canonical step、EvidenceState、audit、hooks、latency 与 `critic_actions` 顺序保持；
- revision 后必须 revalidate；最终正文/citation/persist 来自同一候选；
- scope 无法证明时 fail closed，包括 `annotate_only`；
- `visible_kb_ids=None` 的现有“全部可见”语义不被误伤；
- 默认 flags OFF，Golden/workflow diff 0，runtime rollout NO。

## 10. 必需负向回归

1. 使用真实 `AgentToolScope` 与生产 plan construction，禁止仅靠 `MagicMock` 证明 scope；
2. foreign initial + allowed recovery：revision context、post-critic input、final citations 均必须是 allowed subset；
3. mixed initial：保留 allowed 旧 evidence，删除 foreign；
4. 全部旧 evidence foreign 且 recovery 空/失败：fail closed；
5. foreign chunk/document/doc name/excerpt 不得进入 SSE、done state 或 citation；
6. `visible_kb_ids=frozenset()` 全拒绝，`None` 保持既有 unrestricted 行为；
7. step=1、attempt=1、max_retries=0、retrieve→revision actions、两个 audit、validation=2 不回归；
8. post-revision critic failure/deadline 后不得发布 mutation；
9. evaluator 的 safe outcome 必须检查最终 citation scope，不能只比较正文变化。

## 11. 是否需要 Sol 级架构评审

- 只修测量协议：不需要额外产品架构评审；
- 若要把 provenance 纵深校验下沉到 finalize/critic/recovery：**需要一次窄范围 Sol-level 只读架构评审**。

在 owner 决议前，不实施产品修复、不运行 P3、不运行任何本地/外部模型。
