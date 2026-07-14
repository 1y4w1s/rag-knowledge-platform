# Eval-Ops M10 · 备份恢复 Runbook

> **状态**：✅ M10 完成（2026-07-08）  
> **性质**：运维文档 + `scripts/backup-prod.ps1` / `restore-prod.ps1` · **不 Implement 应用代码**  
> **对齐**：[`enterprise-wave-plan.md`](enterprise-wave-plan.md) Wave 6 持久化 · [`DEPLOY.md`](../DEPLOY.md) §3.7

---

## 0. 一句话（大白话）

知岸有两块「不能丢」的数据：**PostgreSQL 里的用户/库/向量** 和 **uploads 卷里的原始上传文件**。M10 教你用两条脚本 **先打包、再整卷恢复**，恢复后 `GET /health` 要还是 `database: ok`。

---

## 1. 备份什么（M10-1）

| 资产 | Docker 卷 / 来源 | 备份文件 | 丢了会怎样 |
|------|------------------|----------|------------|
| **数据库** | `rag-knowledge-platform_postgres_data` | `zhiku.dump`（`pg_dump -Fc`） | 用户、资料库、chunk、向量、审计全没 |
| **上传文件** | `rag-knowledge-platform_uploads_data` | `uploads.tar.gz` | DB 还在但预览/重嵌入找不到磁盘文件 |

**不备份**：Docker 镜像、`.env` 密钥、前端 `dist/`（可 `compose build` 重建）。

---

## 2. 前置条件

| 项 | 要求 |
|----|------|
| 栈 | **生产 compose**：`docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d` |
| 卷 | `uploads_data` 命名卷存在（仅 dev compose 无此卷 → 先加 prod overlay） |
| 工具 | Docker Desktop / Engine 24+ · PowerShell 5+（Windows）或见 §6 bash |
| 磁盘 | 备份目录建议预留 **≥ 2×**（DB + uploads）当前用量 |

备份产出默认在仓库内 `backups/m10-YYYYMMDD-HHmmss/`（**已在 `.gitignore`**，勿提交）。

---

## 3. 备份步骤（M10-2）

```powershell
cd D:\path\to\rag-knowledge-platform

# 确认三容器 running（zhiku-postgres / zhiku-api / zhiku-web）
docker compose -f docker-compose.yml -f docker-compose.prod.yml ps

.\scripts\backup-prod.ps1
```

**通过标准**：

- [ ] 终端绿色 `backup complete`
- [ ] 目录含 `zhiku.dump`、`uploads.tar.gz`、`manifest.json`
- [ ] `zhiku.dump` 大于 1 KB（空库也应有 catalog）

自定义输出目录：

```powershell
.\scripts\backup-prod.ps1 -OutDir backups\before-migration
```

---

## 4. 恢复步骤（M10-3）

> **破坏性操作**：覆盖当前 DB 与 uploads 卷。演练前务必 **先备份**（§3）。

```powershell
.\scripts\restore-prod.ps1 -BackupDir backups\m10-20260708-223045
```

> **注意**：`-BackupDir` 填 **备份脚本打印出来的真实目录名**（如 `backups\m10-20260708-drill`），**不要**复制文档里的 `<时间戳>` 占位符。

脚本会：

1. 停 `api` + `web`（postgres 保持）
2. `pg_restore --clean --if-exists` 灌入 `zhiku.dump`
3. 清空 uploads 卷后解压 `uploads.tar.gz`
4. 拉起 `api` + `web`
5. `GET http://localhost:8000/health` → `status: ok` · `database: ok`

跳过探活（只恢复、自己验）：

```powershell
.\scripts\restore-prod.ps1 -BackupDir backups\m10-... -SkipHealthCheck
```

内网经 nginx：

```powershell
.\scripts\restore-prod.ps1 -BackupDir backups\m10-... -BaseUrl http://SERVER_IP
# 注意：$BaseUrl 不含 /health 后缀；经 web :80 时用 http://IP，直连 API 用 http://IP:8000
```

---

## 5. 乱操作 / 边界（M10-4）

| 乱操作 | 系统/脚本行为 | 你怎么验 |
|--------|---------------|----------|
| 未起 prod 栈就备份 | 脚本报 `uploads volume missing` | 加 `-f docker-compose.prod.yml` 后重试 |
| 只 dev compose（无 uploads 卷） | 备份失败 | `docker volume ls` 应有 `*_uploads_data` |
| 恢复时路径错 | `missing zhiku.dump` | `-BackupDir` 指向含三文件的目录 |
| 恢复中途拔电 | DB/卷可能半残 | **永远先有一份新备份**；再 restore 或从旧备份重来 |
| `pg_restore` 警告退出码 1 | 常见（对象已不存在） | 脚本仅 **exit > 1** 才失败；以 `/health` 为准 |
| 恢复后密码/Key 不对 | health 可能 ok 但对话失败 | `.env` 与备份时一致；Key 不在 dump 里 |
| 把 `backups/` 提交 Git | 可能含业务数据 | 已 gitignore；备份放网盘/内网 NAS |

---

## 6. Linux / bash 等价命令（无 ps1 时）

**备份**：

```bash
cd /path/to/rag-knowledge-platform
STAMP=$(date +%Y%m%d-%H%M%S)
DEST="backups/m10-$STAMP"
mkdir -p "$DEST"
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec -T postgres \
  pg_dump -U zhiku -Fc zhiku > "$DEST/zhiku.dump"
docker run --rm \
  -v rag-knowledge-platform_uploads_data:/data:ro \
  -v "$(pwd)/$DEST:/backup" \
  alpine:3.20 tar czf /backup/uploads.tar.gz -C /data .
```

**恢复**（先 `compose stop api web`）：

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec -T postgres \
  pg_restore -U zhiku -d zhiku --clean --if-exists --no-owner --no-privileges < backups/m10-.../zhiku.dump
docker run --rm \
  -v rag-knowledge-platform_uploads_data:/data \
  -v "$(pwd)/backups/m10-...:/backup:ro" \
  alpine:3.20 sh -c 'find /data -mindepth 1 -maxdepth 1 -exec rm -rf {} +; tar xzf /backup/uploads.tar.gz -C /data'
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d api web
curl -s http://localhost:8000/health
```

---

## 7. 演练记录（M10-5 · 2026-07-08）

| 项 | 记录 |
|----|------|
| **日期** | 2026-07-08 |
| **环境** | Windows · Docker Desktop · prod compose（zhiku-postgres / zhiku-api / zhiku-web） |
| **备份命令** | `.\scripts\backup-prod.ps1` |
| **备份目录** | `backups/m10-20260708-drill/`（演练专用；不提交 Git） |
| **恢复命令** | `.\scripts\restore-prod.ps1 -BackupDir backups\m10-20260708-drill` |
| **恢复后 health** | `{"status":"ok","database":"ok"}` |
| **dump 大小** | `zhiku.dump` 66,298,927 bytes · `uploads.tar.gz` 1,876 bytes |
| **结果** | ✅ **通过** — dump + uploads 往返后 API 探活正常（本机实跑验证） |
| **脚本修复** | Windows PS 二进制：`pg_dump`/`pg_restore` 经 **docker cp** 传 `/tmp/zhiku.dump`（勿管道 `Set-Content -Encoding Byte`） |
| **耗时（粗估）** | 备份 ~30s · 恢复 ~45s（视库大小） |
| **面试 30 秒** | 「知岸用 Docker 命名卷存 PG 和 uploads；M10 用 pg_dump 自定义格式 + tar 打卷，脚本化备份恢复，演练证明删卷后可回到 health ok。」 |

### 7.1 建议节奏（答辩后运营）

| 频率 | 动作 |
|------|------|
| **每周** | `backup-prod.ps1` → 拷到内网 NAS |
| **每季度** | 本 runbook §4 完整 restore 演练一次，更新 §7 日期 |
| **发版前** | 见 [`eval-M11-release-checklist.md`](eval-M11-release-checklist.md) |

---

## 8. 相关文档

| 文档 | 关系 |
|------|------|
| [`DEPLOY.md`](../DEPLOY.md) §3.3 / §3.7 | prod compose 与卷验收 |
| [`eval-ops-plan.md`](eval-ops-plan.md) | M10 模块定义 |
| [`eval-M11-release-checklist.md`](eval-M11-release-checklist.md) | 发版回归 |
| [`TECH.md`](../TECH.md) §6 | Docker 架构 |
