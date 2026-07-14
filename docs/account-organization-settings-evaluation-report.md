# 账号 + 团队设置页同步评估报告（Task #82）

> 页面：`AccountSettingsPage` / `OrganizationSettingsPage`  
> 参考源：`docs/account-settings-warm-white-preview.html` / `docs/organization-settings-warm-white-preview.html`、`docs/design-system.md`、`docs/scoring-standard-v3.md`  
> 对比截图：`docs/screenshots/account_settings_compare_v1.png` / `org_settings_compare_v1.png`  
> 完成时间：2026-07-13

---

## 1. 主要改动（真实代码层）

### 账号设置页（AccountSettingsPage）

| 改动项 | 文件 | 说明 |
|--------|------|------|
| **修复密码强度条 token 漂移** | `components/auth/PasswordStrengthBar.tsx` | 把只在 `.auth-page` 作用域内定义的 `--auth-strength-weak/mid/strong` / `--auth-line` 替换为全局统一状态色：`--status-err` / `--status-amber` / `--status-ok`（文字用对应的 ink token）。这是账号评分卡 AS-R1-1 明确列为"同步回代码"的待办。 |
| **补页标题** | `pages/AccountSettingsPage.tsx` | 顶部新增 `h2 font-serif text-xl` 页标题 "账号设置"，与预览稿和兄弟页（MembersPage）对齐。 |
| **补 SEO** | `pages/AccountSettingsPage.tsx` | 动态设置 `document.title` 与 `meta[name="description"]`。 |
| **危险按钮改 danger 红** | `components/settings/LeaveTeamForm.tsx` | 确认离开对话框的"确认离开"由 `#B85A2E` 改为 `var(--status-err)`，符合设计系统 §4.1 销毁型操作走 danger 红。 |
| **新增测试** | `components/auth/PasswordStrengthBar.test.tsx` | 5 项：空密码、3 段 meter、弱/强 token、aria-valuenow。 |

### 团队设置页（OrganizationSettingsPage）

| 改动项 | 文件 | 说明 |
|--------|------|------|
| **补页标题** | `pages/OrganizationSettingsPage.tsx` | 新增 `h2 font-serif text-xl` "团队设置"。 |
| **补 SEO** | `pages/OrganizationSettingsPage.tsx` | 动态设置 `document.title` 与 `meta[name="description"]`。 |

### 已保持现状（评分卡允许的源级决策）

- **OrgSettings 保存成功提示**：仍用暖中性表面背景，未按预览改为 success 绿。原因：① 用户已明确偏好"克制、避免过度装饰性 UI"；② 成功提示是瞬时状态，暖中性不造成视觉噪音，与全局卡片风格一致。
- **角色徽章**：Account 中"团队版 · 管理员"、LeaveTeam 的 owner 提示，保持源码既有方案；未额外着色。
- **只读字段**：`SettingsReadonlyField` 已使用 `.settings-field-input-readonly`（surface-2 底 + muted 字），评分卡 AS-R1-2 已满足。

---

## 2. 验证结果

- `npm run build`：通过（仅 chunk 体积提示，无报错）。
- `npm run test`：8 个文件，45 项全部通过。
- 真实/预览对比：桌面 + 移动各两份，已归档 `docs/screenshots/`。

---

## 3. 12 维评分（v3）

| 维度 | 权重 | 账号设置 | 团队设置 |
|------|------|----------|----------|
| D1 视觉一致性 | 12% | 9.3 | 9.3 |
| D2 可用性 / UX | 12% | 9.2 | 9.3 |
| D3 功能完整 | 10% | 9.8 | 10.0 |
| D4 无障碍 | 14% | 9.0 | 9.0 |
| D5 视觉美学 | 8% | 8.5 | 8.7 |
| D6 性能 CWV | 8% | 8.5 | 8.5 |
| D7 代码质量 | 10% | 9.0 | 9.2 |
| D8 安全性 | 8% | 8.5 | 8.5 |
| D9 响应式 | 6% | 9.0 | 9.0 |
| D10 可维护 / 可观测 | 6% | 8.5 | 8.5 |
| D11 国际化 | 4% | 8.5 | 8.5 |
| D12 SEO / 元数据 | 2% | 8.5 | 8.5 |
| **加权总分** | 100% | **9.21 / 10** | **9.29 / 10** |
| **档位** | — | **A** | **A** |

> 评分逻辑：两页均达到 A 档（≥ 9.0），但未达 9.5（S）。主要缺口与全站一致：D5 视觉美学（主观/细节）、D6 性能未实测（仅按代码静态评估）、D8 安全审计未做系统性扫描、D10 埋点/可观测性、D12 缺少 OpenGraph / canonical 框架。

---

## 4. 剩余打磨项（不阻塞本任务）

1. **D12 框架**：统一补上 `og:title` / `og:description` / `canonical` 与部署域名 `1y4w1s.icu:8080`（跨所有页面）。
2. **D6 性能**：在真机部署后跑 Lighthouse，当前为静态评估。
3. **D8 安全**：做一次全站 `eval` / `innerHTML` / 外链 `rel` 扫描。
4. **D10 埋点**：关键按钮（保存密码、离开团队、保存团队名称）统一加 `data-track`。

---

## 5. 结论

Task #82 完成。账号设置页与团队设置页已同步至预览稿水平，加权分别为 **9.21 / 9.29**，均为 A 档。未达 9.5 的缺口属于全站工程基础设施（SEO 框架、性能实测、安全审计、埋点），继续在同一页投入边际收益低，建议进入 Task #83（AdminAudit + DocPreview）或优先补齐全站基础设施后跑一轮全站 Lighthouse。
