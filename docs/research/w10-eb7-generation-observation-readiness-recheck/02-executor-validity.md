# 02 — Executor validity

> Confirm E-B6 After executor remains a legal observation harness — not a product or formal-evidence path.

## Verdict

| Check | Result |
|---|---|
| test-only | **PASS** |
| no `backend/app` change | **PASS** |
| real generation path boundary preserved | **PASS** |
| synthetic content cannot become formal evidence | **PASS** |

---

## 1. test-only

| Fact | Evidence |
|---|---|
| Module location | `backend/tests/w10_eb6_generation_observation_executor.py` |
| Tests location | `backend/tests/test_w10_eb6_generation_observation_executor.py` |
| Imports product symbols | Read-only use of `align_citations_to_answer` / `workspace_chunk_to_citation` / E-A2 prepare |
| Product entrypoints / routers / services edited | **None in this track**（本复核未见 E-B6 对 `backend/app` 的 diff） |

Executor 是测试侧捕获器，不是产品 runtime 组件。

---

## 2. no backend/app change

Static review of E-B6 surface:

- 无对 `backend/app/**` 的写入/补丁
- 不修改 `prepare_agent_generation` / `_stream_generation_phase` / Critic 控制面
- 不解除 P2-R1（artifact 强制 `p2_r1_status=BLOCKED` ∧ `does_not_unblock_p2_r1=true`）

---

## 3. Real generation path boundary preserved

E-B4 `01` 区分：

| Path | Allowed for | E-B6 status |
|---|---|---|
| Canonical：prepare → `_stream_generation_phase` → After | 产品生成终态正式观察 | **Not implemented**（故意） |
| Allowed isomorphic：prepare → author body → real align → After | T1 / wiring；须 `llm_called=false` | **Implemented** |
| Forbidden：W9 fixture `answer`/`citations` 回填 | — | **Guarded**（`_assert_not_fixture_answer` + prefix body） |
| Forbidden：E-A5 plan citations as final | — | **Not used**（不经 `artifact_from_execution` plan-as-final） |
| Forbidden：`execute_frozen_case` / P2-R3 runner | — | **Not called** |

边界结论：E-B6 **没有**把同构路径伪装成产品 stream After；也没有打开未授权 LLM / LM Studio。

---

## 4. Synthetic content cannot become formal evidence

Hard locks in E-B6:

| Lock | Behavior |
|---|---|
| `build_smoke_observation_artifact` | Always `measurement_valid=false`；`invalid_reasons` 含 `OTHER_PROTOCOL_BREAK` |
| `notes` | Explicit「Not a formal generation observation」 |
| `write_observation_artifact` | Refuses `measurement_valid=true` |
| Reserved path | Refuses write to `w10-eb2-generation-observation-result.json` |
| `llm_called` | Forced / required `false` |
| `targets_measured` | Smoke ⊆ `{T1}` only |
| `grounding_observation_status` | `NOT_OBSERVED`（不假装测了 T2/T3） |

因此：**合成正文可以证明接线与 T1 align 槽可填充，但不能作为正式测量证据落 reserved formal result。**

---

## 5. What this does *not* unlock

| Unlock | Status |
|---|---|
| Full `E-B_FORMAL_READY` | Still **NO** |
| Writing reserved formal result | Still **blocked** |
| Claiming generation quality / grounding / Critic validated | Still **forbidden** |
| Treating isomorphic After as product faithfulness | Still **forbidden** |
