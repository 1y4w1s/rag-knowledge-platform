# 03 — Runtime Identity Freeze Record (Draft)

> **Record draft** converted from E-B32 template
> [`../w10-eb32-freeze-preparation/03-runtime-and-reproducibility-freeze-template.md`](../w10-eb32-freeze-preparation/03-runtime-and-reproducibility-freeze-template.md).  
> **Template ≠ Record** · **Record draft ≠ Approved freeze** ·
> **Reproducibility draft ≠ runtime frozen**

## 1. Purpose

Reproducibility fields bind future capture execution to auditable runtime
state. This window only materializes the **draft record shape** with
template-fixed / repository-verified constants. Live runtime values remain
`<FILL>` — no environment scan, no git HEAD inference, no stamp artifact.

```text
reproducibility draft filled constants  ≠  runtime frozen
environment scan                        ≠  stamp artifact
base_sha <FILL>                         ≠  permission to invent sha
```

## 2. Freeze record draft

```text
================================================================
RUNTIME & REPRODUCIBILITY FREEZE — Narrow Formal · candidate A
RECORD KIND              = DRAFT (not FROZEN · not APPROVED)
================================================================
freeze_kind              = NARROW_FORMAL_RUNTIME_REPRO_FREEZE
                           provenance: template-fixed · eb32 03
schema_ref               = eb32_runtime_repro_freeze_v1
                           provenance: template-fixed · eb32 03
primary_candidate_source = A
                           provenance: repository verified ·
                           eb27 / eb32 README
                           NOTE: selected design candidate only

runtime_identity         = <FILL>
                           provenance required: human supplied
dependency_snapshot      = <FILL>
                           provenance required: human supplied
                           (lockfile ref / manifest id · no auto-scan)
base_sha                 = <FILL>
                           provenance required: human supplied
                           (exact git/tree sha · DO NOT fill from HEAD)
configuration_ref        = <FILL>
                           provenance required: human supplied
                           (config profile ref · no secrets)
run_identity_pattern     = <FILL>
                           provenance required: human supplied
artifact_reference       = <FILL>
                           provenance required: human supplied
                           (optional artifact id pattern or explicit N/A)

freeze_status            = DRAFT
                           provenance: template-fixed · draft window rule
frozen_by                = <FILL>
                           provenance required: human supplied
frozen_at                = <FILL>
                           provenance required: human supplied · ISO-8601 UTC
================================================================
```

## 3. Match predicate (future · not live)

When filled and frozen, acquisition records must match:

```text
acquisition.base_sha               = freeze.base_sha
acquisition.run_identity           ∈ freeze.run_identity_pattern (if allowlist)
acquisition.runtime_identity       = freeze.runtime_identity
acquisition.model_backend_identity = capture_mode freeze (see 02)
```

**This draft window:** predicate known · **no live match possible** (all match
keys remain `<FILL>`).

## 4. Explicit prohibitions

```text
DO NOT populate real hash values from environment introspection.
DO NOT run dependency auto-scan to fill dependency_snapshot.
DO NOT infer runtime_identity from pytest / CI hostname.
DO NOT create stamp artifacts from this draft.
DO NOT set CAPTURE_MODE_FROZEN = YES.
DO NOT set SOURCE_IDENTITY_COMPLETE = YES.
DO NOT set SOURCE_APPROVED / AFTER_SOURCE_APPROVED = YES.
DO NOT set OWNER_AUTHORIZATION_ISSUED = YES.
DO NOT call LLM / API / LM Studio.
DO NOT modify backend/app.
```

## 5. Stamp (this file)

```text
RUNTIME_IDENTITY_FREEZE_RECORD_DRAFT = YES
RUNTIME_FROZEN                       = NO
CAPTURE_MODE_FROZEN                  = NO
SOURCE_IDENTITY_COMPLETE             = NO
OWNER_AUTHORIZATION_ISSUED           = NO
E-B_FORMAL_READY                     = NO
```
