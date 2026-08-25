# W10 E-B36 · Human Owner Stamp Issuance

> **Does:** Issue the **canonical** `eb30_owner_stamp_v1` Owner Stamp with
> `authorization_status=APPROVED` from explicit human owner authorization,
> and apply only E-B30 §3.1 APPROVED issuance effects.
>
> **Does not:** acquisition execution · After capture · scoring ·
> Formal Observation unlock · call LM Studio / API / LLM · modify
> `backend/app` · rewrite frozen `base_sha` to documentation HEAD.

## Status freeze (end of this window)

```text
MAY_ISSUE_APPROVED_OWNER_STAMP      = YES   (precondition remained satisfied)
OWNER_AUTHORIZATION_ISSUED          = YES
SOURCE_APPROVED                     = YES
AFTER_SOURCE_APPROVED               = YES   (E-B30 §3.1 explicit effect)

ACQUISITION_EXECUTION_READY         = NO    (stamp ≠ auto acquisition entry)
E-B_FORMAL_READY                    = NO
MAY_ENTER_FORMAL_OBSERVATION_WINDOW = NO
FORMAL_OBSERVATION                  = NOT_STARTED

WAITING_FOR_ACQUISITION_ENTRY_REVIEW = YES
```

## Parent chain

| Window | Role |
|---|---|
| E-B30 | Stamp schema + issuance gate designed |
| E-B35b | Human Showcase Freeze (identities frozen) |
| Issuance Review | `MAY_ISSUE_APPROVED_OWNER_STAMP=YES` |
| **E-B36** | **Human Owner Stamp Issuance** (this window) |

## Documents

1. [`01-approved-owner-stamp.md`](01-approved-owner-stamp.md) — **canonical APPROVED stamp**
2. [`02-human-issuance-provenance.md`](02-human-issuance-provenance.md) — human authority
3. [`03-post-issuance-effect-evaluation.md`](03-post-issuance-effect-evaluation.md) — E-B30 effects
4. [`04-acquisition-entry-status.md`](04-acquisition-entry-status.md) — entry remains NO
5. [`05-eb36-verdict.md`](05-eb36-verdict.md) — integrity + gate matrix

## Canonical stamp rule

```text
Exactly ONE APPROVED Owner Stamp artifact for this Narrow Showcase chain.
Canonical path = 01-approved-owner-stamp.md
Conflicting second APPROVED stamp = FORBIDDEN
```

## Core separations

```text
stamp APPROVED     ≠  acquisition executed
SOURCE_APPROVED    ≠  After captured
AFTER_SOURCE_APPROVED ≠ Formal Observation
OWNER_AUTHORIZATION_ISSUED ≠ E-B_FORMAL_READY
frozen base_sha    ≠  documentation HEAD after E-B35b/E-B36 commits
```

## Explicit non-goals

```text
DO NOT start acquisition / After capture.
DO NOT flip ACQUISITION_EXECUTION_READY = YES in this window.
DO NOT flip E-B_FORMAL_READY / Formal Observation.
DO NOT call LM Studio / API / LLM.
DO NOT modify backend/app.
DO NOT rewrite stamp base_sha to current HEAD.
```
