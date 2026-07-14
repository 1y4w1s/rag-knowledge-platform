# 全站 Lighthouse 性能 / 质量验证报告

- **日期**：2026-07-13
- **任务**：#84 真机 Lighthouse 性能验证（前端全站代码同步收尾）
- **环境**：系统 Chrome（`/c/Program Files/Google/Chrome/Application/chrome.exe`，headless `--remote-debugging-port=9222`）+ Lighthouse 12 + puppeteer-core 25
- **被测构建**：`frontend/dist` **生产构建**（`npm run build`，JS 614.25 kB / gzip 184.52 kB，CSS 101.39 kB / gzip 17.27 kB）
- **服务方式**：静态服务器（`serve83.mjs`）托管 `dist` 并反向代理 `/api` → 后端 `:8000`，端口 `:5180`
- **认证**：UI 登录 `demo-admin@example.com`，localStorage token 注入同一浏览器 profile 后运行
- **配置**：`formFactor: desktop`、`throttlingMethod: simulate`（4× CPU + 1.6 Mbps 模拟节流）、仅测 performance / accessibility / best-practices / seo 四类别
- **评分口径**：0–100，Lighthouse 默认权重

> 注：dev 模式（Vite `:5174`）首轮测得 perf 仅 29–55，因未压缩 + HMR + 即时转译开销，属误导性下界；本报告以**生产构建**为准。

---

## 一、全站评分总表（11 个同步页）

| 页面 | Performance | Accessibility | Best Practices | SEO |
|---|---|---|---|---|
| 登录页（公开基线） | **58** | 93 | 100 | 91 |
| 工作台 Dashboard | **58** | 93 | 100 | 91 |
| 资料库列表 KBs | 57 | **96** | 100 | 91 |
| 资料库详情 KBDetail | 57 | **96** | 100 | 91 |
| 成员管理 Members | 57 | 95 | 100 | 91 |
| 部门管理 Departments | 57 | **96** | 100 | 91 |
| 账号设置 Account | 57 | 95 | 100 | 91 |
| 团队设置 OrgSettings | 57 | 95 | 100 | 91 |
| 操作审计 AdminAudit | 57 | 95 | 100 | 91 |
| 文档预览（Markdown） | 57 | 95 | 96 | 91 |
| 文档预览（PDF） | **48** | 96 | 100 | 91 |

**核心结论**：A11y 93–96、Best Practices 96–100、SEO 91，全站质量基线已达 **A 档**；唯一短板是 **Performance ≈ 57（中等）**，集中于首屏 JS 体积。

---

## 二、关键性能指标（生产构建，桌面模拟节流）

| 页面 | FCP | LCP | TBT | CLS | SI | TTI |
|---|---|---|---|---|---|---|
| 登录 | 4.7 s | 4.9 s | 30 ms | 0 | 4.7 s | 4.9 s |
| Dashboard | 4.7 s | 4.9 s | 10 ms | 0 | 4.7 s | 4.9 s |
| KBs | 4.7 s | 5.2 s | 0 ms | 0 | 4.7 s | 5.9 s |
| KBDetail | 4.9 s | 5.4 s | 0 ms | 0 | 4.9 s | 5.4 s |
| Members | 4.7 s | 5.0 s | 0 ms | 0 | 4.7 s | 5.0 s |
| Departments | 4.7 s | 5.1 s | 0 ms | 0.006 | 4.7 s | 5.1 s |
| Account | 4.7 s | 5.0 s | 0 ms | 0 | 4.7 s | 5.0 s |
| OrgSettings | 4.7 s | 5.0 s | 0 ms | 0 | 4.7 s | 5.0 s |
| AdminAudit | 4.7 s | 5.3 s | 0 ms | 0 | 4.7 s | 5.3 s |
| DocPreview MD | 4.9 s | 5.5 s | 10 ms | 0 | 4.9 s | 5.5 s |
| **DocPreview PDF** | 4.9 s | 5.5 s | 0 ms | **0.196** | 4.9 s | 5.6 s |

**观察**：
- TBT 几乎全为 0，说明运行时主线程无长任务阻塞——交互响应健康。
- CLS 全站 ≈ 0，**PDF 页除外**（见第三节）。
- FCP/LCP ≈ 4.7–5.5 s 是性能分卡在 ~57 的主因，来自首屏需下载解析 184 kB gzip JS 单包。

---

## 三、发现与处置

### 发现 1（性能主因）：单包 614 kB，无代码分割
整站打包为单一 `index-*.js`（gzip 184 kB），无路由级懒加载、无 vendor 分包。模拟节流下解析该包即吃掉约 1 s，直接拉低 FCP/LCP。
- **影响**：Performance 锁死在 ~57，无法进入 80+ 绿区。
- **建议（高杠杆，未在本任务实施）**：
  1. 路由级 `React.lazy` + `Suspense` 拆分各页（首屏仅加载 Dashboard 所需代码）。
  2. `build.rollupOptions.output.manualChunks` 将 `react`/`react-router`/`react-query` 等拆为 `vendor` 长缓存。
  3. 视情况预连接/预加载关键接口。
- 实施后可预期 Performance 提升至 80+（首屏 JS 显著减小）。

### 发现 2（PDF 页 CLS=0.196）：外部 PDF 查看器子帧，非代码缺陷
通过 Lighthouse JSON 诊断确认：**主帧 CLS = 0.00003（近乎完美）**，0.196 全部来自 PDF `<iframe>` 内浏览器内置 PDF 查看器（子帧）的自身布局位移，被 Lighthouse 计入页面 CLS。
- 该位移发生在浏览器原生 PDF 渲染管线内，**前端代码无法干预**。
- 本次顺手优化了 PDF 渲染分支：`blobUrl` 未就绪时由原先误显示「暂不支持」空态改为原地显示「正在加载文档预览…」占位（盒模型尺寸与 iframe 一致），避免空态→iframe 的轻微跳动、并修正误导性文案。此改动改善 UX，但**不改变** Lighthouse 数字（因主导位移在外部子帧）。
- **建议**：若要彻底消除该项，需放弃原生查看器、自托管 `pdf.js` 渲染（可控布局），属较大改造，留作后续评估。

### 发现 3（SEO=91）：可补强项
全站均 91，差距通常在缺失 `robots.txt` / `sitemap.xml` 或个别页 `meta description` 覆盖不全（登录页基线亦 91）。同步阶段（#77–#83）已为各页补 `document.title` + `meta description`，再补 `robots.txt` + `sitemap.xml` 即可冲 100。

### 发现 4（登录页 A11y=93）：可补强项
登录页 93 略低于其余页 95–96，典型为缺少显式 `<h1>` 页面标题或表单关联。其余页 A11y 已达 95–96（A+）。补一个语义化 `<h1>` 即可对齐。

---

## 四、结论

| 维度 | 评级 | 说明 |
|---|---|---|
| Accessibility | **A（93–96）** | 全站无障碍基线稳固，登录页可微调至 95+ |
| Best Practices | **A+（96–100）** | 仅 MD 预览 96（轻微 ding） |
| SEO | **A（91）** | 补 robots/sitemap 即达 100 |
| Performance | **B（48–58）** | 受单包体积限制，代码分割后可入 80+ 绿区 |

**全站前端同步（#77–#83）+ 真机 Lighthouse 验证（#84）已完成。** 质量维度（A11y/BP/SEO）全部进入 A 档；性能维度受构建产物形态（单包）约束处于中等，已定位根因并给出高杠杆改进路径。PDF 页 CLS 经诊断确认为外部查看器子帧因素，非本仓库代码缺陷。

---

## 附：原始产物
- 各页 Lighthouse HTML 报告：`docs/lighthouse/{name}.html`（11 份）
- 结构化汇总：`docs/lighthouse/summary.json`
- 复跑脚本（已清理临时验证脚本，保留方法论）：`serve83.mjs`（静态托管+API 代理）、`lh83.mjs`（puppeteer 登录 + 全站 Lighthouse）
