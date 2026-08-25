# 01 — Owner Stamp Schema Design

> Freezes the **final protocol field surface** for a Narrow Formal Owner
> Stamp.  
> **Schema design ≠ issued stamp.** No artifact is created in this window.

## 1. Purpose

E-B26 sketched early fields; E-B29 froze the authorization **model**.
E-B30 freezes the **issuance schema** — exact required fields, value
constraints, and honesty rules an issued stamp must satisfy.

```text
schema designed  ⇏  stamp exists
schema designed  ⇏  OWNER_AUTHORIZATION_ISSUED
schema designed  ⇏  SOURCE_APPROVED / AFTER_SOURCE_APPROVED
```

## 2. Stamp envelope

```text
stamp_kind     = OWNER_AFTER_SOURCE_APPROVAL
schema_version = eb30_owner_stamp_v1
auto_derived   = false          # MUST remain false for any APPROVED stamp
issuer_class   = human_owner | human_delegate_written
```

| Envelope field | Constraint |
|---|---|
| `stamp_kind` | Exact literal `OWNER_AFTER_SOURCE_APPROVAL` |
| `schema_version` | Exact literal `eb30_owner_stamp_v1` for this protocol |
| `auto_derived` | Must be `false`; CI/agent-derived stamps are invalid |
| `issuer_class` | Human only; delegate requires out-of-band written grant |

## 3. Mandatory issuance fields

All fields below are **required** for a stamp that may set
`authorization_status=APPROVED`. Incomplete stamps are invalid for gate
flips (may exist only as `WITHHELD` drafts).

| Field | Type (design) | Meaning | Honesty rule |
|---|---|---|---|
| **owner_identity** | string (role/person id) | Human owner or written delegate who issues the stamp | Not CI · not coding agent · not “system” |
| **source_identity** | string (named id) | Product After provenance identity being authorized | Named; not inferred from pytest module names |
| **after_source_id** | string (named id) | Canonical After-source record id bound to this stamp | Must equal or be an explicit alias of `source_identity` for this Narrow chain; no silent synonym class |
| **capture_mode** | enum string | Owner-approved Narrow capture mode id | Must match frozen mode when `CAPTURE_MODE_FROZEN=YES`; never silent smoke→formal |
| **model_backend_identity** | string | Frozen generator / backend identity | Use `none_no_llm` when no model; never omit when a backend exists; Dev backends not claimed as Formal PRIMARY |
| **runtime_identity** | string | Runtime / process identity used for capture | Distinguishes harness runtime, host, or declared N/A; must match acquisition records later |
| **base_sha** | string (git/tree sha) | Exact code+config tree sha approved for capture | Exact match to acquisition records; no “approx HEAD” |
| **run_identity** | string (id or allowlist) | Suite / batch id authorized | Exact id preferred; allowlist pattern only if explicitly declared |
| **authorization_scope** | object (see §3.1) | What the stamp authorizes (and what it does not) | Scope overflow forbidden |
| **issued_at** | ISO-8601 UTC | Wall-clock issuance time | Required for APPROVED / DENIED / REVOKED |
| **expiration_or_review_policy** | object (see §3.2) | When the stamp expires or must be re-reviewed | Required; “forever silent” forbidden |

### 3.1 `authorization_scope` shape

```text
authorization_scope:
  observation_scope     = Narrow Formal Observation (first)
  binding_policy        = observed_after          # BP-A
  suite_id              = w9_critic_frozen_12
  cases_covered         = C01..C11
  c12_policy            = INELIGIBLE_NOT_SCORED
  primary_candidate_ref = E-B27 Option A
  capture_path_identity = eb15_harness_product_after_capture_path_a
  formal_source_claim   = false                   # stamp ≠ Formal Evaluation Source alone
  excludes              = [A4_live_llm, S2_as_T1_T3, synthetic_as_product_after]
```

Scope must **not** silently expand to Formal Evaluation Source, Local Model
PRIMARY, API PRIMARY, or Formal Observation unlock.

### 3.2 `expiration_or_review_policy` shape

```text
expiration_or_review_policy:
  policy_kind           = EXPIRES_AT | REVIEW_BY | EVENT_TRIGGERED
  expires_at            = <ISO-8601 UTC | null>     # if EXPIRES_AT
  review_by             = <ISO-8601 UTC | null>     # if REVIEW_BY
  trigger_events        = [base_sha_change, capture_mode_change,
                           model_backend_change, runtime_identity_change,
                           scope_change]            # always monitored
  on_trigger            = REVOKE_OR_REISSUE         # must re-stamp; no silent reuse
  max_silent_reuse      = 0
```

Default recommended for Narrow first issuance:

```text
policy_kind = REVIEW_BY | EVENT_TRIGGERED (conjunction)
review_by   = <owner-chosen ISO date · not omitted>
on_trigger  = REVOKE_OR_REISSUE
```

Any change to `base_sha` / `capture_mode` / `model_backend_identity` /
`runtime_identity` / scope ⇒ existing APPROVED stamp is **not** reusable.

## 4. Status field (authorization outcome)

```text
authorization_status ∈ { APPROVED, DENIED, WITHHELD, REVOKED }
```

| Status | May flip SOURCE / AFTER_SOURCE approved? | Notes |
|---|---|---|
| `APPROVED` | Yes — only if schema complete + issuance gate green | Human agency required |
| `DENIED` | No | Explicit rejection |
| `WITHHELD` | No | Current effective reality pre-issuance |
| `REVOKED` | No (reverts prior YES if any) | Post-issuance withdrawal |

Companion honesty fields (required when status ≠ WITHHELD draft):

```text
approval_statement   = "APPROVED for Narrow Formal After denom"
                       # only when authorization_status = APPROVED
llm_called_expected  = <bool matching capture_mode honesty>
generation_config_ref = <hash | blob id | N/A>
source_model_separation = YES   # E-B28 acknowledged
```

## 5. Field crosswalk (legacy → E-B30)

| E-B26 / E-B27 / E-B29 name | E-B30 canonical |
|---|---|
| `source_owner` | `owner_identity` |
| `after_source` / `source_identity` | `source_identity` + `after_source_id` |
| `model_identity` / `model_backend_identity` | `model_backend_identity` |
| `capture_path_identity` | inside `authorization_scope.capture_path_identity` |
| `scope` / companion suite fields | `authorization_scope` |
| `approved_at` | `issued_at` |
| *(new)* | `runtime_identity` |
| *(new)* | `expiration_or_review_policy` |

## 6. Illustrative shape (NOT issued)

```text
# EXAMPLE ONLY — DO NOT treat as a real stamp
stamp_kind                 = OWNER_AFTER_SOURCE_APPROVAL
schema_version             = eb30_owner_stamp_v1
auto_derived               = false
owner_identity             = <TBD human>
source_identity            = product_stream_scheme_a_narrow_v1   # illustrative
after_source_id            = product_stream_scheme_a_narrow_v1
capture_mode               = <TBD · see 03>
model_backend_identity     = none_no_llm                         # if A no-LLM
runtime_identity           = <TBD>
base_sha                   = <TBD>
run_identity               = <TBD>
authorization_scope        = { Narrow · BP-A · C01..C11 · … }
issued_at                  = <TBD>
expiration_or_review_policy = { REVIEW_BY + EVENT_TRIGGERED · … }
authorization_status       = WITHHELD                            # current reality
```

## 7. Validation predicate (design)

```text
STAMP_SCHEMA_COMPLETE = YES  ⇔
    all §3 mandatory fields present and non-empty
  ∧ authorization_scope matches Narrow Formal constraints
  ∧ expiration_or_review_policy present with on_trigger = REVOKE_OR_REISSUE
  ∧ auto_derived = false
  ∧ owner_identity is human (issuer_class allowed)

STAMP_VALID_FOR_APPROVAL = YES  ⇔
    STAMP_SCHEMA_COMPLETE
  ∧ authorization_status = APPROVED
  ∧ issuance gate (04) green at issue time
```

```text
STAMP_SCHEMA_COMPLETE  ⇏  OWNER_AUTHORIZATION_ISSUED
STAMP_VALID_FOR_APPROVAL design  ⇏  any approved gate flipped in this window
```

## 8. Forbidden shortcuts

| Shortcut | Why forbidden |
|---|---|
| Issue APPROVED with missing `runtime_identity` / review policy | Incomplete schema |
| Reuse APPROVED after `base_sha` change without reissue | Event trigger violated |
| Treat illustrative §6 strings as frozen identities | Design ≠ freeze |
| Agent fills `owner_identity` with its own name | Agency rule |
| Collapse `source_identity` into pytest node id | Provenance honesty |

## 9. Current stamp (E-B30)

```text
OWNER_STAMP_SCHEMA_DESIGNED      = YES
OWNER_STAMP_ISSUANCE_DESIGNED    = YES   (package)
OWNER_AUTHORIZATION_ISSUED       = NO
authorization_status (effective) = WITHHELD
SOURCE_APPROVED                  = NO
AFTER_SOURCE_APPROVED            = NO
ACQUISITION_EXECUTION_READY      = NO
E-B_FORMAL_READY                 = NO
```
