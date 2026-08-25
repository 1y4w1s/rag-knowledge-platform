# 02 — Matching · T2/T3 measurement entries · citations

> Design only. No scoring run.

## 1. Claim matching strategy

### 1.1 What “match” means here

Matching connects **observed After** to **ledger rows**, then assigns each ledger claim a score contribution. It does **not** invent labels.

```text
After snapshot ──bind──► ledger case
                              │
                              ▼
                    for claim in asserted_claims:
                         identity = claim.claim_id
                         label    = claim.label          # gold only
                         G2 probe = After citations / marks
```

### 1.2 Matching layers

| Layer | Key | Rule |
|---|---|---|
| **Case match** | `case_id` | Must equal frozen suite id |
| **Body bind** | BP-*（`03`） | Hash / presence / rebound；fail → case T2/T3 **invalid** |
| **Pool bind** | `gated_pool_binding` | Observed gated evidence ids / `pool_sha256` must compatible；drift → **invalid** |
| **Claim identity** | `claim_id` | Stable string；scorer iterates ledger order |
| **Claim text integrity** | `claim.text` ⊆ After（normalized） | Recommended hard gate for formal；soft only if protocol explicitly allows reconstruct-only BP-B |

### 1.3 Forbidden matching

| Anti-pattern | Why |
|---|---|
| Fuzzy embedding / NLI claim alignment | Second oracle；unstable |
| Token-overlap ≥ θ auto-label | E-B4/E-B8 forbid as formal |
| Match by Critic `expected_action` / C03 name | Control plane ≠ generation claims |
| Silent reuse of gold after content drift | Hash/presence fail must invalidate |
| Match E-B6 `[eb6-synthetic:…]` body to E-B12B claim_texts gold | Different authored texts；known mismatch |

### 1.4 Verdict on matching

**Adopt: identity matching on ledger `claim_id` after explicit body/pool bind.**  
No soft NLP match for formal first window.

---

## 2. T2 `unsupported_rate` measurement entry

### 2.1 Normative formula（E-B8 `02`）

```text
unsupported_rate = |{c ∈ asserted : label=unsupported}| / |asserted|
```

| Rule | Detail |
|---|---|
| Denominator | Ledger `asserted_claims` after `exclude_refusal_boilerplate` |
| `unverifiable` | In denom；**not** in unsupported numerator |
| Denom 0 | `NOT_APPLICABLE`（not 0.0 PASS） |
| Labels | **Only** from gold；scorer never re-labels |

### 2.2 Recommended entry point（future tests-only module）

```text
score_t2(
  after: {final_content_observation, …},
  gold_case: ClaimGoldCase,
  gated_snapshot: …,
  binding_policy: BP_*,
) -> T2CaseResult
```

**Pipeline:**

1. `assert_formal_targets_include("T2")` else return `NOT_OBSERVED`  
2. Refusal / empty asserted → `NOT_APPLICABLE`  
3. Run binding gate（body + pool）→ fail ⇒ `INVALID`  
4. Optional integrity：each `claim.text` locatable in After  
5. Count labels → `unsupported_rate`（micro later at suite）  
6. Set observation status `OBSERVED_SLOT`（≠ proven）

**Home:** `backend/tests/` only（e.g. future `w10_eb_t2_t3_scorer.py`）.  
**Not home:** `backend/app` · Critic · reserved formal writer（writer consumes scores later）.

### 2.3 What is *not* the T2 entry

| Signal | Home |
|---|---|
| E-A2 `unsupported_final_citation_count` | Citation **shape** |
| Critic `REMOVE_UNSUPPORTED_CLAIM` | W9 control plane |
| E-B15 `grounding_observation_status=NOT_OBSERVED` | Honest：T2 not scored yet |
| Hit@3 | Retrieval |

---

## 3. T3 grounding G1/G2 measurement entry

### 3.1 Normative（E-B8 `03`）

```text
grounded(claim) ⇔ G1 ∧ G2
grounded_rate = |{grounded}| / |{asserted}|
```

### 3.2 G1 entry（excerpt support）

**Inputs:** gold claim row + same-run gated pool snapshot.

| G1 true | G1 false |
|---|---|
| `label == supported` | `unsupported` / `unverifiable` |
| `supporting_evidence_ids` non-empty ⊆ observed gated ids | Evidence id left the pool → **invalidate case** |
| Auditable span notes present（or protocol-accepted equivalent） | — |

G1 **does not** require a citation chip（that is G2）.

**Entry function sketch:**

```text
g1 = evaluate_g1(claim, gold_case.gated_pool_binding, observed_gated_ids)
```

Deterministic；zero LLM.

### 3.3 G2 entry（citation pointer）

**Inputs:** After `final_citations` + After content marks + claim `supporting_evidence_ids`.

G2 true iff **≥1 resolvable pointer** to a supporting chunk/evidence:

| Pointer form | Operational check |
|---|---|
| Final citation row | Some `final_citations[i]` id ∈ claim supporting set（chunk_id / evidence id as protocol maps） |
| In-body mark | Legal `[片段N]` in After content maps（same numbering space as `align_citations_to_answer`）to supporting chunk |

| Bad pointer → G2 false |
|---|
| Empty citations and no legal mark |
| Chip points to non-supporting chunk |
| keep-all full chip table alone（no claim-resolved support） |
| Citation missing resolvable id |

**Entry function sketch:**

```text
g2 = evaluate_g2(claim, final_citations, after_content, gated_chunks)
grounded = g1 and g2
```

Optional research field `grounded_semantic_only = G1 ∧ ¬G2` — **not** formal grounded.

### 3.4 Recommended T3 entry point

```text
score_t3(
  after: {final_content_observation, final_citations, align_bucket?},
  gold_case,
  gated_snapshot,
  binding_policy,
) -> T3CaseResult  # per-claim G1/G2 + grounded_rate + bucket
```

Must **bucket** by `align_bucket ∈ {shrink, keep_all, refuse_empty, fail_closed_empty}`.  
keep-all bucket must not alone claim product grounding PASS.

Shared with T2: same binding gate + same asserted denom.

---

## 4. Citation alignment ↔ `final_citations`

### 4.1 Product fact

In `_stream_generation_phase`（non-refusal, gated present）:

```text
assistant_content  →  align_citations_to_answer(...)  →  citations
state["content"]   = assistant_content
state["citations"] = citations          # AFTER align
```

Refusal / critic fail-closed → content = no-context reply；`citations = []`（skip align).

### 4.2 Evaluation boundary

| Concept | Definition | Used by |
|---|---|---|
| Plan citations | `gen_plan.citations` / gated list **before** generation | Before / T1 contrast only |
| **Final citations** | `state["citations"]` after align（or `[]`） | E-B2 slot · **T3 G2** · T1 scope |
| Align mechanism | Product-internal `align_citations_to_answer` | Not re-implemented in scorer；**observe result** |
| Keep-all | Align fallback when marks missing | Record bucket；**≠ grounded** |

```text
citation_align  ──produces──►  final_citations
                                      │
                                      ├── T1: scope / preservation / bucket
                                      └── T3 G2: claim→pointer→supporting chunk
```

### 4.3 Hard separations

| Confusion | Correct split |
|---|---|
| Plan citations == final | **Forbidden** as After（E-A3 `SCORED_NON_FINAL` class） |
| Align ran ⇒ grounded | Align is mechanical；G1∧G2 still required |
| Chip present ⇒ supported | Shape ≠ support（F2） |
| E-A2 missing `chunk_id` count | Citation shape；≠ T2 unsupported_rate |

### 4.4 Gold assist fields

E-B8 allows optional `grounding.expected_citation_ids` / `expected_fragment_indices`.  
**Current E-B12B ledger does not store these**; G2 can still be derived from `supporting_evidence_ids` + After pointers. Optional assist fields are **not** a blocker if derivation rule stays frozen.

---

## 5. Answers to research Q3–Q6

| # | Question | Answer |
|---|---|---|
| 3 | claim matching 策略？ | `case_id` + BP bind + `claim_id` identity；禁 fuzzy/NLI/Critic |
| 4 | T2 unsupported_rate 入口？ | Future tests-only `score_t2(after, gold, gated, BP)` after bind；labels from gold only |
| 5 | T3 G1/G2 入口？ | Future `score_t3(...)`：G1=label+pool；G2=`final_citations`/`[片段N]` → supporting id |
| 6 | citation alignment 与 final_citations？ | Align **produces** final_citations；G2 consumes final only；plan citations ≠ After |

---

## 6. Stop

No formal scores written this window.
