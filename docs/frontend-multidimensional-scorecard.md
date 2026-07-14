# 前端多维度专业评分报告（v3 · 真实代码实测版）

> 评审对象：知岸 RAG 平台前端全站（React 19 + Vite 6 + TS + Tailwind v3）
> 评审体系：`scoring-standard-v3.md`（12 维硬阈值 · 未测=0 · 一票否决）
> 关键区别：本次为**同步回真实代码 + 性能优化落地后**的实测评分，D6 性能由「9.0 起评占位」升级为**真机 Lighthouse 实测**。
> 日期：2026-07-13　｜　评审基准：生产构建（gzip 等价，nginx 部署一致）

---

## 0. 结论速览

| 项 | 结果 |
|---|---|
| **全站加权总分** | **9.07 / 10** |
| **档位** | **A 优秀（通过）** |
| 最低维度 | D6 性能 8.6 / D12 SEO 8.6（均 ≥ 8.0，无强制降档） |
| 一票否决触发 | **无**（键盘可达 / 焦点环 / LCP<4s / CLS<0.25 / 无 eval / XSS<3 全部通过） |
| 相比静态预览均值（9.21） | −0.14（诚实回落，源于真机 D6/D12 取代占位分，非质量下降） |

**一句话**：全站在真实代码 + 真机数据下仍稳居 A 档，无任何一票否决；短板集中在「性能 LCP 边缘」与「SEO 元数据补全」两处工程细节，均为可低成本冲刺 S 档的路径。

---

## 1. 十二维评分矩阵

| 维 | 维度 | 权重 | 得分 | 档 | 关键证据 / 扣分点 |
|---|---|---|---|---|---|
| **D1** | 视觉一致性 | 12% | **9.3** | A | 5 套色 token 统一（`--terracotta/--amber/--ok/--err/--role`）；图标 100% lucide SVG（stroke 体系）；字号/圆角/间距全走 token。无漂移。 |
| **D2** | 可用性 / UX | 12% | **9.2** | A | 加载/失败/空态/成功 4 态齐备；危险操作二次确认；自定义 `Select` 全套 `role=listbox/option`+键盘可达。 |
| **D3** | 功能完整 | 10% | **9.3** | A | 原功能 100% 保留；核心路径 ≤5 步；token/workspace 持久化（localStorage）；`RouteFallback`+空态无白屏降级。 |
| **D4** | 无障碍 (WCAG AA) | 14% | **9.1** | A | Lighthouse a11y **93–96**；`:focus-visible` 赤陶 2px、skip-link、landmark、`prefers-reduced-motion` 守卫、aria 齐备。**扣**：登录页缺独立 `<h1>`（H4.4）。 |
| **D5** | 视觉美学 | 8% | **8.7** | A | 暖白/赤陶语言契合，节奏/对齐/留白达标；受 v3「视觉上限 8.8」约束（人眼审美不可程序化替代）。 |
| **D6** | 性能 (CWV) | 8% | **8.6** | A | 真机 gzip：Perf **67–78**、TBT **3–55ms**（近 0）、主帧 CLS **0**；分包后首屏入口 15KB gzip。**扣**：LCP **2.2–2.8s**，部分页略越 2.5s 门线（H6.1，未达一票 4s）。 |
| **D7** | 代码质量 | 10% | **9.3** | A | 无 `console.log`/`debugger`；无 `eval`；`!important` 仅 8 处且全在 reduced-motion 守卫/移动抽屉（合理）；TS 严格 + 55 单测全绿；manualChunks 分包架构清晰。 |
| **D8** | 安全性 | 8% | **8.9** | A | 无 `eval`/`new Function`/`document.write`；登录走 POST；无硬编码密钥。**扣**：1 处 `dangerouslySetInnerHTML`（渲染 Postgres `ts_headline` 高亮，后端已转义、仅 `<mark>`，受控注入）。 |
| **D9** | 响应式 | 6% | **9.1** | A | viewport meta ✓；三档断点（≤767/768–1023/≥1024）无横向溢出；1024 以下侧栏转抽屉。 |
| **D10** | 可维护性 / 可观测 | 6% | **9.1** | A | token 集中 `:root`；命名语义化；列表数据驱动；错误 `console.error`+用户可见提示。 |
| **D11** | 国际化 | 4% | **9.0** | A | `lang="zh-CN"`；日期走 `Intl`；中英混排间距处理；文案 i18n-ready。 |
| **D12** | SEO / 元数据 | 2% | **8.6** | A | title/description/og(type,title,desc,site_name)/twitter/theme-color 齐备。**扣**：缺 canonical、og:image、JSON-LD、robots.txt/sitemap.xml（Lighthouse SEO 91）。 |
| | **加权合计** | 100% | **9.07** | **A** | — |

### 加权明细
```
D1 9.3×.12=1.116   D2 9.2×.12=1.104   D3 9.3×.10=0.930
D4 9.1×.14=1.274   D5 8.7×.08=0.696   D6 8.6×.08=0.688
D7 9.3×.10=0.930   D8 8.9×.08=0.712   D9 9.1×.06=0.546
D10 9.1×.06=0.546  D11 9.0×.04=0.360  D12 8.6×.02=0.172
────────────────────────────────────────────────────
合计 = 9.07  →  A 档（9.0 ≤ x < 9.5）
```

---

## 2. 程序化取证（未测=0 原则）

| 检查项 | 结果 | 判定 |
|---|---|---|
| 源码规模 | 201 源文件 / 101 组件 / 12 页面 / CSS 1693 行 | — |
| 单元测试 | **10 文件 55 用例全绿**（vitest run，11.0s） | ✅ 新鲜实测 |
| `console.log`/`debugger` | **0 处** | ✅ H7.1 |
| `eval`/`new Function`/`document.write` | **0 处** | ✅ H8.1/H8.3 |
| `dangerouslySetInnerHTML` | 1 处（ts_headline 受控高亮） | ⚠️ H8.2 可控 |
| `!important` | 8 处，全在 reduced-motion / 移动抽屉媒体查询 | ✅ 合理 |
| 图标 SVG | 全量 lucide-react（stroke:currentColor） | ✅ H1.5 |
| `target="_blank"` 外链 | 0 处 | ✅ 无 noopener 风险 |
| `lang` / viewport | `zh-CN` / `width=device-width` | ✅ H11.1/H9.1 |
| focus-visible/skip-link/sr-only/reduced-motion | CSS 命中 17 处 | ✅ H4.1/4.2/4.10 |
| 真机 Lighthouse（gzip 生产等价，11 页） | Perf 67–78｜A11y 93–96｜BP **100**｜SEO 91 | ✅ 见 `docs/lighthouse-v2-gzip/` |

---

## 3. 冲刺 S 档（9.5+）路径 · 按价值/成本排序

| 优先级 | 动作 | 影响维 | 预期增益 | 成本 |
|---|---|---|---|---|
| ① | 补 `robots.txt` + `sitemap.xml` + `canonical`(`1y4w1s.icu:8080`) + `og:image` | D12 8.6→9.5 | +0.018 | 极低 |
| ② | 登录页补独立 `<h1>` | D4 9.1→9.4 | +0.042 | 极低 |
| ③ | 首屏关键 chunk `modulepreload` + 字体 `font-display:swap` 优化 LCP 至 <2.5s | D6 8.6→9.2 | +0.048 | 中 |
| ④ | 长列表（成员/审计 >100 项）引入虚拟化 | D6 | +0.01 | 中 |

**预期**：①②③ 全做后加权约 **9.18**，D6/D12 脱离短板；若叠加人眼美学复核 D5 +0.2，可冲 **9.3+**，部分页进入 S 档。

---

## 4. 归档产物
- 真机 Lighthouse：`docs/lighthouse-v2-gzip/`（11 页 HTML + summary.json，生产等价）
- 性能优化：`docs/performance-optimization-report.md`
- 逐页 v3 静态基线：`previews-gallery.html` + 各 `*-scorecard.md`
- 本报告：`docs/frontend-multidimensional-scorecard.md`
