# 02 — Owner Input Decision Sheet

> For the **human owner / written delegate** only.  
> Cursor / CI / coding agents **must not** act as owner.  
> Status tags allowed per field:  
> `REPOSITORY_VERIFIED_CANDIDATE` · `HUMAN_INPUT_REQUIRED` · `DEFER_TO_BENCHMARK_TRACK`

```text
PROPOSED / recommended candidate ≠ FROZEN
REPOSITORY_VERIFIED_CANDIDATE ≠ HUMAN_FROZEN
```

## Decision table

| Field | Recommended candidate | Provenance | Human decision required? | Status |
|---|---|---|---|---|
| `source_identity` | Name a canonical Product After source id for candidate A (e.g. pattern tying to `eb15_harness_product_after_capture_path_a` — **owner invents exact string**) | Design path id is repo-verified; **canonical name is not** | **YES** | HUMAN_INPUT_REQUIRED |
| `after_source_id` | Exact match or **explicit** alias of `source_identity` | Schema rule E-B30/32 | **YES** | HUMAN_INPUT_REQUIRED |
| `product_name` | `Suoyin / rag-knowledge-platform` (Showcase proposal) | Brand `索隐` + repo dir verified in docs; freeze string still owner | **YES** | HUMAN_INPUT_REQUIRED |
| `product_version` | Owner-chosen research-instance / release label | No single frozen product version string in repo for this freeze | **YES** | HUMAN_INPUT_REQUIRED |
| `deployment_identity` | `local_research_instance` (Showcase proposal class) | Class proposed in E-B34 profile; not frozen | **YES** | HUMAN_INPUT_REQUIRED |
| `environment_identity` | Windows local research environment / named config profile (no secrets) | Host class is situational; must be owner-declared | **YES** | HUMAN_INPUT_REQUIRED |
| `capture_mode_id` | `product_stream` (Showcase **proposal** among enum) | Enum `{product_stream, authorized_export}` repo-verified; **choice** is human | **YES** | HUMAN_INPUT_REQUIRED |
| `runtime_identity` | Capture runtime id matching future acquisition records | No frozen runtime id in repo | **YES** | HUMAN_INPUT_REQUIRED |
| `model_backend_identity` | Showcase honesty candidate often `none_no_llm` if harness path without live LLM; **or** explicit backend id if owner asserts otherwise | Forbidden: silent LM Studio as Narrow Formal Primary (E-B28/32) | **YES** | HUMAN_INPUT_REQUIRED |
| `llm_called_expected` | Must match `model_backend_identity` honesty (`true`/`false`) | Schema honesty E-B30 | **YES** | HUMAN_INPUT_REQUIRED |
| `generation_config_ref` | Config blob/hash ref **or** explicit `N/A` | No formal gen-config freeze in repo | **YES** | HUMAN_INPUT_REQUIRED |
| `base_sha` | Owner picks exact git/tree sha to authorize | Observed HEAD at E-B34 audit = `ef7170ae397c1292febc40f69905315e1b33d9af` is **candidate observation only** | **YES** | HUMAN_INPUT_REQUIRED |
| `run_identity_pattern` | Suite/batch id or allowlist for C01–C11 acquisition | Suite design `w9_critic_frozen_12` is candidate binding; pattern string still human | **YES** | HUMAN_INPUT_REQUIRED |
| `review_policy` | Fill E-B30 shape: `REVIEW_BY` + `EVENT_TRIGGERED` recommended; choose `review_by` date | Policy **shape** repo-verified; dates/kind choice human | **YES** | HUMAN_INPUT_REQUIRED |
| `owner_identity` | Human owner or written delegate id | **Never** auto-filled by agent/CI | **YES** | HUMAN_INPUT_REQUIRED |

### Adjacent surfaces (not in table above · still relevant)

| Field | Recommended stance | Status |
|---|---|---|
| Formal Model Identity (file/hash/quant/runtime) | Leave `<FILL>`; do not invent for Showcase | DEFER_TO_BENCHMARK_TRACK (or separate pin window) |
| Hardware / trials / ablation | Out of Showcase near-term | DEFER_TO_BENCHMARK_TRACK |
| `PRIMARY_CANDIDATE_SOURCE` | Keep `A` (design inheritance) | REPOSITORY_VERIFIED_CANDIDATE |
| `capture_path_identity` | Keep `eb15_harness_product_after_capture_path_a` as design candidate | REPOSITORY_VERIFIED_CANDIDATE |
| `suite_binding` / `case_scope` | `w9_critic_frozen_12` · `C01..C11` design | REPOSITORY_VERIFIED_CANDIDATE (still needs human confirm on freeze) |
| `provenance_class` | Keep template `Product After` as **target class** | REPOSITORY_VERIFIED_CANDIDATE — **does not** approve After |

## Owner checklist before any future freeze window

```text
[ ] I understand PROPOSED ≠ FROZEN
[ ] I will fill every HUMAN_INPUT_REQUIRED field myself (or written delegate)
[ ] I will NOT treat observed HEAD as frozen base_sha without explicit choice
[ ] I will NOT treat LM Studio as Formal Evaluation Source
[ ] I will NOT infer AFTER_SOURCE_APPROVED from provenance_class=Product After
[ ] I will NOT ask Cursor to invent owner_identity
```

Boxes above remain **unticked** in E-B34 (no auto-tick).

## Stamp (this file)

```text
OWNER_DECISION_SHEET_READY = YES
OWNER_IDENTITY_FILLED      = NO
ANY_FIELD_HUMAN_FROZEN     = NO
```
