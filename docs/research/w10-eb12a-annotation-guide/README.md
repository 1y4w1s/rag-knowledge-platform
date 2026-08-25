# W10 E-B12A-2 — Human Annotation Workflow Guide

> **Type:** annotation workflow guide only  
> **Date:** 2026-08-25  
> **Does not:** create claim gold JSON · execute annotation · auto-label · LLM / Critic judgement · schema change · `backend/app` edits

## Gate

```text
E_B12A_ANNOTATION_GUIDE_READY = YES
E_B_FORMAL_READY = NO
```

Upstream helper (display only): `backend/tests/w10_eb12a_claim_gold_annotation_helper.py`  
Target formal path (still **absent**): `w10-eb-generation-claim-gold-v1.json`

---

## 1. Purpose of claim gold annotation

Claim gold is the **human-authored ledger** for T2 (support / unsupported / unverifiable) and shared claim segmentation for T3.

| Claim gold **is** | Claim gold **is not** |
|---|---|
| Independent factual propositions labeled against the **same-run gated evidence pool** | Critic capability score / `expected_action` |
| Evidence-based labels filled by a human | LLM-as-judge / NLI / lexical auto-label |
| Input to later deterministic scorers | Re-labeling of fixture `answer` as truth |
| Bound later to After / synthetic `content_sha256` | Formal measurement authorization |

This guide prepares **how** humans annotate. It does **not** authorize writing the formal gold file or flipping `E-B_FORMAL_READY`.

---

## 2. Core distinctions

| Term | Meaning | Annotator uses it as… |
|---|---|---|
| **Evidence** | Frozen gated excerpt(s) for the case (`chunk_id` + `content` in the helper). Authoritative text for support judgements. | **Only** basis for `label` and `supporting_evidence_ids` |
| **Claim** | One atomic asserted factual proposition under review (`claim_text`). | Unit of labelling |
| **Answer** | Model / fixture / After response body. May *contain* claims to segment later. | **Never** truth; never sole basis for gold label |
| **Gold label** | Human judgement: `supported` \| `unsupported` \| `unverifiable` relative to **evidence**, not relative to “what the model said” | Output field on each claim row |

```text
evidence  ──judges──►  claim  ──produces──►  gold label
answer    ──may supply claim text to split──►  claim
answer    ──✗ must not judge──►  gold label
```

---

## 3. Label rules

Judge **claim vs gated evidence only**.

### `supported`

Evidence **explicitly supports** the claim (literal or unambiguous paraphrase of the same fact).

- Requires ≥1 `supporting_evidence_ids` entry from the case pool.
- Do not mark supported because the answer sounds confident or cites a marker.

### `unsupported`

Evidence **contradicts** the claim (states an incompatible fact for the same proposition).

- Contradiction must be readable in the excerpt(s), not inferred from world knowledge.
- `supporting_evidence_ids` may be empty **or** list the contradicting chunk(s) when useful for audit notes; contradiction itself is enough for the label. Prefer listing contradicting ids when they exist in-pool.

### `unverifiable`

Evidence **does not establish** the claim either way: silent, vague, or orthogonal; no clear support and no clear contradiction.

- Typical when the excerpt discusses a related topic but does not decide the asserted value.
- Do not guess toward supported/unsupported to “be helpful.”

| Label | Evidence relation | Guessing allowed? |
|---|---|---|
| `supported` | Explicit support | No |
| `unsupported` | Explicit contradiction | No |
| `unverifiable` | Neither | No — this **is** the non-guess outcome |

---

## 4. Claim splitting rules

**Unit = one asserted factual claim** (E-B8). Split until each row can be labelled independently.

### Must split

| Pattern | Action |
|---|---|
| Coordinated facts (“A and B”, “X，Y”) | One claim per fact |
| Enumerated facts in a list | Usually one claim per item |
| Citation markers (`[片段N]`) | Keep with the claim; markers are **not** separate claims |

### Do not split

| Pattern | Action |
|---|---|
| Single fact with a modifier clause | Keep one claim |
| Pure connective / “根据资料” boilerplate | Exclude from asserted denominator |
| Unparseable fragment | Exclude (prefer) or `unverifiable`; do not invent meaning |

### Worked examples — C01–C04 only

Sources: frozen `query` + `evidence` from `w9-critic-cases.json`.  
**Pedagogy only** — illustrative claim texts are **not** submitted gold and must **not** copy fixture `answer` as truth.

#### C01 — `C01-fully-supported-exact`

| Field | Content |
|---|---|
| Query | 生产备份保留多久？ |
| Evidence `E1` | 生产环境备份的保留期限为 30 天。 |

| Illustrative claim | Split? | Intended label vs `E1` |
|---|---|---|
| 生产环境备份保留 30 天。 | Already atomic | `supported` (+ `E1`) |

Do **not** treat fixture answer `生产备份保留 30 天[片段1]。` as gold; if After content equals that wording, segment the **proposition**, then judge vs `E1`.

#### C02 — `C02-supported-paraphrase-low-lexical`

| Field | Content |
|---|---|
| Query | 报销申请最迟什么时候提交？ |
| Evidence `E1` | 员工应于费用发生之日起 30 日内提交报销申请。 |

| Illustrative claim | Split? | Intended label vs `E1` |
|---|---|---|
| 报销申请须在费用发生后 30 日内提交。 | Already atomic | `supported` (paraphrase OK if same fact) |

Lexical overlap may be low; label by **semantic support**, not string match. Still human; no auto lexical scorer as gold.

#### C03 — `C03-one-unsupported-among-supported` (must split)

| Field | Content |
|---|---|
| Query | 基础版的存储和电话支持是什么？ |
| Evidence `E1` | 基础版包含 5 GB 存储空间，支持渠道为电子邮件。 |

Multi-claim statement under review (example):

> 基础版支持 5 GB 存储，并提供无限次电话支持。

| Split claim | Intended label vs `E1` | Evidence ids |
|---|---|---|
| 基础版支持 5 GB 存储。 | `supported` | `["E1"]` |
| 基础版提供无限次电话支持。 | `unsupported` | `["E1"]` (contradicts: 渠道为电子邮件) |

Leaving both facts in one row is **invalid** — labels would conflict.

#### C04 — `C04-valid-citation-wrong-evidence`

| Field | Content |
|---|---|
| Query | 管理员初始密码是什么？ |
| Evidence `E1` | 系统不设置通用默认密码；管理员首次登录须通过一次性链接设置密码。 |

| Illustrative claim | Split? | Intended label vs `E1` |
|---|---|---|
| 管理员初始密码是 Admin@123。 | Already atomic | `unsupported` (evidence denies a shared default password) |

A valid citation marker in an answer does **not** make the claim `supported`. Judge the proposition vs excerpt, not vs citation syntax.

---

## 5. Evidence selection rules (`supporting_evidence_ids`)

| Situation | Rule |
|---|---|
| `label = supported` | **Required** ≥1 id from the case’s `evidence_chunks` / gated pool |
| `label = unsupported` | Prefer ids that contradict; empty allowed only if contradiction is still clear in notes — prefer listing in-pool contradicting ids |
| `label = unverifiable` | Usually `[]`; do not invent ids outside the pool |
| Id not in pool | **Reject** (helper / E-B9a validators) |
| Duplicate ids | **Reject** |
| “Looks related” but does not support | Do not list as support; use `unverifiable` or split claims |

Only fill ids when a human can point to the excerpt span that justifies support (or contradiction audit).

---

## 6. Forbidden behavior

Reject / do not do:

| Forbidden | Why |
|---|---|
| Reading model / fixture **answer as truth** | Answer is not gold authority |
| Using **Critic oracle** / `oracle_cases` / capability labels | Wrong measurement layer |
| Using **`expected_action`** | Control-plane action ≠ factual claim |
| **Guessing** labels when evidence is silent | Use `unverifiable` |
| Auto-label / LLM judge / NLI / lexical-only gold | Formal gold forbids |
| Prefilling claims in the helper template | Template must stay empty until human fill |
| Writing `w10-eb-generation-claim-gold-v1.json` in this prep lane without a dedicated gold window | Formal artifact still reserved / absent |
| Flipping `E-B_FORMAL_READY` to YES | Full observation still blocked |

Allowed inputs for judgement: **query (context) + evidence chunks + claim_text under review**.

---

## 7. Workflow (human only)

1. Open helper template / frozen case display (`case_id`, `query`, `evidence_chunks`).
2. Decide which atomic claims exist for the content under annotation (After / synthetic body when bound; do not invent from Critic).
3. Split per §4; fill `claim_id`, `claim_text`, `label`, `supporting_evidence_ids`, `annotation_notes`.
4. Run the [annotation checklist](./03-checklist.md) per case.
5. Later windows: draft validation → formal gold file (not this window).

---

## 8. Related artifacts

| Role | Path |
|---|---|
| Helper module | `backend/tests/w10_eb12a_claim_gold_annotation_helper.py` |
| Helper template | `backend/tests/fixtures/l4_critic/w10-eb-generation-claim-gold-v1.annotation-helper.template.json` |
| Annotation draft (E-B12A-3) | `backend/tests/fixtures/l4_critic/w10-eb-generation-claim-gold-v1.annotation-draft.json` |
| E-B9a schema (unchanged) | `backend/tests/fixtures/l4_critic/w10-eb-generation-claim-gold-v1.schema.json` |
| Construct design | `docs/research/w10-eb8-generation-ground-truth-construct/` |
| Checklist | [`03-checklist.md`](./03-checklist.md) |

## Stop

Guide complete. Human fill / formal gold JSON are later windows. No LLM. `E-B_FORMAL_READY` remains **NO**.
