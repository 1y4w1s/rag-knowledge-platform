# 03 — Runtime & Reproducibility Freeze Template

> **Template only** — designs the reproducibility surface for a future human
> freeze record.  
> **Preparation ≠ Freeze** · **Template ≠ Filled Record** · **Designed ≠ Approved**

## 1. Purpose

Reproducibility fields bind capture execution to auditable runtime state. They
support stamp issuance and acquisition record match — but **designing fields**
does not freeze runtime truth.

```text
reproducibility template designed  ≠  runtime frozen
environment scan                   ≠  stamp artifact
```

## 2. Reproducibility surface (field design)

| Field | Role |
|---|---|
| `runtime_identity` | Host/process/runtime label for capture |
| `dependency_snapshot` | Declared dependency lock / manifest ref (no auto-scan) |
| `base_sha` | Exact git/tree sha of code+config |
| `configuration_ref` | Config profile / env ref (no secrets) |
| `run_identity_pattern` | Batch/suite run id or allowlist |
| `artifact_reference` | Optional pointer to companion artifact id pattern |

## 3. Freeze record template (fill later · human only)

```text
================================================================
RUNTIME & REPRODUCIBILITY FREEZE — Narrow Formal · candidate A
================================================================
freeze_kind              = NARROW_FORMAL_RUNTIME_REPRO_FREEZE
schema_ref               = eb32_runtime_repro_freeze_v1
primary_candidate_source = A

runtime_identity         = <FILL: human declared runtime id>
dependency_snapshot      = <FILL: lockfile ref / manifest id · no auto-scan>
base_sha                 = <FILL: exact git/tree sha>
configuration_ref        = <FILL: config profile ref · no secrets>
run_identity_pattern     = <FILL: exact id or allowlist>
artifact_reference       = <FILL: optional artifact id pattern or N/A>

freeze_status            = DRAFT
frozen_by                = <FILL: human>
frozen_at                = <FILL: ISO-8601 UTC>
================================================================
```

## 4. Rules (this window)

```text
[ ] Design fields only — all values remain <FILL>
[ ] Do NOT fill real git sha / hash / lockfile digest
[ ] Do NOT scan current environment to auto-generate stamp fields
[ ] Do NOT infer runtime_identity from pytest or CI hostname
[ ] Human freeze window must supply exact strings later
```

## 5. Match predicate (future · acquisition honesty)

When filled and frozen, acquisition records must match:

```text
acquisition.base_sha              = freeze.base_sha
acquisition.run_identity          ∈ freeze.run_identity_pattern (if allowlist)
acquisition.runtime_identity      = freeze.runtime_identity
acquisition.model_backend_identity = capture_mode freeze (see 02)
```

**This window:** predicate designed only — **no live match possible**.

## 6. Explicit prohibitions

```text
DO NOT populate real hash values in this template.
DO NOT run environment introspection to fill dependency_snapshot.
DO NOT create stamp artifacts from this template.
DO NOT set CAPTURE_MODE_FROZEN = YES.
DO NOT set SOURCE_APPROVED / AFTER_SOURCE_APPROVED = YES.
DO NOT set OWNER_AUTHORIZATION_ISSUED = YES.
DO NOT call LLM / API / LM Studio.
```

## 7. Stamp (this file)

```text
RUNTIME_REPRO_FREEZE_TEMPLATE_DESIGNED = YES
RUNTIME_TEMPLATE_READY                 = YES
CAPTURE_MODE_FROZEN                    = NO
SOURCE_IDENTITY_COMPLETE               = NO
OWNER_AUTHORIZATION_ISSUED             = NO
E-B_FORMAL_READY                       = NO
```
