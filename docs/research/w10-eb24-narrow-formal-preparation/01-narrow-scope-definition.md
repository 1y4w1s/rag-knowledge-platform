# 01 — Narrow Formal scope definition

> Freezes **what** the first Narrow Formal Observation window would measure
> **if and only if** later authorization clears Formal Entry.  
> This window does **not** authorize execution.

## 1. Scope identity

```text
SCOPE_ID            = narrow_formal_first_bp_a_c01_c11
SCOPE_CLASS         = Narrow Formal Observation
BINDING_POLICY      = BP-A only
SUITE_ID            = w9_critic_frozen_12
CASE_ENVELOPE       = 12 slots (W9 frozen identity intact)
MEASURED_CASES      = C01 … C11
EXCLUDED_CASES      = C12
TARGETS_MEASURED    = {T1, T2, T3}
EXCLUDED_TARGETS    = {T4}
EXCLUDED_PACKAGES   = S2 empty-gate dual-suite
EXCLUDED_CAPTURE    = A4 live LLM product After
```

## 2. In scope

| Dimension | Declared value | Notes |
|---|---|---|
| **Binding** | **BP-A only** (`observed_after`) | Gold rebound to After **content-string** hash; no silent BP-B/C blend |
| **Primary suite** | `w9_critic_frozen_12` | Envelope `case_count=12` identity unchanged |
| **Measured cases** | **C01–C11** | Eligible After / claim denom for T1–T3 |
| **Targets** | **T1 · T2 · T3** | Citation scope · unsupported claim · grounding |
| **Scorer path** | E-B20/E-B22 tests-only contract | Formal use still gated; rates → L-Score companion only |
| **Wireup** | E-B22 compose contract | Compose ≠ write; reserved write still locked |

## 3. Explicitly out of scope (this Narrow Formal)

| Exclusion | Why |
|---|---|
| **C12** | Protocol `INELIGIBLE` / `ineligible_no_after`; **not** in claim denominator; must not inflate rates |
| **S2 empty-gate packaging** | T4 / dual-suite Full packaging; `E_B_S2_PACKAGING_AUTHORIZED=NO` and **not required** for Narrow |
| **A4 live LLM** | Live product LLM After thaw; owner A4 auth absent; Narrow forbids live LLM calls |
| **BP-B / BP-C as suite default** | Narrow first window is **BP-A only**; other BPs need separate declared scopes |
| **Full Formal** | Full = Narrow + T4/S2 (+ optional A4 if live); not this scope |
| **E-B10 “T1-only isomorphic unlock”** | Historical alternate narrow; **superseded** for this first Narrow Formal by T1–T3 · BP-A · C01–C11 |

## 4. Envelope vs denominator honesty

```text
Envelope slots:     C01–C12  (case_count=12 · W9 identity)
Claim / T2–T3 denom: C01–C11 only
C12 reporting:       INELIGIBLE (or equivalent protocol status) — never scored as claim case
T4 / empty-gate:     absent from this Narrow artifact claim set
```

**Forbidden narratives under this scope:**

- Silent `12 → 13` or merge empty-gate ids into W9 envelope  
- Treating C12 as claim-supported / unsupported / grounded  
- Claiming T4 / `empty_gate_refuse_ok` from Narrow-only run  
- Claiming product LLM faithfulness while `llm_called` under A4 freeze without A4 auth  

## 5. Relation to E-B23 gate

E-B23 `MAY_ENTER_FORMAL_OBSERVATION_WINDOW` remains **NO**.  
E-B24 supplies **C-T** (target / scope freeze design) material for Narrow Formal
only — it does **not** flip C-A / C-B live / C-O / write unlock.

```text
E-B24 defines scope  ⇏  MAY_ENTER = YES
E-B24 defines scope  ⇏  E-B_FORMAL_READY = YES
E-B24 defines scope  ⇒  future clearance windows know exact Narrow denom
```

## 6. Stamp

```text
NARROW_SCOPE_DEFINED                = YES
BINDING_POLICY_DECLARED             = BP-A
TARGETS_MEASURED_DECLARED           = {T1,T2,T3}
CASES_MEASURED_DECLARED             = C01–C11
C12_EXCLUDED                        = YES
S2_EXCLUDED                         = YES
A4_EXCLUDED                         = YES
E-B_FORMAL_READY                    = NO
MAY_ENTER_FORMAL_OBSERVATION_WINDOW = NO
FORMAL_OBSERVATION                  = NOT_STARTED
```
