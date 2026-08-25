# 04 — Claim ledger feasibility

> Define attachment mechanics only. **No annotations. No gold file created.**

## 1. Purpose

E-B4 决议：T2/T3 金标 = **独立人工 claim ledger**（禁止 Critic oracle / LLM-as-judge / 纯词面重叠）。  
本文件审计：**ledger 如何挂到 case / After**，以及是否可在不改 `backend/app` 下落地。

---

## 2. Attachment model

```text
W9 case_id  ──run──►  After content (observed or synthetic)
                              │
                              ▼
                     content_sha256  (binding key)
                              │
                              ▼
              claim ledger row(s) for that case_id + hash
```

| Binding kind | When | Proves |
|---|---|---|
| `observed_after` | Real `_stream_generation_phase` After（授权模型窗） | T2/T3 on product path |
| `synthetic_authored` | E-B4 同构零 LLM 正文 | Protocol scorability only |

**Hash mismatch → T2/T3 该案无效**；不得静默沿用旧标注。

**禁止绑定：** 未声明 rebound 的 W9 fixture `answer`；Critic `oracle_cases` 行。

---

## 3. Required fields（规范意图，继承 E-B4 `02`）

### 3.1 File / identity

| Field | Required value / rule |
|---|---|
| Suggested path | `backend/tests/fixtures/l4_critic/w10-eb-generation-claim-gold-v1.json` |
| `protocol_version` | `w10_eb_generation_claim_gold_v1` |
| `parent_observation_protocol` | `w10_eb1_generation_observation_v1` |
| Forbidden keys | 同 E-B2 Critic/oracle 禁键列表 |

### 3.2 Per-case ledger entry

| Field | Type | Rule |
|---|---|---|
| `case_id` | string | W9 id 或未来 empty-gate id |
| `content_binding.kind` | enum | `observed_after` \| `synthetic_authored` |
| `content_binding.content_sha256` | string | 绑定 After / 合成正文 |
| `content_binding.synthetic_body_id` | string \| null | 同构正文稳定 id（可选） |
| `asserted_claims[]` | array | 事实命题列表 |
| `asserted_claims[].claim_id` | string | 稳定 id |
| `asserted_claims[].text` | string | 命题原文 |
| `asserted_claims[].span_optional` | object \| null | 可选字符跨度 |
| `asserted_claims[].label` | enum | `supported` \| `unsupported` \| `unverifiable` |
| `asserted_claims[].supporting_evidence_ids[]` | string[] | **仅**同次 gated 池 evidence/chunk id |
| `asserted_claims[].notes` | string | 可选 |
| `denominator_policy` | string | 至少 `exclude_refusal_boilerplate` |

### 3.3 T3 grounding（同 ledger 或并列块）

E-B4 `03`：grounded = **G1**（claim 在 gated excerpt 可定位）∧ **G2**（final citation / `[片段N]` 可指）。  
建议在 claim 行增加可选：

| Field | Rule |
|---|---|
| `grounding.g1_span_ok` | bool |
| `grounding.g2_citation_ok` | bool |
| `grounding.grounded` | `g1 ∧ g2`（或 artifact 脚注冻结的等价规则） |

---

## 4. Ownership

| Concern | Owner |
|---|---|
| Ledger schema + fixture file | Eval / research harness（`backend/tests/fixtures/...` + 可选 contract 模块） |
| Annotation authorship | Human annotator per protocol（E-B4 `02` §4） |
| Binding validation | Future test-only validator（对比 observation artifact `final_content_observation` hash） |
| Product runtime | **No ownership** — ledger 不得进入 `backend/app` |
| Critic control plane | **Not owner** — 禁键 |

---

## 5. Storage location

| Artifact | Location | Status today |
|---|---|---|
| Claim gold JSON | `backend/tests/fixtures/l4_critic/w10-eb-generation-claim-gold-v1.json`（建议） | **Absent**（故意） |
| Construct design | `docs/research/w10-eb4-.../02-t2-...` · `03-t3-...` | Present |
| Observation results | `w10-eb2-generation-observation-result.json` | Reserved；未创建 |
| Critic oracle | `w9-critic-capability-contract.json` | Present；**禁止 reuse** |

---

## 6. Feasibility vs E-B5

| Question | Answer |
|---|---|
| Can ledger attach without `backend/app` changes? | **YES** — pure fixture + test validators |
| Does E-B5 need ledger to start? | **NO** — E-B5 窄窗默认 `targets_measured ⊆ {T1}` |
| Does Full / T2–T3 formal need ledger? | **YES** — C3 blocker until annotated rows exist |
| Annotations this window? | **None** |

---

## 7. Verdict

手工 claim ledger **挂接可行**：按 `case_id` + `content_sha256` 绑定 After；存测试夹具；产品零改动。  
**本窗不创建文件、不标注。** 不构成 E-B5 实现 blockers；构成后续 T2/T3 正式窗 blockers。
