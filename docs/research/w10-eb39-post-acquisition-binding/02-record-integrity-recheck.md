# 02 — Record Integrity Recheck (C01–C11)

## Method

Deterministic field checks against E-B38 machine-readable records + dual-hash recomputation declared in E-B38 summary:

| Hash field | Declared codec | Check |
|---|---|---|
| `source_hash` / `observed_content_hash` | raw UTF-8 of `content` | recompute == stored |
| `harness_after_content_hash` | E-B15/E-B17 canonical-JSON of string | recompute == stored |

## Suite constants (all C01–C11)

| Field | Expected | Result |
|---|---|---|
| `run_identity` | `w10_showcase_narrow_eb38_20260825T085526Z` | PASS |
| `base_sha` | `3ce0e75f06d35aecaaccd245dd3a234b1c6f79a6` | PASS |
| `source_identity` / `after_source_id` | `suoyin_local_research_product_after_v1` | PASS |
| `runtime_identity` | `suoyin_backend_venv_cpython_3.11.9_win10_amd64` | PASS |
| `capture_mode` | `product_stream` | PASS |
| `capture_path_submode` | `product_stream_degraded` | PASS |
| `llm_called_observed` | `false` | PASS |
| content present (non-empty string) | required | PASS |
| citations present + `chunk_id` shape | required | PASS |
| `source_hash == observed_content_hash` | required | PASS |
| utf8 recompute of `observed_content_hash` | required | PASS |
| harness recompute of `harness_after_content_hash` | required | PASS |
| no synthetic / E-B18 / author-owned / eb6 markers | required | PASS |
| no fixture-answer provenance | required | PASS |

C12 remains `INELIGIBLE_NOT_SCORED` (excluded before acquisition).

## Note (not an integrity fail)

E-B38 `observed_content_hash` (raw UTF-8) **≠** E-B17 Binding Gate `observed_content_digest` (canonical-JSON). Both are present and self-consistent on every record. This is a **later binding/applicability** concern (see `08`), not a corrupted acquisition record.

## Verdict

```text
POST_ACQUISITION_RECORD_INTEGRITY = PASS
SCORER_INPUT_READY (via integrity alone) = NOT_SUFFICIENT
```
