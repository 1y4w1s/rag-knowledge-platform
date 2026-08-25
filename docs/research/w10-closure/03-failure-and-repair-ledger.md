# 03 — Failure and Repair Ledger

Failures discovered during W10 are **formal assets**. Each entry records failure → root cause → repair → remaining limitation.

---

## 1. C12 harness / product-path protocol invalidity

| Field | Content |
|---|---|
| **failure** | C12 cannot enter Formal T1/T2/T3 claim denominators on the product After path; treating it as a scored claim case would invalidate rates. |
| **root cause** | Frozen W9 identity keeps C12 in the envelope, but protocol marks it `INELIGIBLE` / foreign-workspace / no claim After path for Narrow Formal. |
| **repair** | E-B24 / E-B2 eligibility: C12 = `INELIGIBLE_NOT_SCORED`; excluded from Formal T1 denominator (excluded=1). Envelope identity retained. |
| **remaining limitation** | C12 still does not prove cross-workspace refusal quality as a scored Formal claim target. |

---

## 2. Synthetic-authored gold vs real After binding incompatibility

| Field | Content |
|---|---|
| **failure** | E-B12B gold (`kind=synthetic_authored`) cannot bind as BP-A Formal claim units against E-B38 real Product After. |
| **root cause** | Gold ledger authored for protocol/smoke universe; real After bodies are product-stream degraded fragments with different pool IDs and assertion semantics. |
| **repair** | E-B39 rebinding audit: BP-A `INCOMPATIBLE` · BP-B `INVALID`; forbid E-B18 compat as Formal substitute; do not invent asserted claims from unrebounded gold. |
| **remaining limitation** | Speech-act / real-After claim annotation for ANSWER bodies remains future work; T2/T3 still need real ANSWER After + rebound gold. |

---

## 3. Degraded output scorer applicability gap

| Field | Content |
|---|---|
| **failure** | Force-scoring unrebounded gold against degraded After risks fictional assertions and silent “perfect” T2/T3. |
| **root cause** | Frozen empty-ledger N/A path existed, but degraded After with non-empty gold lacked a complete response-mode routing into claim-quality exclusion. |
| **repair** | E-B40 versioned `response_mode` gate; DEGRADED excluded from T2/T3 denominator; empty/degraded perfect-score path closed. |
| **remaining limitation** | Gap resolved **for response_mode**; historical E-B39 artifact still records old-protocol `SCORER_APPLICABILITY_GAP=YES`. Assertion semantics (substring ≠ assertion) remain open for future ANSWER scoring. |

---

## 4. Target-scope ambiguity (E-B21 vs E-B24)

| Field | Content |
|---|---|
| **failure** | Unclear whether Showcase Narrow Formal may legally measure T1-only while T2/T3 stay N/A under DEGRADED. |
| **root cause** | E-B21/E-B10 subset semantics conflicted with E-B24 Narrow declared `targets_measured={T1,T2,T3}`; global `E-B_FORMAL_READY` semantics became ambiguous (E-B42). |
| **repair** | E-B43 Formal target-scope v2: `w10_showcase_t1_only_v1` authorizes `{T1}` with `{T2,T3}=NOT_APPLICABLE` without rewriting historical E-B21/E-B24/E-B42 conclusions. |
| **remaining limitation** | Historical `E-B_FORMAL_READY=NO` remains untouched; readers must use scope-v2 ids, not flip old global flags. |

---

## 5. Candidate–oracle leakage risk (prevented)

| Field | Content |
|---|---|
| **failure risk** | Promoting E-B41 candidate 11/11 as Formal, or feeding Formal writer from candidate oracle, would leak non-Formal scores into Formal claim surface. |
| **root cause** | Companion reacquisition produces a convenient candidate evaluation adjacent to Formal inputs. |
| **repair** | Explicit isolation: candidate ≠ Formal; E-B44 recomputes only from immutable raw records; integrity audit `FORMAL_ORACLE_LEAK_RISK=NO`; single canonical Formal result. |
| **remaining limitation** | Process discipline must continue: never overwrite Formal result from candidate artifacts. |

---

## 6. Git baseline protocol coverage gap and repair

| Field | Content |
|---|---|
| **failure** | Authorization / docs commits live on the evolving research branch while Formal Product After must execute against a frozen evaluation `base_sha`, creating easy protocol drift if acquisition runs in the wrong tree. |
| **root cause** | Single working tree mixed authorization provenance with evaluation baseline; HEAD after E-B36+ ≠ frozen `3ce0e75…`. |
| **repair** | E-B37 topology + E-B38 dedicated detached worktree pinned at frozen `base_sha`; acquisition products written back to authorized docs workspace; post-run clean HEAD check; SHA separation recorded (`authorization_record_commit` ≠ `base_sha`). |
| **remaining limitation** | Frozen baseline is Showcase research baseline, not production deployment pin; dependency snapshot remains explicitly unpinned. |
