# 01 — Current readiness map

> Labels: `READY` | `PARTIAL` | `BLOCKED`.  
> Scope = Formal Observation **authorization** readiness, not “tests green”.

## 1. Matrix

| Component | Status | Evidence (as of E-B22 freeze) | Why not full READY for Formal Entry |
|---|---|---|---|
| **Claim Gold** | **READY** | `E_B_CLAIM_GOLD_ANNOTATED=YES` (E-B12B ledger) | — (T2/T3 gold material present; still must bind per case under declared BP) |
| **After Capture** | **PARTIAL** | `PRODUCT_AFTER_CAPTURE_HARNESS_READY=YES` (E-B15 Scheme A) | Harness ≠ formal / authorized After evidence; B2′ residual |
| **Binding** | **PARTIAL** | `BINDING_GATE_IMPLEMENTED=YES` · `GOLD_AFTER_BINDING_COMPATIBLE=YES` (E-B18 BP-A **compat pack**) | Live E-B15×unrebounded E-B12B still `INCOMPATIBLE`; AG-5 live rebound absent |
| **Scorer** | **READY** | `T2_T3_SCORER_CONTRACT_DESIGNED=YES` · `T2_T3_SCORER_IMPLEMENTED=YES` (E-B20 tests-only) | Formal use still gated; rates live in companion L-Score only |
| **Wireup** | **READY** | `FORMAL_WIREUP_DESIGNED=YES` · `FORMAL_WIREUP_IMPLEMENTED=YES` (E-B22 tests-only) | Compose ≠ write; reserved formal write still locked |
| **Empty Gate** | **PARTIAL** | `E_B_EMPTY_GATE_CASES_MATERIAL_READY=YES` (N=2 · zh/en) | Material ready; dual-suite formal packaging not authorized (S2) |
| **S2 Packaging** | **BLOCKED** | Contract/prep ready · `E_B_S2_PACKAGING_AUTHORIZED=NO` | No authorized dual-suite formal packaging result |
| **A4 Live LLM** | **BLOCKED** | Owner auth absent · E-B2 `llm_called=false` freeze | Live product After forbidden without thaw + unlock |
| **Reserved Write** | **BLOCKED** | `RESERVED_RESULT=ABSENT` · gate hard-locks write | Independent write step + `E-B_FORMAL_READY=YES` required |

## 2. Aggregate reading

```text
Pipeline shape (LAAE):
  Capture → Binding → Score → Project (wireup) → Reserved Write

READY pieces:     Claim Gold · Scorer · Wireup (tests-only contracts)
PARTIAL pieces:   After Capture · Binding (compat-only) · Empty Gate
BLOCKED pieces:   S2 Packaging · A4 Live LLM · Reserved Write
```

**Implication:** the observation **assembly line** is designed and partially
implemented under tests; the **authorization / evidence / write** layers that
would make Formal Observation honest remain closed.

## 3. Honesty boundaries (do not conflate)

| Green signal | Does **not** mean |
|---|---|
| E-B15 harness pytest green | Formal After snapshots exist |
| E-B18 BP-A compat pack | Product LLM faithfulness |
| E-B20 scorer rates on fixtures | Formal T2/T3 measured |
| E-B22 `compose_l_obs` / `compose_l_score` | Reserved result written |
| Empty-gate MATERIAL_READY | S2 packaging authorized / T4 Full ready |

## 4. Stamp

```text
READINESS_MAP_FROZEN               = YES
E-B23_READINESS_DESIGNED           = YES
E-B_FORMAL_READY                   = NO
MAY_ENTER_FORMAL_OBSERVATION_WINDOW = NO
```
