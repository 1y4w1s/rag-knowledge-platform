# 02 — Runtime and Git Observation

> Read-only environment inspection for E-B35a.  
> Observations are **candidates**, not freezes.  
> **`observed_base_sha ≠ frozen base_sha`**.  
> **`RUNTIME_OBSERVED_CANDIDATE ≠ HUMAN_FROZEN`**.

Observation timestamp context: window **W10 E-B35a** (2026-08-25).

## 1. Git observation

Commands (read-only):

```text
git rev-parse HEAD
git rev-parse --abbrev-ref HEAD
git status --short
```

| Field | Observed value | Provenance |
|---|---|---|
| `observed_base_sha` | `ef7170ae397c1292febc40f69905315e1b33d9af` | RUNTIME_OBSERVED_CANDIDATE |
| `observed_branch` | `test/agent-l4-w9-p3-e1-local-runtime-exploration` | RUNTIME_OBSERVED_CANDIDATE |
| `working_tree_state` | **DIRTY** (modified + untracked research/test fixtures) | RUNTIME_OBSERVED_CANDIDATE |
| `proposed_base_sha` | `ef7170ae397c1292febc40f69905315e1b33d9af` (same as observed HEAD; proposal only) | RUNTIME_OBSERVED_CANDIDATE |
| `base_sha_frozen` | **NO** | template-fixed · this window |
| `WORKING_TREE_CLEAN` | **NO** | RUNTIME_OBSERVED_CANDIDATE |
| `BASE_SHA_CANDIDATE_READY` | **NO** | derived · dirty tree |
| `BASE_SHA_FREEZE_READINESS` | **BLOCKED_PENDING_OWNER_REVIEW** | derived · dirty tree |
| `BASE_SHA_FROZEN` | **NO** | must remain NO |

### Dirty-tree note (owner must review)

Working tree at observation time included at least:

- modified: `docs/status/progress.md`
- many untracked `backend/tests/` / `backend/tests/fixtures/l4_critic/` W10 artifacts

```text
DO NOT commit / stash / reset in this window.
Owner must decide whether proposed_base_sha is acceptable
despite dirty tree, or choose another sha after a clean tree.
```

## 2. Python runtime observation

Preferred interpreter: project `backend/.venv` (present).

Commands (read-only):

```text
backend\.venv\Scripts\python.exe --version
backend\.venv\Scripts\python.exe -c "import sys,platform; ..."
```

| Field | Observed value | Provenance |
|---|---|---|
| `python_version` | `3.11.9` | RUNTIME_OBSERVED_CANDIDATE |
| `sys.executable` | `D:\MyPrograms\rag-knowledge-platform\backend\.venv\Scripts\python.exe` | RUNTIME_OBSERVED_CANDIDATE |
| `sys.version` | `3.11.9 (tags/v3.11.9:de54cf5, Apr 2 2024, 10:12:12) [MSC v.1938 64 bit (AMD64)]` | RUNTIME_OBSERVED_CANDIDATE |
| `platform.platform()` | `Windows-10-10.0.26200-SP0` | RUNTIME_OBSERVED_CANDIDATE |

### Runtime identity candidate (proposal only)

```text
observed_runtime_candidate =
  cpython-3.11.9@backend/.venv · Windows-10-10.0.26200-SP0 · AMD64

runtime_identity_candidate =
  suoyin_backend_venv_cpython_3.11.9_win10_amd64

RUNTIME_IDENTITY_CANDIDATE_READY = YES
runtime_identity frozen          = NO
provenance                       = REPOSITORY_OR_RUNTIME_OBSERVED_CANDIDATE
  (recorded below as RUNTIME_OBSERVED_CANDIDATE for package tags)
```

## 3. Dependency surface (read-only)

| Artifact | Present? | Notes |
|---|---|---|
| `backend/requirements.txt` | YES | ranged pins (`>=,<`) |
| `backend/requirements-dev.txt` | YES | declared |
| `backend/requirements-ocr.txt` | YES | declared |
| `pyproject.toml` (project root / backend) | NO | not used as project dep root |
| `poetry.lock` | NO | absent |
| `uv.lock` | NO | absent |
| `Pipfile.lock` | NO | absent |

```text
DEPENDENCY_DECLARATION_STYLE = requirements*.txt (ranged)
DEPENDENCY_SNAPSHOT_PINNED   = NO
  (no frozen lockfile / no pip freeze artifact created this window)
DO NOT run: pip freeze > new file
DO NOT modify the environment
```

## 4. Capture honesty cross-check (observation vs E-B15)

Human-supplied Showcase Narrow honesty:

```text
capture_mode_id          = product_stream
model_backend_identity   = none_no_llm
llm_called_expected      = false
generation_config_ref    = N/A
primary_candidate_source = A
capture_path_identity    = eb15_harness_product_after_capture_path_a
                           (REPOSITORY_VERIFIED_CANDIDATE · design)
```

E-B15 harness (`backend/tests/w10_eb15_product_after_capture.py`) uses product-stream
modes (`product_stream_refusal` / `product_stream_degraded`) with
`llm_called=False`, and forbids live LLM / LM Studio as capture shortcuts.
Freeze-level `product_stream` is the enum parent of that E-B15 product-stream path.

```text
CAPTURE_HONESTY_CONFLICT = NO
product_stream + candidate A + none_no_llm + llm_called_expected=false
  is semantically consistent with E-B15 Narrow product-stream path
```

LM Studio remains Development Generation Backend only:

```text
development_generation_backend     = LM Studio
LOCAL_MODEL_AS_NARROW_FORMAL_PRIMARY = NO
formal_model_identity              = DEFER_TO_BENCHMARK_TRACK
```

## 5. Stamp (this file)

```text
GIT_OBSERVATION_RECORDED             = YES
RUNTIME_OBSERVATION_RECORDED         = YES
RUNTIME_IDENTITY_CANDIDATE_READY     = YES
DEPENDENCY_SNAPSHOT_PINNED           = NO
WORKING_TREE_CLEAN                   = NO
BASE_SHA_CANDIDATE_READY             = NO
BASE_SHA_FREEZE_READINESS            = BLOCKED_PENDING_OWNER_REVIEW
BASE_SHA_FROZEN                      = NO
CAPTURE_HONESTY_CONFLICT             = NO
```
