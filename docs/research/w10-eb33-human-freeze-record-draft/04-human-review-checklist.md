# 04 — Human Review Checklist (Freeze Record Draft)

> Checklist for **human review of the E-B33 draft records**.  
> Boxes are **unchecked** and must **not** be auto-ticked by CI, pytest, or
> coding agent.  
> **Template ≠ Record** · **Record draft ≠ Approved freeze** ·
> **Review checklist ≠ freeze complete**

Derived from E-B32
[`../w10-eb32-freeze-preparation/04-human-freeze-checklist.md`](../w10-eb32-freeze-preparation/04-human-freeze-checklist.md),
narrowed to **draft review** duties (fill / confirm later; no approval
inference).

## 1. How to use

1. Review `01`–`03` draft records against live owner knowledge.
2. Tick a box **only** with live evidence (human supplied string present, or
   repository-verified draft value explicitly accepted for freeze).
3. Unticked boxes ⇒ corresponding freeze predicate stays **NO**.
4. Completing this review checklist **alone** does **not** issue a stamp or
   set `SOURCE_APPROVED`.

```text
checkbox template  ≠  freeze complete
CI green           ≠  human tick
draft filled       ≠  approved freeze
```

## 2. Draft integrity (E-B33)

```text
[ ] Template ≠ Record acknowledged
[ ] Record draft ≠ Approved freeze acknowledged
[ ] All unknown fields remain <FILL> (no invented ids / shas / modes)
[ ] Every filled identity field has provenance (human supplied | repository verified)
[ ] No auto-inference of SOURCE_APPROVED / formal eligibility / owner authorization
```

## 3. Identity (must become human-confirmed before SOURCE_IDENTITY_COMPLETE)

```text
[ ] source_identity confirmed (named · not pytest-inferred)     — currently <FILL>
[ ] after_source_id confirmed (exact or explicit alias)         — currently <FILL>
[ ] product_name confirmed                                      — currently <FILL>
[ ] product_version confirmed                                   — currently <FILL>
[ ] deployment_identity confirmed                               — currently <FILL>
[ ] environment_identity confirmed (no secrets in record)       — currently <FILL>
[ ] suite_binding accepted for freeze
      (draft shows w9_critic_frozen_12 · repository verified · not frozen)
[ ] case_scope accepted for freeze
      (draft shows C01..C11 · C12 INELIGIBLE · repository verified · not frozen)
[ ] authorization_scope confirmed                               — currently <FILL>
```

## 4. Capture (must become human-confirmed before CAPTURE_MODE_FROZEN)

```text
[ ] capture_mode_id selected (product_stream | authorized_export) — currently <FILL>
[ ] mode_owner confirmed                                        — currently <FILL>
[ ] runtime_identity frozen                                     — currently <FILL>
[ ] model_backend_identity + llm_called_expected frozen         — currently <FILL>
[ ] generation_config_ref frozen (or explicit N/A)              — currently <FILL>
[ ] base_sha frozen (exact · human)                             — currently <FILL>
[ ] run_identity_pattern frozen                                 — currently <FILL>
```

## 5. Runtime / reproducibility

```text
[ ] dependency_snapshot confirmed                               — currently <FILL>
[ ] configuration_ref confirmed (no secrets)                    — currently <FILL>
[ ] artifact_reference confirmed (or explicit N/A)              — currently <FILL>
[ ] frozen_by + frozen_at present on records set to FROZEN      — currently <FILL>
```

## 6. Honesty

```text
[ ] E-B28 separation acknowledged (Formal Evaluation Source ≠ Development Backend)
[ ] synthetic After excluded (no E-B6 / smoke / fixture as Product After)
[ ] E-B18 rebound excluded (no author-owned claim-text embedding as Product After)
[ ] no LLM hallucinated provenance (ids must be human-declared · auditable)
[ ] candidate ≠ approved source acknowledged
[ ] capture path candidate ≠ Formal Evaluation Source acknowledged
[ ] PRIMARY_CANDIDATE_SOURCE=A remains selected design candidate only
```

## 7. Explicit non-actions (this checklist)

```text
DO NOT auto-tick any checkbox in E-B33.
DO NOT infer confirmation from PRIMARY_CANDIDATE_SOURCE=A alone.
DO NOT set SOURCE_IDENTITY_COMPLETE = YES from this unchecked checklist.
DO NOT set CAPTURE_MODE_FROZEN = YES from this unchecked checklist.
DO NOT set SOURCE_APPROVED / AFTER_SOURCE_APPROVED = YES.
DO NOT set OWNER_AUTHORIZATION_ISSUED = YES.
DO NOT treat draft suite_binding / case_scope fills as freeze complete.
```

## 8. Checklist readiness

```text
HUMAN_REVIEW_CHECKLIST_READY    = YES   (checklist exists · boxes intentionally empty)
HUMAN_REVIEW_CHECKLIST_COMPLETE = NO    (no ticks in E-B33)
HUMAN_CHECKLIST_COMPLETE        = NO    (freeze execution still future)
```

## 9. Stamp (this file)

```text
HUMAN_REVIEW_CHECKLIST_DESIGNED = YES
HUMAN_REVIEW_CHECKLIST_READY    = YES
HUMAN_REVIEW_CHECKLIST_COMPLETE = NO
SOURCE_IDENTITY_COMPLETE        = NO
CAPTURE_MODE_FROZEN             = NO
OWNER_AUTHORIZATION_ISSUED      = NO
SOURCE_APPROVED                 = NO
AFTER_SOURCE_APPROVED           = NO
E-B_FORMAL_READY                = NO
```
