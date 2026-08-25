# 05 — Acquisition binding validation

> Deterministic structural / schema / binding checks only.  
> **No** Formal scorer · **No** Formal Observation writer · **No** A4 · **No** live LLM.

## Validator outcome

```text
checks_total = 116
checks_failed = 0
BINDING_VALIDATION = PASS
```

## Checks covered

| Class | Asserted |
|---|---|
| Acquisition schema | E-B26 required fields present on C01–C11 records |
| Source identity binding | `source_identity` / `after_source_id` = authorized id |
| `base_sha` binding | exact `3ce0e75f06d35aecaaccd245dd3a234b1c6f79a6` |
| Runtime binding | `suoyin_backend_venv_cpython_3.11.9_win10_amd64` |
| Run identity pattern | `^w10_showcase_narrow_.+$` |
| Citation/content shape | `content` string · `citations` list · hashes recompute |
| No synthetic provenance | no eb6 / author-owned markers |
| C12 exclusion | `INELIGIBLE_NOT_SCORED` · `attempted_acquisition=false` |
| `llm_called=false` | suite + every captured record |
| Auth commit ≠ base | `authorization_record_commit` ≠ `base_sha` |
| Formal gates locked | `E-B_FORMAL_READY=NO` · `FORMAL_OBSERVATION=NOT_STARTED` |

## Explicitly not run

```text
Formal T1/T2/T3 denominator scoring
Formal Observation result writer
Reserved formal result path write
A4 live generation
LM Studio / DeepSeek / Tongyi / any LLM call
```
