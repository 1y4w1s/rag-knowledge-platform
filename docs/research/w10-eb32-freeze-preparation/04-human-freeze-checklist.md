# 04 — Human Freeze Checklist

> **Checklist template only** — boxes are **unchecked** and must **not** be
> auto-ticked by CI, pytest, or coding agent.  
> **Preparation ≠ Freeze** · **Template ≠ Filled Record** · **Designed ≠ Approved**

## 1. How to use (future human freeze window)

1. Copy this checklist into the human freeze execution record.
2. Owner or written delegate ticks boxes **only** with live evidence.
3. Unticked boxes ⇒ corresponding freeze predicate stays **NO**.

```text
checkbox template  ≠  freeze complete
CI green           ≠  human tick
```

## 2. Identity

```text
[ ] source_identity confirmed (named · not pytest-inferred)
[ ] after_source_id confirmed (exact or explicit alias)
[ ] product version confirmed (product_name + product_version)
[ ] deployment confirmed (deployment_identity)
[ ] environment confirmed (environment_identity · no secrets in record)
```

## 3. Capture

```text
[ ] capture_mode selected (product_stream | authorized_export · human choice)
[ ] runtime frozen (runtime_identity on filled record)
[ ] backend identity frozen (model_backend_identity + llm_called_expected)
[ ] run identity policy frozen (run_identity_pattern + base_sha)
```

## 4. Honesty

```text
[ ] E-B28 separation acknowledged (Formal Evaluation Source ≠ Development Backend)
[ ] synthetic After excluded (no E-B6 / smoke / fixture as Product After)
[ ] E-B18 rebound excluded (no author-owned claim-text embedding as Product After)
[ ] no LLM hallucinated provenance (ids must be human-declared · auditable)
[ ] candidate ≠ approved source acknowledged
[ ] capture path candidate ≠ Formal Evaluation Source acknowledged
```

## 5. Explicit non-actions (this template)

```text
DO NOT auto-tick any checkbox in E-B32.
DO NOT infer confirmation from PRIMARY_CANDIDATE_SOURCE=A alone.
DO NOT set SOURCE_IDENTITY_COMPLETE = YES from this unchecked template.
DO NOT set CAPTURE_MODE_FROZEN = YES from this unchecked template.
DO NOT set SOURCE_APPROVED / AFTER_SOURCE_APPROVED = YES.
DO NOT set OWNER_AUTHORIZATION_ISSUED = YES.
```

## 6. Checklist readiness (design only)

```text
HUMAN_CHECKLIST_READY = YES   (template exists · boxes intentionally empty)
HUMAN_CHECKLIST_COMPLETE = NO (no ticks until human freeze execution)
```

## 7. Stamp (this file)

```text
HUMAN_FREEZE_CHECKLIST_DESIGNED = YES
HUMAN_CHECKLIST_READY           = YES
HUMAN_CHECKLIST_COMPLETE        = NO
SOURCE_IDENTITY_COMPLETE        = NO
CAPTURE_MODE_FROZEN             = NO
OWNER_AUTHORIZATION_ISSUED        = NO
E-B_FORMAL_READY                  = NO
```
