# 03 — Capture Mode Readiness Audit

> Audits whether capture-mode freeze is ready for
> `CAPTURE_MODE_FROZEN=YES` and for APPROVED stamp binding.  
> **Audit only** — does **not** set `CAPTURE_MODE_FROZEN=YES`.

## 1. Predicate under audit

From E-B30 `03-capture-mode-freeze-plan.md` §3.3:

```text
CAPTURE_MODE_FROZEN = YES  ⇔
    freeze record fully filled
  ∧ freeze_status = FROZEN
  ∧ capture_mode ∈ registered enum and Narrow-allowed
  ∧ forbidden Narrow items remain excluded
  ∧ model_backend_identity + llm_called_expected + runtime_identity consistent
  ∧ frozen_by is human (not CI/agent)
```

```text
mode plan designed  ≠  CAPTURE_MODE_FROZEN
```

## 2. Design inheritance (READY)

| Input | Status |
|---|---|
| `CAPTURE_MODE_FREEZE_PLAN_DESIGNED` (E-B30) | YES |
| Mode enum `{product_stream, authorized_export, …}` | READY |
| Narrow FORBIDDEN list (A4 / S2 / smoke→formal / LM Studio·API PRIMARY / synthetic) | READY |
| Freeze record template (`eb30_capture_mode_freeze_v1` shape) | READY |
| E-B29 freeze template (superseded/aligned by E-B30) | READY |
| `PRIMARY_CANDIDATE_SOURCE=A` still holds | YES |
| `SOURCE_MODEL_SEPARATION_DESIGNED=YES` | YES |
| Narrow scope still BP-A · C01–C11 · C12 INELIGIBLE | YES |

**Verdict:** planning surface is READY to *support* a freeze window.

## 3. Live freeze record audit

Evidence: no filled freeze record with `freeze_status=FROZEN` exists.
Templates remain DRAFT-capable only.

| Freeze field / check | Live status |
|---|---|
| `capture_mode` chosen (`product_stream` \| `authorized_export`) | **NO** · human input |
| `mode_display_name` / `mode_owner` | **NO** |
| `model_backend_identity` | **NO** |
| `runtime_identity` | **NO** |
| `llm_called_expected` consistent with mode | **NO** |
| `generation_config_ref` | **NO** |
| `base_sha` or PLAN_REF | **NO** |
| `run_identity_pattern` | **NO** |
| ALLOWED checklist checked | **NO** |
| FORBIDDEN Narrow items held | policy READY · not on FROZEN record |
| `frozen_at` / `frozen_by` human | **NO** |
| `freeze_status` | **not FROZEN** (absent / DRAFT only) |

```text
CAPTURE_MODE_FROZEN = NO
```

## 4. Readiness classification

| Layer | Class | Meaning |
|---|---|---|
| Enum + template + Narrow exclusions | **READY** | May open a human freeze window |
| Precondition acknowledgments (A / E-B28 / Narrow scope) | **READY** | Design inputs hold |
| Filled freeze record | **BLOCKED** | Needs human fill |
| `CAPTURE_MODE_FROZEN=YES` | **BLOCKED** | Predicate fails |
| Honest `authorization_status=APPROVED` | **BLOCKED** | Requires frozen mode (E-B30 §4) |

## 5. Human inputs required (capture-mode freeze)

1. Choose exact `capture_mode` ∈ `{product_stream, authorized_export}` (or open a
   new planning window before any other mode).
2. Fill full E-B30 §3.2 freeze record (mode owner, runtime, model, llm flags,
   run pattern, sha plan).
3. Check ALLOWED / FORBIDDEN / HONESTY boxes with human agency.
4. Set `freeze_status=FROZEN`, `frozen_by=<human>`, `frozen_at=<ISO-8601 UTC>`.
5. Do **not** treat freeze as SOURCE_APPROVED, acquisition ready, or formal ready.

## 6. Relation to issuance (simulation hint)

| Artifact | Needs frozen mode? | E-B31 reality |
|---|---|---|
| WITHHELD draft stamp | No | allowed in theory · **not created here** |
| APPROVED stamp | **Yes** | **blocked** |
| `MAY_ISSUE_APPROVED_OWNER_STAMP` | **Yes** | **NO** (see `04`) |
| Acquisition execution | **Yes** | still NO |

## 7. Stamp

```text
CAPTURE_MODE_FREEZE_PLAN_DESIGNED = YES
CAPTURE_MODE_FROZEN               = NO
OWNER_AUTHORIZATION_ISSUED        = NO
SOURCE_APPROVED                   = NO
AFTER_SOURCE_APPROVED             = NO
ACQUISITION_EXECUTION_READY       = NO
E-B_FORMAL_READY                  = NO
```
