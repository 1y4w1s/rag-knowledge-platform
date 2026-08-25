# 02 — Capture Mode Freeze Template

> **Template only** — defines the field shape for a future **filled** capture
> mode freeze record.  
> **Preparation ≠ Freeze** · **Template ≠ Filled Record** · **Designed ≠ Approved**

## 1. Allowed mode enum (design · not selected here)

```text
capture_mode ∈ {
  product_stream,       # Product-path After via authorized product stream
  authorized_export,    # Owner-authorized export path (explicit · audited)
}
```

**Not selected in this window.** Choosing a mode is a **later human freeze**
action.

```text
candidate mode design  ≠  capture mode frozen
CAPTURE_MODE_FROZEN    = NO   (this window)
```

## 2. Forbidden as Narrow Formal Primary (design rule)

```text
[x] LM Studio as Narrow Formal Primary capture path
[x] Cloud API as Narrow Formal Primary capture path
[x] A4 live LLM capture as Narrow T1–T3 After
[x] S2 / empty-gate relabeled as Narrow After
[x] Development Generation Backend runs as Formal After
```

## 3. Freeze record template (fill later · human only)

```text
================================================================
CAPTURE MODE FREEZE — Narrow Formal · PRIMARY candidate A
================================================================
freeze_kind              = NARROW_FORMAL_CAPTURE_MODE_FREEZE
schema_ref               = eb32_capture_mode_freeze_v1
primary_candidate_source = A
capture_path_identity    = eb15_harness_product_after_capture_path_a

capture_mode_id          = <FILL: product_stream | authorized_export>
mode_owner               = <FILL: human>
runtime_identity         = <FILL: capture runtime id>
model_backend_identity   = <FILL: e.g. none_no_llm>
llm_called_expected      = <FILL: true | false>
generation_config_ref    = <FILL: config ref or N/A>
base_sha                 = <FILL: exact git/tree sha at freeze>
run_identity_pattern     = <FILL: exact id or allowlist pattern>

freeze_status            = DRAFT
frozen_by                = <FILL: human>
frozen_at                = <FILL: ISO-8601 UTC>
================================================================
```

## 4. Field definitions

| Field | Purpose |
|---|---|
| `capture_mode_id` | Enum member from §1 |
| `mode_owner` | Human accountable for mode choice |
| `runtime_identity` | Process/host/runtime of capture |
| `model_backend_identity` | Generator identity (`none_no_llm` allowed) |
| `llm_called_expected` | Honest LLM call expectation for this mode |
| `generation_config_ref` | Config blob / hash ref if LLM used; else N/A |
| `base_sha` | Code+config tree at freeze |
| `run_identity_pattern` | Suite/batch id or allowlist |
| `freeze_status` | `DRAFT` until human freeze window sets `FROZEN` |
| `frozen_by` / `frozen_at` | Human freeze audit trail |

## 5. Freeze predicate (future · not satisfied by this template)

```text
CAPTURE_MODE_FROZEN = YES  ⇔
    capture_mode_id chosen from §1 enum (human)
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

**This window:**

```text
CAPTURE_TEMPLATE_READY  = YES
CAPTURE_MODE_FROZEN     = NO
freeze_status (template) = DRAFT only — DO NOT write FROZEN as achieved
```

## 6. Explicit prohibitions

```text
DO NOT set freeze_status = FROZEN on this template.
DO NOT pre-select product_stream or authorized_export as a formal decision.
DO NOT use LM Studio / API as Narrow Formal Primary in any filled record here.
DO NOT set CAPTURE_MODE_FROZEN = YES in this window.
DO NOT set SOURCE_APPROVED / AFTER_SOURCE_APPROVED = YES.
DO NOT set OWNER_AUTHORIZATION_ISSUED = YES.
DO NOT call LLM / API / LM Studio.
```

## 7. Stamp (this file)

```text
CAPTURE_MODE_FREEZE_TEMPLATE_DESIGNED = YES
CAPTURE_MODE_FROZEN                   = NO
SOURCE_APPROVED                       = NO
AFTER_SOURCE_APPROVED                 = NO
OWNER_AUTHORIZATION_ISSUED            = NO
ACQUISITION_EXECUTION_READY           = NO
E-B_FORMAL_READY                      = NO
```
