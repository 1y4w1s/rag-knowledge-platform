# 02 — Source Identity Readiness Audit

> Audits the four identity pillars required for
> `SOURCE_IDENTITY_COMPLETE=YES`.  
> **Audit only** — no identity string is frozen or approved here.

## 1. Predicate under audit

From E-B30 `02-source-identity-freeze-plan.md` §2:

```text
SOURCE_IDENTITY_COMPLETE = YES  ⇔
    source identifier frozen
  ∧ product version frozen
  ∧ deployment identity frozen
  ∧ environment identity frozen
  ∧ anti-contamination checks acknowledged for the planned suite
```

Inherited target (unchanged):

```text
PRIMARY_CANDIDATE_SOURCE = A
  = selected design candidate only
  = E-B15 harness validated Product After capture path candidate
  ≠ Formal Evaluation Source
  ≠ owner-approved After
```

## 2. Design inheritance (READY)

| Input | Status |
|---|---|
| `SOURCE_IDENTITY_FREEZE_PLAN_DESIGNED` (E-B30) | YES |
| E-B29 after-source identity checklist (design) | YES |
| Narrow scope (BP-A · C01–C11 · C12 INELIGIBLE) | READY (inherited) |
| E-B28 separation acknowledgment policy | READY |
| Anti-contamination **policy** text | READY |

## 3. Four-pillar live audit

### 3.1 Source identifier — **BLOCKED**

| Checklist item | Status |
|---|---|
| Named `source_identity` chosen (not pytest-inferred) | **NO** · human input |
| `after_source_id` equal/explicit-alias | **NO** · human input |
| Provenance = Product After (not synthetic / author-owned) | policy YES · live id **NO** |
| `suite_id` / C01–C11 / C12 policy bound on freeze | design YES · freeze **NO** |
| Owner will stamp exact ids | **NO** · human confirm |

### 3.2 Product version — **BLOCKED**

| Checklist item | Status |
|---|---|
| Product version / release label declared | **NO** · human input |
| Version covers Scheme A harness Product After surface | **NO** |
| Stamp / acquisition will cite same version | **NO** (nothing to cite) |
| Version change ⇒ REVOKE_OR_REISSUE acknowledged | policy READY · not on freeze record |

### 3.3 Deployment identity — **BLOCKED**

| Checklist item | Status |
|---|---|
| Deployment topology declared | **NO** · human input |
| Distinguishes local/dev demo vs Narrow capture deployment | **NO** |
| Harness path A as authorized deployment path | candidate selected · **not frozen** |
| Deployment swap ⇒ re-stamp | policy READY · not frozen |

**Note:** `PRIMARY_CANDIDATE_SOURCE=A` is a **selected design candidate only**
(**READY as candidacy**), not as deployment freeze / approval /
source approved / formal eligible / After approved.

### 3.4 Environment identity — **BLOCKED**

| Checklist item | Status |
|---|---|
| Environment name / config profile declared | **NO** · human input |
| Secrets policy acknowledged (no secrets in stamp) | policy READY · freeze **NO** |
| Environment ≠ Dev Backend as Formal PRIMARY | policy READY · freeze **NO** |
| Environment change ⇒ REVOKE_OR_REISSUE | policy READY · freeze **NO** |

## 4. Adjacent stamp fields (not pillars; still incomplete)

| Field | Role | Live freeze |
|---|---|---|
| `runtime_identity` | process/host | **NO** |
| `model_backend_identity` | generator (`none_no_llm` allowed) | **NO** (illustrative only) |
| `base_sha` | code/config tree | **NO** |
| `run_identity` | suite/batch | **NO** |

```text
candidate A pick   ⇏  SOURCE_IDENTITY_COMPLETE
runtime draft      ⇏  SOURCE_IDENTITY_COMPLETE
```

## 5. Anti-contamination acknowledgment

| Check | Policy | Suite proof |
|---|---|---|
| No E-B6 isomorphic / synthetic as Product After | READY | pending acquisition (out of E-B31) |
| No E-B18 author-owned embedding as Product After | READY | pending |
| No W9 / Critic oracle as Product After | READY | pending |
| No Dev Backend relabeled Formal After | READY | pending |
| E-B28 separation acknowledged | READY | pending on stamp |

For **pre-issuance**, policy acknowledgment design is READY; live freeze
record must still list these checks checked by a human. Suite proof remains
**post-issuance / acquisition** (E-B30 §5 / E-B29).

## 6. Predicate evaluation

```text
source identifier frozen     = NO
product version frozen       = NO
deployment identity frozen   = NO
environment identity frozen  = NO
anti-contamination on freeze = NO (no freeze record)
```

```text
SOURCE_IDENTITY_COMPLETE = NO
SOURCE_IDENTITY_FROZEN   = NO
SOURCE_APPROVED          = NO
AFTER_SOURCE_APPROVED    = NO
```

## 7. Human inputs required (identity freeze)

1. Exact `source_identity` / `after_source_id` strings.
2. `authorization_scope.product_version` (or equivalent freeze field).
3. `deployment_identity` + confirm `capture_path_identity=eb15_harness_product_after_capture_path_a`.
4. Environment / config profile id.
5. Human confirmation of anti-contamination checklist on the freeze record.
6. (Recommended same window) draft `runtime_identity` / `model_backend_identity` /
   `base_sha` plan / `run_identity` pattern for later stamp bind.

## 8. Stamp

```text
SOURCE_IDENTITY_FREEZE_PLAN_DESIGNED = YES
SOURCE_IDENTITY_COMPLETE             = NO
OWNER_AUTHORIZATION_ISSUED           = NO
SOURCE_APPROVED                      = NO
AFTER_SOURCE_APPROVED                = NO
```
