# 02 — Capture Mode Freeze Record (Draft)

> **Record draft** converted from E-B32 template
> [`../w10-eb32-freeze-preparation/02-capture-mode-freeze-template.md`](../w10-eb32-freeze-preparation/02-capture-mode-freeze-template.md).  
> **Template ≠ Record** · **Record draft ≠ Approved freeze** ·
> **Draft ≠ CAPTURE_MODE_FROZEN**

## 1. Allowed mode enum (design · not selected in this draft)

```text
capture_mode ∈ {
  product_stream,       # Product-path After via authorized product stream
  authorized_export,    # Owner-authorized export path (explicit · audited)
}
```

```text
candidate mode design  ≠  capture mode frozen
capture_mode_id on this draft = <FILL>  (human must choose later)
CAPTURE_MODE_FROZEN    = NO
```

## 2. Forbidden as Narrow Formal Primary (design rule · not a mode pick)

```text
[x] LM Studio as Narrow Formal Primary capture path
[x] Cloud API as Narrow Formal Primary capture path
[x] A4 live LLM capture as Narrow T1–T3 After
[x] S2 / empty-gate relabeled as Narrow After
[x] Development Generation Backend runs as Formal After
```

Provenance: repository verified ·
`docs/research/w10-eb32-freeze-preparation/02-capture-mode-freeze-template.md` §2 ·
`docs/research/w10-eb28-source-model-separation/`.

## 3. Freeze record draft

```text
================================================================
CAPTURE MODE FREEZE — Narrow Formal · PRIMARY candidate A
RECORD KIND              = DRAFT (not FROZEN · not APPROVED)
================================================================
freeze_kind              = NARROW_FORMAL_CAPTURE_MODE_FREEZE
                           provenance: template-fixed · eb32 02
schema_ref               = eb32_capture_mode_freeze_v1
                           provenance: template-fixed · eb32 02
primary_candidate_source = A
                           provenance: repository verified ·
                           eb27 / eb32 README
                           NOTE: selected design candidate only
capture_path_identity    = eb15_harness_product_after_capture_path_a
                           provenance: template-fixed · eb32 02
                           NOTE: capture path candidate ·
                           ≠ Formal Evaluation Source

capture_mode_id          = <FILL>
                           allowed: product_stream | authorized_export
                           provenance required: human supplied
                           DO NOT pre-select either value in E-B33
mode_owner               = <FILL>
                           provenance required: human supplied
runtime_identity         = <FILL>
                           provenance required: human supplied
model_backend_identity   = <FILL>
                           provenance required: human supplied
                           (e.g. none_no_llm is allowed · not auto-filled)
llm_called_expected      = <FILL>
                           allowed: true | false
                           provenance required: human supplied
generation_config_ref    = <FILL>
                           provenance required: human supplied
                           (config ref or explicit N/A)
base_sha                 = <FILL>
                           provenance required: human supplied
                           (exact git/tree sha · DO NOT auto-scan HEAD)
run_identity_pattern     = <FILL>
                           provenance required: human supplied

freeze_status            = DRAFT
                           provenance: template-fixed · draft window rule
frozen_by                = <FILL>
                           provenance required: human supplied
frozen_at                = <FILL>
                           provenance required: human supplied · ISO-8601 UTC
================================================================
```

## 4. Freeze predicate status

```text
CAPTURE_MODE_FROZEN = YES  ⇔
    capture_mode_id chosen from enum (human)
  ∧ mode_owner = human
  ∧ runtime_identity frozen (human)
  ∧ model_backend_identity frozen (human)
  ∧ llm_called_expected frozen (human)
  ∧ generation_config_ref frozen (human or explicit N/A)
  ∧ base_sha frozen (human · exact)
  ∧ run_identity_pattern frozen (human)
  ∧ freeze_status = FROZEN
  ∧ frozen_by + frozen_at present
  ∧ E-B28 separation acknowledged on filled record
```

**This draft window:**

```text
CAPTURE_MODE_RECORD_DRAFT = YES
CAPTURE_MODE_FROZEN       = NO
freeze_status             = DRAFT only
SOURCE_APPROVED           = NO
AFTER_SOURCE_APPROVED     = NO
OWNER_AUTHORIZATION_ISSUED = NO
```

## 5. Explicit prohibitions

```text
DO NOT set freeze_status = FROZEN on this draft.
DO NOT pre-select product_stream or authorized_export as a formal decision.
DO NOT fill base_sha from git HEAD / CI / agent scan.
DO NOT use LM Studio / API as Narrow Formal Primary.
DO NOT set CAPTURE_MODE_FROZEN = YES.
DO NOT set SOURCE_APPROVED / AFTER_SOURCE_APPROVED = YES.
DO NOT set OWNER_AUTHORIZATION_ISSUED = YES.
DO NOT call LLM / API / LM Studio.
DO NOT modify backend/app.
```

## 6. Stamp (this file)

```text
CAPTURE_MODE_FREEZE_RECORD_DRAFT = YES
CAPTURE_MODE_FROZEN              = NO
SOURCE_APPROVED                  = NO
AFTER_SOURCE_APPROVED            = NO
OWNER_AUTHORIZATION_ISSUED       = NO
E-B_FORMAL_READY                 = NO
```
