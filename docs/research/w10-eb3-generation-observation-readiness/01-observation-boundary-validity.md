# 01 — Observation boundary validity

> Dimension 1. Verify Before / After cut and that E-A5 objects are not reused as generation results.

## 1. Before boundary（生成前基线）

| Required object | Code / protocol anchor | Status |
|---|---|---|
| `gen_plan` (`AgentGenerationPlan`) | `backend/app/services/agent/finalize.py` · `class AgentGenerationPlan` | **VALID** |
| `gated_chunks` | `AgentGenerationPlan.gated_chunks` | **VALID** |
| plan citations | `AgentGenerationPlan.citations` | **VALID**（E-A5 主打分对象） |
| refusal state | `AgentGenerationPlan.refusal`（`gate_agent_chunks`：`refusal=not gated`） | **VALID** |

E-B1 `01-observation-boundary.md` 将上述钉为 **观察窗口左边界（含）**。本窗复验：字段在生产类型上存在；E-A5 正式结果对 C01–C11 记录了 `plan_refusal=false` 与 `scorer_observation_point=plan_construction_citations`。

## 2. After boundary（生成后主对象）

| Required object | Code / protocol anchor | Status |
|---|---|---|
| `state["content"]` | `backend/app/services/agent/stream.py` · `_stream_generation_phase` 末尾写入 | **VALID**（机制存在） |
| `state["citations"]` | 同文件；与 SSE `done.citations` 同对象语义 | **VALID**（机制存在） |
| `align_citations_to_answer` output | `backend/app/services/rag/citation_align.py`；在非拒答且有 gated 时裁剪终态列表 | **VALID**（机制存在；漏标 → keep-all） |

E-B1 钉死：**主观察对象是 After，不是 plan citations。** 若把 `gen_plan.citations` 单独当终态分母，会重犯 E-A3「错观察点」（`SCORED_NON_FINAL`）。

### 时间切分（继承 E-B1，本窗确认未漂移）

```text
prepare / gate → gen_plan (BEFORE)
        ↓
_stream_generation_phase (+ optional critic)
        ↓
align_citations_to_answer（非拒答路径）
        ↓
state["content"] + state["citations"] (AFTER)
```

## 3. E-A5 objects must not be generation results

| E-A5 object | May be used as | Must not be used as |
|---|---|---|
| `observation_point=plan_construction_citations` | L0 Before 对照 / `parent_l0_artifact` 文件名引用 | generation-final PASS 证据 |
| `scope_compliance_pass` | plan ⊆ scope 历史记录 | `scope_compliance_result` 冒充终态 |
| `per_case_result[]` | E-A5 信封专有数组 | E-B2 `per_case_observation` |
| E-A5 `11/11` | plan-construction citation scope compliance | T1–T4 通过率 / grounding |

**Deterministic separation check（本窗）：** 将 `w10-ea4-formal-window-result.json` 传入 E-B2 `validate_reserved_artifact` → **拒绝**（检测到 `per_case_result`、`adapter_protocol_version` 等外键）。

**结论：** Before/After 边界在协议与代码锚点上 **仍然成立**；E-A5 工件 **不能**、也 **未被** 校验器接受为 generation observation 结果。

## 4. Boundary validity verdict

| Check | Verdict |
|---|---|
| Before objects named and anchored | **PASS** |
| After objects named and anchored | **PASS**（机制 PROVEN；观测值未产生） |
| E-A5 ≠ generation result | **PASS**（协议钉死 + validator 拒绝） |
| Ready to *observe* After in a formal run | **FAIL** — 见 blocker：无 executor、无 After 快照（维度 5） |

边界定义 **有效** ≠ 正式观测 **可执行**。
