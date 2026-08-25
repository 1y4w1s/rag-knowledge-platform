# 03 — API Dependency Risk Analysis

> Cloud API generation is useful but **externally controlled**.  
> It is **not prohibited** — it must not be the sole experimental foundation.

## 1. Risk inventory

| Risk | Impact on Development | Impact on Formal Evaluation |
|---|---|---|
| **Price changes** | Budget shock; experiment volume cut | Re-run cost; may freeze suite mid-campaign |
| **Provider availability** | Outages block Agent iteration | Formal window blocked / delayed |
| **Rate limits** | Slow CI / agent loops | Incomplete capture batches |
| **Reproducibility** | Soft — prompts drift; provider silent updates | Hard fail for provenance honesty |
| **Policy / ToS / region** | Access revoked | Formal source identity may vanish |
| **Model deprecation** | Force migration mid-experiment | Historical After not re-playable under same id |

---

## 2. Past posture vs required posture

```text
Past practice:
  DeepSeek API (and similar) used as primary generation surface.

Required posture (E-B28):
  Development Generation Backend → Local Model First + optional API.
  Formal Evaluation Source      → authorized, reproducible, provenance-bound
                                   (role separate from any capture-path candidate;
                                    Narrow Product After candidacy = A · not API live;
                                    Formal Evaluation Source not approved).
```

API remains:

- Valid **Development** backend option.
- Possible future Formal track **only** after Narrow scope revision +
  owner stamp + A4-class authorization (E-B27 Option C currently OUT).

API is **not**:

- The only allowed experiment substrate.
- An automatic Formal Evaluation Source.

---

## 3. Reproducibility gap (API vs Local vs Harness)

| Surface | Typical reproducibility | Narrow Product After capture-path role |
|---|---|---|
| E-B15 no-LLM harness modes | Highest (deterministic) | Validated Product After capture path candidate (PRIMARY=A) · ≠ Formal Evaluation Source |
| Local pinned weights + params | High if pin surface frozen | Development / future Track B · `LOCAL_MODEL_AS_NARROW_FORMAL_PRIMARY=NO` |
| Cloud API (unpinned) | Low–medium (provider drift) | OUT for Narrow PRIMARY candidacy |
| Cloud API (pinned model id only) | Medium (still provider-side change) | Needs explicit owner contract · not automatic Formal Evaluation Source |

---

## 4. Mitigation principles (design only)

1. **Do not** bind Formal rates solely to an unpinned cloud model.
2. **Do** keep Development able to run offline / local.
3. **Do** record provider + model id + date if API used for informal runs —
   still `formal_measurement=false`.
4. **Do not** treat API green demos as Product After authorization.
5. When Formal eventually uses live generation (post-Narrow), require full
   identity + stamp + binding — same honesty bar as E-B24/E-B25.

---

## 5. Claims / non-claims

| Claims | Does not claim |
|---|---|
| API dependency risks documented | API banned from product forever |
| API alone insufficient as Formal foundation | Current product must migrate off API this window |
| Local First mitigates Development risk | Local stack already deployed |

## 6. Stamp

```text
API_DEPENDENCY_RISK_DOCUMENTED = YES
API_AS_SOLE_EXPERIMENT_BASE    = REJECTED_BY_POLICY
API_ALLOWED_FOR_DEVELOPMENT    = YES
API_AS_NARROW_FORMAL_PRIMARY   = NO   (E-B27 Option C OUT)
E-B_FORMAL_READY               = NO
```
