# 03 — Gold ↔ Real After Rebinding

## Forbidden inputs (honored)

- E-B18 author-owned BP-A compatibility pack
- Synthetic claim-text embedding After bodies
- Modifying E-B12B gold or E-B38 After to force bind

## Required pair

```text
E-B12B human claim gold  (kind=synthetic_authored)
    ↔
E-B38 actual Product After records (observed_content_hash = real utf8 digest)
```

## Per-case binding (frozen E-B17 `validate_binding`)

| case_id | gold_ledger_hash (prefix) | observed_content_hash (prefix) | evidence_pool_hash (gold) | BP-A verdict | BP-B verdict | binding_verdict |
|---|---|---|---|---|---|---|
| C01 | `87c54c18…` | `sha256:deb8a384…` | `1e38788e…` | INCOMPATIBLE | INVALID | **BLOCK** |
| C02 | `0f6845de…` | `sha256:c360ea17…` | `9d0194a6…` | INCOMPATIBLE | INVALID | **BLOCK** |
| C03 | `fb62fae6…` | `sha256:8eaec856…` | `3348a685…` | INCOMPATIBLE | INVALID | **BLOCK** |
| C04 | `6810e2ef…` | `sha256:3edb11b9…` | `b085b179…` | INCOMPATIBLE | INVALID | **BLOCK** |
| C05 | `f2f4fa1a…` | `sha256:645f9b97…` | `aa8c7dfe…` | INCOMPATIBLE | INVALID | **BLOCK** |
| C06 | `383c9155…` | `sha256:9916dd40…` | `865a96c6…` | INCOMPATIBLE | INVALID | **BLOCK** |
| C07 | `058c497a…` | `sha256:93c688fd…` | `b099334b…` | INCOMPATIBLE | INVALID | **BLOCK** |
| C08 | `0f8388e2…` | `sha256:9e38c5a9…` | `5f4b267c…` | INCOMPATIBLE | INVALID | **BLOCK** |
| C09 | `c0f6a70c…` | `sha256:25772ebe…` | `3f31f3ed…` | INCOMPATIBLE | INVALID | **BLOCK** |
| C10 | `1ad3e86f…` | `sha256:7d1655de…` | `8af60e0d…` | INCOMPATIBLE | INVALID | **BLOCK** |
| C11 | `d352eabf…` | `sha256:deb8a384…` | `1e38788e…` | INCOMPATIBLE | INVALID | **BLOCK** |

All eleven use **real** E-B38 `observed_content_hash` values (not E-B18 hashes).

### BP-A blocker (uniform)

```text
BP-A requires gold.content_binding.kind='observed_after'
(got 'synthetic_authored')
```

### BP-B blockers (uniform class)

1. Pool drift: gold `evidence_ids` (`E1`/`E2`) ⊈ observed product `chunk_id` UUIDs  
2. Often: claim-text presence fail (whitespace-normalized substring) against degraded body

## Verdict

```text
REAL_AFTER_BINDING_COMPLETE = NO
BP_A_REAL_AFTER_BOUND       = NO
```

Do **not** patch gold/After. Binding is BLOCKED pending protocol-repair / human rebound window.
