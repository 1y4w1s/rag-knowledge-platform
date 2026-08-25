# 02 — Eligibility rules（资格规则）

> 资格在**执行前**判定。不合格 case 不得进入产品路径分母，也不得用其 Critic action 对错声称产品控制面 PASS/FAIL。

## 判定材料（无模型）

只读以下来源即可分类，**禁止**为资格调用 LLM / 外部模型：

1. 冻结 case：`backend/tests/fixtures/l4_critic/w9-critic-cases.json`
2. 冻结 oracle：`backend/tests/fixtures/l4_critic/w9-critic-capability-contract.json`（只用于「是否存在冻结语义」，不用于改写）
3. 入口身份：将要调用的是 `execute_frozen_case`（注入）还是「真实 `AgentToolScope` + `prepare_agent_generation`」
4. 本目录规则

P2-R2 的 `assess_case_product_path_eligibility` 是同构草稿，后续 I 应对齐本文件，而不是对齐 P2-R1 注入路径。

## 合法产品路径 case（valid product-path case）

必须 **全部** 为真：

| ID | 规则 |
|---|---|
| E1 | **生产等价入口**：证据进入生成相之前，经过 `run_react_loop` 的真实 tool dispatch **或** 与之同构的 steps→`prepare_agent_generation` 构造，而不是把 `RetrievedChunk` 写进内部 `gen_plan.gated_chunks`。 |
| E2 | **真实 scope**：`AgentToolScope` 为真实实例（`visible_kb_ids` 来自 case `allowed_kb_ids`）。禁止用 `MagicMock()` 当 scope 证明。 |
| E3 | **合法证据路径**：初始 evidence 的 `kb_id` ⊆ case `scope.allowed_kb_ids`，且 `workspace_id` 与 allowed workspace 一致（C01–C11：`ws-main` / `kb-main`）。`provenance` 为 `current_run_retrieval`（或等价「本 run 检索」），不是 `foreign_workspace_fixture`。 |
| E4 | **无直注入**：`direct_foreign_injection = false`。 |
| E5 | **Plan-front**：`AgentGenerationPlan.gated_chunks` 仅来自成功 scoped steps 的重载+gate。 |
| E6 | **终态计分**：对 `state["citations"]` / done 列表计分，且检查 citation scope（见 `04`），不只比正文 diff。 |
| E7 | **Critic 若跑**：只作 advisory 输入；不得把「Critic 看见 foreign chunk」当作产品隔离失败，除非该 plan 本身满足 E1–E5。 |

C01–C11 在 **fixture 静态检查** 下满足 E3；若执行器满足 E1–E2、E4–E7，则计为 valid product-path。

## 非法 harness-only case（invalid harness-only）

任一为真即 **不能** 进入产品路径分母：

| ID | 规则 |
|---|---|
| H1 | 调用 P2-R1 `execute_frozen_case`：直调 `_stream_generation_phase` + `gated_chunks=initial_chunks`。 |
| H2 | `tool_scope=MagicMock()` 或 mock `_execute_step` **替代**真实 `resolve_kb_ids` deny。 |
| H3 | 把 `kb_id ∉ allowed` 或 `workspace_id` 外的 chunk **预装**进 `AgentGenerationPlan`。 |
| H4 | 模式标为 `DEFENSE_IN_DEPTH_PROBE` / 纵深探针，却把结果写入产品 `pass_rate` 分母。 |
| H5 | 仅因「正文相对初始答案变了」记 `safe_outcome=true`。 |
| H6 | 为让 Critic 看见 SCOPE_VIOLATION，故意在 plan-front 之后补回 foreign evidence。 |

此类结果可保留为 **探针观察**（H2 纵深缺口，EXPERIMENTAL），标签必须是探针，不是 `PRODUCT_CONTROL_PLANE_FAILURE`。

## 为何 C12 类 harness 注入对产品路径测量无效

冻结 C12（`C12-out-of-scope-provenance`）：

- allowed：`ws-main` / `kb-main`
- 唯一 evidence：`ws-other` / `kb-other`，`provenance=foreign_workspace_fixture`
- 冻结 critic oracle：`RETRIEVE_MISSING_EVIDENCE` + `SCOPE_VIOLATION`（fixture 字段名以 contract 为准）

Direction A：**合法 scope 是 plan construction 的前置不变量**。产品路径上：

1. `AgentToolScope.resolve_kb_ids` 对 forbidden KB 返回 `ToolDenial`（或根本不检索该库）；
2. `prepare_agent_generation` 只重载成功 steps 的 hits → **不会**把 `kb-other` 装进 `gated_chunks`；
3. 因此 `_stream_generation_phase` 在合法入口下 **不会**以「foreign-only gated plan」为输入。

P2-R1 所做的是跳过 1–2，把 foreign chunk 交给 3。这证明的是：

> 在**已经非法**的内部 plan 上，recovery merge / 终态 citation 仍可能带出 foreign KB。

这不是「用户请求经 AgentToolScope 后隔离失败」。独立复核 H1 = **CONFIRMED_PRIMARY**。故 C12 的该执行 **invalid for product-path execution measurement**。

## 静态分类算法（无模型）

对冻结套件每个 case：

```text
allowed_kbs := set(case.scope.allowed_kb_ids)
allowed_ws  := case.scope.workspace_id
foreign := evidence where kb_id ∉ allowed_kbs OR workspace_id ≠ allowed_ws
         OR provenance ∈ {foreign_workspace_fixture, foreign_workspace_fixture}
scoped  := evidence \ foreign

if planned_entry is inject_gated_chunks or MagicMock_scope:
    → INVALID_FOR_PRODUCT_PATH_EXECUTION (harness-only)
elif scoped empty and foreign non-empty:
    → INVALID_FOR_PRODUCT_PATH_EXECUTION
      reason: fixture cannot admit a legal AgentGenerationPlan without changing frozen evidence
      (C12)
elif foreign empty and scoped non-empty:
    → valid product-path (C01–C11)
elif both non-empty:
    → 本冻结套件当前不存在；若未来出现：产品路径只允许 scoped 子集进入 plan；
      若 oracle 要求 critic 在混合 plan 上见 foreign，则 oracle 不可映射，整案 INVALID
else:  # both empty
    → 无证据拒答类：须单独对照 oracle（C07 类已在套件内且 scoped 语义不同，按 C01–C11 通道）
```

**今天的套件：** 仅 C12 落入 `scoped empty ∧ foreign non-empty`。无混合 evidence 对等案。

## 执行器绑定

| 意图 | 允许的执行器 | 分母 |
|---|---|---|
| 产品路径测量 | 真实 `AgentToolScope` + `prepare_agent_generation`（P2-R2 `execute_production_path_case` 方向） | 仅 E1–E7 为真的 case |
| 纵深探针 | `execute_frozen_case` / DEFENSE_IN_DEPTH_PROBE | **不计**产品分母；不得解阻 P2-R1 |

## 禁止的资格把戏

- 删掉 C12 使 11/11 变成「12 案全过」。
- 把 pre-critic scope rejection 记成冻结 oracle 的 `RETRIEVE_MISSING_EVIDENCE`。
- 开着注入路径却设 `product_path_eligible=true`。
- 用 Critic 接口缺口（H3）当产品 FAIL。
