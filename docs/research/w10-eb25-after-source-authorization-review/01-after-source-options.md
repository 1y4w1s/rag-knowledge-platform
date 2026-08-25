# 01 — After source options (Narrow Formal candidates)

> Compares three After candidates for eligibility as Narrow Formal
> denominator input under E-B24 contract.  
> Authorization review only — no capture, no rebound, no formal write.

## 1. Evaluation axes

For each candidate:

| Axis | Question |
|---|---|
| **Formal-usable now?** | May it enter Narrow Formal denom today? |
| **Proof scope** | What does the artifact / path actually prove? |
| **Limits** | What must remain unclaimed? |

Contract reference (E-B24 `03`): formal After requires **all** of  
`source identity ∧ hash binding (BP-A) ∧ capture mode ∧ no synthetic contamination`  
(+ owner stamp).

---

## 2. Candidate A — E-B15 product stream capture

```text
ID:     A
Name:   E-B15 Product After Snapshot Capture (Scheme A harness)
Path:   prepare_agent_generation → _stream_generation_phase
        → state["content"] / state["citations"] → E-B2 per_case slot
Signals: PRODUCT_AFTER_CAPTURE_HARNESS_READY=YES
         PRODUCT_AFTER_CAPTURE_FEASIBLE=YES
         formal_measurement=false (default)
         B2_PRIME_AFTER_SNAPSHOTS=BLOCKING_RESIDUAL
```

### Formal-usable now?

**NO.**

Harness readiness ≠ authorized formal After. E-B24 §4 and E-B23 B2′ both
freeze: green harness does not clear formal denominator.

### Proof scope

| Proves | Does not prove |
|---|---|
| Product generation path is reachable from tests without app hook | Owner-approved formal-eligible After suite for C01–C11 |
| After slots can be filled from real `state["content"]`/`citations` | AG-5 live rebound gold `BOUND` under BP-A for those bodies |
| Scheme A is the correct capture architecture (vs B/C) | Product LLM faithfulness / live generation quality |
| Refusal / empty / smoke modes exist with honest `llm_called` labels | A4 thaw or Narrow Formal capture-mode stamp |

### Limits

- Default runs remain informal (`formal_measurement=false`).  
- Live unrebounded E-B12B × E-B15 After stays `INCOMPATIBLE` under BP-A
  (`LIVE_EB15_X_EB12B_COMPATIBLE=NO`).  
- A4 live LLM is **out of Narrow Formal scope** even if harness can call it later.  
- Cannot be relabeled as formal denom without separate owner clearance +
  rebound gold.

---

## 3. Candidate B — E-B18 synthetic rebound (compat pack)

```text
ID:     B
Name:   E-B18 Gold↔After Binding Compatibility Materialization
Path:   author_owned_after_body(claim texts) → BP-A rebound gold
        → BindingVerdict BOUND (compat pack)
Signals: GOLD_AFTER_BINDING_COMPATIBLE=YES
         after_source=compatibility_materialization_author_owned
         llm_called=false · formal_measurement=false
         compatibility_proof_only=true
         AG-5=PARTIAL (compat YES · live NO)
```

### Formal-usable now?

**NO.**

Pack itself forbids product interpretation: author-owned synthetic After,
explicit honesty veto against product faithfulness claims.

### Proof scope

| Proves | Does not prove |
|---|---|
| BP-A content-string codec works (AG-1 cleared for rebound path) | Product stream After exists for formal denom |
| `after.case_id ↔ gold.case_id` + three-hash verify under BP-A | Live E-B15 × unrebounded E-B12B is BOUND |
| Binding gate + compatibility validator are implementable | T2/T3 rates / formal observation scores |
| Hygiene path for future authorized rebound | Absence of synthetic contamination in formal suite |

### Limits

- Body is **constructed** from human claim texts — not product generation.  
- Using B as Narrow Formal After would violate
  `no synthetic contamination` by definition.  
- Compat `BOUND` ⇏ formal After authorized (E-B24 §2.2).  
- Must stay labeled `compatibility_materialization_author_owned`.

---

## 4. Candidate C — future live authorized generation

```text
ID:     C
Name:   Future live / owner-authorized product After generation
Path:   (not yet captured under formal-eligible stamp)
Signals: A4=NO · owner live auth absent · llm_called freeze still false-forced
         Narrow Formal also excludes A4 from first scope
```

### Formal-usable now?

**NO** — source does not exist as an authorized artifact suite.

Even a future capture would still need:

1. Owner capture-mode stamp (Narrow: non-A4 product-path Scheme A, or a
   separately declared eligible mode with honest `llm_called`).  
2. AG-5 rebound of claim gold to those After content hashes → BP-A `BOUND`.  
3. Suite coverage ∀ C01–C11 + C12 recorded INELIGIBLE.  
4. Zero synthetic mixing with E-B6 / E-B18 stubs.

### Proof scope (prospective)

| Would prove (when authorized) | Still would not prove alone |
|---|---|
| Product After bodies as formal denom candidates | Full Formal (S2/T4) or A4 live unless separately scoped |
| Bindable observed content for T2/T3 under BP-A | Reserved write unlock / `E-B_FORMAL_READY` |
| Clearance of B2′ residual for Narrow After evidence | Scorer correctness beyond existing tests-only gates |

### Limits

- Approving C now would be approving a placeholder.  
- Narrow Formal **excludes A4**; live-key generation is a different scope.  
- Cannot invent artifacts in this review window.

---

## 5. Comparative matrix

| Candidate | Formal-usable now? | Primary proof | Hard limit |
|---|---|---|---|
| **A** E-B15 product stream | **NO** | Capture path / harness | Harness ≠ authorized After; unrebounded gold INCOMPATIBLE |
| **B** E-B18 synthetic rebound | **NO** | BP-A codec / binding hygiene | Author-owned synthetic = contamination for formal |
| **C** Future live authorized | **NO** | (none yet) | Source absent; A4 out of Narrow scope |

```text
∃ candidate formal-eligible today?  = NO
Recommended future path (not this window):
  authorize product-path After (A class, owner-stamped, non-A4)
  → AG-5 rebound gold to those hashes
  → re-run authorization review
  ⇏ use B as denom · ⇏ silent harness→formal upgrade
```

## 6. Stamp

```text
AFTER_CANDIDATES_COMPARED = YES
CANDIDATE_A_FORMAL_USABLE = NO
CANDIDATE_B_FORMAL_USABLE = NO
CANDIDATE_C_FORMAL_USABLE = NO
E-B_FORMAL_READY          = NO
```
