# 成员管理 MembersPage · 评分卡（Round 1）

> **标尺**：`docs/design-system.md`（暖白/赤陶 · 状态色 绿·琥珀·红）+ `docs/iteration-loop.md` 六维门禁。
> **母版**：KBs / KBDetail 统一外壳 + 表格规范（已达标基线）。
> **源码对齐**：`MembersPage.tsx` + `MembersTable` / `MemberRoleActions` / `AddMemberDialog` / `RemoveMemberDialog` / `TransferOwnershipDialog` / `InviteCodePanel`。

---

## 1. 本轮发现（痛点总结）

| 编号 | 严重度 | 痛点 | 改造动作 | 状态 |
|---|---|---|---|---|
| M-R1-1 | 🟠 P2 | 提升/降级按钮首次点击后被 `outerHTML` 替换、原监听器丢失 → 变死控件（违反"无死控件"硬规则） | 改为**事件委托**（监听器挂在稳定的 `#view-admin` 容器，动态替换的按钮仍生效） | ✅ 已修 |
| M-R1-2 | 🟡 P3 | 对话框打开未 trap / 移动焦点（预览层；真实 Radix 已处理） | 记已知限制（代码层 Radix Dialog 已处理） | ⏸ |
| M-R1-3 | 🟡 P3 | 角色徽章复用琥珀（=处理中状态色），与状态语义图例碰撞（**源码当前行为** `doc-badge-wait`） | 忠实保留源码外观 + 提产品决策（是否改为中性/赤陶色 chip） | ⏸ |
| M-R1-4 | 🟡 P3 | 转让所有权自定义 select 非完整键盘 listbox（预览层） | 记已知限制 | ⏸ |

> **说明**：M-R1-3 是"忠实还原源码"与"设计语义纯净"的张力。源码对所有角色统一用 `doc-badge-wait`（琥珀），预览如实保留；是否改中性色属产品决策，不在本轮预览修复范围。

---

## 2. 六维打分（门禁：每维 ≥ 8.0）

| 维度 | 权重 | 得分 | 达标 | 评审依据 |
|---|---|---|---|---|
| 一致性 Consistency | 20% | **9.3** | ✅ | 外壳/Token/表格与 KBs·KBDetail 基线一致；转让原生 `<select>` 已换自定义（跨页控件统一） |
| 可用性 Usability | 20% | **9.2** | ✅ | 四态可切；增/删/转让/邀请四对话框均可开合（Esc+遮罩+取消）；提升降级委托修复后零死控件；邀请码生成/复制可用 |
| 功能保全 Function | 20% | **9.7** | ✅ | 管理员视图（所有者/管理员/成员三类行 + 转让/升降/移除逻辑）、邀请面板、三对话框、四状态（管理员/加载/失败/只读）全覆盖源码分支，零增零减 |
| 无障碍 A11y | 15% | **8.8** | ✅ | `<th scope="col">` + 操作列 `aria-label`；对话框 `role=dialog/aria-modal/aria-labelledby`；自定义 select `aria-expanded`+`listbox`；关闭按钮 `aria-label`；M-R1-2/4 为预览层已知限制 |
| 视觉 Visual | 15% | **9.1** | ✅ | 表格圆角/行 hover/分隔清晰；按钮三级（primary/outline/ghost）层次统一；角色 amber chip 忠实（见 M-R1-3） |
| 性能 Perf | 10% | **9.0** | ✅ | 加载骨架 `prefers-reduced-motion` 守卫；无长列表卡顿；动效轻量 |

**加权总分** = 0.20×9.3 + 0.20×9.2 + 0.20×9.7 + 0.15×8.8 + 0.15×9.1 + 0.10×9.0
= 1.86 + 1.84 + 1.94 + 1.32 + 1.365 + 0.90 = **9.23 / 10**

---

## 3. 门禁结论

**六维全部 ≥ 8.0 → 门禁 ✅**，加权 **9.23**。本轮仅 1 处真实缺陷（M-R1-1 死控件）已修复，3 处为预览层已知限制 / 产品决策，不阻断达标。

---

## 4. 同步回代码待办（预览 → 代码）

- `MembersTable` 角色 `<span className="doc-badge doc-badge-wait">` 是否改中性 chip（对应 M-R1-3）。
- 转让对话框若保留原生 `<select>`，建议与预览一致换自定义（一致性）。
- 其余视觉 token 已与 `design-system.md` 对齐，直接套用即可。
