# code-refactor-E1 · Plan

> **父 SPEC**：`docs/tasks/code-refactor-spec.md` §2 · 任务 E  
> **阶段**：E-1（阶段一：异常类 + 映射器 + documents/ + auth/ 替换）  
> **风险**：**高**（涉及异常架构变更，但第一阶段仅影响 services/documents/ 和 services/auth/）  
> **基线**：Docker 3 services up · pytest A 层 65+ 全绿

---

## §0 · 做什么 / 不做什么

### 做

1. **新建** `backend/app/core/exceptions.py` — 领域异常层次
2. **新建** `backend/app/core/exception_handlers.py` — FastAPI exception handlers
3. **注册** handler 到 `app/main.py`
4. **替换** `services/documents/` 6 个文件中的 `raise HTTPException` → 领域异常
5. **替换** `services/auth/` 4 个文件中的 `raise HTTPException` → 领域异常

### 不做

- 不替换 `services/agent/`、`services/organization/`、`services/rag/` 的 raise（留阶段二/三）
- 不替换 `api/` 层的 `raise HTTPException`（保持不动）
- 不改业务行为（detail 字符串完全一致）
- 不改 DB schema / migration

---

## §1 · 领域异常层次

```
ServiceError(Exception)          # 抽象基类，status_code=500
├── NotFoundError                 # 404
├── ConflictError                 # 409
├── UnauthorizedError             # 401
├── ValidationError               # 400, 413, 422 → 统一映射为 422
└── RateLimitError                # 429
```

每个异常类：
- 接受 `detail: str` 位置参数
- 可选 `extra: dict | None` 参数（预留，当前阶段不用）
- 继承 `status_code: int` 类属性

---

## §2 · 异常 -> HTTP 映射表

| 原始 status_code | 领域异常 | 用途示例 |
|-----------------|---------|---------|
| 400 | `ValidationError` | 文件类型不支持、文件名空、空文件、内容哈希重复 |
| 401 | `UnauthorizedError` | 登录密码错误 |
| 404 | `NotFoundError` | 文档不存在 |
| 409 | `ConflictError` | 文档正在 processing、同名文件已存在、注册邮箱/用户名被占用 |
| 413 | `ValidationError` | 单文件超过大小限制 |
| 422 | `ValidationError` | 密码长度不足、用户名不合法 |
| 429 | `RateLimitError` | 对话/登录频率超限 |
| 500 | `ServiceError` | 企业账号数据不一致 |

---

## §3 · 改动清单

| 文件 | 操作 | 内容 |
|------|------|------|
| `backend/app/core/exceptions.py` | **新建** | ServiceError + 5 个子类 |
| `backend/app/core/exception_handlers.py` | **新建** | `@app.exception_handler` 各异常→HTTP 映射 |
| `backend/app/main.py` | **modify** | import + 注册 handler |
| `services/documents/content_hash.py` | **modify** | `HTTPException(409)` → `ConflictError` |
| `services/documents/filters.py` | **modify** | `HTTPException(400)` → `ValidationError` |
| `services/documents/lifecycle.py` | **modify** | 3 处替换 |
| `services/documents/listing.py` | **modify** | 1 处替换 |
| `services/documents/preview.py` | **modify** | 3 处替换 |
| `services/documents/upload.py` | **modify** | 9 处替换 |
| `services/auth/api_rate_limit.py` | **modify** | `HTTPException(429)` → `RateLimitError` |
| `services/auth/org_context.py` | **modify** | `HTTPException(500)` → `ServiceError` |
| `services/auth/service.py` | **modify** | 8 处替换 |
| `services/auth/username.py` | **modify** | 2 处替换 |

---

## §4 · 变更步骤

### Step 1: 新建 `exceptions.py`

```python
from __future__ import annotations


class ServiceError(Exception):
    """领域异常基类（所有 services/ 层的 HTTPException 替代品）。"""
    status_code: int = 500

    def __init__(self, detail: str, *, extra: dict | None = None) -> None:
        self.detail = detail
        self.extra = extra
        super().__init__(detail)


class NotFoundError(ServiceError):
    status_code = 404


class ConflictError(ServiceError):
    status_code = 409


class UnauthorizedError(ServiceError):
    status_code = 401


class ValidationError(ServiceError):
    status_code = 422


class RateLimitError(ServiceError):
    status_code = 429
```

### Step 2: 新建 `exception_handlers.py`

```python
from fastapi import Request
from fastapi.responses import JSONResponse

from app.core.exceptions import (
    ConflictError,
    NotFoundError,
    RateLimitError,
    ServiceError,
    UnauthorizedError,
    ValidationError,
)


async def service_error_handler(request: Request, exc: ServiceError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )


EXCEPTION_HANDLERS: list[tuple[type[Exception], type]] = [
    (NotFoundError, service_error_handler),
    (ConflictError, service_error_handler),
    (UnauthorizedError, service_error_handler),
    (ValidationError, service_error_handler),
    (RateLimitError, service_error_handler),
    (ServiceError, service_error_handler),
]
```

### Step 3: 注册到 main.py

在 `app = FastAPI(...)` 之后添加：

```python
from app.core.exception_handlers import EXCEPTION_HANDLERS

for exc_cls, handler in EXCEPTION_HANDLERS:
    app.add_exception_handler(exc_cls, handler)
```

### Step 4-5: 替换 documents/ + auth/ 共 10 个文件

每处替换模式：
```python
# 旧
from fastapi import HTTPException
raise HTTPException(status_code=404, detail="文档不存在")

# 新
from app.core.exceptions import NotFoundError
raise NotFoundError("文档不存在")
```

### Step 6: Docker rebuild + pytest 验证

```powershell
docker compose build api
docker compose up -d api
docker compose exec -w /app api python -m pytest tests/test_upload.py tests/test_upload_security.py tests/test_documents.py tests/test_auth.py -q --no-header --tb=no --asyncio-mode=auto
```

---

## §5 · 验收强门禁

| 门禁 | 标准 |
|------|------|
| pytest 文档/上传/认证 | `test_upload.py` + `test_upload_security.py` + `test_documents.py` + `test_auth.py` 全绿 |
| 无回归 | 全量测试 `pytest tests/ --ignore=tests/test_agent_golden.py` 无新增失败 |
| 100% 替换 | services/documents/ + services/auth/ 中无残留 `raise HTTPException` |
| api/ 层不受影响 | api/ 层的 `raise HTTPException` 保持不动 |

---

## §6 · 回退方案

```powershell
git checkout -- backend/app/core/exceptions.py backend/app/core/exception_handlers.py
git checkout -- backend/app/main.py
git checkout -- backend/app/services/documents/*.py backend/app/services/auth/*.py
docker compose build api && docker compose up -d api
```
