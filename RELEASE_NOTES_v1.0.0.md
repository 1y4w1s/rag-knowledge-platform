# Suoyin (索隐) V1.0.0 Release Notes

**Tag target:** `v1.0.0`  
**Product:** enterprise knowledge-base Agentic-RAG with citation provenance.

## Proven deliverables

- Trustworthy Agentic-RAG foundation (Legacy Agent default path)
- Hybrid retrieval (PG FTS + pgvector + RRF) with evidence-oriented generation
- Citation / provenance (document name, location, snippet) and resolve path
- Refusal / degraded semantics when evidence is insufficient
- Safe defaults: L3 / Critic / L4 / rerank / HyDE / query rewrite / graph recall **OFF**
- Evaluation / CI discipline (Tier-1 PR gates; retrieval Hit@3 + local-BGE baseline)
- Clean-room install path (Windows + Docker Desktop verified)
- Canonical product demo (`scripts/demo.ps1`)

## Explicit non-claims

This release does **not** advertise: GraphRAG, Evolver, Multi-Agent, MCP expansion, local-model superiority, production SLA, or general 100% RAG/Agent/grounding accuracy.

Scoped research evidence (ADV / W9 / W10 Formal T1) remains archive/discipline only — see `docs/benchmark-summary.md` and `docs/status/v1-known-limitations.md`.

## Known limitations

See [`docs/status/v1-known-limitations.md`](docs/status/v1-known-limitations.md).

## Install / demo

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

```powershell
.\scripts\demo.ps1
```
