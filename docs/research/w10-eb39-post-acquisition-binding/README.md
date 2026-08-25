# W10 E-B39 — Post-Acquisition Binding & Scorer Applicability

> **Does:** Persist E-B38 acquisition provenance commit · recheck C01–C11 record integrity · attempt Gold↔real After binding under frozen BP · audit claimed-unit / claim-presence / degraded BP class · separate T1/T2/T3 input readiness.  
> **Does not:** Formal scorer run · Formal Observation · LLM/API/LM Studio · modify gold · modify E-B38 After · modify scorer formulas · use E-B18 author-owned compat pack · invent fuzzy/NLI matcher · flip `E-B_FORMAL_READY`.

## Inherited freeze

```text
ACQUISITION_EXECUTED                 = YES
PRODUCT_AFTER_CAPTURED               = YES
ACQUISITION_VALID                    = YES
capture_submode                      = product_stream_degraded (C01–C11)
llm_called_observed                  = false
frozen evaluation base_sha           = 3ce0e75f06d35aecaaccd245dd3a234b1c6f79a6
run_identity                         = w10_showcase_narrow_eb38_20260825T085526Z
acquisition_record_commit            = f82cf46e04da6670acd3ca8a38c12fc6206c03a9
acquisition_record_commit ≠ base_sha = YES
```

## Verdict (this window)

```text
POST_ACQUISITION_RECORD_INTEGRITY     = PASS
REAL_AFTER_BINDING_COMPLETE           = NO
BP_A_REAL_AFTER_BOUND                 = NO
CLAIM_UNIT_SEMANTICS                  = GOLD_LEDGER_UNIVERSE
CLAIM_PRESENCE_UNRESOLVED_BY_FROZEN_PROTOCOL = YES
BP_A_FORMAL_ELIGIBILITY               = NO
T1_REAL_AFTER_INPUT_READY             = NO
T2_REAL_AFTER_INPUT_READY             = NO
T3_REAL_AFTER_INPUT_READY             = NO
SCORER_APPLICABILITY_GAP              = YES
POST_ACQUISITION_BINDING_READY        = NO
BLOCKED_PENDING_PROTOCOL_REPAIR       = YES

E-B_FORMAL_READY                      = NO
MAY_ENTER_FORMAL_OBSERVATION_WINDOW   = NO
FORMAL_OBSERVATION                    = NOT_STARTED
```

## Package

| File | Role |
|---|---|
| `01-acquisition-provenance-commit.md` | E-B38 commit identity |
| `02-record-integrity-recheck.md` | C01–C11 integrity |
| `03-gold-real-after-rebinding.md` | Binding attempts / blockers |
| `04-claimed-unit-semantics.md` | Frozen scorer claim-universe evidence |
| `05-claim-presence-audit.md` | C01–C11 presence / assertion audit |
| `06-degraded-bp-classification.md` | BP-A/B/C vs degraded |
| `07-t1-t2-t3-readiness.md` | Per-target readiness |
| `08-scorer-applicability-gaps.md` | Protocol gaps / empty-perfect pathology |
| `09-eb39-verdict.md` | Gate matrix + stop |

## Stop

Do **not** run Formal T1/T2/T3. Do **not** write Formal results. Next window = protocol-repair design only.
