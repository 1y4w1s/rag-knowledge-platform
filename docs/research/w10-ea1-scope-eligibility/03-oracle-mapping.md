# 03 — Oracle mapping（Oracle 映射）

> 冻结 oracle 是能力契约，不是可以悄悄改的答案键。Direction A 下，**看不懂映射就保持 INVALID**，不要发明产品 PASS。

## 冻结 oracle 是什么

来源：`backend/tests/fixtures/l4_critic/w9-critic-capability-contract.json` 的 `oracle_cases`。  
C12 条目（语义；字段名以文件为准）：

- `case_id`: `C12-out-of-scope-provenance`
- `critic_pass`: false
- `expected_action`: `RETRIEVE_MISSING_EVIDENCE`
- `expected_reason_code`: `SCOPE_VIOLATION`
- claim 引用越权 evidence（fixture `E-OUT`）；`decision_owner=DETERMINISTIC`

该 oracle 的**假设世界**是：Critic（或确定性前置）**已经看见**越权 evidence，并因此建议检索缺失的 **in-scope** 证据。

Direction A 的**产品世界**是：越权 evidence **不得**成为 `AgentGenerationPlan` 成员，Critic 作为 advisory **不是**隔离所有者。两个世界不对齐时，不能把产品路径上的「空 plan / 拒答 / 仅 in-scope 检索」**默认为**打中了 `RETRIEVE_MISSING_EVIDENCE`。

## 何时原 oracle 仍有效

原 oracle 仍可作为产品路径打分键，当且仅当：

1. Case 满足 `02` 的 valid product-path；**并且**
2. 冻结动作/理由是 **plan-front 之后仍可观察** 的控制面行为（Critic 建议 + stream 执行），而不是「本不该存在的 foreign plan」；**并且**
3. 不需要给 Critic 增加 provenance 字段（H3）才能表达该动作。

**C01–C11：** 全部为 in-scope `current_run_retrieval`。P2-R1 独立复核在 **11 个 product-path-valid** 上 action mapping / orchestration 为 11/11。本协议规定：**C01–C11 原 oracle 保持有效**，后续产品路径执行应继续对照同一冻结动作，不得借 C12 协议修复改写它们。

## 何时必须保持 `INVALID_FOR_PRODUCT_PATH_EXECUTION`

对某一冻结 case，下列任一成立则 **不得** 在产品路径上判 PASS/FAIL 打进 P2-R1 分母：

| 条件 | 解释 |
|---|---|
| M1 | 唯一/必要 evidence 无法经 `AgentToolScope` + `prepare_agent_generation` 进入 plan（C12 foreign-only）。 |
| M2 | 打分需要「Critic 输入含 foreign chunk」或「invalid evidence refs」，而现网 `run_critic(answer, chunks, query)` 无 allowed-KB 上下文（H3）。为对齐去改冻结语义 = 静默改 oracle。 |
| M3 | 唯一能「打中」oracle 的办法是恢复 P2-R1 注入（H1）。 |
| M4 | 把 plan-front 拒绝、空 `gated_chunks`、无依据拒答、或 scoped 再检索 **改贴标签** 成 `SCOPE_VIOLATION` + `RETRIEVE_MISSING_EVIDENCE`，未另开契约冻结窗。 |

**C12 在本协议下的默认分类：`INVALID_FOR_PRODUCT_PATH_EXECUTION`。**  
这不是产品隔离已修好，也不是产品隔离已证伪；这是 **诚实缺口**：冻结 critic-oracle 与 Direction A 产品路径观察量不一致。

W10 Decision 已写明该 stop rule（**PROVEN**）：无法在不改冻结语义下映射 → 保持 INVALID，P2-R1 继续 BLOCKED。

## 允许的未来映射（本窗不实施、不冻结新 oracle）

仅当**单独**的契约窗明确改写 C12 的产品路径观察量之后，才可离开 INVALID。候选（均为 **EXPERIMENTAL**，未授权）：

| 候选产品路径观察 | 能否冒充当前冻结 oracle |
|---|---|
| Scope deny + 空 plan + 无依据拒答 | **否**（动作不是 RETRIEVE_MISSING_EVIDENCE） |
| Scope deny 后仅在 allowed KB 上检索 | **否**（除非新契约把「计划前检索」定义为该动作，且不再要求 foreign claim refs） |
| Critic 仍输出 SCOPE_VIOLATION 但输入无 foreign chunk | **否**（与确定性「看见 E-OUT」冲突） |
| 保持探针路径专测 merge 再授权 | 合法 **探针**，非法 **产品分母** |

在新契约冻结前，执行器应对 C12 输出：

```text
product_path_eligible: false
classification: INVALID_FOR_PRODUCT_PATH_EXECUTION
# 或现用等价：MEASUREMENT_PROTOCOL_INVALID / PRODUCT_PATH_ELIGIBILITY_PRECONDITION
first_failed_stage: PRODUCT_PATH_ELIGIBILITY_PRECONDITION
oracle_mapping: UNMAPPED_UNDER_DIRECTION_A
```

不得填写 `PRODUCT_CONTROL_PLANE_FAILURE`。

## 对等 case 映射表（当前冻结 12 案）

套件：`w9-critic-cases.json`。无第二例 foreign-only。P3 construct：`PROTOCOL_INVALID_SHORT_IDS = ("C12",)`。

| case_id | 静态资格 | 原 oracle | Direction A 产品路径 |
|---|---|---|---|
| C01-fully-supported-exact | valid | 保持 | 可执行、可对照 |
| C02-supported-paraphrase-low-lexical | valid | 保持 | 可执行、可对照 |
| C03-one-unsupported-among-supported | valid | 保持 | 可执行、可对照 |
| C04-valid-citation-wrong-evidence | valid | 保持 | 可执行、可对照 |
| C05-known-conflict-overcertain | valid | 保持 | 可执行、可对照 |
| C06-required-fact-missing | valid | 保持 | 可执行、可对照 |
| C07-correct-insufficiency-refusal | valid | 保持 | 可执行、可对照 |
| C08-nonassertive-preface-supported-fact | valid | 保持 | 可执行、可对照 |
| C09-supported-plus-unverifiable | valid | 保持 | 可执行、可对照 |
| C10-supported-multiclaim-multicitation | valid | 保持 | 可执行、可对照 |
| C11-citation-format-only-defect | valid | 保持 | 可执行、可对照 |
| **C12-out-of-scope-provenance** | **invalid** | **不映射** | **`INVALID_FOR_PRODUCT_PATH_EXECUTION`** |

Golden / retrieval Hit@3（`test_retrieval_golden.py`）**不是** C12 对等案：它们不注入 `AgentGenerationPlan.gated_chunks`，不进入本协议分母。

P3 semantic construct 把 C12 放在 `PROTOCOL_INVALID` 且 **不得进入 L1 分母**——与本协议一致；不得解释为「C12 产品 FAIL」。

## 无模型如何标 C12 / 对等案

不跑生成、不跑 Critic 模型：

1. 读 `w9-critic-cases.json` 的 `scope` 与 `evidence`。
2. 应用 `02` 静态算法。
3. C12 → INVALID + `oracle_mapping=UNMAPPED_UNDER_DIRECTION_A`。
4. C01–C11 → valid；oracle 行仍用 capability-contract 原动作。
5. 若某执行日志显示 `MagicMock` / `gated_chunks=initial_chunks`（C12 foreign）→ 无论产物如何，覆盖为 harness-only invalid。

## 本文件不声称

- 不声称已存在「C12 产品路径 oracle」。
- 不授权修改 `w9-critic-capability-contract.json`。
- 不因 11/11 有效案而解阻 P2-R1（12 案冻结套件仍缺诚实的第 12 个产品路径观察量）。
