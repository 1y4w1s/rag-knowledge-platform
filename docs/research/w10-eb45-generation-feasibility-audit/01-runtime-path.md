# 01 — Runtime path audit

> Trace only. No execution. No product changes.

## 1. Canonical chain（产品）

```text
_stream_agent_core / thorough path
        │
        ▼
run_react_loop  →  AgentRunOutcome.steps
        │
        ▼
prepare_agent_generation(db, query, steps, workspace_mode, outcome)
        │  finalize.merge_step_hits_to_chunks → gate_agent_chunks
        ▼
AgentGenerationPlan  (gated_chunks, citations, refusal, external_context)
        │
        ▼
_stream_generation_phase(..., gen_plan, state, ...)
  · refusal=true  → stream_no_context_reply
  · else          → LLM | degraded fragment stream
  · optional critic (default OFF) → may rewrite content / empty citations
  · non-refusal + gated → align_citations_to_answer
        │
        ▼
state["content"]    = assistant_content
state["citations"]  = aligned or [] (refusal / critic fail-closed)
yield SSE "done" { citations, ... }
```

生产调用点（ownership 证据）：

```1190:1239:backend/app/services/agent/stream.py
        gen_plan = await prepare_agent_generation(
            db,
            query=retrieval_query,
            steps=outcome.steps,
            workspace_mode=workspace_mode,
            outcome=outcome,
        )
        ...
        async for frame in _stream_generation_phase(
            db,
            message=message,
            gen_plan=gen_plan,
            outcome=outcome,
            ...
            state=state,
            ...
        )
```

终态写入：

```774:809:backend/app/services/agent/stream.py
    # F1：流式 citation 为候选；done/落库按正文 [片段N] 硬对齐（拒答跳过；漏标 keep-all）
    if (
        not critic_fail_closed
        and not active_plan.refusal
        and active_plan.gated_chunks
    ):
        ...
        citations = align_citations_to_answer(
            assistant_content,
            gated,
            to_citation=to_cite,
            strip_prefix=strip,
        )
    ...
    state["content"] = assistant_content
    state["citations"] = citations
```

---

## 2. File locations & function ownership

| Step | File | Symbol | Owner role |
|---|---|---|---|
| Plan construction | `backend/app/services/agent/finalize.py` | `prepare_agent_generation` · `gate_agent_chunks` · `AgentGenerationPlan` | Before 快照；L0 空闸 `refusal=not gated` |
| Hit merge / DB load | same | `merge_step_hits_to_chunks` · `_load_retrieved_chunks` | 依赖 `AsyncSession` + Document/Chunk ORM（测试可 monkeypatch `_load_retrieved_chunks`） |
| Generation phase | `backend/app/services/agent/stream.py` | `_stream_generation_phase` | **唯一**产品生成相；写 `state["content"]` / `state["citations"]` |
| Citation align | `backend/app/services/rag/citation_align.py` | `align_citations_to_answer` · `align_chunks_to_answer` | 非拒答路径终态裁剪；漏标 keep-all |
| Refusal copy | `backend/app/services/rag/generation.py` | `stream_no_context_reply` · `no_context_reply_for` | 空闸 / critic fail-closed 正文 |
| Degradation (no key) | `backend/app/services/rag/degraded_answer.py` | `stream_degraded_fragment_reply` | 无 chat key 时的非 LLM 流（**≠** 产品 faithfulness） |
| Orchestration caller | `backend/app/services/agent/stream.py` | `_stream_agent_core`（及同类 thorough 入口） | 先 ReAct，再 prepare，再 generation |

**Ownership 裁决（与 W9 P1 / E-B0 一致）：**  
Critic 为 advisory；`_stream_generation_phase` 是 recommendation/action 与终态 citation 的产品 owner。评测不得把 Critic oracle 当 After 金标。

---

## 3. Required dependencies（按路径）

### 3.1 `prepare_agent_generation`

| Dependency | Need |
|---|---|
| `AsyncSession` | 真实路径加载 chunk；E-A2 已用 `AsyncMock` + monkeypatch `_load_retrieved_chunks` |
| `steps: tuple[AgentStepRecord, ...]` | 带 chunk 命中的只读 tool 输出 |
| `workspace_mode` | 决定 citation 形状（workspace vs single-kb） |
| `filter_relevant_chunks` / `apply_kb_diversity` | gate 实现（产品内） |
| LLM | **不需要** |

### 3.2 `_stream_generation_phase`

| Dependency | Need |
|---|---|
| `gen_plan: AgentGenerationPlan` | 必填 |
| `state: dict` | 可变；函数末尾写入 content/citations |
| `outcome: AgentRunOutcome` | run_id / steps / critic 记账 |
| `assistant_message_id` · `user_id` | SSE done / 审计占位 |
| Chat provider key / `stream_deepseek_tokens` | 仅当非 refusal 且 degradation 要求 LLM 且 key 可用 |
| Critic | 仅 `settings.rag_critic_enabled`（默认 OFF） |
| DB persistence | 本函数注释：A2 不落库，由 core finally 收口；直调测试可用 `AsyncMock` |

### 3.3 `align_citations_to_answer`

| Dependency | Need |
|---|---|
| `answer: str` | 含可选 `[片段N]` |
| `chunks: list[RetrievedChunk]` | gated 池 |
| `to_citation` callable | `chunk_to_citation` / `workspace_chunk_to_citation` |
| LLM / DB | **不需要** |

---

## 4. Testability（先例）

| Pattern | Where | What it proves |
|---|---|---|
| Plan-only product path | `backend/tests/w10_ea2_scope_eligibility.py` · `execute_product_path_plan` | C01–C11 → 真实 `prepare_agent_generation`；C12 拒；**零 LLM** |
| Direct stream + mock DB | `backend/tests/test_dual_no_key_chat_degradation.py` · `_run_thorough_phase` | 直调 `_stream_generation_phase`；双无 key → 降级流；读 `state["content"]`/`state["citations"]` |
| Align unit | `backend/tests/test_citation_align.py` | shrink / keep-all 机械行为 |
| Production-path + patched tokens | `backend/tests/w9_critic_p2_r2_protocol.py` · `execute_production_path_case` | prepare → stream；**但**常 patch `stream_deepseek_tokens` 喂 fixture `answer` — **不得**当 E-B After 诚实源（E-B4 禁捷径） |

**结论：** 目标链在产品与测试两侧均可定位；E-B5 不必改 `backend/app` 即可 import / 调用这些符号（下划线私有函数已被多套件导入，先例充分）。

---

## 5. Align buckets（观察元数据，非主体）

| Condition | Align behavior | Suggested `align_bucket` |
|---|---|---|
| `refusal=true` | 跳过 align；citations 空 | `refuse_empty` |
| Critic fail-closed | citations `[]` | `fail_closed_empty` |
| 正文无合法 `[片段N]` | keep-all gated | `keep_all` |
| 有合法标记 | 按 similarity 升序映射裁剪 | `shrink` |

E-B 观察主体仍是 `state["content"]` + `state["citations"]`；plan citations 仅作 Before 对照。

---

## 6. Verdict

| Question | Answer |
|---|---|
| Path complete? | **Yes** — prepare → stream → align → state |
| Observation point honest? | After = generation-final；≠ E-A5 `plan_construction_citations` |
| Blocker for E-B5 path knowledge? | **None** |
