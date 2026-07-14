# Eval-Ops M5 · 限流实测报告

> **状态**：✅ M5 完成（2026-07-08）  
> **性质**：纯文档 + **沿用现有 pytest**（5/5 绿）· 本任务 **不 Implement 新限流逻辑**  
> **代码依据**：`login_rate_limit.py` · `api_rate_limit.py` · EW-A4 / EW-A5 · `TECH.md` TECH-SEC

---

## 0. 一句话（大白话）

知岸有三道「防刷」：**登录连错 5 次锁 15 分钟**；**同一用户 1 小时最多对话 30 次、上传 20 次**。超了返回 **429**，页面上会看到中文提示。计数存在 **API 进程内存**里——单机 Docker 够用；以后多副本要换 Redis（本任务不测）。

---

## 1. 三道限流总表（M5-1）

| # | 场景 | 触发点 | 维度 | 阈值 | 窗口 | HTTP | 用户看到什么 |
|---|------|--------|------|------|------|------|--------------|
| **L1** | 登录失败 | `POST /api/v1/auth/login` | **IP + 用户名/邮箱** | **5 次失败** | **15 分钟**滑动 | 前 5 次 **401** · 第 6 次起 **429** | 「登录失败次数过多，请 15 分钟后再试」 |
| **C1** | 对话 | `POST .../knowledge-bases/{id}/chat` | **user_id** | **30 次** | **1 小时**滑动 | 第 31 次 **429** | 「对话请求过于频繁，请 60 分钟后再试」 |
| **U1** | 上传 | `POST .../knowledge-bases/{id}/documents` | **user_id** | **20 次** | **1 小时**滑动 | 第 21 次 **429** | 「上传过于频繁，请 60 分钟后再试」 |

### 1.1 不拦什么（心里有数）

| 动作 | 限流？ | 说明 |
|------|--------|------|
| 列表 / 概览 / 搜索 GET | ❌ | 读路径不计入 C1/U1 |
| 登录 **成功** | 清空 L1 计数 | 见 §3.2 |
| member 上传 **403** | 不计入 U1 | 权限先拦，没到限流 |
| 注册 | ❌ | 无独立注册限流（Wave 2+ 可加） |

### 1.2 实现位置

| 模块 | 文件 |
|------|------|
| 登录失败 | `backend/app/services/auth/login_rate_limit.py` · `auth/service.py` `login_user` |
| 对话/上传 | `backend/app/services/auth/api_rate_limit.py` · `api/chat.py` · `api/documents.py` |
| 审计 | L1 触顶写 `auth.login_rate_limited`；失败写 `auth.login_failed` |

---

## 2. 登录限流实测（M5-2 · L1）

### 2.1 规则（代码常量）

```text
MAX_FAILURES = 5
WINDOW_SECONDS = 15 * 60   # 15 分钟
key = f"{ip}:{identifier.lower()}"
```

- **只计失败**（用户不存在或密码错）。
- **成功登录** → `clear_login_failures`，计数清零。
- 第 6 次起：先判 `is_login_rate_limited` → **429** + 审计 `auth.login_rate_limited`（不再尝试验密码）。

### 2.2 Docker 手工实测（2026-07-08）

**环境**：`http://localhost:8000` · 容器 `zhiku-api` running

```powershell
$base = "http://localhost:8000/api/v1/auth/login"
$body = '{"identifier":"demo_admin","password":"故意错误"}'
1..6 | ForEach-Object {
  try {
    Invoke-WebRequest -Uri $base -Method POST -Body $body -ContentType "application/json" -UseBasicParsing
  } catch {
  }
}
```

| 次数 | HTTP | 说明 |
|------|------|------|
| 第 1～5 次 | **401** | `用户名/邮箱或密码错误` |
| 第 **6** 次 | **429** | `登录失败次数过多，请 15 分钟后再试` |

- [x] 与 EW-A4 / plan 设计一致

> **注意**：实测用错误密码会**真的锁住** `demo_admin` 15 分钟。验收后请等窗口过期，或用正确密码登录一次（成功会清计数）。

### 2.3 pytest（自动化）

```powershell
cd D:\MyPrograms\rag-knowledge-platform\backend
py -3.11 -m pytest tests/test_login_rate_limit.py -v --tb=short
```

| 用例 | 验证什么 | 2026-07-08 |
|------|----------|------------|
| `test_sixth_failed_login_returns_429` | 5×401 → 6×429 + 审计 | ✅ PASSED |
| `test_successful_login_clears_failure_counter` | 成功后计数重置 | ✅ PASSED |

---

## 3. 对话 / 上传限流实测（M5-3 · C1 / U1）

### 3.1 规则（代码常量）

```text
CHAT_MAX_REQUESTS = 30
CHAT_WINDOW_SECONDS = 3600
UPLOAD_MAX_REQUESTS = 20
UPLOAD_WINDOW_SECONDS = 3600
key = f"chat:{user_id}" 或 f"upload:{user_id}"
```

- **按用户 ID**，admin 与 member **各自独立**计数。
- **每次请求先计数再执行业务**（到达上限的请求本身也算在窗口内）。
- member 无上传权 → **403**，**不消耗** upload 配额。

### 3.2 pytest（自动化 · 用小阈值模拟）

生产 30/20 次打满太慢；测试用 `monkeypatch` 改为 **3 次/小时**：

```powershell
py -3.11 -m pytest tests/test_api_rate_limit.py -v --tb=short
```

| 用例 | 验证什么 | 2026-07-08 |
|------|----------|------------|
| `test_chat_exceeds_limit_returns_429` | 3 次 200 → 第 4 次 429 · 含「对话」 | ✅ PASSED |
| `test_upload_exceeds_limit_returns_429` | 3 次 201 → 第 4 次 429 · 含「上传」 | ✅ PASSED |
| `test_member_and_admin_share_same_upload_limit` | admin 打满 upload 不影响 member chat 独立配额；member 上传 403 | ✅ PASSED |

**合计**：`test_login_rate_limit` + `test_api_rate_limit` → **5/5 passed**（约 12s）

### 3.3 生产阈值手工抽测（可选 · 费 API）

> 默认 **不做**——30 次对话会调 DeepSeek/通义。若要口播「亲眼见过 429」：

1. 登录拿 token，对**空库或拒答库**连发 31 次 `POST .../chat`（短问题即可）。
2. 第 31 次应 **429**，`detail` 含「对话请求过于频繁」。

上传同理：对有权库连传 21 个小 `.txt` → 第 21 次 429。

---

## 4. 与成本 / 性能的关系（M5-4）

| 限流 | 防什么 | 和 M4 成本的关系 |
|------|--------|------------------|
| L1 | 暴力猜密码 | 不花 API 钱，保账号安全 |
| C1 | 刷对话烧 DeepSeek + 通义 embed/rerank | 单用户最多 **30 次/小时** → 粗算上限见 [`eval-M4-cost-model.md`](eval-M4-cost-model.md) ×30 |
| U1 | 刷上传烧通义 embed | 单用户最多 **20 次/小时** 上传请求 |

**demo 月预算建议（沿用 M4）**：限流是「硬顶」，正常答辩/demo 远低于 30/20；真打满说明脚本或攻击，应查审计。

---

## 5. 已知限制（面试要能讲）

| 限制 | 白话 | 以后怎么办 |
|------|------|------------|
| **内存计数** | API 重启 → 计数清零 | Wave 2+ Redis |
| **单实例** | 开 2 个 api 副本 → 限额变 2 倍 | 同上 |
| **按 user_id** | 同一人换 IP 仍共享 C1/U1 | 符合「按账号防滥用」 |
| **L1 按 IP+账号** | 同 WiFi 不同账号互不影响 | 合理 |

---

## 6. 你怎么验（M5 DoD）

### 6.1 合并前（跟 M11 一起）

```powershell
cd D:\MyPrograms\rag-knowledge-platform\backend
py -3.11 -m pytest tests/test_login_rate_limit.py tests/test_api_rate_limit.py -v --tb=short
```

- [ ] **5/5 passed**

### 6.2 发版后（可选 2 分钟）

- [ ] 对测试账号故意错密 6 次 → 第 6 次 **429**（勿用答辩前要用的账号）
- [ ] 或只读本文 §2.2 实测表，不再重复打锁

---

## 7. M5 DoD（plan 对照）

| # | 退出条件 | 本文 |
|---|----------|------|
| M5-1 | login / chat / upload 三道阈值表 | §1 |
| M5-2 | 登录实测数字 | §2.2（6 次→429） |
| M5-3 | chat/upload pytest 绿 | §3.2（5/5） |
| — | 文档可跟跑 | §2.2 · §6 |

---

## 8. 关联文档

| 文档 | 关系 |
|------|------|
| [`eval-ops-plan.md`](eval-ops-plan.md) | M5 任务来源 |
| [`eval-M11-release-checklist.md`](eval-M11-release-checklist.md) | 发版可附带 §6.1 pytest |
| [`eval-M4-cost-model.md`](eval-M4-cost-model.md) | 限流 ↔ 成本上限 |
| [`TECH.md`](../TECH.md) TECH-SEC | EW-A4/A5 设计 |
| [`DEPLOY.md`](../DEPLOY.md) | 内网 HTTP 无 TLS，限流是补偿之一 |
