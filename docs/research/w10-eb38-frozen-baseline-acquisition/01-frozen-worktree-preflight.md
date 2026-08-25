# 01 — Frozen worktree preflight

## Worktree

```text
path = D:\MyPrograms\rag-knowledge-platform-eb38-frozen-3ce0e75
command =
  git worktree add --detach <path> 3ce0e75f06d35aecaaccd245dd3a234b1c6f79a6
```

Main authorization workspace HEAD was **not** checked out / reset / stashed.
Authorization commits were **not** rewritten.

## Preflight (required)

```text
git rev-parse HEAD
  = 3ce0e75f06d35aecaaccd245dd3a234b1c6f79a6
  MATCH frozen base_sha                         = YES

git status --short
  = <empty>
  WORKING_TREE_CLEAN                            = YES

E-B15 harness present
  backend/tests/w10_eb15_product_after_capture.py = YES

FROZEN_WORKTREE_PREFLIGHT = PASS
```

## Runtime identity (observed on acquisition interpreter)

```text
interpreter =
  D:\MyPrograms\rag-knowledge-platform\backend\.venv\Scripts\python.exe
python_version = 3.11.9
platform       = Windows AMD64
implementation = CPython

runtime_identity_observed =
  suoyin_backend_venv_cpython_3.11.9_win10_amd64
runtime_identity_authorized =
  suoyin_backend_venv_cpython_3.11.9_win10_amd64
RUNTIME_IDENTITY_MATCH = YES
```

Note: Showcase `DEPENDENCY_SNAPSHOT_PINNED=NO` remains a reproducibility
limitation and is **not** treated as an acquisition hard blocker (per E-B36 stamp).

## Post-run frozen-worktree status

```text
git rev-parse HEAD
  = 3ce0e75f06d35aecaaccd245dd3a234b1c6f79a6
git status --short
  = <empty>
IMPLEMENTATION_MUTATION_DURING_RUN = NO
artifact_output_location =
  authorization workspace:
  docs/research/w10-eb38-frozen-baseline-acquisition/
  (external to frozen tracked tree)
```
