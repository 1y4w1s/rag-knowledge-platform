# 03 — Selected source rationale (candidate only)

> Applies `01` weights + `02` matrix.  
> **Candidate selection ≠ authorization.**

## 1. Primary candidate

```text
PRIMARY_CANDIDATE_SOURCE = A
  = selected design candidate only
name                     = E-B15 product stream harness
role                     = validated Product After capture path candidate
NOTE                     = E-B15 harness ≠ Formal Evaluation Source
                           (Formal Evaluation Source requires owner stamp;
                            currently AFTER_SOURCE_APPROVED=NO;
                            PRIMARY_CANDIDATE_SOURCE=A is a selected design
                            candidate only · ⇏ source approved / formal
                            eligible / After approved)
Scheme                   = Scheme A · prepare_agent_generation
                           → _stream_generation_phase
                           → state["content"] / state["citations"]
```

```text
SOURCE_SELECTED_DESIGN   = YES
SOURCE_APPROVED          = NO
AFTER_SOURCE_APPROVED    = NO
OPTION_SELECTED          = A   (design pointer only · not owner stamp)
```

## 2. Why selected (A)

Under frozen Narrow Formal (A4 excluded · BP-A · C01–C11):

1. **formal eligibility** — Only option with **in-scope potential** without
   revising Narrow. B/C are A4-class OUT; D is absent.
2. **reproducibility** — Current harness modes are no-LLM deterministic
   (refusal/degraded) → highest replay honesty for a first Narrow suite.
3. **provenance / source identity** — Product stream path already exists;
   a named formal `after_source` can be minted without inventing a side
   generation surface.
4. **hash binding** — Bodies from real `state["content"]` are BP-A-bindable
   after AG-5 rebound (same codec path as E-B17/E-B18; live×E-B12B still
   INCOMPATIBLE until rebound).
5. **capture feasibility / cost / maintenance** — Harness ready signal
   present; lowest effort and pin surface among surviving options.
6. **owner authorization difficulty** — Hard but tractable: freeze
   `capture_mode` + `model_identity` (e.g. `none_no_llm`) + `base_sha` +
   `run_identity`, then human stamp. Does not require “approve a missing
   production export.”

Weight reminder:  
`formal eligibility > reproducibility > provenance > cost` → A dominates.

## 3. Why alternatives rejected

| Option | Rejection (for Narrow PRIMARY) |
|---|---|
| **B** LM Studio | Hard veto: live local LLM ≈ A4-class under E-B24 Narrow freeze; reproducibility weaker; owner auth would need scope revision first |
| **C** API model | Hard veto: A4 live / cloud generation excluded from Narrow; cost + nondeterminism; approving C contradicts frozen scope |
| **D** Future authorized prod | Not extant as formal-eligible suite; cannot stamp absent source (E-B25); highest ops; keep as **future** path after Narrow first observation — not PRIMARY now |

E-B18 synthetic pack remains **forbidden** as Product After (not an option).

## 4. Remaining blockers (post-candidate)

Candidate design does **not** clear execution or formal gates:

```text
[ ] Owner approval stamp issued          → AFTER_SOURCE_APPROVED still NO
[ ] after_source named + frozen
[ ] capture_mode frozen (Narrow-allowed; non-silent smoke→formal)
[ ] model_identity frozen (likely none_no_llm for A no-LLM modes)
[ ] run_identity / base_sha frozen
[ ] generation_config frozen (canonical)
[ ] Acquisition execution checklist green (E-B26 §05)
[ ] Product After suite captured C01–C11   (not this window)
[ ] Gold rebound → ∀ C01–C11 BindingVerdict=BOUND
[ ] B2_PRIME_AFTER_SNAPSHOTS residual      (still BLOCKING_RESIDUAL)
[ ] AG-5 live/authorized rebound           (still PARTIAL)
[ ] E-B_FORMAL_READY / formal entry        (must stay locked)
```

```text
ACQUISITION_EXECUTION_READY = NO
SOURCE_APPROVED             = NO
AFTER_SOURCE_APPROVED       = NO
E-B_FORMAL_READY            = NO
FORMAL_OBSERVATION          = NOT_STARTED
```

## 5. What this window claims / does not claim

| Claims | Does not claim |
|---|---|
| A is the designed PRIMARY **candidate** = validated Product After capture path candidate | A is owner-approved Formal Evaluation Source |
| Selection design complete (`SOURCE_SELECTED_DESIGN=YES`) | Acquisition may execute |
| B/C OUT under current Narrow; D deferred | Formal Observation may start |
| E-B15 harness ≠ Formal Evaluation Source | Live LLM faithfulness for A no-LLM modes |

## 6. Stamp

```text
SOURCE_SELECTED_DESIGN              = YES
PRIMARY_CANDIDATE_SOURCE            = A
SOURCE_APPROVED                     = NO
AFTER_SOURCE_APPROVED               = NO
ACQUISITION_EXECUTION_READY         = NO
E-B_FORMAL_READY                    = NO
FORMAL_OBSERVATION                  = NOT_STARTED
```
