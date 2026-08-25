# 02 — Capture path & `state["content"]` / `state["citations"]` boundaries

## 1. Canonical product path（正式 After 必须对齐）

```text
eligibility (E-A1/E-A2; C12 refuse)
        │
        ▼
prepare_agent_generation  →  gen_plan     ← BEFORE
        │
        ▼
_stream_generation_phase(..., gen_plan, state, ...)
  · refusal=true  → stream_no_context_reply / 固定拒答；跳过 align
  · else          → (optional critic) → align_citations_to_answer
        │
        ▼
state["content"]  /  state["citations"]   ← AFTER (唯一产品终态)
        │
        ▼
E-B2 per_case: final_content_observation / final_citations
```

| Step | Anchor | Role |
|---|---|---|
| Prepare | `finalize.prepare_agent_generation` | Before；gate / refusal / plan citations |
| Stream | `stream._stream_generation_phase` | **唯一**产品生成相 |
| Align | `citation_align.align_citations_to_answer` | 非拒答且有 gated 时终态裁剪；漏标 keep-all |
| Capture | `state["content"]` / `state["citations"]`（约 `stream.py` 807–808） | E-B After 槽 |

E-A5 停在 prepare。E-B 必须越过 prepare。

---

## 2. Product write boundaries for After slots

| Condition | `state["content"]` | `state["citations"]` |
|---|---|---|
| `gen_plan.refusal=true` | 固定无依据话术族 | `[]`（不对齐满表） |
| Critic fail-closed | `no_context_reply_for` | `[]` |
| Normal + gated | 模型/降级正文 | `align_citations_to_answer` 结果 |
| Low confidence | 可能带 disclaimer 前缀 | align 时可 `strip_prefix` |
| Critic ON buffering | 缓冲后再写终态 | 与 done.citations 同对象语义 |

**边界纪律：**

- After 主体 = stream 结束时的 `state`，**不是** `gen_plan.citations`
- **不是** W9 fixture `answer` / Critic model-facing `citations`
- **不是** E-A5 `per_case_result` / `scope_compliance_pass`

---

## 3. E-B6 isomorphic path（当前唯一已实现 harness）

```text
execute_product_path_plan  →  gen_plan
        │
        ▼
author_owned_synthetic_content  ([eb6-synthetic:{case_id}] …)
        │
        ▼
align_citations_to_answer(synthetic, gated_chunks, …)   # refusal → citations=[]
        │
        ▼
state["content"] / state["citations"]  (in-memory harness dict)
```

| Property | Value |
|---|---|
| Uses real prepare | **Yes** |
| Uses real align | **Yes**（非拒答） |
| Uses `_stream_generation_phase` | **No** |
| `llm_called` | `false` |
| Honest for | **T1 wiring / align mechanics only** |
| Honest for T2/T3 product faithfulness | **No** |

---

## 4. Claim-gold binding vs After body（B2′ 交叉点）

| Artifact | Bound object | Hash meaning |
|---|---|---|
| E-B12B claim gold | `kind=synthetic_authored` · claim_texts payload | T2/T3 gold for **that** synthetic body |
| E-B6 isomorphic After | `[eb6-synthetic:…]` wiring body | **Different** text → different `content_sha256` |

**Implication:** annotated gold **does not** clear B2′. Even a future isomorphic formal unlock for T2/T3 must either:

1. Feed After content whose hash matches gold binding, **or**  
2. Rebind gold to authorized After hashes after capture  

Current E-B6 smoke bodies cannot score against E-B12B ledger as-is.

---

## 5. Empty-gate path note

| Item | Status |
|---|---|
| Cases material `w10-eb-empty-gate-cases.json` | **Present**（N=2 · REAL_ELIGIBLE） |
| Product prepare → refusal After mechanism | **Exists** in stream |
| E-B6 suite produces empty-gate After | **No**（runner = frozen-12 only） |
| S2 packaging authorized | **NO** |

T4 材料就绪 ≠ T4 After 已捕获 ≠ B2′ 清障。
