# Eval-Ops M2 · k6 读路径压测

> **范围**：登录 → 资料库列表（分页）→ 概览统计  
> **数据前提**：L 档 seed（6000+ 库）· 团队空间 `demo_admin`  
> **通过线**（plan 初版）：20 VU · 列表 p95 < 500ms · 5xx 错误率 0%

## 前置

1. Docker 栈已起：`docker compose up -d` · `/health` → `database: ok`
2. L 档数据已写入（见 `docs/TEST_ACCOUNTS.md` §L 档）
3. k6：本机安装 **或** 用下方 Docker 一行命令（推荐）

## 环境变量

| 变量 | 默认 | 说明 |
|------|------|------|
| `BASE_URL` | `http://localhost:8000` | API 根；Docker 内跑 k6 时用 `http://host.docker.internal:8000` |
| `IDENTIFIER` | `demo_admin` | 登录名 |
| `PASSWORD` | `password123` | 密码 |
| `WORKSPACE` | （登录响应 org_id） | 组织 UUID；一般留空 |
| `KB_LIMIT` | `24` | 与前端分页 v1 一致 |
| `KB_OFFSET` | `0` | 列表 offset |
| `VUS` | `10` | 并发虚拟用户 |
| `DURATION` | `30s` | 场景时长 |

## 本机 k6

```powershell
cd D:\MyPrograms\rag-knowledge-platform\backend\loadtests

# 10 VU · 30s
k6 run -e VUS=10 -e DURATION=30s read_paths.js

# 20 VU · 30s
k6 run -e VUS=20 -e DURATION=30s read_paths.js
```

## Docker k6（Windows 推荐）

```powershell
cd D:\MyPrograms\rag-knowledge-platform

docker run --rm `
  -v "${PWD}/backend/loadtests:/scripts" `
  -e BASE_URL=http://host.docker.internal:8000 `
  -e VUS=10 -e DURATION=30s `
  grafana/k6 run /scripts/read_paths.js
```

20 VU 场景把 `VUS=20` 即可。

## 输出说明

- 终端末尾打印 **Eval-Ops M2 summary**：`GET /knowledge-bases` 与 `GET /dashboard/stats` 的 p50/p95
- 完整数字写入 `docs/tasks/eval-M2-report.md`（M2-3 产出）
- `kb list has total >= 6000` 检查失败 → 先跑 L 档 seed

## 不做什么

- 不测写路径 / 上传 / 对话（属 M3/M5）
- 不调 embedding / LLM
- 不修改后端代码
