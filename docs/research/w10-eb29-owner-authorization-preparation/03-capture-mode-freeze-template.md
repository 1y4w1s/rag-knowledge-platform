# 03 — Capture mode freeze template

> Template an owner / later freeze window fills to lock `capture_mode` for
> Narrow Formal Product After acquisition under candidate A.  
> **Template only** — `CAPTURE_MODE_FROZEN=NO`.

## 1. Purpose

Capture mode is a first-class stamp field. Without a frozen mode id:

```text
owner stamp cannot honestly set authorization_status = APPROVED
acquisition entry gate stays closed
```

This file is the **form**, not the filled freeze.

## 2. Freeze template (fill later)

```text
================================================================
CAPTURE MODE FREEZE — Narrow Formal · PRIMARY candidate A
================================================================

freeze_kind              = NARROW_FORMAL_CAPTURE_MODE_FREEZE
primary_candidate_source = A
capture_path_identity    = eb15_harness_product_after_capture_path_a

capture_mode             = <FILL: exact mode id>
mode_display_name        = <FILL>
mode_owner               = <FILL: human>

scope                    = Narrow Formal Observation (first)
binding_policy           = observed_after
suite_id                 = w9_critic_frozen_12
cases_measured           = C01..C11
c12_policy               = INELIGIBLE_NOT_SCORED

model_backend_identity   = <FILL: e.g. none_no_llm>
llm_called_expected      = <FILL: true|false>
generation_config_ref    = <FILL: hash / blob id / N/A>
base_sha                 = <FILL: git/tree sha>
run_identity_pattern     = <FILL: exact id or allowlist>

------------------------------------------------------------------
ALLOWED under this freeze
------------------------------------------------------------------
[ ] Product-path After capture via E-B15 harness Scheme A (non-A4)
[ ] Honest llm_called matching reality
[ ] Real product state["content"] / state["citations"] for C01–C11
[ ] C12 recorded INELIGIBLE only

------------------------------------------------------------------
FORBIDDEN under this freeze (Narrow)
------------------------------------------------------------------
[x] A4 live LLM capture / thaw
[x] S2 / empty-gate claimed as Narrow T1–T3 After
[x] Silent smoke → formal upgrade
[x] LM Studio / API as silent Formal PRIMARY path
[x] E-B6 / E-B18 synthetic / author-owned bodies as Product After
[x] Development Backend runs labeled as Formal After

------------------------------------------------------------------
HONESTY STATEMENTS (owner initials later)
------------------------------------------------------------------
[ ] This mode is formal-eligible only after owner stamp APPROVED
[ ] This freeze ≠ Formal Observation authorization
[ ] This freeze ≠ E-B_FORMAL_READY
[ ] E-B28 separation acknowledged (Formal Source ≠ Dev Backend)

frozen_at                = <FILL ISO-8601 UTC>
frozen_by                = <FILL human>
freeze_status            = DRAFT | FROZEN | SUPERSEDED
================================================================
```

## 3. Freeze predicate (future)

```text
CAPTURE_MODE_FROZEN = YES  ⇔
    template fully filled
  ∧ freeze_status = FROZEN
  ∧ capture_mode non-empty and Narrow-allowed
  ∧ forbidden Narrow items remain excluded
  ∧ model_backend_identity + llm_called_expected consistent
  ∧ frozen_by is human (not CI/agent)
```

Until then:

```text
CAPTURE_MODE_FROZEN = NO
```

## 4. Relation to owner stamp

| Artifact | Needs frozen mode? |
|---|---|
| Stamp with `authorization_status=WITHHELD` | No (current) |
| Stamp with `authorization_status=APPROVED` | **Yes** — `capture_mode` must equal frozen id |
| Acquisition execution | **Yes** — every capture record must match |
| Formal Observation | Separate unlock; still requires approved After |

```text
mode template designed  ⇏  mode frozen
mode frozen             ⇏  After approved
mode frozen             ⇏  acquisition ready
```

## 5. Suggested mode families (illustrative · not chosen)

| Family | Eligible for Narrow PRIMARY? | Note |
|---|---|---|
| Scheme A harness · no live LLM | Candidate (if owner stamps) | Aligns with Option A |
| Scheme A harness · A4 live LLM | **No** under current Narrow | Requires scope revision first |
| LM Studio local gen | **No** as Narrow PRIMARY | Dev / future track only (E-B27/28) |
| Cloud API gen | **No** as Narrow PRIMARY | Same |
| Smoke / fixture / synthetic | **Never** as Product After | Contamination veto |

Choosing among eligible families is a **later freeze window**, not this one.

## 6. Explicit non-goals

```text
DO NOT fill freeze_status = FROZEN in this window.
DO NOT invent a final capture_mode id as approved.
DO NOT call harness / LLM to “discover” a mode.
DO NOT modify backend/app capture flags.
```

## 7. Stamp

```text
CAPTURE_MODE_FREEZE_TEMPLATE_DESIGNED = YES
CAPTURE_MODE_FROZEN                   = NO
SOURCE_APPROVED                       = NO
AFTER_SOURCE_APPROVED                 = NO
ACQUISITION_EXECUTION_READY           = NO
E-B_FORMAL_READY                      = NO
```
