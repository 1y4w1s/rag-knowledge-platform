# 01 — Schema Completeness Audit

> Audits whether an `eb30_owner_stamp_v1` stamp surface is **complete enough**
> for honest APPROVED issuance.  
> **Audit only** — no stamp artifact is created.

## 1. Predicate under audit

From E-B30 `01-owner-stamp-schema-design.md` §7:

```text
STAMP_SCHEMA_COMPLETE = YES  ⇔
    all §3 mandatory fields present and non-empty
  ∧ authorization_scope matches Narrow Formal constraints
  ∧ expiration_or_review_policy present with on_trigger = REVOKE_OR_REISSUE
  ∧ auto_derived = false
  ∧ owner_identity is human (issuer_class allowed)
```

```text
schema designed (E-B30)  ≠  STAMP_SCHEMA_COMPLETE
illustrative example     ≠  live filled stamp
```

## 2. Design inheritance (READY)

| Input | Status | Evidence |
|---|---|---|
| Envelope literals (`stamp_kind`, `schema_version`) | READY (design) | E-B30 §2 |
| Mandatory field list (11 fields) | READY (design) | E-B30 §3 |
| `authorization_scope` shape | READY (design) | E-B30 §3.1 |
| `expiration_or_review_policy` shape | READY (design) | E-B30 §3.2 |
| Status enum + companion honesty fields | READY (design) | E-B30 §4 |
| `OWNER_STAMP_SCHEMA_DESIGNED` | YES | E-B30 |
| `OWNER_STAMP_ISSUANCE_DESIGNED` | YES | E-B30 |

**Verdict on design surface:** protocol schema is sufficient to *support*
issuance. That is **not** the same as `STAMP_SCHEMA_COMPLETE=YES`.

## 3. Live field fill audit

Search / evidence: no real `OWNER_AFTER_SOURCE_APPROVAL` artifact under
`eb30_owner_stamp_v1` exists in-repo (design docs + illustrative WITHHELD
examples only). Effective status remains WITHHELD (E-B30 §9).

| Field | Required for APPROVED | Live value | Status |
|---|---|---|---|
| `owner_identity` | Yes | `<TBD human>` | **BLOCKED** · human input |
| `source_identity` | Yes | illustrative only / not frozen | **BLOCKED** · human input |
| `after_source_id` | Yes | not frozen | **BLOCKED** · human input |
| `capture_mode` | Yes | not frozen | **BLOCKED** · human input |
| `model_backend_identity` | Yes | illustrative `none_no_llm` only | **BLOCKED** · human confirm |
| `runtime_identity` | Yes | `<TBD>` | **BLOCKED** · human input |
| `base_sha` | Yes | `<TBD>` | **BLOCKED** · human input |
| `run_identity` | Yes | `<TBD>` | **BLOCKED** · human input |
| `authorization_scope` | Yes | Narrow shape designed; not stamped | **BLOCKED** · human bind |
| `issued_at` | Yes (APPROVED path) | absent (no issue event) | **BLOCKED** · at issue time |
| `expiration_or_review_policy` | Yes | shape designed; dates unset | **BLOCKED** · human input |

Envelope / honesty:

| Check | Status |
|---|---|
| `auto_derived=false` policy | READY (rule) · not yet on live stamp |
| `issuer_class` human-only | READY (rule) · issuer person **unset** |
| Narrow scope constraints known | READY (design) |
| `on_trigger=REVOKE_OR_REISSUE` required | READY (design) · not filled on live stamp |

## 4. Predicate evaluation

```text
all §3 mandatory fields present and non-empty     = NO
authorization_scope Narrow-matched on live stamp  = NO (no live stamp)
expiration_or_review_policy present on live stamp = NO
auto_derived = false on live stamp                = N/A (no live stamp)
owner_identity human on live stamp                = NO
```

```text
STAMP_SCHEMA_COMPLETE = NO
```

## 5. Human inputs required (schema fill)

Before any future window may claim `STAMP_SCHEMA_COMPLETE=YES`:

1. Human `owner_identity` (person/role id; not CI/agent).
2. Concrete `source_identity` + matching/aliased `after_source_id`.
3. Frozen `capture_mode` id (see `03`).
4. Confirmed `model_backend_identity` / `runtime_identity` / exact `base_sha` /
   `run_identity`.
5. Bound Narrow `authorization_scope` object (BP-A · C01–C11 · exclusions).
6. `expiration_or_review_policy` with `review_by` and/or `expires_at` +
   `on_trigger=REVOKE_OR_REISSUE`.
7. At APPROVED issue time only: `issued_at` + `authorization_status=APPROVED`
   (E-B31 does **not** perform that issue).

## 6. Forbidden shortcuts (reaffirmed)

| Shortcut | Why forbidden |
|---|---|
| Treat E-B30 §6 illustrative strings as complete | Design ≠ fill |
| Agent invents `owner_identity` | Agency rule |
| Mark schema COMPLETE without non-empty fields | Predicate violation |
| Issue APPROVED to “prove” schema | Out of E-B31 scope |

## 7. Stamp

```text
OWNER_STAMP_SCHEMA_DESIGNED   = YES
STAMP_SCHEMA_COMPLETE         = NO
OWNER_AUTHORIZATION_ISSUED    = NO
SOURCE_APPROVED               = NO
AFTER_SOURCE_APPROVED         = NO
```
