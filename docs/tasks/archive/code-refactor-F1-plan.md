# code-refactor-F1 · Plan

> **父 SPEC**：`docs/tasks/code-refactor-spec.md` §2 任务 F-1  
> **风险**：低（纯 import 路径修复，不改业务逻辑）  
> **预计改动**：2 个测试文件 import 行修改 + 3 个文件注释更新，约 5 行增删  
> **基线**：当前 `pytest tests/ -k "org"` 报 4 errors（含 2 个断链和 1 个无关的 FileNotFoundError）

## §0 做什么 / 不做什么

### 做
- 修复 `test_retrieval_workspace.py:31` 和 `test_org_kb_create.py:11` 中断掉的 import：指向 `tests.fixtures.org_isolation`
- 更新 3 个 agent 测试文件中的注释（docstring 仍引用旧路径 `tests/test_org_isolation.py`）
- 验证 `pytest tests/ -q -k "org"` 收集 errors 归零

### 不做
- 不修改 `fixtures/org_isolation.py`（已正确提取完毕）
- 不修改 `conftest.py`（line 9 无 `pytest_plugins`，已符合要求）
- 不创建新文件 / 不重命名现有文件
- 不改任何业务逻辑

## §1 改动清单

| 文件 | 操作 | 内容 |
|------|------|------|
| `tests/test_retrieval_workspace.py:31` | modify | `from tests.test_org_isolation import OrgIsolationFixture` → `from tests.fixtures.org_isolation import OrgIsolationFixture` |
| `tests/test_org_kb_create.py:11` | modify | `from tests.test_org_isolation import OrgIsolationFixture, _login_user` → `from tests.fixtures.org_isolation import OrgIsolationFixture, _login_user` |
| `tests/test_agent_audit.py:16` | modify | 更新注释中的旧路径引用 |
| `tests/test_agent_g4_resolve_adopt.py:17` | modify | 同上 |
| `tests/test_agent_g4_resolve_cancel.py:18` | modify | 同上 |

## §2 变更步骤

1. 修复 `test_retrieval_workspace.py` 的 import（断链源头）
2. 修复 `test_org_kb_create.py` 的 import（断链源头）
3. 更新 3 个 agent 测试文件的注释（纯文档）
4. 运行 `pytest tests/ -q -k "org"` 确认 errors 归零

## §3 边界 & 异常

- `test_ask_chat.py`（行 29）已正确使用 `tests.fixtures.org_isolation`，修复后自动恢复
- `fixtures/org_isolation.py` 中 `_login_user` 函数名和签名与旧文件完全相同，无兼容问题
- `OrgIsolationFixture` 是纯 dataclass，无隐式依赖

## §4 验收门禁（本窗专用）

▢ 仅改 SPEC 约定的 5 个文件（2 import + 3 注释）
▢ `pytest tests/ -q -k "org"` 收集阶段 0 errors（原报 4 errors）
▢ 不改业务逻辑 / DB schema / API 签名
▢ 本节完成时删除子 plan 文件

## §5 回退指令

```bash
git checkout -- backend/tests/test_retrieval_workspace.py backend/tests/test_org_kb_create.py backend/tests/test_agent_audit.py backend/tests/test_agent_g4_resolve_adopt.py backend/tests/test_agent_g4_resolve_cancel.py
```
