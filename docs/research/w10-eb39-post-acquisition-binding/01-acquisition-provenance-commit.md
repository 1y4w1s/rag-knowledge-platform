# 01 — Acquisition provenance commit

## Commit

```text
acquisition_record_commit = f82cf46e04da6670acd3ca8a38c12fc6206c03a9
message                   = docs(research): record frozen Product After acquisition
paths staged (explicit)   =
  docs/research/w10-eb38-frozen-baseline-acquisition/**
  docs/status/progress.md
```

No `git add -A`. E-B38 record bodies were **not** rewritten for scoring convenience.

## Separation

| Identity | Value | Role |
|---|---|---|
| `frozen evaluation base_sha` | `3ce0e75f06d35aecaaccd245dd3a234b1c6f79a6` | Evaluation worktree / harness code freeze |
| `authorization_record_commit` | `bd23448f561a541ba6bed7fa1308c3f7de3f6236` | Owner stamp / freeze docs |
| `acquisition_record_commit` | `f82cf46e04da6670acd3ca8a38c12fc6206c03a9` | Product After capture provenance |

```text
acquisition_record_commit ≠ frozen evaluation base_sha = YES
```
