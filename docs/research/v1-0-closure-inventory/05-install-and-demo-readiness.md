# 05 — Install and Demo Readiness

> Repo-level verification only · **no** full reinstall this window.  
> HEAD checked: `f06e8d92…`

## Install path checklist（new-user questions）

| # | Question | Repo answer? | Evidence | Gap |
|---|----------|:------------:|----------|-----|
| 1 | prerequisites | YES | README：Docker Compose · LLM key · HF mirror for BGE | Bare-metal Python/Node not first-class |
| 2 | backend install | YES（compose） | `docker-compose.yml` · `backend/requirements.txt` | Local venv path secondary |
| 3 | frontend install | YES（compose web） | prod overlay · `frontend/package.json` | npm-only path not in 快速开始 |
| 4 | environment config | YES | README `.env` template · `scripts/init-secrets.ps1` | Must replace placeholders |
| 5 | database / vector store | YES | Postgres 16 + pgvector in compose | — |
| 6 | model / provider config | YES | `CHAT_PROVIDER` · `EMBEDDING_PROVIDER=bge` · DeepSeek/Tongyi | Local chat model not product path |
| 7 | start commands | YES | `docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build` | `scripts/docker-up.ps1` may use plain `up`（overlay drift） |
| 8 | minimal demo | PARTIAL | README 使用方法 4 步 | No single canonical demo script（see below） |
| 9 | test commands | PARTIAL | CONTRIBUTING / AGENTS Hit@3 · pytest paths | Scattered；Agent Golden not CI |
| 10 | known limitations | YES | `docs/status/v1-known-limitations.md` · W10 closure limitations | README V1 section partially stale |

### Light verification performed

```text
EXISTS: README.md, docker-compose.yml, docker-compose.prod.yml,
        docs/TEST_ACCOUNTS.md, docs/status/v1-known-limitations.md,
        backend/app/core/config.py, .github/workflows/ci.yml,
        scripts/docker-up.ps1, scripts/init-secrets.ps1, scripts/smoke-deploy.ps1,
        frontend/package.json, backend/requirements.txt, CONTRIBUTING.md
MISSING_ROOT: docs/BROWSER-MODULE-ACCEPTANCE.md
ARCHIVE_OK: docs/archive/tasks/ops/wave/BROWSER-MODULE-ACCEPTANCE.md
NOT_RUN: full docker rebuild / smoke-deploy / live /health
```

## Install verdict

```text
INSTALL_PATH_STATUS = PARTIAL
```

**Not BROKEN** at documentation level（compose path coherent）.  
**Not READY** because: overlay/script inconsistency · BROWSER acceptance root link drift · live smoke not re-verified this window · bare-metal undocumented as primary.

---

## Demo readiness

### Is there a canonical interviewer/developer demo path?

**No single authoritative product demo path.**

| Candidate | Status |
|-----------|--------|
| README browser workflow（login→upload→chat→cite/refuse） | Informal · workable if env up |
| `docs/archive/.../ENTERPRISE_DEMO_SCRIPT.md` | **Minimal stub** · explicitly not 15-min SSOT |
| BROWSER M1–M12 | Archive path only；**root file missing** |
| `docs/TEST_ACCOUNTS.md` | Accounts exist |
| W10 “Showcase” | **Research Formal scope** · not product tour |
| Frontend “演示资料库” breadcrumb | Naming only |

### If forced to describe a provisional flow（documentation only）

| Field | Value |
|-------|--------|
| DEMO_ENTRY | `http://localhost/` after compose prod up · login via `TEST_ACCOUNTS` |
| DEMO_FLOW | Create/open KB → upload doc → wait ingest → ask grounded Q → show citation chips → ask ungrounded Q → show refuse → optional member read-only |
| DEPENDENCIES | Docker stack · LLM key · embeddings download · seeded or uploaded docs · demo accounts |
| EXPECTED_OUTPUT | Cited answer with doc name/location/snippet · clear refuse when no evidence |
| KNOWN_LIMITATIONS | L3/Critic off；memory utilization not proven；no scripted 15-min talk track；BROWSER SSOT path broken |

### Verdict

```text
DEMO_READINESS = GAP
```

**Do not implement Demo in this window.**
