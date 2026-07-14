# Eval-Ops M2 · 读路径性能报告

> **状态**：✅ M2-1～M2-3 完成（2026-07-08）  
> **脚本**：`backend/loadtests/read_paths.js` · 用法见 `backend/loadtests/README.md`  
> **数据**：L 档 **6005** 库 · 每库 1 文档 · 团队空间 `demo_admin`  
> **分页**：v1 已上线（默认 `limit=24` · URL `?page=` · 跳页）

---

## 1. 测什么（大白话）

模拟 **10 / 20 个用户同时** 在团队空间里：

1. 登录  
2. 打开资料库列表（只拉 **第 1 页 24 条**，不是 6000 条全量）  
3. 打开概览统计（Dashboard 数字）

看：**慢不慢、会不会报错**。

---

## 2. 环境与通过线

| 项 | 值 |
|----|-----|
| API | `http://localhost:8000`（Docker · 本机 Windows） |
| k6 | `grafana/k6:latest` · `host.docker.internal:8000` |
| 组织 workspace | `0f121650-e48f-4954-ab7c-f34f20be4930` |
| 列表参数 | `limit=24` · `offset=0` |
| 场景时长 | 各 **30s** |

**plan 初版通过线**（M2 §3）：

| 指标 | 目标 |
|------|------|
| 20 VU · `GET /knowledge-bases` p95 | **< 500 ms** |
| 5xx 错误率 | **0%** |

---

## 3. 结果数字

### 3.1 场景 A · 10 VU · 30s

| 接口 | p50 (med) | p95 | avg | 迭代数 | 5xx |
|------|-----------|-----|-----|--------|-----|
| `GET /knowledge-bases` | **1809 ms** | **3098 ms** | 1941 ms | 43 | 0 |
| `GET /dashboard/stats` | **3070 ms** | **6818 ms** | 3782 ms | 43 | 0 |
| `POST /auth/login` | 1367 ms | 2780 ms | 1525 ms | 43 | 0 |

- 检查项：**301/301 全绿**（含 `total ≥ 6000`、`limit=24`）  
- 原始 JSON：`backend/loadtests/results/m2-10vu.json`

### 3.2 场景 B · 20 VU · 30s

| 接口 | p50 (med) | p95 | avg | 迭代数 | 5xx |
|------|-----------|-----|-----|--------|-----|
| `GET /knowledge-bases` | **3653 ms** | **5438 ms** | 3883 ms | 51 | 0 |
| `GET /dashboard/stats` | **6128 ms** | **10074 ms** | 6111 ms | 51 | 0 |
| `POST /auth/login` | 3880 ms | 4529 ms | 3574 ms | 51 | 0 |

- 检查项：**357/357 全绿**  
- 原始 JSON：`backend/loadtests/results/m2-20vu.json`

---

## 4. 结论：6000+ 库 + 分页后是否达标？

### 4.1 分页有没有用？——**必须有，且已生效**

| 维度 | 无分页（假想） | 分页 v1（现状） |
|------|----------------|-----------------|
| 单次响应条数 | 6005 条 | **24 条** |
| 浏览器/网络 | 易卡死、JSON 巨大 | 可翻页、体积可控 |
| 本次 k6 验证 | — | `limit=24` · `total=6005` · 全绿 |

**结论 1**：6000+ 库场景下 **服务端分页是刚需**；前端 v1（24/页 · URL · 跳页）方向正确，**不应回退全量列表**。

### 4.2 性能有没有达标？——**未达标（可用但不快）**

| 场景 | 列表 p95 | 通过线 500 ms | 判定 |
|------|----------|---------------|------|
| 10 VU | 3098 ms | ❌ | 超线 ~6× |
| **20 VU** | **5438 ms** | ❌ | **超线 ~11×** |
| 20 VU · 5xx | 0% | ✅ | 稳定、无崩溃 |

**结论 2**：分页解决了 **「一次吐太多数据」**，但 **没解决「每次都要数 6000+ 库 + 聚合文档统计」** 的后端成本。并发一高，列表和 Dashboard 仍 **秒级** 响应。

**结论 3（总括）**：

> **6000+ 库 + 分页 v1：功能达标、性能未达标。**  
> 适合 demo / 低并发内网；若目标 20 并发用户列表 p95 < 500 ms，需 **Phase 1 后端优化**（见 §5），不是再加前端分页能解决的。

---

## 5. 慢在哪（给后续 plan 用 · 本窗不 Implement）

| 可疑点 | 白话 |
|--------|------|
| 列表 `COUNT(*)` | 每请求对 6005 行做 total，并发时 Postgres 压力大 |
| 文档统计子查询 | 列表 JOIN 每库 document 聚合（doc_count / failed 等） |
| Dashboard stats | 组织级多表聚合（6005 KB + 6003 文档） |
| Docker 资源 | API 限 768M · 与 postgres 同机，压测非生产规格 |

**建议 backlog（R→I，非 M2 范围）**：

1. 列表 total 缓存或近似计数（TTL / 仅首页精确）  
2. 复合索引：`owner_org_id` + `updated_at` / 搜索字段  
3. Dashboard stats 物化或定时刷新  
4. 生产规格下复测（M9 SLO 输入）

---

## 6. 你怎么验（复跑）

```powershell
cd D:\MyPrograms\rag-knowledge-platform

# 10 VU
docker run --rm -v "${PWD}/backend/loadtests:/scripts" `
  -e BASE_URL=http://host.docker.internal:8000 -e VUS=10 -e DURATION=30s `
  grafana/k6 run /scripts/read_paths.js

# 20 VU
docker run --rm -v "${PWD}/backend/loadtests:/scripts" `
  -e BASE_URL=http://host.docker.internal:8000 -e VUS=20 -e DURATION=30s `
  grafana/k6 run /scripts/read_paths.js
```

前提：L 档 seed 已跑 · `/health` ok · 见 `docs/TEST_ACCOUNTS.md` §L 档。

---

## 7. 面试 30 秒口播

> 我们用 k6 在 6005 个模拟库上压了读路径：登录、分页列表、Dashboard 统计。分页 v1 把单次响应压到 24 条，避免了全量 JSON，但后端每次仍要数 6000+ 行并做文档聚合。20 虚拟用户下列表 p95 约 5.4 秒，零 5xx，说明 **功能稳定但离企业 SLO（p95 500ms）还有距离**。所以 M2 结论是：**分页必须做且已做，下一步是索引/缓存优化而不是回退列表设计。**

---

## 8. 关联文档

| 文档 | 关系 |
|------|------|
| `eval-ops-plan.md` §M2 | 任务定义 · 通过线 |
| `TEST_ACCOUNTS.md` §L 档 | 6000 库 seed |
| `enterprise-master-plan.md` | 库列表分页 v1 ✅ · 后端优化排 Phase 1 |
