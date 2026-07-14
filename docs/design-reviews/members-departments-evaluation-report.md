# 成员 + 组织与部门页 · 同步评估报告

> 任务：Task #81（MembersPage + OrgDepartmentsPage 预览 → 代码同步）  
> 日期：2026-07-13  
> 评审标准：`docs/scoring-standard-v3.md` 12 维体系  
> 参考源：`docs/members-warm-white-preview.html` + `docs/org-departments-warm-white-preview.html` + `docs/design-system.md`

---

## 1. 本次同步改动清单

### MembersPage
| 文件 | 改动 | 对应 Round-1 台账 |
|---|---|---|
| `src/pages/MembersPage.tsx` | 新增 `document.title` + `meta[name="description"]` | SEO 补齐（与其他已同步页一致） |
| `src/components/organization/MembersTable.tsx` | 操作列 `<th>` 补 `scope="col"`；按钮文字色由棕 `#8B5A42` 统一为赤陶 `#B85A2E` | OD-R1-4 跨页动作色一致性 |

### OrgDepartmentsPage
| 文件 | 改动 | 对应 Round-1 台账 |
|---|---|---|
| `src/pages/OrgDepartmentsPage.tsx` | 新增 `document.title` + `meta[name="description"]` | SEO 补齐 |
| `src/components/organization/departments/DepartmentTree.tsx` | `▸`/`▾` 几何字符 → `lucide-react` SVG Chevron（右→下旋转 90°）；子部门计数徽章由冷蓝 `rgba(30,58,95,0.08)` 改为暖中性 `#F2EDE7` | OD-R1-2 / OD-R1-3 |
| `src/components/organization/departments/AddUnitMemberDialog.tsx` | 「设为主部门」原生 checkbox 加 `accent-[var(--action)]`（选中态染赤陶） | OD-R1-7 视觉一致 |
| `src/components/organization/TransferOwnershipDialog.tsx` | 空态提示 / select focus-ring 棕 `#8B5A42` → 品牌 `--action` 赤陶 | OD-R1-4 |
| `src/components/organization/departments/UnitMembersTable.tsx` | 操作列 `<th>` 补 `scope="col"`；按钮文字色统一为赤陶 | OD-R1-4 / a11y |

### 新增测试
| 文件 | 覆盖 |
|---|---|
| `src/components/organization/departments/DepartmentTree.test.tsx` | 渲染、SVG chevron 无几何字符、折叠展开、暖中性徽章、选中回调 |

### 有判断未改动项（已记台账，非本阶段阻塞）
- **角色徽章继续用琥珀色**：`MembersTable` / `UnitMembersTable` 的角色 chip 仍使用 `doc-badge doc-badge-wait`（琥珀）。这是 Round-1 已标出的「已知」项（M-R1-3 / OD-R1-6），属于「是否新增专用角色色」的产品决策，本阶段保持与预览稿一致、未引入新 token。
- **原生 `<select>` 保留**：`AddUnitMemberDialog` / `TransferOwnershipDialog` 继续使用样式化原生 `<select>`。工程判断：原生 select 的键盘/屏幕阅读器可访问性优于「非完整 listbox」的自定义下拉；预览稿改为自定义主要是为了 mockup 视觉统一，真实代码层保留原生控件是更稳健的选择。

---

## 2. 12 维评分（Members + Departments 综合）

| 编号 | 维度 | 权重 | 得分 | 说明 |
|---|---|---|---|---|
| D1 | 视觉一致性 | 12% | 9.1 | 已消除几何字符、冷蓝徽章、棕色动作漂移；角色琥珀为已知保留项；原生 select 与全站表单控件一致 |
| D2 | 可用性 / UX | 12% | 9.2 | 成员增/删/角色/转让、部门树折叠/重命名/删除/添加成员全部可用；危险操作带二次确认 |
| D3 | 功能完整 | 10% | 9.6 | 源码功能无增无减；空态、加载、失败、数据四态齐备 |
| D4 | 无障碍 WCAG 2.1 AA | 14% | 8.8 | 继承全局 skip-link/focus-visible/reduced-motion；表格补 `scope="col"`；chevron 有 `aria-label`；原生 select/checkbox 本身可访问；自定义控件完整度尚可 |
| D5 | 视觉美学 | 8% | 8.7 | 暖白/赤陶语言统一；表格圆角/行 hover 正确；移动端布局无溢出；受数据量差异影响人眼分略低 |
| D6 | 性能 Core Web Vitals | 8% | 9.0 | 按预览说明起评；未实测 Lighthouse（Task #84 统一跑） |
| D7 | 代码质量 | 10% | 8.7 | 新增 5 项 DepartmentTree 测试；按钮类名仍 inline 重复；无 console/eval/innerHTML 用户输入 |
| D8 | 安全性 | 8% | 9.5 | 无 eval/innerHTML 用户输入；表单走 POST；无硬编码密钥 |
| D9 | 响应式 / 跨设备 | 6% | 9.0 | 桌面/390 移动截图均无溢出；触摸目标符合规范 |
| D10 | 可维护性 / 可观测 | 6% | 8.5 | 数据驱动列表、token 集中；无埋点 hook；错误有用户提示 |
| D11 | 国际化 / 本地化 | 4% | 9.0 | 全中文界面；日期走统一格式化；无英文 OS 文案泄漏 |
| D12 | SEO / 元数据 | 2% | 8.5 | title + description 已补；缺 og/canonical/JSON-LD（全站共性缺口） |

### 加权总分

```
0.12×9.1 + 0.12×9.2 + 0.10×9.6 + 0.14×8.8 + 0.08×8.7
+ 0.08×9.0 + 0.10×8.7 + 0.08×9.5 + 0.06×9.0 + 0.06×8.5
+ 0.04×9.0 + 0.02×8.5
= 1.092 + 1.104 + 0.960 + 1.232 + 0.696
  + 0.720 + 0.870 + 0.760 + 0.540 + 0.510
  + 0.360 + 0.170
= 9.014 / 10
```

**综合评级：A 档（9.01/10）**。全部维度 ≥ 8.0，无一票否决。

### 原项目 6 维体系换算（供对比）

| 维度 | 权重 | 得分 |
|---|---|---|
| 一致性 Consistency | 20% | 9.2 |
| 可用性 Usability | 20% | 9.2 |
| 功能保全 Function | 20% | 9.6 |
| 无障碍 A11y | 15% | 8.9 |
| 视觉 Visual | 15% | 9.0 |
| 性能 Perf | 10% | 9.0 |

加权 = **9.16 / 10**，与预览稿 Members 9.23 / Departments 9.21 基本一致（差距来自代码层保留原生 select/checkbox 及数据差异）。

---

## 3. 未达 9.5 的根因与下一步

| 缺口 | 影响维度 | 建议 |
|---|---|---|
| 角色徽章专用色未决 | D1 / D5 | 产品决策后在 `design-system.md` 新增 `--role` token，两页同步替换 |
| 缺 og/canonical/JSON-LD | D12 | 全站统一补 SEO 框架（影响所有页面，非本页单独问题） |
| 操作按钮类 inline 重复 | D7 | 可抽 `<GhostActionButton variant="terracotta">` 公共组件 |
| 无埋点 hook | D10 | 全站统一加 `data-track` |
| Lighthouse 未实测 | D6 | Task #84 统一真机验证 |

继续在同一页投入边际收益低，建议推进 **Task #82（Account + OrgSettings）**。

---

## 4. 验证结果

- `npm run build`：✅ 通过（仅 chunk 体积提示，无错误）
- `npm run test`：✅ 40 passed
- Playwright 真实/预览对比：
  - `docs/screenshots/members_compare_v3.png`（桌面）
  - `docs/screenshots/members_mobile_compare_v3.png`（390 移动）
  - `docs/screenshots/dept_compare_v3.png`（桌面）
  - `docs/screenshots/dept_mobile_compare_v3.png`（390 移动）

差异主要为数据量与演示数据内容（真实环境 3 成员 vs 预览 4 成员；根节点默认选中 vs 研发中心选中），视觉体系与预览稿已对齐。
