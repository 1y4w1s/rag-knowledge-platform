# Eval-Ops M9 · Demo 环境 SLO 基线

> **状态**：✅ M9 完成（2026-07-08）  
> **性质**：纯文档 · **不 Implement** · 无 Prometheus/Grafana  
> **输入**：[`eval-M2-report.md`](eval-M2-report.md) · [`eval-M5-rate-limit.md`](eval-M5-rate-limit.md) · R5-3b 浏览器抽检 · 本窗单用户抽测

---

## 0. 一句话（大白话）

**SLO** = 你对用户承诺的「服务好不好」三条尺子：**对话多久出字**、**API 会不会挂**、**列表多久刷出来**。本文给 **demo 内网环境** 的可手工量基线 + 数字；不是云厂商 99.99% 那种正式运维合同。

---

## 1. 三条 SLO 总览（M9-1）

| ID | 名称 | 量什么 | **Demo 目标**（内网 · 单用户 · S 档≈10 库） | **Stretch 目标**（企业向 · 参考 M2） | 2026-07-08 基线 |
|----|------|--------|---------------------------------------------|--------------------------------------|-----------------|
| **SLO-C** | 对话首字延迟 | 发问 → 浏览器/SSE **第一个 `token` 事件** | **≤ 8 s**（p95 手工 5 次） | 完整答完 ≤ 30 s | 抽测 **~1.3 s** 流结束（见 §3） |
| **SLO-A** | API 可用率 | `/health` + 读路径 **无 5xx** | **100%** 抽检窗口内 | 20 VU 压测 **5xx = 0%** | M2 **0%** · health **ok** |
| **SLO-L** | 资料库列表延迟 | `GET /knowledge-bases?limit=24` **TTFB** | **≤ 500 ms**（单用户 p95 · 5 次） | 20 VU **p95 < 500 ms** | 单用户 **186～267 ms**；20 VU p95 **5438 ms** ❌ |

### 1.1 两层目标怎么理解

| 层 | 给谁用 | 白话 |
|----|--------|------|
| **Demo** | 答辩 / 内网演示 / 你亲手点 | 一个人用、库不多（S 档）时要 **够快、不挂** |
| **Stretch** | 面试讲「企业差距」 | M2 已证：**6000+ 库 + 20 并发** 离 500 ms 还远，要后端优化 backlog |

> **诚实口径**：Stretch **未达标** 不挡 demo；须在答辩时说清「分页已做、高并发列表待优化」——见 M2 §4。

---

## 2. 度量环境（M9-2）

| 项 | Demo SLO 默认 | 备注 |
|----|---------------|------|
| 部署 | `docker compose up -d` · API `:8000` | 或 prod compose `localhost` |
| 前端 | `npm run dev` → `:5173` 或 prod `:80` | 浏览器量 SLO-C 用 dev 即可 |
| 数据 | **S 档** `seed_volume_data.py --tier S`（≥10 库） | 列表用；对话用 **答辩演示库**（有 md/pdf） |
| 账号 | `demo_admin` / `password123` | `TEST_ACCOUNTS.md` |
| Key | `.env` 配 `DEEPSEEK_API_KEY` + `TONGYI_API_KEY` | 无 Key 对话 SLO 不测 |
| 并发 | Demo = **单用户**；Stretch 引用 M2 k6 | |

---

## 3. SLO-C · 对话首字延迟（M9-3）

### 3.1 定义

| 项 | 说明 |
|----|------|
| **触发** | `POST /api/v1/knowledge-bases/{kb_id}/chat` · body `{"message":"…"}` |
| **指标** | **TTFT**：从请求发出 → SSE 流中 **第一个 `event: token`**（或浏览器 Network **首包后首字**） |
| **通过** | 连续 **5 次** golden 题（P1「年假有多少天？」）· **≤ 8 s**；且 **有引用 chip**（R5-3b） |
| **不计量** | 拒答 AC-4 题（无 token 或固定话术）· 限流 429（见 M5） |

### 3.2 手工量法（浏览器 · 推荐）

1. 登录 `demo_admin` → 团队空间 → 进 **答辩演示库** → **开始对话**。
2. F12 → **Network** → 勾选 Preserve log。
3. 问：**「年假有多少天？」** → 点 `chat` 请求 → **Timing** 看 **Waiting (TTFB)** ≈ 检索+排队；首字看响应流开始时间。
4. 重复 **5 次**（可换问法 P2/P3），记最大值 ≈ p95 粗估。

### 3.3 PowerShell 抽测（2026-07-08 · 端到端流完）

```powershell
# 需已登录拿 token · kb_id = 答辩演示库
# 见 eval-M9-slo.md 仓库内实测记录
```

| 次 | 流结束 total_ms | 首个事件 | 备注 |
|----|-----------------|----------|------|
| 1 | **1543** | token | `?q=答辩` 命中库 · 2 文档 |
| 2 | **1314** | token | 同库同问 |

- **结论**：本机 Docker + 真 Key 下，**单次对话全流 ~1.3～1.5 s**；Demo 目标 **8 s** 余量充足。
- **注意**：Invoke-WebRequest **缓冲整段 SSE**，不能精确 TTFT；答辩验收以 **浏览器首字体感的 5 次** 为准。

### 3.4 与 R5-3b 对齐

| 题 | 浏览器抽检 | SLO-C |
|----|------------|-------|
| P1～P3 | ✅ 有引用 · 流式 | 纳入 5 次手工 |
| GQ-11/12 | ✅ | 可选加测 |

---

## 4. SLO-A · API 可用率（M9-4）

### 4.1 定义

| 项 | 说明 |
|----|------|
| **范围** | `GET /health` · `POST /auth/login` · `GET /knowledge-bases` · `GET /dashboard/stats` |
| **Demo 通过** | 发版后连续 **10 次** 抽检 · 全部 **2xx**（login 错密 **401** 算可用，不算挂） |
| **Stretch 通过** | M2 k6 20 VU · **5xx 错误率 0%** |

### 4.2 手工脚本（2 分钟）

```powershell
$ok = 0; 1..10 | ForEach-Object {
  $h = Invoke-RestMethod http://localhost:8000/health
  if ($h.status -eq 'ok' -and $h.database -eq 'ok') { $ok++ }
  Start-Sleep -Seconds 1
}
"health_pass=$ok/10"
```

| 检查 | 2026-07-08 |
|------|------------|
| `/health` 10/10 | 可跟跑 |
| M2 · 20 VU · 5xx | **0%**（357/357 检查绿） |
| M2 · 10 VU · 5xx | **0%**（301/301） |

### 4.3 不算「不可用」

| HTTP | 场景 |
|------|------|
| **401** | 密码错 |
| **403** | 权限 / workspace 缺参 |
| **429** | M5 限流（设计行为） |

---

## 5. SLO-L · 资料库列表延迟（M9-5）

### 5.1 定义

| 项 | 说明 |
|----|------|
| **接口** | `GET /api/v1/knowledge-bases?workspace={org_uuid}&department_id={dept}&limit=24&offset=0` |
| **指标** | 客户端 **TTFB**（首字节时间） |
| **Demo 通过** | 单用户 **5 次** · p95（取第 5 大值）**≤ 500 ms** |
| **Stretch 通过** | M2：**20 VU · p95 < 500 ms** |

### 5.2 单用户抽测（2026-07-08）

**环境**：L 档残留 **6005 库**（比 S 档 10 库更严）· `demo_admin` · 研发部 scope

| 次 | TTFB (ms) |
|----|-----------|
| 1 | 267 |
| 2 | 231 |
| 3 | 186 |
| 4 | 243 |
| 5 | 228 |
| **p95≈max** | **267** |

- **Demo SLO-L**：✅ **267 ms < 500 ms**
- **Stretch（M2 20 VU）**：❌ **5438 ms**（见 `eval-M2-report.md` §3.2）

### 5.3 PowerShell 跟跑

```powershell
$loginBody = '{"identifier":"demo_admin","password":"password123"}'
$tok = (Invoke-RestMethod -Uri http://localhost:8000/api/v1/auth/login -Method POST -Body $loginBody -ContentType "application/json").access_token
$headers = @{ Authorization = "Bearer $tok" }
$ws = "0f121650-e48f-4954-ab7c-f34f20be4930"   # 以 /me 的 org_id 为准
$dept = "d69950ad-79ae-4909-9c61-45928c7143d2" # 以 /me 的 primary_unit_id 为准
$ms = @()
1..5 | ForEach-Object {
  $t = Measure-Command {
    $null = Invoke-RestMethod -Uri "http://localhost:8000/api/v1/knowledge-bases?workspace=$ws&department_id=$dept&limit=24&offset=0" -Headers $headers
  }
  $ms += [int]$t.TotalMilliseconds
}
"runs=$($ms -join ',') max=$($ms | Measure-Object -Maximum | Select -Expand Maximum)"
```

### 5.4 S 档 vs L 档

| 数据档 | 库数 | 单用户列表（本窗） | 20 VU p95（M2） |
|--------|------|-------------------|-----------------|
| **S** | ≥10 | 预期 **< 300 ms**（未单独 k6） | 未测 |
| **L** | 6005 | **267 ms** ✅ | **5438 ms** ❌ |

答辩 demo 用 **S 档**；压测讲故事用 **L 档 + M2**。

---

## 6. 发版后怎么勾（M9-6 · 可勾选）

### Demo 三连（建议每次内网发版）

- [ ] **SLO-A**：`/health` 10 次 ok/ok
- [ ] **SLO-L**：列表 5 次 · max ≤ 500 ms（单用户）
- [ ] **SLO-C**：答辩库对话 P1 · 5 次首字 ≤ 8 s · 有引用

### Stretch（季度 / 优化后复跑）

- [ ] M2 k6 20 VU · 列表 p95 是否仍 > 500 ms
- [ ] 5xx 仍是否为 0%

---

## 7. 记录表（请你填）

| 项 | 值 |
|----|-----|
| 日期 | |
| 环境 | dev / prod compose |
| 数据档 | S / L |
| SLO-A health | /10 |
| SLO-L list max ms | |
| SLO-C TTFT max s（5 次） | |
| Stretch M2 是否复跑 | 是/否 · 列表 p95 |

---

## 8. M9 DoD（plan 对照）

| # | 退出条件 | 本文 |
|---|----------|------|
| M9-1 | 三条 SLO 表 | §1 |
| M9-2 | 对话延迟定义 + 量法 | §3 |
| M9-3 | API 可用率 | §4 |
| M9-4 | 列表延迟 + M2 数字 | §5 |
| — | 可手工量 | §6 · §7 |

---

## 9. 面试 30 秒口播

> 我们给 demo 环境定了三条 SLO：对话首字 8 秒内、health 和读 API 不发 5xx、单用户列表 500 毫秒内。实测单用户 6000 库列表两百多毫秒能过，但 k6 二十并发 p95 还有五秒多——所以 SLO 分 Demo 和 Stretch 两层，答辩用 S 档十库，压测数据诚实讲瓶颈在 COUNT 和文档聚合，下一步做索引缓存而不是砍分页。

---

## 10. 关联文档

| 文档 | 关系 |
|------|------|
| [`eval-M2-report.md`](eval-M2-report.md) | Stretch 列表 · 5xx 0% |
| [`eval-M5-rate-limit.md`](eval-M5-rate-limit.md) | 429 不算宕机 |
| [`eval-M11-release-checklist.md`](eval-M11-release-checklist.md) | 发版可附带 §6 |
| [`RAG_PRODUCTION_BASELINE.md`](../RAG_PRODUCTION_BASELINE.md) | SLO-C 质量侧 R5-3b |
| [`backend/loadtests/README.md`](../../backend/loadtests/README.md) | 复跑 M2 |
