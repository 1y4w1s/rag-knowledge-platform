# 01 — Source Identity Freeze Record (Draft)

> **Record draft** converted from E-B32 template
> [`../w10-eb32-freeze-preparation/01-source-identity-freeze-template.md`](../w10-eb32-freeze-preparation/01-source-identity-freeze-template.md).  
> **Template ≠ Record** · **Record draft ≠ Approved freeze** ·
> **Draft ≠ SOURCE_IDENTITY_COMPLETE**

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
```

Narrow Formal scope (design inheritance · not freeze confirmation):
BP-A · C01–C11 · C12 INELIGIBLE · A4/S2-as-T1–T3 excluded.

## 2. Freeze record draft

Provenance legend:

| Tag | Meaning |
|---|---|
| `repository verified` | Value taken from committed research / AGENTS / prior window docs |
| `human supplied` | Must be written by owner / delegate (not present → `<FILL>`) |
| `template-fixed` | Schema / status constant from E-B32 template shape |

```text
================================================================
SOURCE IDENTITY FREEZE — Narrow Formal · PRIMARY candidate A
RECORD KIND              = DRAFT (not FROZEN · not APPROVED)
================================================================
freeze_kind              = NARROW_FORMAL_SOURCE_IDENTITY_FREEZE
                           provenance: template-fixed · eb32 01
schema_ref               = eb32_source_identity_freeze_v1
                           provenance: template-fixed · eb32 01
primary_candidate_source = A
                           provenance: repository verified ·
                           docs/research/w10-eb27-source-selection/README.md
                           · docs/research/w10-eb32-freeze-preparation/README.md
                           NOTE: selected design candidate only

source_identity          = <FILL>
                           provenance required: human supplied
after_source_id          = <FILL>
                           provenance required: human supplied
                           (exact or explicit alias to source_identity)
product_name             = <FILL>
                           provenance required: human supplied
                           (do NOT auto-fill from AGENTS.md product brand alone)
product_version          = <FILL>
                           provenance required: human supplied
deployment_identity      = <FILL>
                           provenance required: human supplied
environment_identity     = <FILL>
                           provenance required: human supplied
                           (env name / config profile · no secrets)

suite_binding            = w9_critic_frozen_12
                           provenance: repository verified ·
                           docs/research/w10-eb27-source-selection/README.md
                           ("Suite: w9_critic_frozen_12")
                           · docs/research/w10-eb30-owner-stamp-issuance-planning/
                             03-capture-mode-freeze-plan.md
                           NOTE: design binding on draft · human must still
                           confirm on freeze execution (not frozen)
case_scope               = C01..C11 · c12_policy=INELIGIBLE_NOT_SCORED
                           provenance: repository verified ·
                           docs/research/w10-eb24-narrow-formal-preparation/
                           · docs/research/w10-eb32-freeze-preparation/
                             01-source-identity-freeze-template.md §1 Scope
                           NOTE: design scope on draft · human must still
                           confirm on freeze execution (not frozen)
authorization_scope      = <FILL>
                           provenance required: human supplied
                           (Narrow Formal scope narrative + binding refs)

provenance_class         = Product After
                           provenance: template-fixed · eb32 01
formal_evaluation_source = NO
                           provenance: template-fixed · eb32 01
                           (candidate path only until owner freeze + stamp)

freeze_status            = DRAFT
                           provenance: template-fixed · draft window rule
                           (DO NOT write FROZEN as achieved in E-B33)
frozen_by                = <FILL>
                           provenance required: human supplied
frozen_at                = <FILL>
                           provenance required: human supplied · ISO-8601 UTC
================================================================
```

## 3. Completeness against E-B32 predicate

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

**This draft window:**

| Pillar / field | Draft state |
|---|---|
| `source_identity` | `<FILL>` |
| `after_source_id` | `<FILL>` |
| `product_name` | `<FILL>` |
| `product_version` | `<FILL>` |
| `deployment_identity` | `<FILL>` |
| `environment_identity` | `<FILL>` |
| `suite_binding` | filled as design draft · **not frozen** |
| `case_scope` | filled as design draft · **not frozen** |
| `authorization_scope` | `<FILL>` |
| anti-contamination ack on record | **NO** (checklist unticked) |

```text
SOURCE_IDENTITY_COMPLETE = NO
SOURCE_IDENTITY_FROZEN   = NO
SOURCE_APPROVED          = NO
AFTER_SOURCE_APPROVED    = NO
```

## 4. Explicit prohibitions

```text
DO NOT invent source_identity / after_source_id.
DO NOT treat PRIMARY_CANDIDATE_SOURCE=A as approved source.
DO NOT set freeze_status = FROZEN in this window.
DO NOT set SOURCE_IDENTITY_COMPLETE = YES while pillars remain <FILL>.
DO NOT set SOURCE_APPROVED / AFTER_SOURCE_APPROVED = YES.
DO NOT set OWNER_AUTHORIZATION_ISSUED = YES.
DO NOT call LLM / API / LM Studio.
DO NOT modify backend/app.
```

## 5. Stamp (this file)

```text
SOURCE_IDENTITY_FREEZE_RECORD_DRAFT = YES
SOURCE_IDENTITY_COMPLETE            = NO
SOURCE_APPROVED                     = NO
AFTER_SOURCE_APPROVED               = NO
OWNER_AUTHORIZATION_ISSUED          = NO
E-B_FORMAL_READY                    = NO
```
