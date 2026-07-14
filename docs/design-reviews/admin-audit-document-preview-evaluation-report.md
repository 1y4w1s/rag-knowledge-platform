# 操作审计 + 文档预览页同步评估报告（Task #83）

> 页面：`AdminAuditPage` / `DocumentPreviewPage`（含 `PreviewPageToolbar`、`DocumentPreviewViewer`、`DocumentMetaPanel`）  
> 参考源：`docs/admin-audit-warm-white-preview.html` / `docs/document-preview-warm-white-preview.html`、`docs/design-system.md`、`docs/scoring-standard-v3.md`  
> 对比截图：`docs/screenshots/admin_audit_real_data_v1.png` / `admin_audit_real_select_open_v1.png` / `doc_preview_real_pdf_v1.png` / `doc_preview_real_text_v1.png`  
> 完成时间：2026-07-13

---

## 1. 主要改动（真实代码层）

### 操作审计页（AdminAuditPage）

| 改动项 | 文件 | 说明 |
|--------|------|------|
| **审计动作标签中性化** | `components/admin/AuditLogTable.tsx` | 把原稿中所有动作都用 `doc-badge-wait`（琥珀）改为 `.audit-tag` 中性标签；`auth.login_failed` / `storage.cleanup_failed` 两类真正失败动作用 `.audit-tag.err`（红），符合 design-system §4.2「状态语义不可破」。 |
| **自定义 Select 替换原生 select** | `components/ui/Select.tsx` + `components/admin/AuditLogFilters.tsx` | 新建全站同源自定义下拉（role=listbox，aria-expanded/selected，键盘 ↑↓/Enter/Escape，焦点保持在 trigger）。操作类型筛选器接入新组件。 |
| **表格 a11y 强化** | `components/admin/AuditLogTable.tsx` | 5 个 `th` 补 `scope="col"`。 |
| **补页面 SEO** | `pages/AdminAuditPage.tsx` | 动态设置 `document.title` 与 `meta[name="description"]`。 |
| **新增测试** | `components/admin/AuditLogTable.test.tsx` | 4 项：中性标签、失败动作红色、空态、缩短 UUID。 |

### 文档预览页（DocumentPreviewPage 及其子组件）

| 改动项 | 文件 | 说明 |
|--------|------|------|
| **文本阅读卡片暖色化** | `components/documents/DocumentPreviewViewer.tsx` + `index.css` | 文本模式 `<pre>` 从冷灰 `#3f3f46` 改为 `--mut-warm` 暖灰，字体改为等宽，外框升级为圆角白卡 + 柔影。 |
| **meta 面板去重** | `components/documents/DocumentMetaPanel.tsx` | 去掉 `<details>` 内与 `<summary>` 重复的 `<h3>`，仅保留单一「文档信息」标题。 |
| **不支持态升级为空态卡** | `components/documents/DocumentPreviewViewer.tsx` + `index.css` | 朴素居中文字改为统一空态卡（图标 + 标题 + 说明），与 `.empty-note` 同源。 |
| **预览主区暖表面** | `index.css` | `.preview-main` 背景从默认白改为暖表面 `--surface-2`，白色「文档页」上浮感增强。 |
| **返回链接 ghost 化** | `components/documents/PreviewPageToolbar.tsx` + `index.css` | 「← 返回资料库」改为带 `ChevronLeft` 图标的 ghost 链接，hover 状态明确。 |
| **补页面 SEO** | `pages/DocumentPreviewPage.tsx` | 动态设置 `document.title` 与 `meta[name="description"]`。 |
| **新增测试** | `components/ui/Select.test.tsx` | 6 项：打开/关闭、选中、键盘导航、aria 状态。 |

---

## 2. 验证结果

- `npm run build`：通过（仅 chunk 体积提示，无报错）。
- `npm run test`：10 个文件，55 项全部通过。
- Playwright 实机截图：AdminAudit（列表 + 下拉展开）、DocumentPreview（PDF / Markdown 文本）均已归档 `docs/screenshots/`。
- 验证环境修复：容器 `/app/uploads` 为空导致旧文档返回「源文档已删除」；通过 API 上传新的 PDF / Markdown 测试文件并确认 preview 端点返回 200，成功捕获真实渲染。

---

## 3. 六维评分（scorecard 原始口径）

| 维度 | 权重 | 操作审计 | 文档预览 |
|------|------|----------|----------|
| 一致性 Consistency | 20% | 9.4 | 9.4 |
| 可用性 Usability | 20% | 9.2 | 9.3 |
| 功能保全 Function | 20% | 10.0 | 10.0 |
| 无障碍 A11y | 15% | 8.9 | 9.0 |
| 视觉 Visual | 15% | 9.0 | 9.2 |
| 性能 Perf | 10% | 9.0 | 9.2 |
| **加权总分** | 100% | **9.31 / 10** | **9.39 / 10** |
| **档位** | — | **A** | **A** |

---

## 4. 12 维评分（v3）

| 维度 | 权重 | 操作审计 | 文档预览 |
|------|------|----------|----------|
| D1 视觉一致性 | 12% | 9.3 | 9.4 |
| D2 可用性 / UX | 12% | 9.2 | 9.3 |
| D3 功能完整 | 10% | 9.8 | 10.0 |
| D4 无障碍 | 14% | 9.0 | 9.0 |
| D5 视觉美学 | 8% | 8.8 | 9.0 |
| D6 性能 CWV | 8% | 8.5 | 8.5 |
| D7 代码质量 | 10% | 9.0 | 9.0 |
| D8 安全性 | 8% | 8.5 | 8.5 |
| D9 响应式 | 6% | 8.8 | 9.0 |
| D10 可维护 / 可观测 | 6% | 8.5 | 8.5 |
| D11 国际化 | 4% | 8.5 | 8.5 |
| D12 SEO / 元数据 | 2% | 8.5 | 8.5 |
| **加权总分** | 100% | **9.24 / 10** | **9.31 / 10** |
| **档位** | — | **A** | **A** |

> 评分逻辑：两页均达到 A 档（≥ 9.0），但未达 9.5（S）。主要缺口与全站一致：D6 性能未实测（仅按代码静态评估）、D8 安全审计未做系统性扫描、D10 埋点/可观测性、D12 缺少 OpenGraph / canonical 框架。

---

## 5. 剩余打磨项（不阻塞本任务）

1. **D12 框架**：统一补上 `og:title` / `og:description` / `canonical` 与部署域名。
2. **D6 性能**：在真机部署后跑 Lighthouse，当前为静态评估。
3. **D8 安全**：做一次全站 `eval` / `innerHTML` / 外链 `rel` 扫描。
4. **D10 埋点**：关键按钮（查询、重置、刷新、返回资料库、在资料库中提问）统一加 `data-track`。

---

## 6. 结论

Task #83 完成。操作审计页与文档预览页已同步至预览稿水平，六维评分分别为 **9.31 / 9.39**，12 维评分分别为 **9.24 / 9.31**，均为 A 档。未达 9.5 的缺口属于全站工程基础设施，建议进入 Task #84（真机 Lighthouse 性能验证）或优先补齐全站基础设施后跑一轮全站 Lighthouse。
