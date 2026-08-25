# 04 — Candidate Consistency Audit

> Twelve-point audit for E-B35a materialization honesty.  
> On conflict: set `FREEZE_CANDIDATE_STATUS = BLOCKED_PENDING_HUMAN_REVIEW`  
> and **do not** guess-fix values.

## Audit table

| # | Check | Result | Notes |
|---|---|---|---|
| 1 | Human-supplied candidates consistent with E-B34 Showcase decisions | **PASS** | Showcase PRIMARY · Benchmark LONG_TERM · LM Studio Dev-only · formal model deferred · product_stream / none_no_llm honesty matches E-B34 tendency now owner-accepted as candidate |
| 2 | Candidate A remains selected **design** candidate only | **PASS** | `PRIMARY_CANDIDATE_SOURCE=A` · not Formal Evaluation Source · not SOURCE_APPROVED |
| 3 | `product_stream` not miswritten as formally approved / frozen | **PASS** | Tagged `HUMAN_SUPPLIED_CANDIDATE` · `CAPTURE_MODE_FROZEN=NO` · `freeze_status≠FROZEN` |
| 4 | `none_no_llm` consistent with `llm_called_expected=false` | **PASS** | Both human-supplied · generation_config_ref=`N/A` |
| 5 | LM Studio not entered as Narrow Formal Primary | **PASS** | `development_generation_backend=LM Studio` · `LOCAL_MODEL_AS_NARROW_FORMAL_PRIMARY=NO` |
| 6 | Current HEAD is only `proposed_base_sha` / `observed_base_sha` | **PASS** | `base_sha_frozen=NO` · `BASE_SHA_FROZEN=NO` · dirty tree → `BASE_SHA_FREEZE_READINESS=BLOCKED_PENDING_OWNER_REVIEW` |
| 7 | Runtime observation is candidate only | **PASS** | `runtime_identity_candidate` · not frozen runtime_identity |
| 8 | `formal_model_identity` still deferred | **PASS** | `DEFER_TO_BENCHMARK_TRACK` · not invented |
| 9 | No human checkbox auto-ticked | **PASS** | `05-human-confirmation-sheet.md` all `[ ]` |
| 10 | No owner stamp issued | **PASS** | `OWNER_AUTHORIZATION_ISSUED=NO` · `MAY_ISSUE_APPROVED_OWNER_STAMP=NO` |
| 11 | No After generated | **PASS** | No acquisition / capture execution this window |
| 12 | No formal measurement executed | **PASS** | `FORMAL_OBSERVATION=NOT_STARTED` · `E-B_FORMAL_READY=NO` |

## Capture honesty (extra gate)

```text
product_stream
  + candidate A (E-B15 Product After capture path)
  + none_no_llm
  + llm_called_expected=false
CAPTURE_HONESTY_CONFLICT = NO
```

## Verdict

```text
CONSISTENCY_AUDIT                         = PASS
FREEZE_CANDIDATE_STATUS                   = PENDING_HUMAN_CONFIRMATION
BLOCKED_PENDING_HUMAN_REVIEW              = NO

Note (non-blocking for candidate status; blocking for base_sha freeze):
  WORKING_TREE_CLEAN                      = NO
  BASE_SHA_CANDIDATE_READY                = NO
  BASE_SHA_FREEZE_READINESS               = BLOCKED_PENDING_OWNER_REVIEW
```

Owner must still confirm whether `proposed_base_sha` is acceptable under a dirty
tree, or choose another sha after cleanup — that confirmation is **human**, not
an automatic audit failure of the candidate package itself.

## Stamp (this file)

```text
E-B35A_CONSISTENCY_AUDIT_COMPLETE = YES
FREEZE_CANDIDATE_STATUS           = PENDING_HUMAN_CONFIRMATION
```
