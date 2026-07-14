# 仪表盘 Dashboard · 评分卡（重建 · v2）

> **重建背景**：原 `dashboard-warm-white-preview.html` 是「闭环前旧原型」——自造了 `hero + emoji(👋) + 独立 .app shell`，既未对齐真实 `DashboardPage` 渲染树，也违反 v2 跨页地板（emoji、非统一 shell、无 `ws-caret`）。本次在统一 AppShell 上**忠实重建**，已取代旧原型并进入达标列表。

## 六维评分（v2 门禁：六维均 ≥ 9.0；加权 ≥ 9.2）

| 维度 | 分 | 依据 |
|---|---|---|
| 一致性 | 9.4 | 统一 `.shell/.sidebar/.topbar/.content`；`ws-caret` 为线性 SVG；状态 token 与已达标页同构；侧栏导航与全站一致 |
| 可用性 | 9.3 | 文档搜索实时过滤 + 文件名/正文模式切换；提问框提交跳 Ask 页；卡片可点击跳转；空态正确禁用提问框；四态切换清晰 |
| 功能保全 | 9.4 | 忠实覆盖 `DashboardPage`：`DashboardDocumentSearch`(常驻) → `DashboardZoneA` → `DashboardStatusBanner`(整理中) → `DashboardStatsGrid`(4 卡) → `DashboardOpsMetrics`+`DashboardRagMetrics`；空/加载/错误分支齐全 |
| 无障碍 | 9.0 | `tablist`/`aria-selected`、按钮 `aria-label`、`section` 地标、`prefers-reduced-motion` 守卫；搜索结果过滤未做 `aria-live` 播报（轻微） |
| 视觉 | 9.2 | 暖白/赤陶统一；amber 仅用于真实「整理中」状态；无 emoji；骨架屏平滑 |
| 性能 | 9.3 | 纯静态 SVG/CSS；JS 仅做 DOM 过滤与态切换，轻量无长列表瓶颈 |

**加权** = 9.4×.2 + 9.3×.2 + 9.4×.2 + 9.0×.15 + 9.2×.15 + 9.3×.1
= 1.88 + 1.86 + 1.88 + 1.35 + 1.38 + 0.93 = **9.28** → 门禁 v2 ✅

## 已知缺口（非本页缺陷）
- 侧栏导航未含「团队设置 OrganizationSettings」——该真实路由页**尚无预览**，属全站一致缺口（见 `iteration-loop.md` §12）。
- 文档搜索结果过滤未加 `aria-live` 播报（后续可补，不影响达标）。
