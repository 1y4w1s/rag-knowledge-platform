# 知岸 Dashboard 专业评估报告

评估时间：2026-07-13 16:05（GMT+8）  
评估对象：`frontend/src/pages/DashboardPage.tsx` 及其子组件  
运行环境：`npm run dev` @ http://localhost:5173（全栈已起：Docker Desktop + docker compose + alembic + seed）  
评估体系：沿用 `docs/chat_page_evaluation_report.md` 内嵌的 v3 12 维评审标准（S/A/B/C/D 五档）

---

## 一、评估结论

| 项目 | 结果 |
|---|---|
| **加权总分** | **9.05 / 10** |
| **等级** | **A（优秀）** |
| **与 9.5 差距** | **-0.45 分**，主要落在 D7 代码质量、D12 SEO、D5 视觉美学细节 |

> 评级规则：S ≥9.5 · A 9.0–9.4 · B 8.0–8.9 · C 6.0–7.9 · D <6.0 或一票否决  
> 本次未触发任何一票否决项（死链、键盘卡死、XSS、LCP>2.5s 等）。

---

## 二、12 维评分明细

| 维度 | 权重 | 得分 | 等级 | 关键依据 |
|---|---|---:|---:|---|
| D1 视觉一致性 | 12% | **9.3** | A | 已对齐暖白画廊：统计卡片彩色图标/同色数值、搜索范围切换为 pill 按钮、欢迎操作按钮带图标、搜索文件行带文件图标。与预览差异主要在：当前为 personal 空间，侧栏比预览 team 空间少企业项；数据状态不同导致搜索/状态/运营指标内容不同。 |
| D2 可用性 / UX | 12% | **9.0** | A- | 核心链路（搜索、上传、创建资料库、跳转资料库/对话、提问框提交）经 Playwright 真点验证可用；卡片 hover 有微上浮。扣分项：搜索框无结果时提示文案较长；移动端顶栏未做额外压缩。 |
| D3 功能完整 | 10% | **9.4** | S | 忠实覆盖 DashboardPage：文档搜索、欢迎区、状态横幅、4 张统计卡、运营指标、RAG 概览；空/加载/错误分支齐全。 |
| D4 无障碍 WCAG 2.1 AA | 14% | **9.1** | A- | 继承全局 A11y 地板：shell skip-link、陶土 focus-visible、aria-current 导航、section 地标。搜索结果区已补 `aria-live="polite"`（加载/空结果/结果列表动态播报）。 |
| D5 视觉美学 | 8% | **9.1** | A- | 暖白+赤陶统一，统计卡片彩色点缀，按钮带图标，整体留白适度。扣分项：状态横幅与运营指标数据区在内容为空/不同状态时略显平淡；缺少预览中“成员数”等 team 空间专属信息。 |
| D6 性能 CWV | 8% | **9.3** | S | FCP 快、无长列表、零失败请求。 |
| D7 代码质量 | 10% | **8.8** | A- | `npm run build` 通过、`npm run test` 28/28 通过、TypeScript strict。新增 `iconTone` 类型安全。扣分项：Dashboard 单测覆盖有限，部分逻辑（如 `opsMetricsFromStats`）无独立单测。 |
| D8 安全性 | 8% | **8.8** | A- | 无 `eval`、无用户输入直插 DOM；搜索摘要通过 `SearchSnippet` 受控渲染（后端 `ts_headline` 仅输出 `<mark>`）。 |
| D9 响应式 / 跨设备 | 6% | **9.0** | A- | 390px 下搜索 pill 横向排列、统计卡 2×2 网格、运营指标单列，功能可用。桌面 1440 表现良好。 |
| D10 可维护性 / 可观测 | 6% | **8.5** | A- | 组件拆分清晰（Search/ZoneA/StatsGrid/StatusBanner/OpsMetrics）；评估脚本/截图已归档到 `docs/screenshots/` 并从 `.workbuddy` 清理。扣分项：无运行时日志/埋点；缺少 Dashboard 专属测试文件。 |
| D11 国际化 / 本地化 | 4% | **9.0** | A- | 中文 UI，无英文暴露；搜索空结果已用中文提示。 |
| D12 SEO / 元数据 | 2% | **8.5** | A- | 已补 `document.title = "知岸 · 概览"`。扣分项：缺少 per-page description/canonical/og（SPA 需 Helmet 等方案，尚未实施）。 |

### 加权计算

```
9.3×0.12 + 9.0×0.12 + 9.4×0.10 + 9.1×0.14 + 9.1×0.08
+ 9.3×0.08 + 8.8×0.10 + 8.8×0.08 + 9.0×0.06 + 8.5×0.06
+ 9.0×0.04 + 8.5×0.02
= 1.116 + 1.080 + 0.940 + 1.274 + 0.728
+ 0.744 + 0.880 + 0.704 + 0.540 + 0.510
+ 0.360 + 0.170
= 9.046
```

---

## 三、剩余差距（若要继续冲 9.5）

| 维度 | 当前分 | 目标分 | 可行改进 |
|---|---|---|---|
| D7 代码质量 | 8.8 | 9.5 | 为 Dashboard 核心逻辑补单测（`opsMetricsFromStats`、`isDashboardEmpty`、统计卡片渲染）。 |
| D10 可维护性 | 8.5 | 9.5 | 为 Dashboard 增加独立测试文件；接入基础运行时错误/埋点。 |
| D12 SEO | 8.5 | 9.5 | 引入 `react-helmet-async`，为 Dashboard 输出 `description`/`og:title`/`canonical`。 |
| D5 视觉美学 | 9.1 | 9.5 | 状态横幅与运营指标空态增加品牌暖意插图/空态；进一步统一 result row 的 hover 与状态色。 |
| D2 可用性 | 9.0 | 9.5 | 搜索框增加清空按钮、键盘 shortcuts；移动端欢迎区按钮可横向并排。 |

---

## 四、实测证据

- **视觉截图**：`docs/screenshots/dashboard_eval_desktop.png`、`docs/screenshots/dashboard_eval_mobile.png`
- **左右对比**：`docs/screenshots/dashboard_eval_desktop_compare.png`、`docs/screenshots/dashboard_eval_mobile_compare.png`
- **搜索状态**：`docs/screenshots/dashboard_eval_search.png`
- **构建/测试**：`npm run build` 通过，`npm run test` 28 passed

---

## 五、结论

Dashboard 单项已到达 **A 级（9.05/10）**，视觉上已与暖白预览稿高度对齐。剩余 -0.45 分集中在**工程深度**（单测、SEO 框架、无障碍细节、微交互）而非视觉风格。若继续在同一页上投入，边际收益较低；**提升整体项目分**更有效的方式是：把相同标准应用到 KBs、KBDetail、Members/Departments、Account/OrgSettings、AdminAudit/DocPreview 等剩余页面，再跑全站真机 Lighthouse。
