# 01 — Source Identity Freeze Template

> **Template only** — defines the field shape for a future **filled** source
> identity freeze record.  
> **Preparation ≠ Freeze** · **Template ≠ Filled Record** · **Designed ≠ Approved**

## 1. Inheritance (not approval)

```text
PRIMARY_CANDIDATE_SOURCE = A
  = selected design candidate only
  = E-B15 harness validated Product After capture path candidate
  ≠ Formal Evaluation Source
  ≠ owner-approved After
  ≠ SOURCE_APPROVED
```

```text
PRIMARY_CANDIDATE_SOURCE=A is a selected design candidate only.
  ⇏  source approved
  ⇏  formal eligible
  ⇏  After approved
candidate ≠ approved source
capture path candidate ≠ Formal Evaluation Source
PRIMARY_CANDIDATE_SOURCE = A  ⇏  SOURCE_IDENTITY_COMPLETE = YES
```

Scope (Narrow Formal): BP-A · C01–C11 · C12 INELIGIBLE · A4/S2-as-T1–T3 excluded.

## 2. Freeze record template (fill later · human only)

```text
================================================================
SOURCE IDENTITY FREEZE — Narrow Formal · PRIMARY candidate A
================================================================
freeze_kind              = NARROW_FORMAL_SOURCE_IDENTITY_FREEZE
schema_ref               = eb32_source_identity_freeze_v1
primary_candidate_source = A

source_identity          = <FILL: named string · human chosen>
after_source_id          = <FILL: exact or explicit alias to source_identity>
product_name             = <FILL: product display name>
product_version          = <FILL: release / version label>
deployment_identity      = <FILL: authorized deployment topology>
environment_identity     = <FILL: env name / config profile · no secrets>

suite_binding            = <FILL: e.g. w9_critic_frozen_12>
case_scope               = <FILL: C01..C11 · c12_policy INELIGIBLE_NOT_SCORED>
authorization_scope      = <FILL: Narrow Formal scope narrative + binding refs>

provenance_class         = Product After
formal_evaluation_source = NO   # candidate path only until owner freeze + stamp

freeze_status            = DRAFT
frozen_by                = <FILL: human>
frozen_at                = <FILL: ISO-8601 UTC>
================================================================
```

## 3. Field definitions

| Field | Purpose | Fill rule |
|---|---|---|
| `source_identity` | Canonical named source id for stamp + acquisition | Human names; not pytest-inferred |
| `after_source_id` | After binding id (equal or explicit alias) | Must match acquisition honesty |
| `product_name` | Product surface being authorized | Human declared |
| `product_version` | Release label covering capture surface | Human declared; change ⇒ re-freeze |
| `deployment_identity` | Which deployment topology is authorized | Distinguish demo vs Narrow capture |
| `environment_identity` | Env / config profile (no secrets in record) | Human declared |
| `suite_binding` | Suite id bound to this identity | Typically `w9_critic_frozen_12` |
| `case_scope` | Measured cases + C12 policy | C01–C11; C12 INELIGIBLE |
| `authorization_scope` | Narrow scope + capture path + anti-contamination refs | Human narrative + ids |

## 4. Completeness predicate (future · not satisfied by this template)

```text
SOURCE_IDENTITY_COMPLETE = YES  ⇔
    source_identity frozen (human)
  ∧ after_source_id frozen (human)
  ∧ product_name + product_version frozen (human)
  ∧ deployment_identity frozen (human)
  ∧ environment_identity frozen (human)
  ∧ suite_binding + case_scope frozen (human)
  ∧ authorization_scope frozen (human)
  ∧ anti-contamination acknowledged on filled record
```

**This window:**

```text
SOURCE_IDENTITY_TEMPLATE_READY = YES   (field shape designed)
SOURCE_IDENTITY_COMPLETE       = NO
SOURCE_IDENTITY_FROZEN         = NO
SOURCE_APPROVED                = NO
AFTER_SOURCE_APPROVED          = NO
```

## 5. Explicit prohibitions

```text
DO NOT auto-generate source_identity from pytest / CI / agent.
DO NOT infer identity from runtime scans or git HEAD in this window.
DO NOT fill owner fields (frozen_by, product_version, deployment, environment).
DO NOT treat PRIMARY_CANDIDATE_SOURCE=A as approved source.
DO NOT set SOURCE_APPROVED / AFTER_SOURCE_APPROVED = YES.
DO NOT set OWNER_AUTHORIZATION_ISSUED = YES.
DO NOT generate After to “prove” identity fields.
DO NOT call LLM / API / LM Studio.
```

## 6. Relation to adjacent templates

Runtime / model / sha / run identity fields live in:

- [`02-capture-mode-freeze-template.md`](02-capture-mode-freeze-template.md)
- [`03-runtime-and-reproducibility-freeze-template.md`](03-runtime-and-reproducibility-freeze-template.md)

```text
runtime frozen     ⇏  source identity complete
model frozen       ⇏  source identity complete
template designed  ⇏  SOURCE_IDENTITY_COMPLETE
```

## 7. Stamp (this file)

```text
SOURCE_IDENTITY_FREEZE_TEMPLATE_DESIGNED = YES
SOURCE_IDENTITY_COMPLETE                 = NO
SOURCE_APPROVED                          = NO
AFTER_SOURCE_APPROVED                    = NO
OWNER_AUTHORIZATION_ISSUED               = NO
ACQUISITION_EXECUTION_READY              = NO
E-B_FORMAL_READY                         = NO
```
