# 03 — Recommendation, residuals, implementation-window gate

## 1. Recommended scheme

```text
RECOMMENDED = Scheme A (test-only stream harness)
REJECTED    = Scheme B (observation hook)
REJECTED    = Scheme C (claim capture impossible)
```

**Rationale：**  
产品 After 写入点已是 `state`；tests 已有直调 `_stream_generation_phase` 先例。A 清 B2′ 的「产品 path 不可达」假缺口，且不改 `backend/app`、不污染实验边界。B 多余且有害。C 与证据矛盾。

**首批实现建议（下一窗 plan/impl，仍非正式）：**

1. **A1** empty-gate / refusal drain（材料已 READY；零 LLM）  
2. **可选 A2/A3** 对 C01–C11 的 stream 机制冒烟（`llm_called=false` · 诚实标签）  
3. **禁止 A4** 直至 owner 授权模型窗 + E-B2 `llm_called` freeze 解冻合同  

---

## 2. Residual blockers（post E-B14）

### Still blocking B2′ / formal

| Id | Status | Note |
|---|---|---|
| Product stream After **harness missing** | Open | Feasibility **YES**；implementation **pending** |
| Reserved formal write + owner unlock | Open | `E-B_NARROW_FORMAL_READY=NO` · formal file absent |
| Gold ↔ After hash binding | Open | E-B12B = synthetic_authored；stream After 须匹配或 rebind |
| E-B2 `llm_called=false` freeze | Open for A4 | Live LLM formal 需另窗解冻 |
| S2 packaging auth（T4 Full） | Open | Material YES · `AUTHORIZED=NO` |
| `E-B_FORMAL_READY` | **NO** | Unchanged |

### Cleared by this review（claims only）

| Claim | Value |
|---|---|
| Is product After **capturable** without app hook? | **YES**（Scheme A） |
| Is app observation hook required? | **NO** |
| Is capture impossible (Scheme C)? | **NO** |

---

## 3. Implementation window — allowed?

| Question | Answer |
|---|---|
| May enter **formal observation** window? | **NO** |
| May enter **capture-harness implementation** window（tests/docs only）? | **YES** |
| May modify `backend/app` / runtime? | **NO** |
| May call LLM / LM Studio? | **NO**（until separate owner auth） |
| May write reserved `FORMAL_OBSERVATION_RESULT`? | **NO** |

```text
MAY_ENTER_CAPTURE_HARNESS_IMPL_WINDOW = YES
MAY_ENTER_FORMAL_OBSERVATION_WINDOW   = NO
E-B_FORMAL_READY                      = NO
```

**Impl window scope（建议一窗一事）：**  
在 `backend/tests/` 增加 product-stream After capture mode（prepare → drain `_stream_generation_phase` → E-B2 slot mapping）；默认 informal / `measurement_valid=false`；零 LLM（A1 优先）。

**Impl window must not：** flip formal gates · reserved formal write · P2-R1 inject · patch product stream · claim B2′ cleared until artifacts + unlock exist.

---

## 4. Formal fields reminder

Even after harness exists, Full formal still needs C1∧C2∧C3∧C4∧C5（见 E-B B2′ readiness `03`）。E-B14 only answers：**C2 的产品 stream 捕获在技术上是否可行** → YES via A.

---

## Stop

```text
E-B_FORMAL_READY = NO
B2_PRIME_AFTER_SNAPSHOTS = BLOCKING_RESIDUAL
PRODUCT_AFTER_CAPTURE_FEASIBLE = YES  # Scheme A
MAY_ENTER_CAPTURE_HARNESS_IMPL_WINDOW = YES
MAY_ENTER_FORMAL_OBSERVATION_WINDOW = NO
```
