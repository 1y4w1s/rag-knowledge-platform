# 01 — `state["content"]` → atomic claims & extraction strategy

> Design only. No scorer, no gold rewrite, no LLM.

## 1. What After actually is

Canonical product After（E-B15 / E-B4 `01`）:

```text
prepare_agent_generation → gen_plan
        ↓
_stream_generation_phase  (+ align when non-refusal)
        ↓
state["content"]   →  final_content_observation
state["citations"] →  final_citations
```

| Property | Rule |
|---|---|
| After body | **Only** stream-written `state["content"]` |
| Not After | `gen_plan` text, W9 fixture `answer`, Critic oracle, E-B6 `[eb6-synthetic:…]` wiring body as product faithfulness |
| Hash today (E-B15) | `after_content_hash = sha256:{canonical_json(content_string)}` |

Refusal After（empty-gate / fail-closed）= fixed `no_context_reply_for` + `citations=[]` → **T4 分母**，**不进** T2/T3 asserted 分母。

---

## 2. What Gold actually binds（E-B12B 事实）

正式 ledger `content_binding.content_sha256` **不是** After 正文的哈希。

物化实现（`w10_eb12b_claim_gold_materialization._synthetic_body_payload`）：

```text
content_sha256 = sha256_hex({
  "case_id": …,
  "kind": "synthetic_authored",
  "claim_texts": [claim_text, …]   # draft 人工命题列表
})
```

| Field | Current value |
|---|---|
| `content_binding.kind` | **always** `synthetic_authored` |
| Bound object | Canonical **claim_texts payload** |
| Bound object ≠ | Any product `state["content"]` string |
| Hash codec | Bare 64-hex（**无** `sha256:` 前缀） |
| C12 | `asserted_claims=[]`；排除 claim 分母 |

因此：**不能**用 `after_content_hash == gold.content_sha256` 直接判绑定成功。这是 After→Gold 边界的第一号硬缺口。

---

## 3. Mapping: content → atomic claims

### 3.1 Unit（继承 E-B8 `01`）

**Unit = one asserted factual claim**（可真假、原子、相对同次 gated 池可判定）。

| Is a unit | Is not a unit |
|---|---|
| Ledger `asserted_claims[].text` | Arbitrary punctuation-split sentences |
| Parallel facts → multiple claims | Whole refusal boilerplate |
| Fact with `[片段N]` still 1 claim | A single `final_citations` row |

### 3.2 Recommended mapping（formal）

```text
state["content"]  ──integrity──►  gold.asserted_claims[]
                      │
                      └── NOT: runtime extractor invents new claim set
```

**Formal segmentation authority = ledger.**  
After content is the **observed body under evaluation**；atomic claims are **not re-discovered** at score time.

Integrity gate（绑定闸的一部分，非切分）：

| Check | Pass | Fail |
|---|---|---|
| `case_id` match | Continue | Invalid |
| Binding policy BP-*（见 `03`） | Continue | Invalid / N/A |
| Optional: each `claim.text`（空白规范化后）可在 After content 中定位 | Continue | **Invalid**（金标相对该 After 不可审计） |
| Refusal boilerplate body | T2/T3 **N/A** | — |

这把「content 如何映射到 claims」钉死为：

1. **Lookup** ledger by `case_id`  
2. **Bind** under explicit BP policy（hash / presence / rebound）  
3. **Use** `asserted_claims` as the claim set  
4. **Do not** replace that set with a fresh extractor output for formal metrics

---

## 4. Claim extraction strategy

### 4.1 Options

| Option | Mechanism | Formal role | Verdict |
|---|---|---|---|
| **A. Ledger-as-segmentation** | Human（or same-write synthetic）claims are the only units | **Primary formal** | **Adopt** |
| **B. Deterministic sentence split** | `_SENTENCE_SPLIT` / 标点切句 | Assist annotation / research only | **Reject as formal gold or formal denom** |
| **C. Critic claim split** | Reuse Critic `_split_claims` | Control-plane tooling | **Forbid** for E-B T2/T3 |
| **D. LLM / NLI extraction** | Model invents claims | — | **Forbid**（至少至 formal 首窗） |
| **E. Lexical auto-claim from excerpts** | Copy evidence sentences as claims | Tempting for C01-style | **Forbid** as sole formal path（标注须人工负责） |

### 4.2 Chosen policy

```text
EXTRACTION_FORMAL = LEDGER_ONLY
EXTRACTION_ASSIST = optional deterministic split for human annotation UX only
EXTRACTION_RUNTIME_PRODUCT = never feeds formal T2/T3 denom
```

Implication for product After faithfulness windows:

| Path | Extraction implication |
|---|---|
| **Protocol scorability**（`synthetic_authored`） | Claims already authored；After body must satisfy BP-B（见 `03`） |
| **Product faithfulness**（`observed_after`） | Capture After **first** → human re-annotate / rebound ledger to that content hash → then score |
| **Zero-LLM degraded After**（E-B15 A2） | Content ≠ claim gold texts → **cannot** score T2/T3 without rebound or author-owned body that embeds claim texts |

### 4.3 What E-B15 After can / cannot feed today

| Capture mode | Content nature | T2/T3 vs current gold |
|---|---|---|
| A1 `product_stream_refusal` | Fixed no-context reply | **N/A**（correct；T4） |
| A2 `product_stream_degraded` | Provider-less degraded product text | **Incompatible** with E-B12B claim_texts binding |
| C12 `ineligible_no_after` | No After | **INELIGIBLE** |
| Future A4 live LLM（owner-authorized） | Real model After | Needs **new** `observed_after` gold rows bound to that hash |

---

## 5. Answers to research Q1–Q2

| # | Question | Answer |
|---|---|---|
| 1 | `state["content"]` 如何映射 atomic claims？ | 经 **binding gate** 挂到 ledger；atomic claims = `asserted_claims`；可选 substring integrity；**不是**对 content 再跑 extractor |
| 2 | claim extraction 策略？ | Formal = **ledger-only**；确定性切句仅辅助标注；禁 Critic/LLM/lexical-only 作 formal |

---

## 6. Stop

本文件不实现 scorer、不改 gold、不翻转门禁。
