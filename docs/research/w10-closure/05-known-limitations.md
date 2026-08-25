# 05 — Known Limitations (Frozen)

These limitations are **accepted closure facts**, not open blockers for interpreting Formal T1 under scope v2.

1. **Dependency snapshot not pinned**  
   `dependency_snapshot = EXPLICITLY_UNPINNED_SHOWCASE`. Runtime identity frozen for Showcase; full dependency-complete pin absent → no paper-grade environment claim.

2. **Formal model identity deferred**  
   `formal_model_identity = DEFER_TO_BENCHMARK_TRACK`. W10 does not claim a concrete local/remote generative model identity for answer quality.

3. **Current Product After is DEGRADED**  
   E-B38 C01–C11: `response_mode=DEGRADED` · `llm_called=false`. Captures product-path degraded behavior, not live ANSWER generation.

4. **T2 / T3 need real ANSWER After**  
   Under E-B40, DEGRADED stays out of T2/T3 claim-quality denominator. Measuring unsupported-assertion / grounding rates requires authorized real ANSWER After (+ rebound claim units).

5. **Frozen baseline is Showcase research baseline, not production deployment**  
   `base_sha=3ce0e75…` is Owner-APPROVED Showcase evaluation baseline. Not a production release pin.

6. **Historical `E-B_FORMAL_READY` semantics remain untouched**  
   Pre-v2 global `E-B_FORMAL_READY=NO` stays on the historical record. Closure uses `w10_showcase_t1_only_v1` / `E_B_FORMAL_READY_V2` successor semantics for T1-only Formal Measurement — it does **not** retroactively flip the historical flag to YES.

7. **Formal Scope v2 is target-specific successor**  
   `FORMAL_MEASUREMENT_SCOPE=T1_ONLY` is an explicit successor scope for Showcase Narrow under DEGRADED honesty. It does not silently replace E-B24’s historical `{T1,T2,T3}` declaration text; readers must cite scope id.

## Additional frozen footnotes

```text
CANONICAL_FORMAL_T1_RESULT_COUNT = 1
FORMAL_ORACLE_LEAK_RISK          = NO
C12                              = INELIGIBLE_NOT_SCORED (excluded=1)
```
