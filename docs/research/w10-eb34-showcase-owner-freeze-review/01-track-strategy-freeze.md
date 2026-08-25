# 01 — Track Strategy Freeze (Showcase / Research Benchmark)

> Lane A · Strategy Owner.  
> Freezes **near-term vs long-term track definitions** only.  
> Does **not** execute Research Benchmark Track.  
> Does **not** freeze concrete model / hardware / trial matrices.

## 1. Naming (anti-collision)

| Use this name | Do **not** use |
|---|---|
| **Showcase Track** | 路线 A / Route A |
| **Research Benchmark Track** | 路线 B / Route B |

Reason: E-B27 already uses **Option A/B/C/D** for source-selection
candidates (`PRIMARY_CANDIDATE_SOURCE=A` = E-B15 harness path). Colliding
“A/B route” language would silently merge strategy tracks with capture-path
options.

```text
SHOWCASE_TRACK naming lock          = YES
RESEARCH_BENCHMARK_TRACK naming lock = YES
A/B route naming for these tracks   = FORBIDDEN
```

## 2. Showcase Track = PRIMARY (near-term)

### 2.1 Definition

```text
SHOWCASE_TRACK = PRIMARY

Object:
  Suoyin / rag-knowledge-platform
  Local Research Instance

Purpose:
  · portfolio / hiring showcase of a complete Agentic-RAG research engineering work
  · local long-horizon development
  · first auditable Product Observation
  · Formal infrastructure validation (gates · provenance · binding · scoring)

Priorities:
  · reproducibility (honest, auditable)
  · provenance honesty
  · low recurring cost
  · local-first sustainability
```

### 2.2 Evidence standard (not lowered)

```text
Showcase Track ≠ lowered evidence standard.

Still required for any Formal / approved claim:
  · named source identity (human)
  · capture mode freeze (human)
  · owner stamp (human · separate window)
  · no silent synthetic→Product After
  · no silent Dev backend → Formal Source substitution
```

### 2.3 Explicitly **not** required in Showcase Track (this phase)

```text
paper-grade hardware freeze
repeated stochastic trials
cross-model leaderboard
benchmark publication claim
concrete local model file hash / quant / runtime pin
multi-backend ablation matrix
```

These belong to **Research Benchmark Track** (long-term upgrade), not to
blocking Showcase Track progress.

## 3. Research Benchmark Track = LONG_TERM

### 3.1 Definition

```text
RESEARCH_BENCHMARK_TRACK = LONG_TERM

Upgrade surface (after Showcase Track is stable):
  · concrete local model identity
  · model file hash
  · quantization
  · LM Studio / runtime version
  · inference parameters
  · hardware
  · repeated trials
  · ablation matrix
  · multi-backend comparison

End-state intent:
  benchmark-quality reproducible research
```

### 3.2 This-window execution lock

```text
RESEARCH_BENCHMARK_TRACK_EXECUTED = NO

Long-term plan MUST NOT block Showcase Track owner freeze decisions.
Missing benchmark pins ⇒ leave fields as <FILL> or DEFER_TO_BENCHMARK_TRACK
  — do NOT invent values.
```

## 4. Relationship to Formal Evaluation Source / Development Backend

Inherited from E-B28 (unchanged semantics):

```text
Formal Evaluation Source  ≠  Development Generation Backend

LOCAL_MODEL_FIRST                     = YES   (Showcase sustainability posture)
LOCAL_MODEL_AS_NARROW_FORMAL_PRIMARY  = NO
LOCAL_MODEL_PINNED                    = NO    (no concrete Formal Model Identity)

LM Studio = long-term primary Development Generation Backend
  ⇏  any concrete GLM/Qwen/Llama file is Formal Evaluation Source
  ⇏  LOCAL_MODEL_PINNED
```

## 5. What this window freezes vs does not freeze

| Item | State after E-B34 |
|---|---|
| Showcase Track = PRIMARY | **FROZEN (strategy)** |
| Research Benchmark Track = LONG_TERM | **FROZEN (strategy)** |
| Research Benchmark executed | **NO** |
| Concrete source / capture / model identity | **NOT frozen** |
| Owner stamp / approvals | **NOT issued / still NO** |

```text
Strategy freeze  ⇏  identity freeze
Strategy freeze  ⇏  SOURCE_APPROVED
Strategy freeze  ⇏  CAPTURE_MODE_FROZEN
Strategy freeze  ⇏  formal observation
```

## 6. Stamp (this file)

```text
SHOWCASE_TRACK                    = PRIMARY
RESEARCH_BENCHMARK_TRACK          = LONG_TERM
RESEARCH_BENCHMARK_TRACK_EXECUTED = NO
LOCAL_MODEL_FIRST                 = YES
LOCAL_MODEL_PINNED                = NO
```
