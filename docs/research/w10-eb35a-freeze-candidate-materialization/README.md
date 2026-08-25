# W10 E-B35a · Human Freeze Candidate Materialization

> **Materialization only** — not freeze execution.  
> **`HUMAN_SUPPLIED_CANDIDATE ≠ HUMAN_FROZEN`**.  
> **`PENDING_HUMAN_CONFIRMATION ≠ FROZEN`**.  
> Cursor / CI / pytest **must not** tick human checkboxes or issue stamps.

## Objective

Combine:

1. Showcase decisions already accepted by the human owner in dialogue
   (`HUMAN_SUPPLIED_CANDIDATE`), and
2. read-only repository / runtime observations from this window

into one freeze **candidate** package whose status is:

```text
E-B35A_FREEZE_CANDIDATE_MATERIALIZED = YES
FREEZE_CANDIDATE_STATUS              = PENDING_HUMAN_CONFIRMATION
```

Then **stop** and wait for human owner confirmation (E-B35b is **out of scope**).

## Package contents

| File | Role |
|---|---|
| [`01-human-supplied-candidate-values.md`](01-human-supplied-candidate-values.md) | Owner-accepted Showcase values (candidate provenance) |
| [`02-runtime-and-git-observation.md`](02-runtime-and-git-observation.md) | Read-only git / Python / dependency observations |
| [`03-showcase-freeze-candidate-record.md`](03-showcase-freeze-candidate-record.md) | Unified candidate record (`PENDING_HUMAN_CONFIRMATION`) |
| [`04-candidate-consistency-audit.md`](04-candidate-consistency-audit.md) | 12-point consistency audit |
| [`05-human-confirmation-sheet.md`](05-human-confirmation-sheet.md) | Unticked owner confirmation checklist |
| [`06-eb35a-verdict.md`](06-eb35a-verdict.md) | End-of-window gate matrix + wait state |

## Inheritance (unchanged by this window)

```text
E-B34_SHOWCASE_FREEZE_REVIEW_COMPLETE = YES
SHOWCASE_TRACK                        = PRIMARY
RESEARCH_BENCHMARK_TRACK              = LONG_TERM
RESEARCH_BENCHMARK_TRACK_EXECUTED     = NO
LOCAL_MODEL_FIRST                     = YES
LOCAL_MODEL_PINNED                    = NO
LOCAL_MODEL_AS_NARROW_FORMAL_PRIMARY  = NO
PRIMARY_CANDIDATE_SOURCE              = A
  = selected design candidate only
  ≠ Formal Evaluation Source
  ≠ SOURCE_APPROVED
```

## Hard separations

```text
HUMAN_SUPPLIED_CANDIDATE  ≠  HUMAN_FROZEN
REPOSITORY_VERIFIED_CANDIDATE ≠ HUMAN_FROZEN
RUNTIME_OBSERVED_CANDIDATE ≠ HUMAN_FROZEN
observed_base_sha         ≠  frozen base_sha
proposed_base_sha         ≠  base_sha_frozen
LM Studio                 =  Development Generation Backend
LM Studio                 ≠  Narrow Formal Primary
formal_model_identity     =  DEFER_TO_BENCHMARK_TRACK
provenance_class=Product After  ⇏  AFTER_SOURCE_APPROVED
```

## Allowed provenance tags (this package)

```text
HUMAN_SUPPLIED_CANDIDATE
REPOSITORY_VERIFIED_CANDIDATE
RUNTIME_OBSERVED_CANDIDATE
DEFER_TO_BENCHMARK_TRACK
HUMAN_CONFIRMATION_REQUIRED
```

**Forbidden as achieved status in this window (DO NOT set):**
`HUMAN_FROZEN` · achieved `freeze_status` value FROZEN · approval/ready gates flipped to `YES`.

## Non-goals (strict)

```text
DO NOT set SOURCE_IDENTITY_COMPLETE / CAPTURE_MODE_FROZEN = YES
DO NOT set freeze_status = FROZEN
DO NOT issue owner stamp / OWNER_AUTHORIZATION_ISSUED
DO NOT approve source / After
DO NOT acquire After / run formal observation
DO NOT call LM Studio / API / LLM
DO NOT modify backend/app
DO NOT auto-commit / stash / reset working tree
DO NOT invent review_by exact date
DO NOT auto-tick human checklist
DO NOT enter E-B35b
```

## Stamp (this README)

```text
E-B35A_FREEZE_CANDIDATE_MATERIALIZED = YES
FREEZE_CANDIDATE_STATUS              = PENDING_HUMAN_CONFIRMATION

SOURCE_IDENTITY_COMPLETE             = NO
CAPTURE_MODE_FROZEN                  = NO
MAY_ISSUE_APPROVED_OWNER_STAMP       = NO
OWNER_AUTHORIZATION_ISSUED           = NO
SOURCE_APPROVED                      = NO
AFTER_SOURCE_APPROVED                = NO
ACQUISITION_EXECUTION_READY          = NO
E-B_FORMAL_READY                     = NO
FORMAL_OBSERVATION                   = NOT_STARTED

WAITING_FOR_HUMAN_CONFIRMATION       = YES
E-B35b entered                       = NO
```
