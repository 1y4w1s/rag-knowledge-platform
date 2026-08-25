# 05 — E-B5 readiness decision

## Decision

```text
E-B5_IMPLEMENTATION_READY = YES
```

**Interpreted scope（owner-confirmed this window）：**  
能否在 **不修改 `backend/app` / 不调 LLM / 不落正式观测结果** 的前提下，实现 E-B4 推荐的 **test-only After-window observation executor + 零 LLM 同构 T1**。

**Not decided here：**

```text
E-B_FORMAL_READY = NO          # still NO (E-B4)
E-B_NARROW_FORMAL_READY = NO   # executor/snapshots not yet landed
```

---

## 1. Why YES（positive evidence）

| Criterion | Evidence |
|---|---|
| Runtime path known & owned | `01`：prepare → `_stream_generation_phase` → align → `state[content/citations]` |
| Capture without product edits | `02`：E-A2 prepare + 直调 align；stream 直调先例已存在 |
| Suite inputs for T1 run | `03`：C01–C11 SUITABLE；C12 INELIGIBLE 已钉 |
| Envelope / claims frozen | E-B2 contract + validator module present |
| Construct boundary frozen | E-B4 `01` 禁止捷径 / 同构规则清晰 |
| Claim ledger not required for E-B5 start | `04`：T2/T3 后置；窄窗可不含 T2/T3 |
| Empty-gate fixture not required for E-B5 start | E-B4 推荐窗明确「不建 empty fixture」 |

---

## 2. Exact blockers — **none for E-B5 implementation**

对本窗定义的 E-B5，**无实现 blockers**。

若有人把「E-B5」误读成 Full formal observation，则下列仍为 **formal** blockers（**不是**本决策的 NO 理由）：

| ID | Blocker | Clears in |
|---|---|---|
| F1 | After executor 代码未落地 | E-B5 实现窗本身 |
| F2 | After 快照未产生 | E-B5+ 执行/冒烟后 |
| F3 | T2/T3 claim gold 文件与标注缺失 | 后续 claim-gold 窗 |
| F4 | T4 empty-gate research fixture 缺失 | E-B5b / fixture 窗 |
| F5 | `E-B2` `case_count=12` 与 empty 案的合同关系未修订 | 合同修订窗（若引入 empty） |

---

## 3. E-B5 implementation guardrails（给下一窗）

| Do | Don't |
|---|---|
| 新模块于 `backend/tests/`（建议旁路 `w10_eb2_*` 或后继） | 改 `backend/app` |
| Reuse E-A2 eligibility + `execute_product_path_plan` as Before | Reuse `artifact_from_execution` plan-as-final |
| 同构：author-owned body → real `align_citations_to_answer` | 回填 W9 fixture `answer`/`citations` |
| C12 → `INELIGIBLE` | `execute_frozen_case` / P2-R3 runner 身份 |
| `llm_called=false`；`targets_measured` 诚实 ⊆ T1 | 声称 quality / grounding / Critic validated |
| 可选：schema smoke only | 写 `FORMAL_OBSERVATION_RESULT` 且 `measurement_valid=true`（门禁仍 NO） |

---

## 4. Mapping to prior gates

| Prior | Status after this audit |
|---|---|
| E-B3 `E-B_FORMAL_READY` | Remains **NO** |
| E-B4 construct repair | Remains design-complete；落地仍缺 |
| E-B4.5 feasibility | **YES** for E-B5 implementation |
| P2-R1 | Remains **BLOCKED** |

---

## 5. Stop

```text
E-B5_IMPLEMENTATION_READY = YES
```

审计完成。下一窗才允许写 executor；本窗禁止实现与正式跑数。
