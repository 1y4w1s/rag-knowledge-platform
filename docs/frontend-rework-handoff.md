# Handoff：睿阁前端重做 — 登录页已完成

## 当前进度

| 页面 | 状态 |
|------|------|
| 登录 Login | ✅ 完成 |
| 问答 Ask | ✅ 通过 |
| 资料库列表 Knowledge Bases | ✅ 通过 |
| 资料库详情 KB Detail | ✅ 通过 |
| 对话 Chat | ✅ 通过 |
| 账号设置 Account Settings | ✅ 通过 |
| 成员管理 Members | ✅ 修复后通过 |
| 组织与部门 Departments | ✅ 修复后通过 |
| 操作审计 Audit Log | ✅ 通过 |
| 文档预览 Document Preview | ✅ 通过 |
| 团队设置 Org Settings | ✅ 修复后通过 |

## 登录页改动清单

| 文件 | 改动 |
|------|------|
| `frontend/src/components/auth/AuthField.tsx` | Input `rounded-[10px]`→`[8px]`；硬编码红色→`--status-err-*`  token；`AuthFormAlert` 红色→token |
| `frontend/src/components/auth/AuthSegmentedTabs.tsx` | Tab 容器 `rounded-[10px]`→`[8px]` |
| `frontend/src/components/auth/LoginAuthForm.tsx` | 中文标题移除 `tracking-[0.02em]`（DESIGN.md §7） |
| `frontend/src/components/ui/button.tsx` | auth/brand/brandGrad 按钮 `rounded-[10px]`→`[8px]` |
| `frontend/src/index.css` | 全局 `focus-visible` 从未定义 `--brand` 修复为 `--action` |

## 设计基线（唯一权威）

- `docs/DESIGN.md`
- `docs/design-reviews/design-system.md`（补充：角色色、圆角梯度、投影、反模式）
- `docs/design-reviews/iteration-loop.md`（评分框架 + 进度矩阵）
- `docs/design-baseline-cleanup-report.md`（清理报告 + 路线图）

## 视觉能力

Reasonix 已配置 Qwen-VL-Plus（阿里云百炼）视觉分析能力：
- 脚本：`.reasonix/vision-server.py`
- 配置：`~/.reasonix-vision.env`（用项目 TONGYI_API_KEY）
- 技能：`/vision <图片路径>` 或直接发截图

## 下一页（知识库列表）需要做的事情

1. **读代码**：`frontend/src/pages/KnowledgeBasesPage.tsx` + 列表相关组件（`KnowledgeBaseCard`、`DocumentTable` 等）
2. **对照 DESIGN.md 改**：
   - 容器 `max-w-[1180px]` `px-7`
   - 卡片 `rounded-2xl`(16px)，控件 `rounded-[8px]`
   - 颜色全走 `var(--*)`，禁止硬编码
   - 双主题全覆盖
   - 角色/权限徽章用 `--role` 系
   - 中文无 `letter-spacing`
3. **构建验证**：`cd frontend && npm run build`
4. **截图验收**：开 dev server → playwright 截图 → `/vision` 分析

## 模型切换提醒

- ✅ **Flash 够用**：登录页、知识库列表、详情页、账号设置、成员管理、团队设置
- ⏳ **建议换 Pro**：Chat 对话框（流式渲染 + 引用 + 审批卡，状态管理复杂）
- ⏳ **建议换 Pro**：Dashboard 如果涉及数据流重写

**规则**：当要开始 Chat 页面时，主动提醒用户「这页建议切到 Pro 模型来写」。
