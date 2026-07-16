# 睿阁 · 设计基线清理报告 & 12 页实施路线图

> **清理时间**：2026-07-15
> **指令来源**：用户确认「仅以 DESIGN.md 为准，清理旧文档，预览 HTML 删掉重做，以 Dashboard 为设计参考」

---

## 一、清理摘要

### 删除的内容

| 类别 | 数量 | 具体文件 |
|------|------|----------|
| 预览 HTML（warm-white 12 页） | 12 个 | `account-settings-` ~ `organization-settings-warm-white-preview.html` |
| 其他预览 HTML | 5 个 | `auth-warm-orange`, `previews-gallery`, `a11y-floor-demo`, `preview-shell-v2.css` |
| docs/ 根目录预览 | 5 个 | `dashboard-bold-preview.html`, `dashboard-dark-preview.html`, `design-compare.html`, `redesign-preview.html`, `shell-preview.html` |
| 旧 UI review | 2 个 | `UI-UX-review-dashboard-bold.md`, `*-independent.md` |
| 评分卡 | 12+ 个 | `*-scorecard.md`（每页一个 + 多维 v3.5~v8） |
| 评估报告 | 10+ 个 | `*-evaluation-report.md`, `dashboard_evaluation_report.md`, `chat_page_evaluation_report.md` |
| 标准/审计文档 | 8 个 | `scoring-standard-v2.md`, `v3.md`, `strict-review-v2.md`, `deviation-correction.md`, `rework-audit.md`, `render-review.md`, `performance-optimization-report.md` |
| 其他 | 5 个 | `chat_quality_metrics.json`, `golden_agent_qa.json`, `keyboard_test.json`, `empty-state-eval-*` |
| 截图的目录 | 5 个 | `_render/`, `_screenshots/`, `screenshots/`, `design-concepts/`, `lighthouse*/`, `shots/` |
| **合计** | **~60+ 文件** | |

### 保留的文件（更新后）

| 文件 | 状态 | 用途 |
|------|------|------|
| `docs/DESIGN.md` | ✅ 保持原样 | **唯一设计权威** |
| `docs/design-reviews/design-system.md` | ✅ 重写 | 简短补充（角色色/圆角梯度/投影/反模式/验收标准） |
| `docs/design-reviews/iteration-loop.md` | ✅ 重写 | 评分框架 + 清空的进度矩阵 |
| `docs/design-reviews/app-shell-audit.md` | ✅ 保持原样 | Shell 8 项审计问题（代码修复 TODO） |
| `frontend/src/index.css` | ✅ 更新 | `--r: 16px`；新增 `--role/--role-bg/--role-ink`（亮+暗） |
| `AGENTS.md` | ✅ 更新 | 移除「preview token」「design-preview.html」引用 |

---

## 二、现存设计资产清单

| 资产 | 说明 |
|------|------|
| `docs/DESIGN.md` v1.0 | 73 行核心规范：颜色/字体/圆角/阴影/过渡/页面布局/数据展示/交互/硬约束/排版红线 |
| `docs/design-reviews/design-system.md` | ~36 行补充：角色色、圆角梯度、投影系统、反模式、验收清单 |
| `docs/design-reviews/app-shell-audit.md` | Shell 审计 8 项问题（S1-S8），需逐条修 |
| `docs/design-reviews/iteration-loop.md` | 评分框架（6 维），空白进度矩阵 |
| `frontend/src/index.css` | 80+ CSS 自定义属性（light + dark），双主题，完整组件样式 |
| `frontend/src/components/` | 100+ React 组件（已落地 Dashboard 为视觉基线） |
| `docs/brand/ruige-mark.svg` | 品牌 SVG 标识 |
| `docs/brand/ruige-favicon.svg` | Favicon |
| `docs/logo-ruige.html` | 最终品牌 LOGO 展示 |

---

## 三、12 页实施路线图

> 按建议优先级排列。每页完成一个独立对话，对话结束后在 `iteration-loop.md` 更新矩阵。

| 优先级 | 页面 | 估计工作量 | 前置条件 |
|--------|------|-----------|----------|
| P0 ✅ | **仪表盘 Dashboard** | 已落地 | — 参考基线页 |
| P1 | **知识库列表 Knowledge Bases** | 中 | — |
| P2 | **知识库详情 KB Detail** | 中 | — |
| P3 | **对话 Chat** | 大（含输入/气泡/引用/流式） | — |
| P4 | **Ask 问答** | 中 | — |
| P5 | **登录 Login** | 小 | — |
| P6 | **账号设置 Account Settings** | 小 | — |
| P7 | **成员管理 Members** | 中 | — |
| P8 | **组织与部门 Departments** | 中 | — |
| P9 | **操作审计 Audit Log** | 中 | — |
| P10 | **文档预览 Document Preview** | 中 | — |
| P11 | **团队设置 Org Settings** | 小 | — |

**每页验收标准**（见 `iteration-loop.md` §4 & `design-system.md` §5）：
- 6 维评分全部 ≥ 8.0
- 视觉与 Dashboard 基线页一致
- 双主题全覆盖、所有颜色走 token

---

## 四、何时可以开始第一页

随时。你决定从哪一页开始，我就打开一个新对话，只做那一页的代码重做。
