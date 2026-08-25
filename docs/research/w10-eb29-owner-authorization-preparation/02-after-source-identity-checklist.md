# 02 — After source identity checklist

> Checklist for proving **source identity** readiness of PRIMARY candidate A
> before any owner stamp can honestly say `APPROVED`.  
> This window **checks design completeness**, not live suite proof.

## 1. Target identity

```text
PRIMARY_CANDIDATE_SOURCE = A
  = selected design candidate only
  = E-B15 harness validated Product After capture path candidate
  ≠ Formal Evaluation Source
  ≠ owner-approved After (still NO)
```

Scope: Narrow Formal · BP-A · C01–C11 · C12 INELIGIBLE · A4/S2-as-T1–T3 excluded.

## 2. Identity checklist

### 2.1 Source identity

```text
[ ] after_source / source_identity string chosen (named · not pytest-inferred)
[ ] provenance narrative matches Product After (not synthetic / author-owned)
[ ] suite_id bound to w9_critic_frozen_12 (or declared companion · not Narrow T4)
[ ] cases_covered = C01..C11; c12_policy = INELIGIBLE_NOT_SCORED
[ ] owner will stamp this exact source_identity (not a synonym class)
```

**Current:** schema YES · concrete `after_source` string **not frozen** · stamp WITHHELD.

### 2.2 Capture path identity

```text
[ ] capture_path_identity = E-B15 harness Product After capture path (candidate A)
[ ] path ≠ Formal Evaluation Source (E-B28 terminology held)
[ ] path ≠ Development Generation Backend (LM Studio / API not silent Formal)
[ ] Option B (LM Studio) / C (API) remain OUT for Narrow PRIMARY path
[ ] no silent swap of capture path after selection without new planning window
```

**Current:** candidate A selected (E-B27) · separation designed (E-B28) · **not approved**.

### 2.3 Run identity

```text
[ ] run_identity (or allowlist pattern) declared for the acquisition suite
[ ] single run_identity across C01–C11 unless per-case variance explicitly declared
[ ] stamp.run_identity will match acquisition records 1:1
```

**Current:** template only · **no run executed** · id **not frozen**.

### 2.4 Base sha

```text
[ ] base_sha = exact git/tree sha of code+config used for capture
[ ] sha covers generation path relevant to Scheme A harness capture
[ ] stamp.base_sha will match acquisition records
```

**Current:** **not frozen** (no acquisition).

### 2.5 Model / backend identity

```text
[ ] model_backend_identity frozen for the suite
[ ] if no LLM: explicit none_no_llm (or equivalent) — not omitted
[ ] if LLM were used: provider+model+rev (+ generation_config_ref)
[ ] llm_called_expected matches Narrow mode honesty
[ ] Development backends (LM Studio / cloud API) not claimed as this Formal path
```

**Current:** expected shape for A no-LLM modes designed · **not frozen as approved**.

### 2.6 Capture mode

```text
[ ] capture_mode id chosen from Narrow-allowed set (see 03)
[ ] mode excludes A4 live LLM and S2 empty-gate as T1–T3 After
[ ] mode forbids silent smoke→formal upgrade
[ ] stamp.capture_mode will match every Formal After Capture Record
```

**Current:** freeze **template** only (`03`) · mode **not frozen**.

### 2.7 Authorization status

```text
[ ] stamp.authorization_status explicitly set (APPROVED / DENIED / WITHHELD / REVOKED)
[ ] APPROVED only when §§2.1–2.6 fields complete and E-B24 four conditions hold
[ ] WITHHELD / DENIED never treated as soft YES
```

**Current:** effective status = **WITHHELD**.

## 3. Anti-contamination identity checks

```text
[ ] no E-B6 isomorphic / synthetic bodies as Product After
[ ] no E-B18 author-owned claim-text embedding as Product After
[ ] no W9 answer / plan-as-final / Critic oracle as Product After
[ ] no Development Backend run relabeled as Formal After
```

**Current:** policy YES (E-B24/E-B25/E-B26) · suite proof pending acquisition.

## 4. Roll-up

```text
AFTER_SOURCE_IDENTITY_CHECKLIST_DESIGNED = YES
AFTER_SOURCE_IDENTITY_COMPLETE           = NO
SOURCE_APPROVED                          = NO
AFTER_SOURCE_APPROVED                    = NO
```

```text
Identity checklist designed  ⇏  source approved
Candidate A selected         ⇏  identity complete
```

## 5. Explicit non-goals

```text
DO NOT invent a final after_source string as “approved”.
DO NOT freeze base_sha / run_identity from this design window.
DO NOT generate After to “fill” identity fields.
DO NOT flip SOURCE_APPROVED / AFTER_SOURCE_APPROVED.
```
