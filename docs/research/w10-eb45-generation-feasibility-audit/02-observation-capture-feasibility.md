# 02 — Observation capture feasibility

> Can a **test-only** observer capture After fields **without modifying `backend/app`**?

## 1. Capture targets（E-B2 slots）

| Target | Product source | E-B2 field |
|---|---|---|
| `gen_plan` | `prepare_agent_generation` → `AgentGenerationPlan` | `gen_plan_reference`（hash/id 对照）+ Before 元数据 |
| Final content | `state["content"]` after `_stream_generation_phase` | `final_content_observation` |
| Final citations | `state["citations"]`（对齐后） | `final_citations` |
| Refusal state | `gen_plan.refusal` + After content/citations 形状 | `refusal_observation_status` 等 |

---

## 2. Feasibility matrix（不改 `backend/app`）

| Capture mode | How（tests-only） | LLM | Honest After? | E-B5 suitable? |
|---|---|---|---|---|
| **A. Zero-LLM isomorphic**（E-B4 §2.3） | Reuse E-A2 `execute_product_path_plan` → author-owned `synthetic_content` → real `align_citations_to_answer` → fill After slots | No | Honest for **T1 / wiring** only；须标 `llm_called=false` | **Yes — E-B5 主路径** |
| **B. Stream refusal** | `gen_plan.refusal=true` → drain `_stream_generation_phase` → read `state` | No | Honest empty-gate / refuse path（需空闸 plan） | Yes for refusal smoke；T4 空闸案仍缺 fixture |
| **C. Stream degraded（no key）** | Patch dual-no-key → `stream_degraded_fragment_reply` | No | After 真写入 state，但是**降级正文**，非产品 chat faithfulness | 仅允许作机制冒烟；**不得**声称 generation quality |
| **D. Stream + patched tokens** | Patch `stream_deepseek_tokens` 喂文本 | No real provider | 技术上可写 state；若喂 W9 fixture `answer` → **观察点撒谎**（E-B4 禁止） | 仅当正文 **作者拥有** 且诚实标注 |
| **E. Live product LLM** | 真 key / LM Studio | Yes | 产品 After | **超出本 E-B5 窗**（需 owner 授权模型窗） |

**硬禁止（仍可行技术上，但契约失败）：**

| Shortcut | Why not |
|---|---|
| 把 `w9-critic-cases.json` 的 `answer`/`citations` 直接写入 After | Critic model-facing ≠ generation-final |
| `artifact_from_execution` 默认 `final = gen_plan.citations` | E-A3 `SCORED_NON_FINAL` |
| `execute_frozen_case` / foreign inject | P2-R1 harness-only |
| 改 `backend/app`「方便观测」 | 本轨禁止 |

---

## 3. Without modifying `backend/app` — detailed answer

### 3.1 `gen_plan` — **YES**

- 已有：`tests.w10_ea2_scope_eligibility.execute_product_path_plan`
- 依赖：monkeypatch `finalize._load_retrieved_chunks`；`AsyncMock` db
- 输出：完整 `AgentGenerationPlan`（含 `refusal`、`gated_chunks`、`citations`）

### 3.2 Final content / citations — **YES（同构路径）**

最小诚实伪代码（未来 E-B5；本窗不实现）：

```text
execution = await execute_product_path_plan(monkeypatch, case)  # Before
# C12 → stop; INELIGIBLE

synthetic = author_owned_body_for(case)   # NOT case["answer"] unless rebound as synthetic
aligned = align_citations_to_answer(
    synthetic,
    list(execution.gen_plan.gated_chunks),
    to_citation=workspace_chunk_to_citation,  # match workspace_mode
)
after_content = synthetic
after_citations = aligned
# map → per_case_observation; llm_called=false; targets_measured ⊆ {T1}
```

不需要调用 `_stream_generation_phase` 即可满足 E-B4 允许的 **零 LLM 同构 After**。

### 3.3 Final content / citations — **YES（直调 stream，零真实 LLM）**

先例：`test_dual_no_key_chat_degradation._run_thorough_phase` 直调 `_stream_generation_phase`，消费 async iterator 后读 `state`。

| 子路径 | 捕获 refusal? | 备注 |
|---|---|---|
| `refusal=True` plan | Yes — 固定无依据话术 + 空/非对齐 citations | 与产品空闸一致 |
| 有 gated + 无 key | Yes — 降级片段正文 + align | 诚实声明降级，勿当 L1 质量 |
| 有 gated + patch tokens（作者正文） | Yes | 须禁止默默使用 W9 fixture answer |

### 3.4 Refusal state — **YES**

| Signal | Source |
|---|---|
| Plan refusal | `gen_plan.refusal` |
| After empty citations on refuse | stream 拒答分支跳过 align |
| Copy family | `no_context_reply_for` / `stream_no_context_reply` |

冻结 12 案 **没有** plan-refusal 真值（E-A5 全 `plan_refusal=false`）；机制可测，T4 空闸分母仍缺新 fixture（见 `03`）。

---

## 4. What already exists vs what E-B5 must add

| Capability | Status |
|---|---|
| E-B2 `validate_reserved_artifact` | **Exists**（`w10_eb2_generation_observation_contract.py`） |
| E-A2 eligibility + prepare | **Exists** |
| `run_formal_observation` / After producer | **Missing**（E-B3 B1；E-B5 要写） |
| After snapshots on disk | **Missing**（B2） |
| Formal result file | **Must not create** in E-B5 unless narrow formal gate flipped；E-B4 建议仅 schema smoke |

缺失项均为 **tests/docs 侧实现**，不是 runtime 缺口。

---

## 5. Verdict

| Question | Answer |
|---|---|
| Capture gen_plan without `backend/app` change? | **YES** |
| Capture final content/citations without `backend/app` change? | **YES**（同构 align 为主；stream 直调为辅） |
| Capture refusal state without `backend/app` change? | **YES**（机制）；空闸案数据 **MISSING** |
| Must modify product runtime for E-B5? | **NO** |
