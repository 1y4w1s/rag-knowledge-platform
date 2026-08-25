# 03 — Repository Verifiable Fields (Lane B · read-only)

> Audit only. Values below are at most
> **`REPOSITORY_VERIFIED_CANDIDATE_VALUE`**.  
> They are **not** `HUMAN_FROZEN`.  
> They do **not** imply `SOURCE_APPROVED` / `CAPTURE_MODE_FROZEN` /
> `OWNER_AUTHORIZATION_ISSUED`.

## 1. Audit posture

```text
Allowed label:     REPOSITORY_VERIFIED_CANDIDATE_VALUE
Forbidden labels:  HUMAN_FROZEN · SOURCE_APPROVED · CAPTURE_MODE_FROZEN
                   OWNER_AUTHORIZATION_ISSUED · AFTER_SOURCE_APPROVED

If repo cannot prove a field → UNKNOWN / HUMAN_INPUT_REQUIRED
No guessing.
```

## 2. Verified candidate inventory

Observed during E-B34 read-only audit (working tree at time of review;
**not** a freeze stamp).

| Field / fact | REPOSITORY_VERIFIED_CANDIDATE_VALUE | Provenance (repo) | Notes |
|---|---|---|---|
| Repository / code dir identity | `rag-knowledge-platform` | workspace root · `AGENTS.md` | Product brand separate |
| Product brand (docs) | `索隐` (Suoyin) | `AGENTS.md` · `docs/TECH.md` title | **≠** auto `product_name` freeze |
| Current branch (observed) | `test/agent-l4-w9-p3-e1-local-runtime-exploration` | `git rev-parse --abbrev-ref HEAD` | candidate observation only |
| Current HEAD (observed) | `ef7170ae397c1292febc40f69905315e1b33d9af` | `git rev-parse HEAD` | **≠ frozen `base_sha`** |
| Latest commit subject (observed) | Merge PR #64 … `test/agent-l4-w9-critic-p3-semantic-construct-repair` | `git log -1` | context only |
| Design candidate source | `PRIMARY_CANDIDATE_SOURCE=A` | `docs/research/w10-eb27-source-selection/` · E-B32/33 | selected design candidate only |
| Capture path identity (design) | `eb15_harness_product_after_capture_path_a` | E-B29/30/32/33 capture docs | ≠ Formal Evaluation Source |
| E-B15 harness module id | `w10_eb15_product_after_capture` (`HARNESS_ID`) | `backend/tests/w10_eb15_product_after_capture.py` | harness id · not approved After |
| Frozen suite identity (design) | `w9_critic_frozen_12` | E-B27 README · E-B30 scope | design binding · not human-frozen |
| Case scope (design) | `C01..C11` · `c12_policy=INELIGIBLE_NOT_SCORED` | E-B24 · E-B32/33 | design scope · not human-frozen |
| Capture mode enum (design) | `{product_stream, authorized_export}` | E-B32 `02` template | enum only · mode **not** selected |
| Forbidden Narrow Primary paths | LM Studio / Cloud API / A4 / S2-as-T1–T3 / Dev-as-Formal | E-B28 · E-B32 `02` | design rule |
| Python runtime declaration | Python **3.11** (+ CI `python-version: "3.11"`) | `docs/TECH.md` · `README.md` · `.github/workflows/ci.yml` | declared class · not host fingerprint |
| Development backend strategy | LM Studio + local model family · Local First | E-B28 `02-local-model-strategy.md` | **PLANNED / strategy** · not pinned |
| Local model pin state | `LOCAL_MODEL_PINNED=NO` | E-B28 | no concrete hash/quant/runtime |
| Narrow Formal Primary local model | `LOCAL_MODEL_AS_NARROW_FORMAL_PRIMARY=NO` | E-B28 | unchanged |
| Stamp schema review-policy **shape** | `EXPIRES_AT \| REVIEW_BY \| EVENT_TRIGGERED` + trigger list | E-B30 `01` §3.2 | schema only · dates unfilled |
| E-B33 draft status | `E-B33_FREEZE_RECORD_DRAFT_READY=YES` · `freeze_status=DRAFT` | `docs/research/w10-eb33-human-freeze-record-draft/` | draft ≠ freeze |
| `provenance_class` (template) | `Product After` | E-B32/33 source identity draft | **target evidence class** — see §4 |

## 3. Explicit UNKNOWN / HUMAN_INPUT_REQUIRED

Repo **cannot** honestly supply these as frozen identities:

| Field | Audit result |
|---|---|
| `source_identity` (canonical named id) | HUMAN_INPUT_REQUIRED |
| `after_source_id` | HUMAN_INPUT_REQUIRED |
| `product_name` (owner freeze string) | HUMAN_INPUT_REQUIRED |
| `product_version` | HUMAN_INPUT_REQUIRED / UNKNOWN |
| `deployment_identity` | HUMAN_INPUT_REQUIRED |
| `environment_identity` | HUMAN_INPUT_REQUIRED |
| `capture_mode_id` (chosen enum member) | HUMAN_INPUT_REQUIRED |
| `runtime_identity` (capture runtime id) | HUMAN_INPUT_REQUIRED |
| `model_backend_identity` (formal capture honesty) | HUMAN_INPUT_REQUIRED |
| `llm_called_expected` | HUMAN_INPUT_REQUIRED |
| `generation_config_ref` | HUMAN_INPUT_REQUIRED |
| `base_sha` (**frozen**) | HUMAN_INPUT_REQUIRED — observed HEAD is **candidate only** |
| `run_identity_pattern` | HUMAN_INPUT_REQUIRED |
| `review_policy` (filled dates / kind choice) | HUMAN_INPUT_REQUIRED |
| `owner_identity` | HUMAN_INPUT_REQUIRED |
| Formal Model Identity (file / hash / quant / runtime) | HUMAN_INPUT_REQUIRED · or DEFER_TO_BENCHMARK_TRACK |
| Hardware / trial / ablation matrix | DEFER_TO_BENCHMARK_TRACK |

## 4. `provenance_class` semantic clarification

E-B33 draft records:

```text
provenance_class = Product After
```

**Correct meaning (E-B34):**

```text
provenance_class names the *target evidence category* for the Narrow Formal
chain (Product After — not synthetic, not Development-backend-only smoke).

It does NOT mean:
  · Product After has been obtained
  · Product After has been authorized
  · Product After has entered the formal denominator
  · AFTER_SOURCE_APPROVED = YES
```

```text
FORBIDDEN inference:
  provenance_class=Product After  ⇒  AFTER_SOURCE_APPROVED=YES
```

## 5. Hard separation reminder

```text
Observed git HEAD
  = REPOSITORY_VERIFIED_CANDIDATE_VALUE for “what HEAD was at audit time”
  ≠ HUMAN_FROZEN base_sha
  ≠ permission to write base_sha into a freeze record without owner action

E-B15 HARNESS_ID / capture_path_identity
  = validated Product After *capture path candidate*
  ≠ Formal Evaluation Source
  ≠ approved After
```

## 6. Stamp (this file)

```text
LANE_B_REPOSITORY_AUDIT           = COMPLETE
HUMAN_FROZEN_FROM_REPO_AUTO       = NO
SOURCE_APPROVED                   = NO
CAPTURE_MODE_FROZEN               = NO
OWNER_AUTHORIZATION_ISSUED        = NO
```
