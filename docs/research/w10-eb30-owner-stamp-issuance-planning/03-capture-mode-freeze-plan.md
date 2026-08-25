# 03 — Capture Mode Freeze Plan

> Designs the **capture_mode** enum and freeze plan for Narrow Formal Owner
> Stamp issuance.  
> **Plan only** — `CAPTURE_MODE_FROZEN=NO`.

## 1. Purpose

`capture_mode` is a first-class stamp field (`01`). Without a frozen mode:

```text
owner stamp cannot honestly set authorization_status = APPROVED
issuance gate (04) stays closed for APPROVED
acquisition entry stays closed
```

This file designs modes and freeze mechanics. It does **not** execute freeze.

## 2. Mode enum (protocol)

```text
capture_mode ∈ {
  product_stream,       # Product-path After via authorized product stream
  authorized_export,    # Owner-authorized export path (explicit · audited)
  <future modes...>     # reserved; require new planning window before use
}
```

### 2.1 Mode definitions

| Mode id | Meaning | Narrow PRIMARY eligibility (design) |
|---|---|---|
| **`product_stream`** | Capture Product After from the declared product stream path under candidate A (E-B15 harness Product After capture path) | Candidate — if owner freezes + stamps |
| **`authorized_export`** | Capture via an owner-declared authorized export (not smoke fixtures; not silent relabel) | Candidate — only if export provenance equals Product After honesty |
| **future modes** | e.g. local-model PRIMARY, API PRIMARY, live A4 | **Out of Narrow** until dedicated scope revision |

### 2.2 Mapping to prior families (illustrative)

| Prior family (E-B29) | Maps toward | Narrow PRIMARY now? |
|---|---|---|
| Scheme A harness · no live LLM | `product_stream` (typical) | Candidate if frozen+stamped |
| Scheme A · A4 live LLM | future / scope revision | **No** under current Narrow |
| LM Studio local gen | future / Dev track | **No** as Narrow PRIMARY |
| Cloud API gen | future / Dev track | **No** as Narrow PRIMARY |
| Smoke / fixture / synthetic | **never** | Contamination veto |

Choosing `product_stream` vs `authorized_export` is a **later freeze window**.

## 3. Freeze plan (future)

### 3.1 Preconditions before freeze

```text
[ ] PRIMARY_CANDIDATE_SOURCE = A still holds (or revised by planning)
[ ] SOURCE_MODEL_SEPARATION_DESIGNED = YES acknowledged
[ ] Narrow scope still BP-A · C01–C11 · C12 INELIGIBLE
[ ] Mode id chosen from §2 enum (not ad-hoc free text without registry)
[ ] model_backend_identity + llm_called_expected drafted consistently
[ ] Human freeze owner identified
```

### 3.2 Freeze record (fill later)

Reuse / supersede E-B29 template with E-B30 enum:

```text
================================================================
CAPTURE MODE FREEZE — Narrow Formal · PRIMARY candidate A
================================================================
freeze_kind              = NARROW_FORMAL_CAPTURE_MODE_FREEZE
schema_ref               = eb30_capture_mode_freeze_v1
primary_candidate_source = A
capture_path_identity    = eb15_harness_product_after_capture_path_a

capture_mode             = <FILL: product_stream | authorized_export | …>
mode_display_name        = <FILL>
mode_owner               = <FILL: human>

scope                    = Narrow Formal Observation (first)
binding_policy           = observed_after
suite_id                 = w9_critic_frozen_12
cases_measured           = C01..C11
c12_policy               = INELIGIBLE_NOT_SCORED

model_backend_identity   = <FILL: e.g. none_no_llm>
runtime_identity         = <FILL>
llm_called_expected      = <FILL: true|false>
generation_config_ref    = <FILL: hash / blob id / N/A>
base_sha                 = <FILL or PLAN_REF if sha locked at acquisition>
run_identity_pattern     = <FILL: exact id or allowlist>

------------------------------------------------------------------
ALLOWED
------------------------------------------------------------------
[ ] Product After under chosen capture_mode honesty
[ ] Honest llm_called matching reality
[ ] Real product content/citations for C01–C11 (when product_stream)
[ ] Authorized export provenance documented (when authorized_export)
[ ] C12 recorded INELIGIBLE only

------------------------------------------------------------------
FORBIDDEN (Narrow)
------------------------------------------------------------------
[x] A4 live LLM capture / thaw as Narrow T1–T3
[x] S2 / empty-gate claimed as Narrow T1–T3 After
[x] Silent smoke → formal upgrade
[x] LM Studio / API as silent Formal PRIMARY path
[x] E-B6 / E-B18 synthetic / author-owned bodies as Product After
[x] Development Backend runs labeled as Formal After
[x] Ad-hoc mode strings outside §2 without new planning window

------------------------------------------------------------------
HONESTY
------------------------------------------------------------------
[ ] Mode formal-eligible only after owner stamp APPROVED
[ ] Freeze ≠ Formal Observation authorization
[ ] Freeze ≠ E-B_FORMAL_READY
[ ] E-B28 separation acknowledged

frozen_at                = <FILL ISO-8601 UTC>
frozen_by                = <FILL human>
freeze_status            = DRAFT | FROZEN | SUPERSEDED
================================================================
```

### 3.3 Freeze predicate

```text
CAPTURE_MODE_FROZEN = YES  ⇔
    freeze record fully filled
  ∧ freeze_status = FROZEN
  ∧ capture_mode ∈ registered enum (§2) and Narrow-allowed for chosen id
  ∧ forbidden Narrow items remain excluded
  ∧ model_backend_identity + llm_called_expected + runtime_identity consistent
  ∧ frozen_by is human (not CI/agent)
```

Until then:

```text
CAPTURE_MODE_FROZEN = NO
```

## 4. Relation to issuance

| Artifact | Needs frozen mode? |
|---|---|
| Schema design (this package) | No |
| Stamp draft `WITHHELD` | No |
| Stamp `authorization_status=APPROVED` | **Yes** — equals frozen id |
| `OWNER_AUTHORIZATION_ISSUED=YES` (APPROVED path) | **Yes** |
| Acquisition execution | **Yes** |
| Formal Observation | Separate unlock; still needs approved After |

```text
mode plan designed   ⇏  mode frozen
mode frozen          ⇏  After approved
mode frozen          ⇏  authorization issued
mode frozen          ⇏  acquisition ready
mode frozen          ⇏  formal ready
```

## 5. Explicit non-goals

```text
DO NOT set CAPTURE_MODE_FROZEN = YES in this window.
DO NOT invent a final capture_mode as approved.
DO NOT call harness / LLM to “discover” a mode.
DO NOT modify backend/app capture flags.
DO NOT open future modes as Narrow PRIMARY silently.
```

## 6. Stamp

```text
CAPTURE_MODE_FREEZE_PLAN_DESIGNED = YES
CAPTURE_MODE_FROZEN               = NO
OWNER_AUTHORIZATION_ISSUED        = NO
SOURCE_APPROVED                   = NO
AFTER_SOURCE_APPROVED             = NO
ACQUISITION_EXECUTION_READY       = NO
E-B_FORMAL_READY                  = NO
```
