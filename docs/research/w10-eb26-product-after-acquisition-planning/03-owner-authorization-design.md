# 03 — Owner authorization design

> Defines what **owner-approved After source** means for Narrow Formal.  
> Design only — **no stamp issued** in this window.

## 1. Definition

```text
owner-approved After source  ⇔
    a named Product After provenance is explicitly accepted by the project
    owner as formal-eligible input for Narrow Formal (BP-A · C01–C11)
    under a frozen capture mode and model identity,
    with a non-automatic approval stamp bound to run identity + base sha.
```

This is **stronger** than:

- harness readiness  
- pytest green  
- binding-codec compatibility (E-B18)  
- scorer / wireup tests green  

E-B24/E-B25 already freeze: those greens **do not** approve After.

## 2. Required stamp contents

An owner approval stamp (future artifact — not created here) must include:

| Element | Requirement |
|---|---|
| **source owner** | Identified approving party (human owner / designated authority). Not “CI”, not “agent”. |
| **approval stamp** | Explicit statement: source is formal-eligible for Narrow Formal; date/time; scope reference (E-B24 Narrow). |
| **run identity** | The acquisition `run_identity` (or allowed run pattern) being approved. |
| **base sha** | Exact code/config tree sha approved for that capture. |
| **model identity** | Exact frozen model / generator identity (including `none_no_llm` if applicable). |

### Recommended stamp fields (design)

```text
stamp_kind            = OWNER_AFTER_SOURCE_APPROVAL
scope                 = Narrow Formal Observation (first)
binding_policy        = observed_after   # BP-A
suite_id              = w9_critic_frozen_12
cases_covered         = C01..C11
c12_policy            = INELIGIBLE_NOT_SCORED
after_source          = <named provenance id>
capture_mode          = <approved mode id>
model_identity        = <frozen>
generation_config_ref = <hash or canonical blob id>
run_identity          = <id or allowlist>
base_sha              = <git/tree sha>
source_owner          = <person / role>
approved_at           = <ISO-8601 UTC>
approval_statement    = "APPROVED for Narrow Formal After denom"
auto_derived          = false
```

## 3. Approval predicate

```text
AFTER_SOURCE_APPROVED = YES  ⇔
    owner stamp present
  ∧ stamp.auto_derived = false
  ∧ stamp.scope matches Narrow Formal
  ∧ stamp.binding_policy = observed_after
  ∧ stamp.after_source / capture_mode / model_identity / base_sha / run_identity
      match the acquired suite records
  ∧ E-B24 four-condition conjunction still holds for the suite
```

Until then:

```text
AFTER_SOURCE_APPROVED = NO
```

## 4. Explicit prohibitions

| Forbidden shortcut | Why |
|---|---|
| **Automatic approval** | Owner agency required; agents/CI must not self-stamp |
| **`pytest` green = approval** | Tests prove harness/codecs/scorers — not formal After authorization |
| E-B15 `PRODUCT_AFTER_CAPTURE_HARNESS_READY=YES` ⇒ approved | Path proof ≠ denom approval |
| E-B18 `GOLD_AFTER_BINDING_COMPATIBLE=YES` ⇒ approved | Synthetic compat pack; contamination if used as Product After |
| E-B20 / E-B22 green ⇒ approved | Scorer/wireup readiness ≠ After source |
| Silent smoke→formal relabel | Capture mode FAIL (E-B24) |
| Approving Option B/C while Narrow excludes A4 | Scope contradiction unless Narrow scope is revised first |
| Approving a missing Option D placeholder | Cannot approve absent source (E-B25) |

## 5. Who may stamp

```text
MAY_STAMP = project owner (human) or explicitly delegated human authority
MAY_NOT_STAMP = CI job · pytest · coding agent · “LGTM” without stamp fields
```

Delegation, if any, must itself be written (out of band); default = **no delegation**.

## 6. Relation to other gates

| Gate | Relationship to owner After approval |
|---|---|
| `AFTER_SOURCE_APPROVED` | **This** stamp’s output |
| `E-B_FORMAL_READY` | Separate; remains NO until formal write intentionally unlocked |
| `MAY_ENTER_FORMAL_OBSERVATION_WINDOW` | Requires After approval **and** other entry checklist items — not auto-flipped by stamp alone |
| B2′ / AG-5 | After approval + rebound progress may later clear residuals; **not** cleared by this design doc |

## 7. Current stamp (E-B26)

```text
OWNER_AFTER_SOURCE_APPROVAL_DESIGNED = YES
OWNER_AFTER_SOURCE_APPROVAL_ISSUED   = NO
AFTER_SOURCE_APPROVED                = NO
E-B_FORMAL_READY                     = NO
```
