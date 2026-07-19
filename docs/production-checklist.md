# 睿阁 — 生产部署检查清单

> 生成于 2026-07-17 · 基于当前代码基线

---

## 1. 环境变量审计

### ✅ 已配置

| 变量 | 当前值 | 建议 |
|------|--------|------|
| `DATABASE_URL` | `postgresql+asyncpg://ruige:changeme@postgres:5432/ruige` | 密码须改为强密码 |
| `JWT_SECRET` | 随机字符串 | ✅ 已改为随机字符串 |
| `DEEPSEEK_API_KEY` | 已配置 | ✅ |
| `TONGYI_API_KEY` | 已配置 | ✅ |
| `CORS_ORIGINS` | localhost:5173 等 | 生产改为 `https://your-domain.com` |
| `UPLOAD_DIR` | `./uploads` | Docker 中挂载 volume |

### ⚠️ 需要改的默认值

| 变量 | 默认值 | 问题 |
|------|--------|------|
| `POSTGRES_PASSWORD` | `changeme` | ❌ 必须改为强密码 |
| `ENVIRONMENT` | `development` | 生产须设为 `production` |
| `FORGOT_PASSWORD_RESET_URL` | `localhost:5173` | 须改为生产域名 |

### 🔧 建议新增的配置

| 变量 | 建议值 | 说明 |
|------|--------|------|
| `LOG_LEVEL` | `WARNING` | 生产环境减少日志输出 |
| `WORKER_CONCURRENCY` | `5` | Celery worker 并发数 |
| `BACKUP_DIR` | `/backups` | 数据库备份路径 |

---

## 2. 备份策略

### PostgreSQL

```bash
# 每日自动备份（cron）
docker exec ruige-postgres pg_dump -U ruige ruige > /backups/ruige-$(date +%Y%m%d).sql

# 保留 30 天
find /backups -name 'ruige-*.sql' -mtime +30 -delete
```

### Uploads 文件

```bash
# 增量备份上传目录
rsync -avz /var/lib/docker/volumes/rag-knowledge-platform_uploads_data/_data/ /backups/uploads/
```

---

## 3. 一键部署命令

```bash
# 生产启动（含监控栈）
docker compose -f docker-compose.yml -f docker-compose.monitoring.yml up -d --build

# 验证
curl http://localhost:8000/health          # {"status":"ok","database":"ok"}
curl http://localhost:8000/health/detailed  # API Keys + 磁盘状态
curl http://localhost:3001/api/health       # Grafana
curl http://localhost:3100/ready            # Loki
```

---

## 4. 安全注意事项

| 项目 | 说明 |
|------|------|
| HTTPS | 当前为内网 HTTP，公网部署须加 Nginx 反代 + Let's Encrypt |
| API Key | 所有 API Key 仅服务端读取，前端永不接触 |
| CORS | 生产环境严格限制 `CORS_ORIGINS` |
| Rate Limit | 已有 API 限流（`test_api_rate_limit.py` 验证通过） |
| 审计日志 | 所有删除/写入操作都有审计记录 |

---

## 5. 健康检查端点

| 端点 | 用途 | 频率 |
|------|------|------|
| `GET /health` | 基础探活（DB + 降级状态） | 每 10s |
| `GET /health/detailed` | 详细检查（API Key + 磁盘） | 每 60s |
| Loki / Tempo / Grafana | 日志 + 链路 + 面板 | — |
