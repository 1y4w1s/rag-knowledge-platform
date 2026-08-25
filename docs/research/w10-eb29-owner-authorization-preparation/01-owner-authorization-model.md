# 01 — Owner authorization model

> Freezes what **owner authorization** means for Narrow Formal Product After
> acquisition under PRIMARY candidate A.  
> **Design only** — no stamp issued · no gate flipped.

## 1. Definition

```text
owner authorization (Narrow Formal After)  ⇔
    a human owner (or written human delegate) explicitly accepts a named
    Product After provenance + capture path + run + base sha + model/backend
    identity + capture mode as formal-eligible input for Narrow Formal
    (BP-A · C01–C11), recorded in a non-automatic approval stamp whose
    authorization_status = APPROVED.
```

This is **stronger** than:

- E-B15 harness readiness  
- E-B27 PRIMARY candidate selection  
- E-B28 source/model separation design  
- pytest / wireup / scorer greens  
- E-B18 binding-codec compatibility  

Those prove path / codec / architecture — **not** denom approval.

## 2. Required stamp contents (mandatory)

An owner stamp artifact (future — **not created here**) must include **all** of:

| Element | Field (design id) | Requirement |
|---|---|---|
| **source identity** | `source_identity` / `after_source` | Named Product After provenance id; not implied from pytest name |
| **capture path identity** | `capture_path_identity` | Explicit path id for candidate A: E-B15 harness validated Product After capture path (not Formal Evaluation Source) |
| **run identity** | `run_identity` | Exact suite/batch id or allowlist pattern being authorized |
| **base sha** | `base_sha` | Exact code/config tree sha approved for that capture |
| **model/backend identity** | `model_backend_identity` | Frozen generator / backend identity; use `none_no_llm` when no model; never omit when a backend exists |
| **capture mode** | `capture_mode` | Owner-approved Narrow mode id; never silent smoke→formal |
| **authorization status** | `authorization_status` | One of `APPROVED` · `DENIED` · `WITHHELD` · `REVOKED`; only `APPROVED` may flip After-source gates |

### 2.1 Companion fields (required for honesty)

```text
stamp_kind              = OWNER_AFTER_SOURCE_APPROVAL
scope                   = Narrow Formal Observation (first)
binding_policy          = observed_after          # BP-A
suite_id                = w9_critic_frozen_12
cases_covered           = C01..C11
c12_policy              = INELIGIBLE_NOT_SCORED
primary_candidate_ref   = E-B27 Option A
formal_source_claim     = false                   # stamp ≠ Formal Evaluation Source alone
generation_config_ref   = <hash or canonical blob id · or explicit N/A>
llm_called_expected     = <bool matching mode>
source_owner            = <person / role · human>
approved_at             = <ISO-8601 UTC>
approval_statement      = "APPROVED for Narrow Formal After denom"
                                                          # only if authorization_status=APPROVED
auto_derived            = false
source_model_separation = YES                     # E-B28 freeze acknowledged
```

### 2.2 Illustrative shape (not issued)

```text
# EXAMPLE ONLY — DO NOT treat as a real stamp
source_identity           = product_stream_scheme_a_narrow_v1   # TBD by owner
capture_path_identity     = eb15_harness_product_after_capture_path_a
run_identity              = <TBD>
base_sha                  = <TBD>
model_backend_identity    = none_no_llm                         # if A no-LLM mode
capture_mode              = <TBD Narrow Scheme A mode id>
authorization_status      = WITHHELD                            # current reality
```

## 3. Authorization predicate

```text
AFTER_SOURCE_APPROVED = YES  ⇔
    owner stamp present
  ∧ stamp.auto_derived = false
  ∧ stamp.authorization_status = APPROVED
  ∧ stamp.scope matches Narrow Formal
  ∧ stamp.binding_policy = observed_after
  ∧ stamp.source_identity / capture_path_identity / capture_mode
      / model_backend_identity / base_sha / run_identity
      match the (future) acquired suite records
  ∧ E-B24 four-condition conjunction holds for the suite
      (source identity ∧ BP-A hash binding ∧ capture mode ∧ ¬synthetic)

SOURCE_APPROVED = YES  ⇔  AFTER_SOURCE_APPROVED = YES
  (synonym gate for this Narrow chain; no silent divergence)
```

Until issuance:

```text
authorization_status (effective) = WITHHELD
AFTER_SOURCE_APPROVED            = NO
SOURCE_APPROVED                  = NO
```

## 4. Hard separations

| Left | Right | Rule |
|---|---|---|
| **authorization** | **formal ready** | Stamp may approve After source; `E-B_FORMAL_READY` stays NO until a dedicated formal unlock |
| **approved source** | **completed observation** | Approved After ≠ Formal Observation executed / scored / reserved |
| **stamp designed** | **stamp issued** | This window = designed only |
| **capture path candidate A** | **Formal Evaluation Source** | E-B28: harness ≠ Formal Evaluation Source |
| **acquisition authorized** | **acquisition executed** | Entry gate may later open; this window executes neither |

```text
authorization          ≠  formal ready
approved source        ≠  completed observation
```

## 5. Who may stamp

```text
MAY_STAMP     = project owner (human) or explicitly written human delegate
MAY_NOT_STAMP = CI · pytest · coding agent · “LGTM” without full stamp fields
                · harness READY · candidate selection · architecture ADR
```

Default = **no delegation**. Any delegate must be written out of band before use.

## 6. Forbidden shortcuts

| Shortcut | Why forbidden |
|---|---|
| Auto-derive stamp from pytest green | Owner agency required |
| E-B15 `PRODUCT_AFTER_CAPTURE_HARNESS_READY=YES` ⇒ approved | Path proof ≠ denom approval |
| E-B27 `PRIMARY_CANDIDATE_SOURCE=A` ⇒ approved | Selection ≠ authorization |
| E-B28 `SOURCE_MODEL_SEPARATION_DESIGNED=YES` ⇒ approved | Architecture ≠ stamp |
| E-B18 `GOLD_AFTER_BINDING_COMPATIBLE=YES` ⇒ approved | Synthetic compat contamination risk |
| Silent smoke→formal capture_mode upgrade | Capture mode FAIL (E-B24) |
| Set `authorization_status=APPROVED` without all mandatory fields | Incomplete stamp = invalid |
| Flip `E-B_FORMAL_READY` because After was approved | Separate unlock window |

## 7. Relation to other gates

| Gate | Relationship |
|---|---|
| `AFTER_SOURCE_APPROVED` / `SOURCE_APPROVED` | Output of this stamp when `APPROVED` |
| `ACQUISITION_EXECUTION_READY` | Requires stamp **and** capture-mode/model freeze **and** entry checklist — not auto |
| `E-B_FORMAL_READY` | Independent; remains NO |
| `MAY_ENTER_FORMAL_OBSERVATION_WINDOW` | Requires After approval **plus** full formal entry checklist |
| `FORMAL_OBSERVATION` | Execution state; stays `NOT_STARTED` |

## 8. Current stamp (E-B29)

```text
OWNER_AUTHORIZATION_DESIGNED         = YES
OWNER_AUTHORIZATION_ISSUED           = NO
OWNER_AFTER_SOURCE_APPROVAL_ISSUED   = NO
authorization_status (effective)     = WITHHELD
SOURCE_APPROVED                      = NO
AFTER_SOURCE_APPROVED                = NO
ACQUISITION_EXECUTION_READY          = NO
E-B_FORMAL_READY                     = NO
FORMAL_OBSERVATION                   = NOT_STARTED
```
