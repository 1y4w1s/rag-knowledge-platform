# 05 — Owner stamp preparation

> Designs the **future** owner approval contents for PRIMARY candidate A.  
> **No stamp created** in this window.

## 1. Intent

Prepare the field list an owner must fill to flip:

```text
AFTER_SOURCE_APPROVED = YES
SOURCE_APPROVED       = YES   (synonym gate for this chain)
```

Issuance remains a **human owner** action in a later window. Agents/CI must
not self-stamp (E-B26 `03`).

## 2. Required stamp contents (design)

| Field | Meaning for candidate A | Example shape (illustrative · not issued) |
|---|---|---|
| **after_source** | Named Product After provenance (formal-eligible **only after** owner stamp APPROVED) | e.g. `product_stream_scheme_a_narrow_v1` |
| **source_owner** | Human approving party | Project owner / delegated human authority |
| **run_identity** | Acquisition suite/batch id approved | Exact id or allowlist pattern |
| **base_sha** | Code/config tree sha for capture | Exact git/tree sha |
| **model_identity** | Frozen generator identity | Likely `none_no_llm` for A no-LLM modes |
| **capture_mode** | Owner-approved Narrow mode id | Declared Scheme A mode · **not** silent smoke→formal |
| **scope** | Observation scope reference | `Narrow Formal Observation (first)` · BP-A · C01–C11 |

### 2.1 Companion fields (recommended · from E-B26)

```text
stamp_kind            = OWNER_AFTER_SOURCE_APPROVAL
binding_policy        = observed_after
suite_id              = w9_critic_frozen_12
cases_covered         = C01..C11
c12_policy            = INELIGIBLE_NOT_SCORED
generation_config_ref = <hash or canonical blob id>
llm_called_expected   = false          # for A no-LLM modes
approved_at           = <ISO-8601 UTC>
approval_statement    = "APPROVED for Narrow Formal After denom"
auto_derived          = false
primary_candidate_ref = E-B27 Option A
```

## 3. Approval predicate (unchanged honesty)

```text
AFTER_SOURCE_APPROVED = YES  ⇔
    owner stamp present
  ∧ stamp.auto_derived = false
  ∧ stamp.scope matches Narrow Formal
  ∧ stamp.binding_policy = observed_after
  ∧ stamp.after_source / capture_mode / model_identity / base_sha / run_identity
      match the acquired suite records
  ∧ E-B24 four-condition conjunction holds for the suite
```

Until issuance:

```text
AFTER_SOURCE_APPROVED = NO
SOURCE_APPROVED       = NO
```

## 4. Explicit non-goals (this window)

```text
DO NOT create a real stamp artifact.
DO NOT set AFTER_SOURCE_APPROVED = YES.
DO NOT set SOURCE_APPROVED = YES.
DO NOT freeze final after_source / capture_mode strings as “approved”
     (design examples only).
DO NOT treat E-B27 candidate pick as the stamp.
```

## 5. Current stamp state

```text
OWNER_STAMP_PREPARATION_DESIGNED = YES
OWNER_AFTER_SOURCE_APPROVAL_ISSUED = NO
SOURCE_APPROVED                    = NO
AFTER_SOURCE_APPROVED              = NO
ACQUISITION_EXECUTION_READY        = NO
E-B_FORMAL_READY                   = NO
FORMAL_OBSERVATION                 = NOT_STARTED
```
