# 03 — Formal fields, remaining blockers, formal-window verdict

## 1. Formal snapshot / envelope fields required（E-B2）

### Top-level（reserved `FORMAL_OBSERVATION_RESULT`）

| Field | Formal expectation |
|---|---|
| Identity consts | `protocol_version` / `artifact_schema_version` / `suite_id=w9_critic_frozen_12` / runners / `observation_point=generation_final_content_and_citations` |
| `case_count` | `12` |
| `eligibility_summary` | 11 eligible · 1 invalid (C12) · `targets_measured` = authorized set |
| `per_case_observation[]` | length 12 |
| `measurement_validity` | Authorized run may set `measurement_valid=true` **only** under gate YES + honest path |
| `measurement_claims.asserted` | ⊆ `{generation observation artifact produced}` |
| `p2_r1_status` | `BLOCKED` · `does_not_unblock_p2_r1=true` |
| `artifact_kind` | `FORMAL_OBSERVATION_RESULT` |
| Reserved file | `w10-eb2-generation-observation-result.json` |

### Per-case After slots（denominator cases）

| Field | Formal expectation |
|---|---|
| `final_content_observation` | Non-null copy of After `state["content"]`（or explicit INELIGIBLE） |
| `final_citations` | Non-null aligned `state["citations"]`（refusal → `[]`） |
| `gen_plan_reference` | Before plan hash/id |
| `scope_compliance_result` | T1 slot when measured（≠ E-A5 `scope_compliance_pass`） |
| `grounding_observation_status` | `OBSERVED_SLOT` iff T2/T3 in `targets_measured` |
| `refusal_observation_status` | `OBSERVED_SLOT` / `INELIGIBLE` as protocol |

**Today:** reserved formal file **ABSENT**；smoke path only produces non-reserved envelopes with `measurement_valid=false`.

Full formal additionally requires S2 companion packaging（empty-gate suite）when T4 included — still `E_B_S2_PACKAGING_AUTHORIZED=NO`.

---

## 2. Condition matrix（post E-B12B / empty-gate materialization）

| Cond | Needed for Full YES | Status after this review |
|---|---|---|
| C1 Executor | Yes | **Met**（E-B6） |
| C2 After snapshots | Yes | **Open residual（B2′）** |
| C3 Claim gold | Yes | **Mostly Met**（annotated ledger present）；After-hash rebind still required for product/stream After |
| C4 Empty-gate | Yes | **Partial** — cases MATERIAL **YES** · S2 packaging AUTHORIZED **NO** |
| C5 Hygiene | Yes | **Met** |

```text
Full YES ⇔ C1 ∧ C2 ∧ C3 ∧ C4 ∧ C5 = false
```

---

## 3. Exact remaining blockers（B2′-centric）

### B2′ — Formal / product After snapshots — **BLOCKING residual**（unchanged class）

| Residual | Evidence |
|---|---|
| No product `_stream_generation_phase` After in E-B harness | E-B6 never calls stream |
| No reserved formal result with authorized `measurement_valid=true` | File absent；write guard refuses |
| Isomorphic smoke hard-locked informal | `measurement_valid=false` · `OTHER_PROTOCOL_BREAK` |
| No owner unlock for narrow T1 isomorphic formal | `E-B_NARROW_FORMAL_READY=NO` |
| Gold ↔ After body mismatch | E-B12B hashes ≠ E-B6 `[eb6-synthetic:…]` bodies |
| Empty-gate After not produced by E-B6 | Runner still W9-12 only |

**Clear when（任一 owner-authorized path）:**

1. **Product After path:** harness drains `_stream_generation_phase`（or equivalent product终态）→ captures `state` → E-B2 validate → reserved write under gate YES；**or**  
2. **Narrow isomorphic formal:** owner 书面解锁 T1-only isomorphic + rewrite E-B6 formal locks；`targets_measured ⊆ {T1}`；**and**  
3. For T2/T3：After `content_sha256` matches claim gold binding（or gold rebound）；  
4. For T4：empty-gate After captured under S2 packaging authorization.

### Adjacent residuals（not B2′ itself, still block Full YES）

| Id | Status | Note |
|---|---|---|
| B3′ Claim gold annotated | **Cleared as material** | Ledger on disk；binding still synthetic_authored |
| B4′ Empty-gate cases | **Material cleared** | REAL_ELIGIBLE N=2 |
| B4′ S2 packaging auth | **Still NO** | Contract ready ≠ authorized |
| Formal observation execution | **Not started** | Correct |

---

## 4. What is *not* a B2′ clear signal

| Signal | Why insufficient |
|---|---|
| E-B6 smoke suite green | Proves wiring only |
| `artifact_kind=FORMAL_OBSERVATION_RESULT` on smoke | Envelope kind ≠ measurement pass |
| E-A5 11/11 | Wrong observation point |
| Claim gold ANNOTATED=YES | Gold ≠ After snapshot |
| Empty-gate MATERIAL_READY=YES | Cases ≠ After capture |
| Schema validators green | Hygiene only |

---

## 5. Formal-window judgment

```text
MAY_ENTER_FORMAL_OBSERVATION_WINDOW = NO
```

| Question | Answer |
|---|---|
| Can Full formal window open now? | **NO** |
| Can Narrow T1 formal window open now? | **NO**（no owner unlock；locks intact） |
| Is B2′ cleared? | **NO** — **BLOCKING residual** |
| Next allowed work | Clearance / unlock design only — **not** formal run |

```text
DO NOT execute formal generation observation.
DO NOT write reserved formal result.
DO NOT call LLM / LM Studio under this readiness claim.
DO NOT flip E-B_FORMAL_READY.
```

---

## 6. Recommended next clearance（suggestion only）

**Recommended:** Owner-authorized After unlock design（product stream After harness **or** narrow T1 isomorphic formal unlock + lock rewrite plan）— research/plan only until confirmed.

**Alternate:** S2 packaging authorization contract flip prep（still does **not** clear B2′ alone）.

---

## Stop

```text
E-B_FORMAL_READY = NO
B2_PRIME_AFTER_SNAPSHOTS = BLOCKING_RESIDUAL
MAY_ENTER_FORMAL_OBSERVATION_WINDOW = NO
```
