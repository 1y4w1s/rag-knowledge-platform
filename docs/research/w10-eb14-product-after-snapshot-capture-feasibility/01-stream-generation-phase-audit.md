# 01 — `_stream_generation_phase` audit

> Trace only. No execution. No product changes.

## 1. Call entry points

| Caller | File | Role for E-B After |
|---|---|---|
| `_stream_agent_core`（thorough chat） | `backend/app/services/agent/stream.py` ≈1190–1240 | **Canonical product path**：`prepare_agent_generation` → `_stream_generation_phase` → `state` |
| Direct test imports | `tests/test_dual_no_key_chat_degradation.py` · `test_chat_degradation.py` · `w9_critic_p2_r2_protocol.execute_production_path_case` · 多套 W9 critic 单测 | **Harness 可直调**；drain async iterator 后读 `state` |
| Edit-mode renderer | `stream.py` ≈1523 `prepare_agent_generation` only | **不是** generation After：确定性 debrief / approval，不进 `_stream_generation_phase` |

**Ownership（W9 P1 / E-B0）：** Critic advisory；`_stream_generation_phase` 是 recommendation/action 与终态 citation 的产品 owner。

```text
_stream_agent_core
        │
        ▼
prepare_agent_generation  →  gen_plan     ← BEFORE
        │
        ▼
_stream_generation_phase(..., gen_plan, state, ...)
        │
        ▼
state["content"] / state["citations"]     ← AFTER（唯一产品终态）
yield SSE "done" { citations, ... }
```

E-A5 / E-B6 isomorphic 停在 prepare+synthetic align；**产品 After** 必须越过 prepare 进入本函数（或经本函数同一写入点）。

---

## 2. Input dependencies

| Input | Required? | Notes |
|---|---|---|
| `gen_plan: AgentGenerationPlan` | Yes | From real `prepare_agent_generation` for product honesty；禁 P2-R1 foreign inject |
| `state: dict` | Yes | 可变；函数末尾写入 After 槽 |
| `outcome: AgentRunOutcome` | Yes | run_id / steps / critic 记账 |
| `message` · `user_id` · `assistant_message_id` | Yes | 拒答文案 / SSE done / 审计占位 |
| `db: AsyncSession` | Yes（签名） | 本函数 A2：**不落库**；直调可用 `AsyncMock` |
| Chat provider / `stream_deepseek_tokens` | Conditional | 仅 `refusal=false` 且 `degradation_requires_llm` 且 `has_available_chat_provider_key` |
| Critic | Conditional | `settings.rag_critic_enabled` 默认 **OFF** |
| `history` / window / workspace / tool_scope | Optional | LLM 路径才拼 prompt；降级/拒答可跳过 |

**分支（影响 After 诚实标签）：**

| Branch | Token source | Align? | After honesty |
|---|---|---|---|
| `gen_plan.refusal=true` | `stream_no_context_reply` | Skip | **Product refuse path**（零 LLM） |
| No key / degradation | `stream_degraded_fragment_reply` | Yes if gated | **Mechanism After**；≠ chat faithfulness |
| LLM available | `stream_deepseek_tokens` | Yes if gated | **Product chat faithfulness**（需授权模型窗） |
| Critic fail-closed | `no_context_reply_for` | Citations `[]` | Product fail-closed（Critic ON 时） |

---

## 3. State write points

终态写入（唯一 E-B After 主体）：

```806:818:backend/app/services/agent/stream.py
    # A2：落库信息交给 core finally（finalize_turn 单次 commit），此处仅记录状态。
    state["content"] = assistant_content
    state["citations"] = citations
    state["retrieval_duration_ms"] = retrieval_duration_ms
    state["outcome"] = outcome

    yield _sse_event(
        "done",
        {
            "message_id": str(message_id),
            "citations": citations,
            ...
        },
    )
```

| Slot | Written when | E-B2 mapping |
|---|---|---|
| `state["content"]` | Always before `done` | `final_content_observation` |
| `state["citations"]` | Always（拒答/fail-closed → `[]` 或跳过 align） | `final_citations` |
| SSE `done.citations` | Same object semantics as `state["citations"]` | Cross-check only；主体仍是 `state` |

**Not After：** `gen_plan.citations` · W9 fixture `answer`/`citations` · E-A5 `scope_compliance_pass` · Critic oracle。

---

## 4. Can a test harness capture Without `backend/app` change?

**YES.**

先例充分：

| Precedent | What it does | After readable? |
|---|---|---|
| `_run_thorough_phase`（dual-no-key / chat degradation） | 直调 `_stream_generation_phase`；`AsyncMock` db；读 `state["content"]`/`citations` | Yes |
| `execute_production_path_case`（P2-R2） | `prepare_agent_generation` → drain stream；读 `state` | Yes（常 patch tokens；不得默默当 E-B 金标） |
| E-B6 isomorphic | prepare + synthetic + align；**不**调 stream | Wiring only — **not** product stream After |

捕获最小形状（未来实现窗，本窗不写代码）：

```text
execution = await execute_product_path_plan(...)   # Before · E-A2
# C12 → INELIGIBLE; stop
state = {}
async for _ in _stream_generation_phase(..., gen_plan=execution.gen_plan, state=state, ...):
    pass
after_content = state["content"]
after_citations = state["citations"]
# → E-B2 per_case slots · honest llm_called / capture_mode labels
```

**硬禁捷径（仍技术可做，契约失败）：**

- P2-R1 `execute_frozen_case` / foreign `gated_chunks` inject  
- 静默喂入 W9 fixture `answer` 当产品正文  
- 改 `backend/app` 仅为「好测」
