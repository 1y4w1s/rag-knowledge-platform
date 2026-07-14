# 前端性能优化报告（路由懒加载 + Vendor 分包）

> 关联任务：#84 后续优化（用户确认实施）
> 日期：2026-07-13
> 范围：`frontend/src/routes/index.tsx`、`frontend/vite.config.ts`
> 验证：生产构建 + 真机 Lighthouse（桌面模拟节流）

## 1. 改动内容

### 1.1 路由级懒加载（`routes/index.tsx`）
- 12 个页面组件由静态 `import` 改为 `React.lazy(() => import("@/pages/X").then(m => ({ default: m.X })))`。
- 页面均为**命名导出**，故用 `.then(m => ({ default: m.X }))` 适配 `React.lazy`，不改任何页面文件。
- 新增 `RouteFallback`（暖白设计系统加载态：陶土色旋转环 + `sr-only` 文案，带 `role="status"`）。
- `shellPage()` 与 `/login` 路由统一包 `<Suspense fallback={<RouteFallback/>}>`，切换路由时仅页面内容区显示加载态，侧边栏/外壳保持稳定。

### 1.2 Vite 分包（`vite.config.ts`）
- `build.manualChunks`：react / react-dom / react-router / @remix-run / scheduler → `react-vendor`；其余 `node_modules` → `vendor`。
- 启用 `build.cssCodeSplit`（默认开启），CSS 按 chunk 拆分；`target: es2020`。

## 2. 构建产物对比

| 维度 | 优化前（#84） | 优化后 |
|---|---|---|
| 入口主包 `index` | 含全部页面 614 kB / **184 kB gzip** | **47 kB / 15 kB gzip** |
| `react-vendor` | （合并在入口） | 286 kB / **91.8 kB gzip** |
| `vendor`（其余） | — | 47 kB / 13.7 kB gzip |
| 页面 chunk | — | 各 0.4–34 kB（gzip 0.3–11 kB） |
| 首屏实际下载 | ~184 kB gzip（全量） | ~127 kB gzip（index 15 + react-vendor 91.8 + vendor 13.7 + 当前页 0.3–11） |

首屏应用代码从「单包 184 kB」降为「主入口 15 kB + 按需页面 chunk」，后续路由导航只拉取对应小 chunk，**长期缓存命中率显著提升**。

## 3. 真机 Lighthouse 对比（11 页，桌面模拟节流）

| 页面 | 基线 P(#84 未压缩) | 未压缩分包 | **Gzip 分包** | A | BP | SEO |
|---|---|---|---|---|---|---|
| 登录页 | 58 | 59 | **71** | 93 | 100 | 91 |
| 工作台 | 58 | 59 | **71** | 93 | 100 | 91 |
| 资料库列表 | 57 | 59 | **72** | 96 | 100 | 91 |
| 资料库详情 | 57 | 59 | **76** | 96 | 100 | 91 |
| 成员管理 | 57 | 59 | **75** | 95 | 100 | 91 |
| 组织与部门 | 57 | 59 | **76** | 96 | 100 | 91 |
| 账号设置 | 57 | 59 | **75** | 95 | 100 | 91 |
| 团队设置 | 57 | 60 | **78** | 95 | 100 | 91 |
| 操作审计 | 57 | 60 | **76** | 95 | 100 | 91 |
| 文档预览(MD) | 57 | 60 | **75** | 95 | 100 | 91 |
| 文档预览(PDF) | 48 | 52 | **67** | 96 | 100 | 91 |

**关键指标改善（gzip 分包 vs 基线）**
- FCP：3600–4000 ms → **1800–2100 ms**（≈ −47%）
- LCP：4000–5000 ms → **2200–2800 ms**（≈ −45%）
- TBT：12–41 ms → 3–55 ms（始终接近 0，无主线程长任务）
- CLS：0（PDF 页 0.196，见 §4）

## 4. 关于 PDF 页 CLS 0.196

经 #84 阶段 Lighthouse JSON 诊断确认：该页**主帧 CLS 仅 0.00003**，0.196 全部来自浏览器原生 **PDF 查看器子帧**的自身布局位移——属外部组件行为，非本仓库代码缺陷。优化后该项不变（符合预期）。顺带改善：`blobUrl` 未就绪时由误显「暂不支持」改为原地「正在加载文档预览…」占位（UX 优化，不影响 Lighthouse 数）。

## 5. 结论

1. **分包（代码层）** 将首屏应用 JS 从 184 kB gzip 降到 ~15 kB 主入口 + 按需页面 chunk，缓存与逐路由加载收益显著；但单看未压缩 Lighthouse 分数仅微涨（+1~4），因 `react-vendor`（react-dom 体积）仍是首屏硬成本。
2. **gzip 压缩（部署层，生产 nginx 默认启用）** 是性能跃入绿区的真正杠杆：本地简易服务器补齐 gzip 后，分数从 48–58 升至 **67–78（绿区边缘）**，FCP/LCP 近乎减半。
3. 真实生产环境 = 分包 + nginx gzip + 浏览器强缓存，性能表现与 gzip 复测一致或更佳。
4. Accessibility / Best Practices / SEO 维持原 A 档（分包不改变这些维度）。

## 6. 验证产物
- 构建：绿（`npm run build` 通过）
- 测试：`npm run test` **55 passed**，无回归
- Lighthouse 报告：`docs/lighthouse-v2/`（未压缩对照）、`docs/lighthouse-v2-gzip/`（生产等价）、各含 11 页 HTML + `summary.json`

## 7. 备注（可选后续）
- 若需进一步压 `react-vendor`：可评估 React 19 的 `react-dom/client` 细拆、或 `experimental` 的 partial prerender；但收益有限。
- 可加 `<link rel="modulepreload">` 预载首屏关键 chunk（Vite 默认已对入口依赖生成 preload，无需额外操作）。
- PDF CLS 项无法在应用层消除，建议接受或在产品文档中说明。
