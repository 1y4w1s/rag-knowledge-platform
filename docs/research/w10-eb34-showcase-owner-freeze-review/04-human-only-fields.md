# 04 — Human-Only Fields & Local Model Boundary (Lane C · read-only)

> Separates (a) fields only a human owner may freeze, from
> (b) Development Generation Backend strategy, from
> (c) Research Benchmark pin surface.  
> **Does not** invent Formal Model Identity.

## 1. Development Generation Backend (strategy · not Formal Source)

```text
Development Generation Backend:
  LM Studio + local model family (GLM / Qwen / Llama or successors)

LOCAL_MODEL_FIRST                     = YES
LOCAL_MODEL_AS_NARROW_FORMAL_PRIMARY  = NO
LOCAL_MODEL_PINNED                    = NO

formal_model_identity                 = <FILL until separately pinned>
```

### Honesty rule

```text
“LM Studio is the long-term primary Development Backend”
  ≠
“A concrete GLM (or other) file is now Formal Evaluation Source”
```

No concrete model version / quantization / file hash / LM Studio runtime
version is pinned in-repo for Formal use. Therefore:

```text
LOCAL_MODEL_PINNED = NO
formal_model_identity remains <FILL>
```

Pinning that surface is either a **separate human freeze** (if Showcase
needs an explicit N/A or none_no_llm capture honesty statement) or
**DEFER_TO_BENCHMARK_TRACK** (if claiming comparable local-model research).

## 2. Human-only freeze fields (Showcase Track)

These **must** remain owner/delegate decisions. Cursor / CI / agents must
**not** act as owner.

| Field | Why human-only |
|---|---|
| `source_identity` | Canonical named id; not pytest/module inference |
| `after_source_id` | Exact or explicit alias; binding honesty |
| `product_name` | Owner freeze string; brand text alone ≠ freeze |
| `product_version` | Release / research-instance version claim |
| `deployment_identity` | Which deployment class is under observation |
| `environment_identity` | Env/profile name; no secrets; host class |
| `capture_mode_id` | Choose `product_stream` \| `authorized_export` |
| `runtime_identity` | Capture process/runtime id for later match |
| `model_backend_identity` | Formal capture honesty (`none_no_llm` allowed) |
| `llm_called_expected` | Must match capture honesty |
| `generation_config_ref` | Config ref or explicit N/A |
| `base_sha` | Exact approved tree; **not** auto HEAD |
| `run_identity_pattern` | Batch/suite allowlist |
| `review_policy` | Filled expiration / review-by / triggers |
| `owner_identity` | Human owner or written delegate — never agent |

Related draft metadata also human-only when freezing:

```text
frozen_by · frozen_at · authorization_scope · mode_owner
anti-contamination acknowledgement
```

## 3. Defer to Research Benchmark Track

Do **not** block Showcase Track on these; keep `<FILL>` or mark defer:

| Field / surface | Track |
|---|---|
| Concrete local model file hash | Research Benchmark |
| Quantization identity | Research Benchmark |
| LM Studio / llama.cpp / CUDA stack version (for comparable claims) | Research Benchmark |
| Inference parameter pin matrix | Research Benchmark |
| Hardware freeze | Research Benchmark |
| Repeated stochastic trials | Research Benchmark |
| Ablation / multi-backend comparison | Research Benchmark |

```text
RESEARCH_BENCHMARK_TRACK_EXECUTED = NO
Missing benchmark pins MUST NOT invent Showcase Formal Model Identity.
```

## 4. Showcase-adequate honesty without model pin

For first Showcase Product Observation via candidate A (E-B15 harness
path), owner may later freeze capture honesty such as:

```text
model_backend_identity = none_no_llm   # example only · NOT frozen here
llm_called_expected    = false         # example only · NOT frozen here
```

That is a **human capture-mode honesty** choice — not a Formal Model pin.
It does **not** make LM Studio the Formal Evaluation Source.

```text
PROPOSED honesty examples ≠ FROZEN values
```

## 5. Stamp (this file)

```text
LOCAL_MODEL_FIRST                    = YES
LOCAL_MODEL_PINNED                   = NO
LOCAL_MODEL_AS_NARROW_FORMAL_PRIMARY = NO
formal_model_identity                = <FILL>
OWNER_IDENTITY_AUTO_FILLED           = NO
```
