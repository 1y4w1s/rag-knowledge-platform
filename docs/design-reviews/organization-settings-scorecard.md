# 团队设置 OrganizationSettings · 评分卡（v2）

> 预览文件：`organization-settings-warm-white-preview.html`
> 真实来源：`frontend/src/pages/OrganizationSettingsPage.tsx` + `components/settings/SettingsFormCard.tsx` + `lib/organization-api.ts`
> 门禁（v2）：六维均 ≥ 9.0，加权 ≥ 9.2，跨页一致性地板达标。

## 1. 六维评分

| 维度 | 权重 | 得分 | 说明 |
|---|---|---|---|
| 一致性 Consistency | 20% | **9.3** | 全站统一 AppShell；侧栏导航顺序与真实 `AppSidebar` 一致（组织与部门 → 成员管理 → 团队设置 → 操作审计）；caret/图标全 SVG；琥珀仅用于真实「整理中」状态。 |
| 可用性 Usability | 20% | **9.3** | 名称可编辑、创建时间/成员数只读且视觉可区分；保存按钮在未改动时禁用、改动后启用；保存成功有确认提示；加载/错误态均可达。 |
| 功能保全 Function | 20% | **10** | 三态（loaded / loading 骨架 / error+重试）完整还原；保存交互（改动检测 → 保存中 → 成功提示）与源码逻辑一致；零增零减。 |
| 无障碍 A11y | 15% | **9.0** | 输入框均有 `<label for>`；按钮显式 `type`；状态切换为评审用 `aria-hidden` 控件；骨架/提示语义清晰。 |
| 视觉 Visual | 15% | **9.2** | 复用账号设置页 `settings-card` / `settings-field-input.readonly` 等令牌，warm-white / 赤陶视觉语言统一；成功提示用 success 绿（确认语义，非状态挪用）。 |
| 性能 Perf | 10% | **9.2** | 纯静态 + 轻量 JS；骨架用 CSS 动画并带 `prefers-reduced-motion` 守卫；无重资源。 |

**加权总分** = 9.3×.2 + 9.3×.2 + 10×.2 + 9.0×.15 + 9.2×.15 + 9.2×.1
= 1.86 + 1.86 + 2.00 + 1.35 + 1.38 + 0.92 = **9.37**

**门禁**：六维均 ≥ 9.0 ✅，加权 ≥ 9.2 ✅ → **通过**。

## 2. 还原要点（对照源码）

| 源码结构 | 预览还原 |
|---|---|
| `SettingsFormCard` 团队信息卡 | `.settings-card` > h3「团队信息」+ 表单 |
| `SettingsReadonlyField` 创建时间 / 成员数 | `.settings-field-input.readonly` 输入框（值 `2024-03-12 14:22` / `4`） |
| 名称 `input` 可编辑 + `maxLength=255` | `.settings-field-input`（`value="知岸演示团队"`） |
| 保存按钮 `disabled={!nameChanged}` | JS 监听 `input`，未改动禁用、改动启用 |
| 保存成功 `保存中…` → `团队名称已更新` | 提交后按钮置「保存中…」，延迟后显示 `.save-ok` |
| `loading` 骨架 / `error` + 重试 | 评审状态切换（loaded / loading / error）三视图 |
| 解散团队 MVP 不做 | `card-note` 提示行 |

## 3. 跨页一致性

- 全站 12 个预览侧栏导航项现已一致包含「团队设置」（admin 视图下）。
- 侧栏统一 `height:100vh;position:sticky;top:0;overflow:hidden` + `.nav{overflow-y:auto}`，长度固定、内部滚动，长内容仍可正常滚动。
