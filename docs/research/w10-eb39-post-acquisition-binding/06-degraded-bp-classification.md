# 06 — Degraded-output BP classification

## Frozen BP definitions (E-B17 / E-B16)

| Policy | Meaning | Body / routing |
|---|---|---|
| **BP-A `observed_after`** | Formal **candidate** (product After) | gold `kind=observed_after` + content-string hash bind + pool |
| **BP-B `synthetic_authored`** | Test / protocol only | claim_texts ledger + claim-text presence |
| **BP-C `refusal_exclude`** | T4 exclusion | skip T2/T3; empty-gate / fail-closed fixed reply |

E-B8 T4 refusal gold requires `gen_plan.refusal == true` ∧ fixed no-context reply ∧ `citations == []`.

## E-B38 observed facts (every C01–C11)

| Field | Value |
|---|---|
| `capture_mode` | `product_stream` |
| `capture_path_submode` | `product_stream_degraded` |
| `plan_refusal` | `false` |
| `stream_phase_entered` | `true` |
| `citations` | non-empty |
| declared `binding_policy` on record | `observed_after` |
| content | unavailable boilerplate + fragment dump |

## Classification (per frozen contract — not by name alone)

| case_id | capture_submode | bp_class | bp_basis |
|---|---|---|---|
| C01 | product_stream_degraded | **UNCLASSIFIED** | Not BP-C (`plan_refusal=false`, citations≠[]); not completed BP-A (gold kind≠`observed_after`); not BP-B protocol body |
| C02 | product_stream_degraded | **UNCLASSIFIED** | same |
| C03 | product_stream_degraded | **UNCLASSIFIED** | same |
| C04 | product_stream_degraded | **UNCLASSIFIED** | same |
| C05 | product_stream_degraded | **UNCLASSIFIED** | same |
| C06 | product_stream_degraded | **UNCLASSIFIED** | same |
| C07 | product_stream_degraded | **UNCLASSIFIED** | same |
| C08 | product_stream_degraded | **UNCLASSIFIED** | same |
| C09 | product_stream_degraded | **UNCLASSIFIED** | same |
| C10 | product_stream_degraded | **UNCLASSIFIED** | same |
| C11 | product_stream_degraded | **UNCLASSIFIED** | same |

### Why not BP-C

BP-C / T4 is **refusal_exclude** for empty-gate / fail-closed fixed replies. E-B16 maps A1 `product_stream_refusal` → T4 N/A, and A2 `product_stream_degraded` → **incompatible with claim_texts binding**, not “auto BP-C”.

### Why not BP-A formal candidate (yet)

Acquisition **intent** used `binding_policy=observed_after`, but E-B16/E-B17 BP-A formal candidacy requires rebound gold `kind=observed_after` with matching content-string codec. That rebound **does not exist** for E-B38 bodies. E-B18 compat pack is forbidden here.

## Eligibility

```text
BP_A_FORMAL_ELIGIBILITY = NO
```

Do **not** force degraded outputs into T2/T3 denominator under frozen protocol.
