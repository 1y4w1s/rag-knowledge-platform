# 02 — Narrow Formal capture design (fields only)

> Designs the **record schema** for one formal-eligible Product After capture
> under Narrow Formal · **C01–C11** · **BP-A only**.  
> **Does not implement** capture, write artifacts, or approve a source.

## 1. Scope freeze

```text
Cases:          C01 … C11  (measured)
C12:            record INELIGIBLE only — never claim-scored / not After denom
Binding:        BP-A (observed_after) only
Targets later:  T1 · T2 · T3   (not scored in acquisition window)
Excluded:       A4 live LLM · S2 empty-gate as T1–T3 After · BP-B/C as formal
```

## 2. Unit of capture

One **Formal After Capture Record** = one case × one authorized run.

Suite acquisition for Narrow Formal requires:

```text
∀ case_id ∈ {C01 … C11}: Formal After Capture Record present
∧ C12 recorded as INELIGIBLE (no claim After denom)
∧ single run_identity / base_sha / model identity / capture_mode across suite
  (or explicitly declared per-case variance — default: suite-uniform)
```

## 3. Required fields (design)

| Field | Type (conceptual) | Meaning |
|---|---|---|
| `case_id` | string enum | One of `C01`…`C11` for measured After; C12 uses separate ineligible record, not this After schema |
| `query` | string | Exact query string used for that case (frozen suite query) |
| `model_identity` | string | Frozen model / generator identity (e.g. `none_no_llm` · provider+model+rev). Must match owner stamp |
| `generation_config` | object / canonical JSON | Sampler / temperature / max tokens / refusal policy / key-presence flags — whatever is needed to interpret the body; empty object only if explicitly “no generation knobs” |
| `capture_mode` | string | Declared mode id (owner-approved for Narrow). Must not be silent smoke→formal upgrade |
| `llm_called` | bool | Honest: `true` iff a model was invoked for this capture |
| `content` | string | Observed After body = product `state["content"]` (or authorized equivalent). **Not** claim-text embedding |
| `citations` | list | Observed After citations = product `state["citations"]` (structure as produced; ids exact for later T3) |
| `timestamp` | ISO-8601 UTC string | Capture wall time |
| `source_hash` | string | Digest of observed content under BP-A codec (`observed_content_hash` / `sha256:{hex}` wire). Computed from `content`, not from gold |

### 3.1 Recommended companion identity fields (still design-only)

Not in the user minimum list, but required for E-B24 source identity / later rebound:

| Field | Purpose |
|---|---|
| `after_source` | Named provenance id (formal-eligible name after owner stamp) |
| `run_identity` | Suite / batch run id |
| `base_sha` | Code / config tree sha at capture |
| `suite_id` | e.g. `w9_critic_frozen_12` |
| `binding_policy` | Must be `observed_after` (BP-A) for Narrow Formal |
| `formal_measurement` | Remains `false` until Formal Observation window; acquisition ≠ formal result |
| `owner_approval_ref` | Pointer / stamp id to owner authorization artifact (see `03`) |

## 4. Field rules (non-implementation)

```text
content        → source_hash   (BP-A content-string codec; same as E-B17/E-B18 observed)
llm_called     ↔ reality       (no false negative / positive)
capture_mode   ∈ owner-approved Narrow set
model_identity frozen for the run
citations      must be the observed product citations, not gold evidence rewrite
case_id        ↔ later gold.case_id (BP-A case bind)
```

### Forbidden field semantics

| Anti-pattern | Why forbidden |
|---|---|
| `content` = E-B18 author-owned claim embedding | Synthetic contamination |
| `content` = W9 answer / plan-as-final / Critic oracle | Non-product After |
| `source_hash` copied from unrebounded E-B12B `content_sha256` | Wrong hash space / fake bind |
| `llm_called=false` while Option B/C/D called a model | Honesty veto |
| Omitting `capture_mode` and inferring from pytest name | Capture mode FAIL |
| Mixing BP-B `synthetic_authored` labels into formal records | Policy violation |

## 5. Per-case checklist (design)

For each of C01–C11, a future acquisition execution must populate all §3 fields
and verify:

```text
[ ] case_id matches frozen suite case
[ ] query matches frozen suite query
[ ] model_identity == suite-frozen identity
[ ] generation_config == suite-frozen config (canonical)
[ ] capture_mode == owner-approved Narrow mode
[ ] llm_called matches actual invocation
[ ] content / citations from authorized product path
[ ] timestamp recorded
[ ] source_hash recomputes from content (BP-A codec)
[ ] no E-B18 / E-B6 synthetic body substitution
```

## 6. Explicit non-goals

```text
DO NOT implement serializers / pytest writers in this window.
DO NOT write formal observation result JSON.
DO NOT flip E-B_FORMAL_READY.
DO NOT call LLM / LM Studio.
DO NOT rebound gold here (see 04 for plan only).
```

## 7. Stamp

```text
NARROW_FORMAL_CAPTURE_SCHEMA_DESIGNED = YES
CAPTURE_IMPLEMENTED                    = NO
AFTER_SOURCE_APPROVED                  = NO
E-B_FORMAL_READY                       = NO
```
