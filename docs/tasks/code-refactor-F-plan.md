# code-refactor-F · Plan — 测试巨型文件按场景拆分

> **父 SPEC**：`docs/tasks/code-refactor-spec.md` §2 任务 F  
> **风险**：中（不影响生产代码，但 fixture 引用链复杂 · 影响 7 个外部文件 import）  
> **预计改动**：3 个原始文件删除 · 10+ 个新文件创建 · 7 个外部文件 import 更新  
> **基线**：pytest 全局环境 · npm run build 先行已确认

---

## §0 做什么 / 不做什么

### 做

| # | 子任务 | 原始文件 | 拆分策略 |
|---|--------|----------|----------|
| F1 | `test_org_isolation.py` 拆分 | 1141 行 / 29 tests | 提取共享 fixture → `tests/fixtures/org_isolation.py`；按 7 个场景拆为独立文件 |
| F2 | `test_organization_members.py` 拆分 | 847 行 / 27 tests | 提取共享 helper → `tests/fixtures/org_members.py`；按 4 个场景拆为独立文件 |
| F3 | `test_audit_events.py` 拆分 | 700 行 / 15 tests | 提取共享 helper → `tests/fixtures/audit_events.py`；按 4 个场景拆为独立文件 |

### 不做

- 不改任何测试逻辑、断言值、API 调用
- 不改 conftest.py 除了删除 `pytest_plugins` 行
- 不改数据库模型 / schema
- 不改前端代码
- 不改 `test_org_grants.py` / `test_ask_chat.py` 等文件的测试逻辑（只改 import 路径）

---

## §1 改动清单

### F1 — `test_org_isolation.py` 拆分

| 文件 | 操作 | 内容 |
|------|------|------|
| `tests/fixtures/__init__.py` | **create** | 空文件，使 `fixtures/` 成为 Python package |
| `tests/fixtures/org_isolation.py` | **create** | 共享 fixture：`OrgIsolationFixture` 类 · `_login_user` · `_build_org_isolation_fixture` · `org_iso` pytest fixture · `_seed_kb_documents` · `_seed_kb_document_with_chunk` · `_seed_kb_document_with_ids` |
| `tests/test_org_scope.py` | **create** | `test_scope_*`（11 个）：`test_scope_rd_member_sees_subtree_and_public` ~ `test_scope_writable_company_admin_all` |
| `tests/test_org_kb_access.py` | **create** | `test_require_kb_access_*`（3 个）：`test_require_kb_access_sibling_department_403` ~ `test_require_kb_access_company_admin_any_dept_kb` |
| `tests/test_org_kb_list_api.py` | **create** | `test_api_list_*` / `test_api_get_*` / `test_api_unassigned_*` / `test_api_e*` / `test_api_admin_*`（7 个） |
| `tests/test_org_stats.py` | **create** | `test_api_stats_*`（3 个）+ `_seed_kb_documents` helper |
| `tests/test_org_search.py` | **create** | `test_api_search_*`（2 个）+ `_seed_kb_document_with_chunk` helper |
| `tests/test_org_chat.py` | **create** | `test_api_chat_*` / `test_chat_retrieval_*`（2 个）+ `_seed_kb_document_with_ids` helper |
| `tests/test_org_citation.py` | **create** | `test_citation_resolve_*` / `test_get_messages_*`（3 个） |
| `tests/test_org_isolation.py` | **delete** | 原始文件删除 |
| `tests/conftest.py` | **modify** | 删除第 9 行 `pytest_plugins = ("tests.test_org_isolation",)` |
| `tests/test_ask_chat.py` | **modify** | 改 import：`from tests.test_org_isolation import OrgIsolationFixture, _login_user` → `from tests.fixtures.org_isolation import OrgIsolationFixture, _login_user` |
| `tests/test_org_grants.py` | **modify** | 同上改 import 路径 |

### F2 — `test_organization_members.py` 拆分

| 文件 | 操作 | 内容 |
|------|------|------|
| `tests/fixtures/org_members.py` | **create** | 共享 helper：`_create_org_member_and_login` · `_register_personal_user` · `_promote_member_to_admin_in_db` |
| `tests/test_org_member_basic.py` | **create** | 基础成员操作（5 个 test）：`test_org_member_can_list_members_readonly` ~ `test_ac5_admin_adds_member_by_email_member_can_access_kb` |
| `tests/test_org_member_access.py` | **create** | 成员权限控制（2 个 test）：`test_ac6_member_cannot_delete_kb_after_being_added` · `test_ac9_admin_removes_member_member_loses_kb_access` |
| `tests/test_org_member_permissions.py` | **create** | 权限边界（7 个 test）：`test_personal_user_cannot_access_members_api` ~ `test_org_settings_includes_member_count` |
| `tests/test_org_member_roles.py` | **create** | 角色管理（13 个 test）：`test_owner_promotes_member_to_admin` ~ `test_owner_cannot_transfer_to_non_member` |
| `tests/test_organization_members.py` | **delete** | 原始文件删除 |

### F3 — `test_audit_events.py` 拆分

| 文件 | 操作 | 内容 |
|------|------|------|
| `tests/fixtures/audit_events.py` | **create** | 共享 helper：`_count_audit_logs` · `_latest_audit_log` · `_register_org_admin` · `_create_org_roster_member` |
| `tests/test_audit_auth.py` | **create** | 认证审计（2 个 test）：`test_login_failed_writes_audit_log` · `test_login_success_writes_audit_log` |
| `tests/test_audit_kb_document.py` | **create** | 知识库/文档审计（4 个 test）：`test_delete_kb_writes_audit_log` ~ `test_delete_document_writes_audit_log` |
| `tests/test_audit_members.py` | **create** | 成员审计（3 个 test）：`test_add_member_writes_audit_log` · `test_remove_member_writes_audit_log` · `test_role_change_writes_audit_log` |
| `tests/test_audit_org_units.py` | **create** | 组织单元审计（6 个 test）：`test_create_org_unit_writes_audit_log` ~ `test_update_unit_member_writes_audit_log` |
| `tests/test_audit_events.py` | **delete** | 原始文件删除 |
| `tests/test_chat_audit_events.py` | **modify** | 改 import：`from tests.test_audit_events` → `from tests.fixtures.audit_events` |
| `tests/test_storage_cleaner.py` | **modify** | 同上改 import 路径 |

---

## §2 变更步骤（按序执行）

### 阶段一：共享 fixture 提取

1. **创建 `tests/fixtures/__init__.py`** — 空文件
2. **创建 `tests/fixtures/org_isolation.py`** — 从 `test_org_isolation.py` 提取：
   - `OrgIsolationFixture` dataclass
   - `_login_user` async helper
   - `_build_org_isolation_fixture` async builder
   - `org_iso` pytest fixture（`@pytest.fixture` 装饰器保留）
   - `_seed_kb_documents` / `_seed_kb_document_with_chunk` / `_seed_kb_document_with_ids`
3. **创建 `tests/fixtures/org_members.py`** — 从 `test_organization_members.py` 提取：
   - `_create_org_member_and_login`
   - `_register_personal_user`
   - `_promote_member_to_admin_in_db`
4. **创建 `tests/fixtures/audit_events.py`** — 从 `test_audit_events.py` 提取：
   - `_count_audit_logs`
   - `_latest_audit_log`
   - `_register_org_admin`
   - `_create_org_roster_member`

### 阶段二：按场景拆分 F1（test_org_isolation.py）

5. **创建 `tests/test_org_scope.py`** — 11 个 `test_scope_*` 函数
6. **创建 `tests/test_org_kb_access.py`** — 3 个 `test_require_kb_access_*` 函数
7. **创建 `tests/test_org_kb_list_api.py`** — 7 个 KB list/get API 测试
8. **创建 `tests/test_org_stats.py`** — 3 个 stats 测试 + `_seed_kb_documents` 副本
9. **创建 `tests/test_org_search.py`** — 2 个 search 测试 + `_seed_kb_document_with_chunk` 副本
10. **创建 `tests/test_org_chat.py`** — 2 个 chat/retrieval 测试 + `_seed_kb_document_with_ids` 副本
11. **创建 `tests/test_org_citation.py`** — 3 个 citation/messages 测试

### 阶段三：按场景拆分 F2（test_organization_members.py）

12. **创建 `tests/test_org_member_basic.py`** — 5 个基础操作测试
13. **创建 `tests/test_org_member_access.py`** — 2 个权限控制测试
14. **创建 `tests/test_org_member_permissions.py`** — 7 个权限边界测试
15. **创建 `tests/test_org_member_roles.py`** — 13 个角色管理测试

### 阶段四：按场景拆分 F3（test_audit_events.py）

16. **创建 `tests/test_audit_auth.py`** — 2 个认证审计测试
17. **创建 `tests/test_audit_kb_document.py`** — 4 个 KB/文档审计测试
18. **创建 `tests/test_audit_members.py`** — 3 个成员审计测试
19. **创建 `tests/test_audit_org_units.py`** — 6 个组织单元审计测试

### 阶段五：更新外部 import + 删除原始文件

20. **修改 `tests/conftest.py`** — 删除 `pytest_plugins = ("tests.test_org_isolation",)` 行
21. **修改 `tests/test_ask_chat.py`** — import 路径迁移到 `tests.fixtures.org_isolation`
22. **修改 `tests/test_org_grants.py`** — import 路径迁移到 `tests.fixtures.org_isolation`
23. **修改 `tests/test_chat_audit_events.py`** — import 路径迁移到 `tests.fixtures.audit_events`
24. **修改 `tests/test_storage_cleaner.py`** — import 路径迁移到 `tests.fixtures.audit_events`
25. **删除 `tests/test_org_isolation.py`**
26. **删除 `tests/test_organization_members.py`**
27. **删除 `tests/test_audit_events.py`**

### 阶段六：验证

28. **运行完整 pytest 验证测试数量一致**

---

## §3 边界 & 异常

### 共享 fixture 提取注意事项

| 问题 | 处理方式 |
|------|----------|
| `org_iso` fixture 通过 `pytest_plugins` 全局暴露 | 改为 `tests/fixtures/org_isolation.py` 的 `@pytest.fixture`，**不再需要** `pytest_plugins`；各新测试文件用 `pytestmark = pytest.mark.asyncio` 简化 |
| `_seed_kb_documents` / `_seed_kb_document_with_chunk` / `_seed_kb_document_with_ids` 只有单一场景使用 | 提取到 fixture 文件统一管理，各场景文件 import 使用 |
| `test_org_stats.py` 中 `_seed_kb_documents` 被共用 | 从 `fixtures/org_isolation.py` import，不重复定义 |
| agent 测试文件（`test_agent_audit.py` / `test_agent_g4_*.py`）使用 `org_iso` fixture | 它们通过 `pytest_plugins` 自动获取；删除 `pytest_plugins` 后，`org_iso` 从 `tests/fixtures/org_isolation.py` 自动被 pytest conftest 机制发现（`fixtures/` 是 `tests/` 的子包，**只要 `conftest.py` 或任何 test 文件 import 了该模块，fixture 就全局可见**） |
| `_count_audit_logs` / `_latest_audit_log` 被外部文件 import | 改为 `from tests.fixtures.audit_events import ...`，签名不变 |
| 测试数量必须与原文件一致 | 最终运行 `pytest tests/ -q` 对比已知基线；若无法运行则手动校验每个新文件的 test 函数数量 |

### 每个新文件的通用结构

```python
"""简短描述（引用自原文件顶部 docstring 的场景部分）。"""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import ...  # 仅本文件需要的 import
from app.models... import ...
from tests.conftest import unique_email, unique_username, create_test_kb, ...
from tests.fixtures.org_isolation import OrgIsolationFixture, _login_user

pytestmark = pytest.mark.asyncio


async def test_xxx(org_iso: OrgIsolationFixture) -> None:
    ...
```

---

## §4 验收门禁（本窗专用）

```
┌─────────────────────────────────────────────────────┐
│            ┏━━━┓  验收强门禁 — code-refactor-F      │
│            ┃   ┃                                    │
│            ┗━━━┛                                    │
│                                                     │
│  📍 对话标记：{日期} · 任务 F · I 窗                │
│                                                     │
│  ▢ 仅改 SPEC 约定的文件（3 删 + N 新 + 5 改 import）│
│  ▢ 每个新文件 ≤400 行                               │
│  ▢ pytest tests/ -q 与原文件通过总数一致            │
│  ▢ 不改业务行为（比较拆分前后同一 test 的断言逻辑） │
│  ▢ 不改 DB schema / migration                       │
│  ▢ 不改 AGENTS.md / PRD / TECH                      │
│  ▢ 不改公共 API 签名                                │
│  ▢ conftest.py 第 9 行 pytest_plugins 已删除        │
│  ▢ 所有外部 import 已更新到 fixtures/ 路径           │
│  ▢ 所有 helper 函数保持原名和签名不变                │
│                                                     │
│  回退方案：git checkout -- tests/ conftest.py       │
│  （如无可回退，手动恢复 3 个原始文件即可）           │
│                                                     │
│  ── 验收人签名：___________  日期：___________  ──  │
└─────────────────────────────────────────────────────┘
```

---

## §5 回退指令

由于当前不是 git 仓库，**回退方式为手动恢复**：

1. 删除所有新创建的 `test_org_*.py` / `test_audit_*.py` / `test_org_member_*.py` 文件
2. 删除 `tests/fixtures/__init__.py` 和 3 个 fixture 文件
3. 从备份恢复 `conftest.py`（undo 第 9 行删除）
4. 恢复 `test_org_isolation.py` / `test_organization_members.py` / `test_audit_events.py`
5. 恢复 `test_ask_chat.py` / `test_org_grants.py` / `test_chat_audit_events.py` / `test_storage_cleaner.py` 的 import
