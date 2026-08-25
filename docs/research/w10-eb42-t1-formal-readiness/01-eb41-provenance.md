# 01 — E-B41 provenance commit

```text
eb41_provenance_commit     = 2951914b3298ef63258d3a1df953bf10a899977b
commit_subject             = test(eval): add T1 same-trajectory companion capture
eb41_provenance_commit    ≠ frozen evaluation base_sha
frozen evaluation base_sha = 3ce0e75f06d35aecaaccd245dd3a234b1c6f79a6
```

## Explicit staging (no `git add -A`)

```text
backend/tests/w10_eb41_t1_companion.py
backend/tests/test_w10_eb41_t1_companion_reacquisition.py
docs/research/w10-eb41-t1-companion-reacquisition/**
docs/status/progress.md
```

## Binding note

Frozen baseline for Formal T1 **inputs** remains `3ce0e75…`.  
Documentation / protocol commits after freeze (including this E-B41 provenance commit) must **not** rewrite evaluation `base_sha`.
