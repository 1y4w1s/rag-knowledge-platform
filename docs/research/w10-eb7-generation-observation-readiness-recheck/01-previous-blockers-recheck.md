# 01 — Previous blockers recheck

> Reclassify E-B3/E-B4 blockers B1–B4 after E-B6 landed.  
> Labels only: `RESOLVED` | `PARTIALLY_RESOLVED` | `BLOCKING`.

## Summary

| # | Blocker | Classification | Why |
|---|---|---|---|
| 1 | After-window executor | **RESOLVED** | E-B6 test-only module exists and captures After slots |
| 2 | After snapshots | **PARTIALLY_RESOLVED** | Isomorphic After 可写非 null；无产品 LLM After；无 reserved formal 快照 |
| 3 | T2/T3 independent claim gold | **BLOCKING** | Ledger 文件与标注仍缺 |
| 4 | T4 empty-gate fixture | **BLOCKING** | Research fixture 仍缺；`case_count=12` 合同未修订 |

---

## 1. After-window executor → **RESOLVED**

### Prior state (E-B3 B1 / E-B4 C1 / E-B4.5 F1)

E-B2 仅有 `validate_reserved_artifact` / schema example；无 After 产出入口。

### Evidence now

| Artifact | Status |
|---|---|
| `backend/tests/w10_eb6_generation_observation_executor.py` | Present（workspace；未要求本窗提交） |
| `backend/tests/test_w10_eb6_generation_observation_executor.py` | Present |
| Surface | `observe_case` · `run_isomorphic_observation_suite` · `capture_isomorphic_after` · `build_smoke_observation_artifact` |
| Path | E-A2 `execute_product_path_plan`（Before）→ author-owned body → real `align_citations_to_answer` → `state[content/citations]` |

满足 E-B4 C1 的「执行器存在」与 E-B4 `01` 允许的 **零 LLM 同构** 路径；C12 → `INELIGIBLE`；不调用 `execute_frozen_case`。

**Not claimed:** 产品 `_stream_generation_phase` 授权 LLM 路径已接通（E-B6 故意不做）。

---

## 2. After snapshots → **PARTIALLY_RESOLVED**

### Prior state (E-B3 B2)

Schema example 中 `final_content_observation` / `final_citations` 为 `null`；无生成终态快照。

### Evidence now

| Capability | Status |
|---|---|
| Runtime isomorphic After for C01–C11 | **Yes**（非 null content + citations；拒答路径 citations=`[]`） |
| C12 After fabricate | **Refused**（null After） |
| `observation_point` | `generation_final_content_and_citations` |
| `llm_called` honesty | `false` on isomorphic path |
| Persisted reserved formal result | **Absent**（`w10-eb2-generation-observation-result.json` 不存在） |
| Product-LLM After (`_stream_generation_phase`) | **Absent** |

**Why not RESOLVED:** C2「可写出」在同构冒烟意义上已通，但正式分母所需的 **诚实产品生成终态** 与 **reserved formal 落盘** 仍未具备；合成快照被 E-B6 显式标为非正式（`measurement_valid=false`）。

---

## 3. T2/T3 independent claim gold → **BLOCKING**

### Prior state (E-B3 B3 / E-B4 C3)

操作定义已冻；策略已选「独立人工 claim ledger」；文件未建。

### Evidence now

| Expected | Status |
|---|---|
| `backend/tests/fixtures/l4_critic/w10-eb-generation-claim-gold-v1.json` | **Absent** |
| Annotated ledger bound to After / synthetic hash | **Absent** |
| Critic oracle as substitute | **Still forbidden**（E-B2 hard reject） |

E-B6 将 `grounding_observation_status` 固定为 `NOT_OBSERVED`，且 `targets_measured ⊆ {T1}` —— 诚实排除 T2/T3，**不清除** Full formal 的 C3。

---

## 4. T4 empty-gate fixture → **BLOCKING**

### Prior state (E-B3 B4 / E-B4 C4)

冻结 12 无 empty-gate 分母；C04/C07 不可替代；fixture 仅设计。

### Evidence now

| Expected | Status |
|---|---|
| New empty-gate research fixture（例 `w10-eb-empty-gate-cases.json`） | **Absent** |
| Eligible case with empty retrieval / empty gated → `gen_plan.refusal=true` | **Absent** in frozen 12 |
| E-B2 `suite_id` / `case_count=12` contract revision for empty case | **Not done** |

E-B6 合成正文在 `gated_count<=0` 时有 empty-gate **字面** 模板，但这是同构作者正文，**不是** T4 分母 fixture。

---

## Mapping to E-B4 clearance checklist

| Condition | Cleared? |
|---|---|
| C1 After executor | **Yes**（isomorphic / test-only） |
| C2 After snapshots | **Partial** |
| C3 T2/T3 claim gold | **No** |
| C4 T4 empty-gate | **No** |
| C5 Envelope hygiene | **Yes**（见 `03`） |

**Full YES requires C1∧C2∧C3∧C4∧C5 → still false.**
