# Handoff：解散团队（Dissolve Organization）

## 任务

实现完整「解散团队」功能：Owner 确认后清空团队所有数据，删除组织记录，跳回个人空间。

---

## 后端

### API

```
POST /api/v1/organization/dissolve
```

- **权限**：仅 Owner（`user.is_owner === true`）
- **请求体**：`{ confirm_name: string }`（需匹配 `org.name`，防误触）
- **响应**：`204 No Content`
- **审计**：记录 `action="org.dissolve"`，`resource_type="organization"`

### Service 层级联顺序（`services/organization/dissolve.py`）

1. 验证当前用户是该组织 Owner + `confirm_name` 匹配组织名称
2. 查该组织下所有 `knowledge_bases`（`kb.org_id == org_id`）
3. 对每个 KB：执行 `remove_kb_tree(kb_id)`（复用 `services/storage/cleaner.py` 已有逻辑——删文档、切片、存储文件）
4. 删所有 `organization_members` 行
5. 删 `org_units` 表相关行
6. 删 `organizations` 行
7. 提交审计：`audit_logs` 插入一条 `org.dissolve` 事件
8. `commit()`，若中途失败全回滚

**参考文件**：
- `backend/app/services/storage/cleaner.py`（`remove_kb_tree` 复用）
- `backend/app/services/auth/service.py`（现有 org 相关 service）
- `backend/app/api/organization.py`（现有组织路由，参考其路由模式）
- `backend/app/models/organization.py`（`Organization` 表模型）

### 审计事件

```python
await audit_service.log(
    db=db,
    action="org.dissolve",
    actor_user_id=user.id,
    resource_type="organization",
    resource_id=org_id,
    details={"org_name": org.name, "kb_count": len(kb_ids)},
)
```

---

## 前端

### 后端对接（`frontend/src/lib/organization-api.ts`）

新增 `dissolveOrganization(confirmName: string): Promise<void>`

```typescript
export async function dissolveOrganization(confirmName: string): Promise<void> {
  const res = await apiFetch("/api/v1/organization/dissolve", {
    method: "POST",
    body: { confirm_name: confirmName },
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || "解散失败");
  }
}
```

### UI：`OrganizationSettingsPage.tsx`

在底部（`SettingsFormCard` 之后）添加「危险操作」区域：

```
<SettingsFormCard title="危险操作">
  <p className="text-sm text-muted">解散团队将永久删除所有资料库、文档和成员记录，不可恢复。</p>
  <Button variant="danger" onClick={openDialog}>解散团队</Button>
</SettingsFormCard>
```

参考 `MemberWriteBlockedButton` 的弹窗和确认模式。需要一个 `<DissolveOrgDialog>` 组件（复用 `DeleteKnowledgeBaseDialog` 的模式）：

1. 弹窗显示警告文案
2. 输入框让 Owner 输入团队全名（`{orgName}`）
3. 输入匹配后才激活「确认解散」按钮（红色）
4. 提交中按钮显示「解散中…」，完成后：

```typescript
// 成功后
setStoredWorkspace("personal");
setWorkspace("personal");
navigate("/dashboard");
showToast("团队已解散");
```

### 前端参考文件

- `frontend/src/pages/OrganizationSettingsPage.tsx` — 入口页
- `frontend/src/components/knowledge-bases/DeleteKnowledgeBaseDialog.tsx` — 确认弹窗模式
- `frontend/src/components/organization/TransferOwnershipDialog.tsx` — 组织级确认弹窗
- `frontend/src/lib/organization-api.ts` — API 封装
- `frontend/src/lib/workspace-storage.ts` — `setStoredWorkspace`
- `frontend/src/lib/workspace-context.tsx` — `setWorkspace`
- `frontend/src/components/ui/Toast.tsx` — Toast 提示
- `frontend/src/components/ui/Button.tsx` — Button variant 系统

---

## 边界情况

| 情况 | 处理 |
|------|------|
| 非 Owner 调用 API | 403 |
| `confirm_name` 不匹配 | 422 `"组织名称不匹配"` |
| 组织已不存在 | 404 |
| 中途失败（DB / 存储） | 全回滚，返回 500 |
| Owner 调用但团队已有 pending ingestion | 等待 ingestion 完成后再解散？先不做，直接强制解散 |
| 并发解散 | DB 行锁或乐观锁，第二个人收到 409 |

---

## 不需做的

- ❌ 解散后恢复/回收站（硬删除）
- ❌ 解散通知邮件
- ❌ 解散前导出数据
- ❌ 支付/计费相关（见 AGENTS.md）

---

## 验收标准

1. Owner 在团队设置页底部看到「解散团队」按钮
2. 点击弹出确认弹窗，输入团队名后启用确认按钮
3. 确认后所有团队 KB 被清空（文件+切片+DB）
4. 所有成员被移除
5. 组织记录被删除
6. 页面跳转到个人空间概览页，显示 toast「团队已解散」
7. 侧栏工作区切换器只显示「个人」（无团队名）
8. 审计日志可查到 `org.dissolve` 事件
