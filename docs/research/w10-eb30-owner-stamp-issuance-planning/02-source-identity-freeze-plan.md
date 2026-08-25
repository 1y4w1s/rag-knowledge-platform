# 02 — Source Identity Freeze Plan

> Defines **when** source identity may be considered complete enough for an
> honest APPROVED owner stamp.  
> Plan only — no identity string is frozen as approved in this window.

## 1. Target

```text
PRIMARY_CANDIDATE_SOURCE = A
  = selected design candidate only
  = E-B15 harness validated Product After capture path candidate
  ≠ Formal Evaluation Source
  ≠ owner-approved After (still NO)
```

Scope: Narrow Formal · BP-A · C01–C11 · C12 INELIGIBLE · A4/S2-as-T1–T3 excluded.

## 2. Completeness definition

```text
SOURCE_IDENTITY_COMPLETE = YES  ⇔
    source identifier frozen
  ∧ product version frozen
  ∧ deployment identity frozen
  ∧ environment identity frozen
  ∧ anti-contamination checks acknowledged for the planned suite
```

Until all four identity pillars are frozen **and** recorded for stamp binding:

```text
SOURCE_IDENTITY_COMPLETE = NO
SOURCE_APPROVED          = NO
AFTER_SOURCE_APPROVED    = NO
```

## 3. Four pillars (required)

### 3.1 Source identifier

```text
[ ] source_identity string chosen (named · not pytest-inferred)
[ ] after_source_id chosen and equal/explicit-alias to source_identity
[ ] provenance narrative = Product After (not synthetic / author-owned)
[ ] suite_id bound to w9_critic_frozen_12 (or declared companion · not Narrow T4)
[ ] cases_covered = C01..C11; c12_policy = INELIGIBLE_NOT_SCORED
[ ] owner will stamp these exact ids (not a synonym class)
```

**Maps to stamp fields:** `source_identity`, `after_source_id`,
`authorization_scope.suite_id` / `cases_covered` / `c12_policy`.

**Current:** schema YES · concrete strings **not frozen** · WITHHELD.

### 3.2 Product version

```text
[ ] product version / release label declared for the capture path
[ ] version covers the Product After surface being authorized
    (app/API contract version relevant to Scheme A harness capture)
[ ] stamp / acquisition records will cite the same version id
[ ] version change ⇒ REVOKE_OR_REISSUE (event trigger)
```

**Maps to:** companion under `authorization_scope` and/or
`generation_config_ref` / product version field recorded at freeze time
(design: store as `authorization_scope.product_version`).

**Current:** **not frozen**.

### 3.3 Deployment identity

```text
[ ] deployment identity declared (which deployment topology is authorized)
[ ] distinguishes local/dev demo vs intended Narrow capture deployment
[ ] captures whether capture uses declared harness deployment path A
[ ] deployment swap ⇒ new freeze + re-stamp (no silent reuse)
```

**Maps to:** `authorization_scope.capture_path_identity` + optional
`authorization_scope.deployment_identity`.

**Current:** candidate A selected · **not approved as deployment freeze**.

### 3.4 Environment identity

```text
[ ] environment identity declared (env name / config profile)
[ ] secrets / Key presence policy acknowledged (Keys stay server-side;
    stamp does not embed secrets)
[ ] environment ≠ Development Generation Backend claimed as Formal PRIMARY
[ ] environment change ⇒ REVOKE_OR_REISSUE
```

**Maps to:** pairs with `runtime_identity` + `model_backend_identity`
honesty; environment id recorded at freeze for later record match.

**Current:** **not frozen**.

## 4. Relation to runtime / model (adjacent, not pillars)

These are **stamp-mandatory** (see `01`) but are **not** substitutes for the
four pillars above:

| Adjacent field | Role |
|---|---|
| `runtime_identity` | Process/host/runtime of capture |
| `model_backend_identity` | Generator identity (`none_no_llm` allowed) |
| `base_sha` | Code/config tree |
| `run_identity` | Suite/batch id |

```text
runtime frozen     ⇏  source identity complete
model frozen       ⇏  source identity complete
candidate A pick   ⇏  source identity complete
```

## 5. Anti-contamination checks (must hold at freeze)

```text
[ ] no E-B6 isomorphic / synthetic bodies as Product After
[ ] no E-B18 author-owned claim-text embedding as Product After
[ ] no W9 answer / plan-as-final / Critic oracle as Product After
[ ] no Development Backend run relabeled as Formal After
[ ] E-B28 separation acknowledged (Formal Source ≠ Dev Backend)
```

**Current:** policy YES · suite proof pending acquisition.

## 6. Freeze procedure (future window)

```text
Step A  Draft the four pillar values (strings / ids)
Step B  Cross-check against E-B29 checklist 02 + E-B24 four conditions
Step C  Human confirms freeze record (not CI)
Step D  Only then may stamp issuance window bind these ids into APPROVED
```

```text
SOURCE_IDENTITY_FREEZE_PLAN_DESIGNED = YES   (this window)
SOURCE_IDENTITY_COMPLETE             = NO
SOURCE_IDENTITY_FROZEN               = NO
```

## 7. Explicit non-goals

```text
DO NOT invent a final after_source / source_identity as “approved”.
DO NOT freeze product version / deployment / environment as live truth here.
DO NOT generate After to “fill” identity fields.
DO NOT flip SOURCE_APPROVED / AFTER_SOURCE_APPROVED.
DO NOT call LLM / API / LM Studio.
```

## 8. Stamp

```text
SOURCE_IDENTITY_FREEZE_PLAN_DESIGNED = YES
SOURCE_IDENTITY_COMPLETE             = NO
SOURCE_APPROVED                      = NO
AFTER_SOURCE_APPROVED                = NO
OWNER_AUTHORIZATION_ISSUED           = NO
ACQUISITION_EXECUTION_READY          = NO
E-B_FORMAL_READY                     = NO
```
