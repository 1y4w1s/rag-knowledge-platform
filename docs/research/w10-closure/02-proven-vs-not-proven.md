# 02 — Proven vs Not Proven

## PROVEN

1. **Frozen baseline + authorization provenance are reconstructible**  
   Owner stamp, freeze records, `base_sha=3ce0e75…`, source/capture/runtime identities, authorization validity chain (E-B35b → E-B36 → E-B37).

2. **Real Product After acquisition can complete**  
   E-B38: eligible=11 · attempted=11 · captured=11 · failed=0 · excluded=1 (C12).

3. **Source / After provenance can be bound**  
   Acquisition records carry source identity, capture mode, content hashes, run identity, frozen baseline binding (E-B38 → E-B39 integrity recheck).

4. **Synthetic contamination can be blocked**  
   Synthetic / isomorphic After paths vetoed for Formal Product After; anti-contamination acknowledged on freeze; E-B18 author-owned embedding forbidden as substitute real After.

5. **DEGRADED responses can be explicitly identified**  
   E-B40 `response_mode` gate; C01–C11 classified `DEGRADED` with `llm_called=false`.

6. **DEGRADED is not miscounted as T2/T3 perfect**  
   Empty/degraded → perfect-score path closed; T2/T3 = `NOT_APPLICABLE` (≠ PASS).

7. **Same-trajectory gated scope + final citations can be captured**  
   E-B41 companion reacquisition: C01–C11 = 11/11 same-trajectory bindings.

8. **Formal candidate and Formal oracle are isolated**  
   E-B41 candidate result ≠ Formal result; E-B44 recomputes from immutable raw only; `FORMAL_ORACLE_LEAK_RISK=NO`.

9. **T1 Formal raw recomputation can complete**  
   E-B44 Formal measurement executed and validated under `w10_showcase_t1_only_v1`.

10. **T1 C01–C11 citation-scope compliance = 11/11**  
    Formal: compliant=11 · violation=0 · excluded=1 · rate=100% on authorized Showcase T1-only Formal scope.

---

## NOT_PROVEN

```text
- live LLM answer quality
- local model capability
- T2 unsupported-assertion rate
- T3 grounding rate
- Critic semantic capability
- A4 live LLM capability
- LM Studio capability
- production availability
- production-scale performance
- paper-grade reproducibility
- dependency-complete environment pin
- Research Benchmark claims
```

These items remain **out of W10 claim surface**. They may appear later only under a separately authorized research or product window — not by reinterpretation of this closure.
