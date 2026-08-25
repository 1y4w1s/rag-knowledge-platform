# 03 — Recommended architecture · blockers · pre-formal checklist

> Design / readiness only. Gates remain locked.

## 1. Recommended evaluation architecture

### 1.1 Name

**LAAE — Ledger-Anchored After Evaluation**

```text
┌─────────────────────────────────────────────────────────────┐
│  Capture（E-B15+）                                          │
│  prepare → _stream_generation_phase → state content/cites   │
│  → AfterSnapshot / E-B2 per_case slots                      │
└───────────────────────────┬─────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  Binding Gate（BP-A / BP-B / BP-C）                         │
│  case_id · body bind · pool bind · hash codec normalize     │
└───────────────────────────┬─────────────────────────────────┘
                            │
              ┌─────────────┼─────────────┐
              ▼             ▼             ▼
           T1 slot       T2 score      T3 score
         (citations)   unsupported   G1 ∧ G2
                           │             │
                           └──────┬──────┘
                                  ▼
                    Suite aggregate + align_bucket
                    measurement_validity honesty
```

### 1.2 Binding policies（must pick explicitly per case）

| Policy | When | Body bind rule | What it may prove |
|---|---|---|---|
| **BP-A `observed_after`** | Real product After（esp. live LLM） | Gold rebound：`kind=observed_after`；`content_sha256` = **same codec** as After content hash；claims re-annotated for **that** body | Product-path T2/T3 faithfulness（after owner auth） |
| **BP-B `synthetic_authored`** | Protocol / scorability | Gold stays claim_texts payload hash；After body must be **author-owned** and pass claim-text **presence**（or reconstruct）integrity vs `asserted_claims` | Protocol wiring only；**not** model quality |
| **BP-C `refusal_exclude`** | Empty-gate / fail-closed fixed reply | Skip T2/T3；T4 only | Refusal behavior |

**Current E-B12B ledger = BP-B material only.**  
**Current E-B15 A2 degraded After ≠ BP-B-compatible body.**  
**BP-A material does not exist yet.**

### 1.3 Hash codec unification（design rule）

| Producer | Today | Required before formal T2/T3 |
|---|---|---|
| E-B15 `after_content_hash` | `sha256:{hex}` of content string | Documented codec + comparator |
| E-B12B gold `content_sha256` | bare `{hex}` of **claim_texts payload** | Either rebound to content-string hash（BP-A）or keep payload hash **only under BP-B** with non-content equality check |

Comparator must **never** naively `==` across these two spaces.

### 1.4 Module ownership（future impl windows）

| Concern | Owner | Forbidden owner |
|---|---|---|
| After capture | tests harness（E-B15 lineage） | app observation hook（rejected E-B14 Scheme B） |
| Gold ledger | fixtures + E-B9a validator | Critic oracle |
| Binding gate + T2/T3 scorer | tests-only module | `backend/app` |
| Formal envelope write | E-B2 reserved writer under gate YES | Smoke paths claiming proven |

### 1.5 Target routing

| Target | After need | Gold need | Entry |
|---|---|---|---|
| T1 | `final_citations` + plan contrast | No claim gold | Existing T1 / align bucket path |
| T2 | Bound After body | Annotated claims | `score_t2` |
| T3 | Bound After body + final citations | Same claims + pool | `score_t3` |
| T4 | Refusal After | Empty-gate cases（not claim gold） | Empty-gate refuse_ok path |

---

## 2. Remaining blockers

### 2.1 After→Gold specific（this window’s focus）

| Id | Blocker | Status |
|---|---|---|
| **AG-1** | Gold binds claim_texts payload；After hashes content string — **incompatible bind spaces** | **OPEN** |
| **AG-2** | Hash codec prefix mismatch（`sha256:` vs bare） | **OPEN**（aggravates AG-1） |
| **AG-3** | No tests-only T2/T3 scorer / binding gate module | **OPEN** |
| **AG-4** | E-B15 degraded/refusal After cannot satisfy BP-B presence vs C01–C11 claim texts | **OPEN** |
| **AG-5** | No BP-A rebound gold for any observed product After | **OPEN** |
| **AG-6** | E-B6 isomorphic `[eb6-synthetic:…]` still ≠ E-B12B claim_texts bodies | **OPEN**（known；do not use as T2/T3 gold pair） |

### 2.2 Broader formal residuals（unchanged class）

| Id | Blocker | Status |
|---|---|---|
| **B2′** | Formal / authorized After snapshots + reserved write unlock | **BLOCKING_RESIDUAL**（harness ready ≠ formal ready） |
| **S2** | `E_B_S2_PACKAGING_AUTHORIZED` | **NO** |
| **A4** | Live LLM product After owner authorization + E-B2 `llm_called` freeze thaw | **NO** |
| **Gate** | `E-B_FORMAL_READY` | **NO**（correct） |

### 2.3 What is *not* blocking After→Gold design

| Cleared material | Still insufficient for |
|---|---|
| Claim gold ANNOTATED=YES | Compatible After bind |
| Empty-gate MATERIAL_READY=YES | T4 formal packaging / After under S2 auth |
| Product After harness READY=YES | Formal measurement_valid write |
| E-B8 construct docs | Executable scorer |

```text
Full formal YES ⇏ Claim Gold ∧ Empty Material ∧ After Harness
Full formal YES  ⇒ those ∧ AG bind compatibility ∧ scorer ∧ unlock ∧ honest targets
```

---

## 3. Must-complete before formal window

Ordered for a **Full** window with `targets_measured` containing T2 and/or T3.  
Narrow windows may skip items marked **(T2/T3 only)** if targets exclude them **and** artifact honesty says so.

### 3.1 Design freeze（this package — done as design）

- [x] Freeze LAAE + BP-A/B/C  
- [x] Freeze ledger-only extraction  
- [x] Freeze T2/T3 entry signatures（conceptual）  
- [x] Freeze final_citations = post-align only for G2  

### 3.2 Binding clearance（**T2/T3 only** · still TODO）

1. Choose formal path: **BP-A**（product faithfulness）and/or **BP-B**（protocol-only）.  
2. If BP-B：author-owned After bodies that embed ledger claim texts；presence gate green；`measurement_claims` must **not** say product faithfulness.  
3. If BP-A：authorized After capture → human rebound ledger（`kind=observed_after` + content-string hash）→ validator green.  
4. Unify hash compare helper（prefix + payload-vs-content semantics）.  
5. Pool bind：observed gated ids vs `gated_pool_binding`（invalidate on drift）.

### 3.3 Scorer clearance（**T2/T3 only** · still TODO）

1. Implement tests-only binding gate + `score_t2` / `score_t3`.  
2. Unit tests：F1–F8 table from E-B8 `03`；hash mismatch → INVALID；refusal → N/A.  
3. Wire statuses：`grounding_observation_status=OBSERVED_SLOT` only when T2/T3 actually scored.

### 3.4 Capture / unlock clearance（all formal）

1. After snapshots for every denominator case under authorized path.  
2. Owner unlock plan for reserved `FORMAL_OBSERVATION_RESULT` write.  
3. If T4 in suite：S2 packaging **authorized** + empty-gate After captured.  
4. If live LLM：A4 authorization；honest `llm_called=true`.  
5. Only then consider `E-B_FORMAL_READY=YES` / `MAY_ENTER_FORMAL_OBSERVATION_WINDOW=YES`.

### 3.5 Explicit non-goals until unlock

```text
DO NOT flip E-B_FORMAL_READY on design alone.
DO NOT treat E-B15 harness green as T2/T3 measured.
DO NOT score E-B12B gold against E-B15 degraded After as-is.
DO NOT call LLM under this readiness claim.
DO NOT write reserved formal result.
```

---

## 4. Recommended next atomic windows（suggestion only）

| Priority | Window | Intent |
|---|---|---|
| **Recommended** | **E-B17 Binding Gate + Hash Codec**（tests/docs） | Implement BP comparator + invalidate rules；still no formal run |
| Alternate | Author-owned BP-B After bodies aligned to claim_texts（protocol scorability smoke） | Proves T2/T3 **wiring** only |
| Alternate | S2 packaging authorization prep | Helps T4 Full；does not clear AG-1 |

---

## 5. Gate stamp（end of E-B16）

```text
AFTER_TO_GOLD_BOUNDARY_DESIGNED     = YES
RECOMMENDED_ARCHITECTURE            = LAAE (Ledger-Anchored After Evaluation)
GOLD_AFTER_BINDING_COMPATIBLE       = NO
T2_T3_SCORER_IMPLEMENTED            = NO
E-B_FORMAL_READY                    = NO
MAY_ENTER_FORMAL_OBSERVATION_WINDOW = NO
B2_PRIME_AFTER_SNAPSHOTS            = BLOCKING_RESIDUAL
```

---

## 6. Stop

```text
E-B_FORMAL_READY = NO
```
