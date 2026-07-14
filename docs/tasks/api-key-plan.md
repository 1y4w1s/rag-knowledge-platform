# API Key 管理 Plan

> **状态**：📋 计划稿  
> **工期**：~3 天  
> **背景**：知岸当前仅支持 JWT 登录认证，外部脚本/系统无法直接调用 API。新增 API Key 机制，支持签发/吊销/scope 限定。

---

## §0 · 做 & 不做

### 做

| # | 项 | 说明 |
|---|-----|------|
| ① | **ApiKey 数据模型** | 新表 `api_keys`：id, user_id, key_hash, prefix, name, scopes, is_active, expires_at, created_at, last_used_at |
| ② | **migration 027** | 建表 |
| ③ | **API Key 认证分支** | 在 `security.py` 中间件中：JWT 解码失败 → fallback 到 API Key 认证（查 ApiKey 表按 key_hash） |
| ④ | **服务层 `api_key_auth.py`** | 生成/哈希/认证 API Key 的工具函数 |
| ⑤ | **CRUD API 端点** | `POST /api/v1/api-keys`（创建）、`GET /api/v1/api-keys`（列表）、`DELETE /api/v1/api-keys/{id}`（撤销） |
| ⑥ | **前端管理页** | 在账号设置页加 API Key 管理面板：列表/创建（显示一次）/撤销 |

### 不做

- ❌ 不改 JWT 签发逻辑
- ❌ 不改现有认证流程
- ❌ 不改限流/审计/org context
- ❌ 不改 API Key scope 的精细化控制（首版 scope 用逗号分隔字符串，后续可升级为 JSON）

---

## §1 · 改动清单

| 文件 | 操作 | 行数 |
|------|------|------|
| `backend/app/models/api_key.py` | **create** | ~40 |
| `backend/alembic/versions/027_api_keys.py` | **create** | ~30 |
| `backend/app/services/auth/api_key_auth.py` | **create** | ~60 |
| `backend/app/core/security.py` | modify | ~+15 |
| `backend/app/core/deps.py` | modify | ~+5 |
| `backend/app/api/auth.py`（或新路由） | modify | ~+40 |
| `frontend/src/pages/AccountSettingsPage.tsx` | modify | ~+200 |
| 新增前端组件若干 | **create** | ~150 |

---

## §2 · 具体方案

### 2.1 数据模型

```python
# models/api_key.py
class ApiKey(Base):
    __tablename__ = "api_keys"
    
    id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, default=uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID, ForeignKey("users.id"), index=True)
    key_hash: Mapped[str] = mapped_column(String(64))       # SHA-256 hex
    prefix: Mapped[str] = mapped_column(String(8))           # 前 8 位明文, 用于展示
    name: Mapped[str] = mapped_column(String(128))           # 备注名
    scopes: Mapped[str] = mapped_column(String(256), default="")  # 逗号分隔权限
    is_active: Mapped[bool] = mapped_column(default=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
```

### 2.2 API Key 格式

```
zkan_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx   # "zkan_" 前缀 + 32 位随机 hex
```

### 2.3 中间件改造

在 `security.py` 的 `JWTAuthMiddleware.dispatch` 中，现有 JWT 解码失败返回 401 之前，插入 API Key fallback：

```python
# 尝试 JWT 解码
try:
    claims = decode_access_token(token_str)
except AuthenticationError:
    # JWT 失败 → fallback API Key
    claims = await authenticate_api_key(db_session, token_str)
    if claims is None:
        return JSONResponse(status_code=401, content={"detail": "未登录或 API Key 无效"})
```

需要在中间件中获取 DB session。现有中间件已经有 `request.state.db`（在 `DBSessionMiddleware` 中设置）。

### 2.4 API 端点

```
POST   /api/v1/api-keys          → 创建 Key（返回 raw_key 仅此一次）
GET    /api/v1/api-keys          → 列出我的 Key（无 raw_key）
DELETE /api/v1/api-keys/{id}     → 撤销 Key
```

### 2.5 Scope 设计（首版简化）

首版 scope 用逗号分隔字符串，可选值：
- `chat` — 允许对话
- `knowledge_bases:read` — 允许列资料库
- `documents:read` — 允许读文档

空 scope 表示无限制（等同于登录用户的全部权限）。

---

## §3 · 边界 & 异常

| 场景 | 处理 |
|------|------|
| API Key 过期 | `is_active=false` 或 `expires_at < now` → 401 |
| API Key 被撤销 | `is_active=false` → 401 |
| 创建 Key 时用户不存在 | 走已有 auth 流程，不可能出现 |
| JWT 和 API Key 同时传 | JWT 优先（现有逻辑不变） |
| 非 Bearer token | 维持现有 401 行为 |

---

## §4 · 验收门禁

```
┌─────────────────────────────────────────────────────┐
│            ┏━━━┓  验收强门禁 — API Key 管理          │
│            ┃   ┃                                    │
│            ┗━━━┛                                    │
│                                                     │
│  ▢ 模型 + migration 创建成功                         │
│  ▢ POST /api-keys 返回 raw_key                      │
│  ▢ 用 raw_key 调 API 成功（免登录）                  │
│  ▢ 撤销后调 API 返回 401                            │
│  ▢ 前端账号设置页可管理 Key                          │
│  ▢ 不改 JWT/现有认证/限流/审计                       │
│  ▢ npm run build 绿                                  │
│                                                     │
│  ── 验收人签名：___________  日期：___________  ──  │
└─────────────────────────────────────────────────────┘
```

---

## §5 · 回退指令

```powershell
git checkout -- backend/app/models/api_key.py backend/app/core/security.py
git checkout -- backend/app/core/deps.py backend/app/services/auth/api_key_auth.py
Remove-Item backend/alembic/versions/027_api_keys.py
git checkout -- backend/app/api/auth.py
# 前端改动按需回退
```
