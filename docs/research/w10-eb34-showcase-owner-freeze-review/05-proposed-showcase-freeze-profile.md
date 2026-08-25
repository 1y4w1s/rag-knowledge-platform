# 05 — Proposed Showcase Freeze Profile

> **Proposal only.**  
> **`PROPOSED ≠ FROZEN`**.  
> Example strings must **not** be copied into freeze records as achieved facts.

## 1. Proposal banner

```text
PROFILE_KIND     = SHOWCASE_TRACK_FREEZE_PROFILE_PROPOSAL
PROFILE_STATUS   = PROPOSED
FROZEN           = NO
SOURCE_APPROVED  = NO
CAPTURE_MODE_FROZEN = NO
OWNER_AUTHORIZATION_ISSUED = NO
```

## 2. Recommended Showcase profile (not executed)

```text
================================================================
SHOWCASE FREEZE PROFILE — PROPOSAL ONLY
================================================================
track                    = SHOWCASE_TRACK (PRIMARY)

product_name             = Suoyin / rag-knowledge-platform
                           # proposal · HUMAN_INPUT_REQUIRED to freeze

product_version          = <FILL>
                           # owner chooses research-instance / release label

deployment_identity      = local_research_instance
                           # class proposal · not frozen

environment_identity     = windows_local_research_environment
                           # class proposal · owner may refine profile name

capture_mode_id          = product_stream
                           # enum candidate proposal · not selected as freeze

capture_path_identity    = eb15_harness_product_after_capture_path_a
                           # REPOSITORY_VERIFIED_CANDIDATE (design)
                           # ≠ Formal Evaluation Source

primary_candidate_source = A
                           # selected design candidate only

suite_binding            = w9_critic_frozen_12
case_scope               = C01..C11 · c12_policy=INELIGIBLE_NOT_SCORED
                           # design candidates · human confirm on freeze

development_backend      = LM Studio (+ local model family)
                           # Development Generation Backend strategy
                           # ≠ Formal Evaluation Source

formal_model_identity    = <FILL until separately pinned>
LOCAL_MODEL_PINNED       = NO
LOCAL_MODEL_FIRST        = YES
LOCAL_MODEL_AS_NARROW_FORMAL_PRIMARY = NO

model_backend_identity   = <FILL>
                           # Showcase honesty often tends toward none_no_llm
                           # when using harness path without live LLM —
                           # example tendency only · NOT frozen here

llm_called_expected      = <FILL>
generation_config_ref    = <FILL>
runtime_identity         = <FILL>
base_sha                 = <FILL>
                           # DO NOT paste observed HEAD as frozen fact
run_identity_pattern     = <FILL>
review_policy            = <FILL>  # use E-B30 shape when filling
owner_identity           = <FILL>  # human only

provenance_class         = Product After
                           # TARGET evidence category only
                           # ⇏ AFTER_SOURCE_APPROVED

formal_evaluation_source = NO
================================================================
```

## 3. What this profile is for

- Give the owner a **coherent Showcase-shaped** starting point.
- Keep Research Benchmark pins out of the critical path.
- Preserve E-B28 separation (Dev backend vs Formal source).

## 4. What this profile is **not**

```text
NOT a freeze record
NOT an owner stamp
NOT SOURCE_APPROVED / AFTER_SOURCE_APPROVED
NOT CAPTURE_MODE_FROZEN
NOT permission to run acquisition / formal observation
NOT a concrete Formal Model Identity
```

## 5. Stamp (this file)

```text
SHOWCASE_PROFILE_PROPOSED = YES
SHOWCASE_PROFILE_FROZEN   = NO
```
