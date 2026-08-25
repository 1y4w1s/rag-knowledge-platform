# 01 — After acquisition options (analysis only)

> Compares four Product After **acquisition** candidates for a future Narrow
> Formal capture.  
> **No selection** in this window. No capture. No approval stamp.

## 1. Evaluation axes

| Axis | Question |
|---|---|
| **source identity** | What named provenance would the After carry? |
| **capture mode** | How is content obtained (path / harness / API / prod)? |
| **llm_called** | Would the capture honestly set `llm_called` true/false? |
| **reproducibility** | Can the same suite be re-run to identical (or declared-bounded) bodies? |
| **hash binding** | Can BP-A `observed_content_hash` / rebound gold bind cleanly? |
| **cost** | Ops, keys, time, infra for C01–C11 suite |
| **formal eligibility** | Could it *ever* satisfy E-B24 four-condition contract (with owner stamp)? |

Contract reference (E-B24 `03`): formal After requires **all** of  
`source identity ∧ hash binding (BP-A) ∧ capture mode ∧ no synthetic contamination`  
(+ owner stamp). E-B25 verdict: **no** current source is approved.

---

## 2. Option A — Current E-B15 product stream harness

```text
ID:     A
Name:   E-B15 Product After Snapshot Capture (Scheme A harness)
Path:   prepare_agent_generation → _stream_generation_phase
        → state["content"] / state["citations"] → E-B2 per_case slot
Signals: PRODUCT_AFTER_CAPTURE_HARNESS_READY=YES
         formal_measurement=false (default)
         B2_PRIME_AFTER_SNAPSHOTS=BLOCKING_RESIDUAL
```

| Axis | Analysis |
|---|---|
| **source identity** | Today: harness / informal capture provenance. Would need a **new** named formal-eligible `after_source` id + owner stamp; current identity is path-proof only (E-B25 FAIL). |
| **capture mode** | Scheme A product-path stream inside tests. Existing modes: `product_stream_refusal`, `product_stream_degraded`, `ineligible_no_after`. Narrow Formal would need a **declared** owner-approved mode (non-A4; non-S2-as-T1–T3). |
| **llm_called** | Current harness forces honest `llm_called=false` (no live keys / no LLM). Formal acquisition under A could stay `false` if mode is degraded/refusal without model call — **or** would become `true` only if a later authorized live path is opened (out of Narrow A4 exclusion). |
| **reproducibility** | High for no-LLM modes (deterministic degraded/refusal paths). Live-key extensions would be lower reproducibility and are **out of Narrow Formal scope** (A4 excluded). |
| **hash binding** | Bodies from real `state["content"]` are bindable under BP-A content-string codec **after** AG-5 rebound of gold to those hashes. Today: live E-B15 × unrebounded E-B12B = `INCOMPATIBLE` (`LIVE_EB15_X_EB12B_COMPATIBLE=NO`). |
| **cost** | Low for no-LLM harness modes (pytest + frozen suite). Zero external API spend for current A1/A2. |
| **formal eligibility** | **Potential** if and only if: owner stamps source + capture mode · suite covers C01–C11 · zero synthetic mix · gold rebound → BP-A `BOUND`. **Not eligible today** (E-B25). Harness green ≠ approval. |

**Limits:** Cannot silently upgrade smoke/degraded captures to formal. Cannot claim product LLM faithfulness when `llm_called=false`. C12 remains INELIGIBLE.

---

## 3. Option B — LM Studio local model generation

```text
ID:     B
Name:   LM Studio local model generation After
Path:   (prospective) local OpenAI-compatible endpoint → generation → After body
Signals: Not authorized · not captured under formal stamp · A4-adjacent
```

| Axis | Analysis |
|---|---|
| **source identity** | Would need explicit id (e.g. `lm_studio_local_<model>_<rev>`) + owner stamp. Absent today. |
| **capture mode** | Local model generation — distinct from Scheme A product stream unless wired through the same product path. Risk of **off-product** path if bypassing `_stream_generation_phase`. |
| **llm_called** | Must be **`true`** if any local model call occurs. Honesty veto if labeled false. |
| **reproducibility** | Medium–low: depends on model file hash, sampler seed, LM Studio version, context. Requires freezing model identity + generation config for suite replay claims. |
| **hash binding** | Content string still BP-A-bindable **after** capture + rebound. Binding quality = same codec; eligibility ≠ automatic. |
| **cost** | Local GPU/CPU time; no cloud API $; ops cost for environment freeze + machine variance. |
| **formal eligibility** | Contested for **Narrow Formal**: E-B24 excludes **A4 live LLM**. Local LM Studio is live generation and likely treated as A4-class / out-of-Narrow unless a separate owner-declared scope redefines Narrow (not this plan’s job). Even if later scoped, needs full four-condition + owner stamp. **Not eligible today.** |

**Limits:** Calling LM Studio is **forbidden in this planning window** and in Narrow Formal as currently frozen. Product-path honesty requires proving generation went through authorized product stream, not a side harness.

---

## 4. Option C — API model generation

```text
ID:     C
Name:   Cloud / HTTP API model generation After
Path:   (prospective) DeepSeek / Qwen / other API → generation → After body
Signals: Not authorized · keys server-side only · A4 live · Narrow excludes A4
```

| Axis | Analysis |
|---|---|
| **source identity** | Would need `api_<provider>_<model>_<rev>` + run identity + owner stamp. Absent today. |
| **capture mode** | API generation — typically A4 live. May ride product `_stream_generation_phase` (preferred for product identity) or a side script (weaker product claim). |
| **llm_called** | Must be **`true`**. |
| **reproducibility** | Low–medium: provider nondeterminism, prompt drift, rate limits. Needs frozen model id + generation config + base sha; still may not bit-reproduce. |
| **hash binding** | Same BP-A content-hash rebound path after bodies exist. Live unrebounded gold remains INCOMPATIBLE until AG-5 rebound. |
| **cost** | Per-token API $ × C01–C11 (+ retries); key management; audit of spend. |
| **formal eligibility** | **Out of Narrow Formal scope** while A4 remains excluded (E-B24). Could be formal-eligible under a **different** future Full Formal / A4-authorized scope — **not** this Narrow first observation. **Not eligible today.** |

**Limits:** E-B26 must not call APIs. Approving C for Narrow would contradict frozen scope unless scope is explicitly revised in a later planning window (not acquisition execution alone).

---

## 5. Option D — Future authorized production path

```text
ID:     D
Name:   Future owner-authorized production / staging generation path
Path:   (prospective) production-equivalent deploy → product generation
        → authorized After export under formal capture stamp
Signals: Not extant as formal-eligible suite · Wave of ops + auth required
```

| Axis | Analysis |
|---|---|
| **source identity** | Strongest product claim if After is exported from the real product path with named `after_source`, deploy/base sha, and owner stamp. |
| **capture mode** | Production or staging product generation (not pytest smoke). Must still declare mode; must not smuggle S2/empty-gate as T1–T3 After. |
| **llm_called** | Honest to reality: `true` if prod used LLM; `false` only if prod path truly did not call a model (unusual for answer generation). |
| **reproducibility** | Depends on whether prod path is pinned (model, config, code sha). Often lower than harness; requires run identity freeze. |
| **hash binding** | Same BP-A rebound after capture. Requires suite completeness C01–C11 + C12 INELIGIBLE record. |
| **cost** | Highest ops: environment, auth, audit, capture export pipeline; may still use API spend if prod LLM enabled. |
| **formal eligibility** | **Potential** for product formal **if** Narrow capture-mode rules allow the declared mode (non-A4 if Narrow stays A4-excluded) **and** owner stamps **and** no synthetic contamination **and** gold rebound BOUND. Today: **source absent** → cannot approve (E-B25 Candidate C class). |

**Limits:** “Future” cannot be stamped approved now. Production path must not be confused with E-B18 synthetic pack or E-B15 informal harness green.

---

## 6. Comparative matrix (no winner)

| Option | source identity (today) | capture mode | llm_called (honest) | reproducibility | hash binding path | cost | formal eligibility (Narrow, today) |
|---|---|---|---|---|---|---|---|
| **A** E-B15 harness | Informal harness only | Scheme A stream (refusal/degraded/…) | `false` in current modes | High (no-LLM modes) | Bindable after rebound; live×E-B12B INCOMPATIBLE now | Low | **Potential later** · **NO now** |
| **B** LM Studio local | Absent | Local model gen (A4-adjacent) | `true` | Medium–low | Bindable after capture+rebound | Local compute | **Likely out of Narrow** · **NO now** |
| **C** API model | Absent | Cloud API gen (A4) | `true` | Low–medium | Bindable after capture+rebound | API $ | **Out of Narrow (A4)** · **NO now** |
| **D** Future authorized prod | Absent | Prod/staging product path | Matches reality | Variable (needs pin) | Bindable after capture+rebound | Highest ops | **Potential later** · **NO now** |

```text
∃ option formal-eligible and approved today?  = NO
Selection in this window?                     = NONE (analysis only)
E-B18 synthetic pack as acquisition option?   = FORBIDDEN (tests-only · contamination)
```

## 7. Honesty notes (all options)

- E-B18 `compatibility_materialization_author_owned` is **not** an acquisition option for Product After; it remains tests-only hygiene.
- Pytest green on E-B15 / E-B18 / E-B20 / E-B22 **never** equals source approval.
- Narrow Formal continues to **exclude A4** and **exclude S2-as-T1–T3**.

## 8. Stamp

```text
AFTER_ACQUISITION_OPTIONS_ANALYZED = YES
OPTION_SELECTED                    = NONE
AFTER_SOURCE_APPROVED              = NO
E-B_FORMAL_READY                   = NO
```
