# 睿阁 · 设计系统补充（Design System Supplement）

> **定位**：本文是 [`docs/DESIGN.md`](../DESIGN.md) 的**简短补充**，仅记录 DESIGN.md 未覆盖的零散规范。
> **权威来源**：`DESIGN.md` 是本仓库前端设计的**唯一事实来源**。如有冲突，以 DESIGN.md 为准。
> **清理记录**：2026-07-15 — 清除了全部过时 warm-white 预览 HTML、评分卡、评估报告。

---

## 1. 角色色（Role Badge）

DESIGN.md 未定义角色/权限徽章色。此处补充，语义明确隔离：

| Token | Light | Dark | 用途 |
|-------|-------|------|------|
| `--role` | `#5B6B8C` | `#7A8BA8` | 角色徽章主色（中性 slate，**禁止**使用状态色或品牌赤陶） |
| `--role-bg` | `rgba(91,107,140,.14)` | `rgba(122,139,168,.14)` | 角色浅底 |
| `--role-ink` | `#3E4A63` | `#9AABC8` | 角色文字（AA 对比度） |

**原则**：角色（所有者/管理员/成员）≠ 流程状态（成功/进行中/失败）。绝不可借用绿/琥珀/红或赤陶。

---

## 2. 圆角梯度

DESIGN.md 定义圆角以 16px 为主。以下为完整梯度：

| 层级 | 值 | 用途 |
|------|----|------|
| 卡片/面板 | `16px`（`rounded-2xl`） | 主内容卡片、对话气泡外壳 |
| 控件/输入框 | `8px` | 按钮、输入框、select |
| 徽章/pill | `999px` | StatusBadge、RoleBadge、引用 chip |
| 特例 | `6px` | 小口径徽章（如 Dashboard 右上角口径标） |

---

## 3. 投影系统

DESIGN.md 未列投影细节，补充如下：

| Token | Light | Dark | 用途 |
|-------|-------|------|------|
| `--card-shadow` | `0 1px 3px rgba(0,0,0,.04), 0 4px 12px rgba(0,0,0,.06)` | `0 12px 30px -22px rgba(12,8,6,.55)` | 卡片默认 |
| `--card-shadow-lift` | `0 2px 6px rgba(0,0,0,.06), 0 8px 24px rgba(0,0,0,.08)` | `0 18px 38px -20px rgba(12,8,6,.70)` | 卡片 hover 抬升 |
| `--shadow-sm` | `0 1px 2px rgba(0,0,0,.04)` | `0 1px 2px rgba(0,0,0,.3)` | 小元素（按钮） |
| `--shadow-md` | `0 4px 24px rgba(0,0,0,.06)` | `0 4px 24px rgba(0,0,0,.4)` | 浮层/弹出面板 |

---

## 4. 反模式清单（Forbidden Patterns）

DESIGN.md §6 硬约束之外，补充：

1. ❌ **状态色借用品牌赤陶**：如「处理中」用 `--action`，破坏赤陶的唯一操作语义。
2. ❌ **侧栏/顶栏用不透明纯白**：破坏「壳轻、内容重」层次。应使用 `--surf-shell`（半透明白/黑玻璃）。
3. ❌ **原生 `<select>` / `<input type=radio>` 裸露**：须替换为自定义组件。
4. ❌ **角色徽章用状态色**：角色用 Slate 系 `--role`，禁止绿/琥珀/红。
5. ❌ **中文 letter-spacing**：中文字距已由 DESIGN.md §7 红线禁止，此处重申。

---

## 5. 页面重做验收标准

每页重做完成后，对照以下清单：

| # | 检查项 | 依据 |
|---|--------|------|
| 1 | 颜色全部使用 `var(--*)`，无硬编码 | DESIGN.md §6.2 |
| 2 | 双主题全覆盖（light / dark） | DESIGN.md §5 |
| 3 | 卡片圆角 16px，控件圆角 8px | 本节 §2 |
| 4 | 缺失值显示 `—`，三个态（loading/error/empty）齐全 | DESIGN.md §6.4 |
| 5 | 容器 max-w-\[1180px\]，px-7 | DESIGN.md §2 |
| 6 | 角色徽章用 `--role` 系，不用状态色 | 本节 §1 |
| 7 | WCAG AA：焦点环、对比度、reduced-motion | DESIGN.md §6.3 |
| 8 | 视觉效果与已落地的 **Dashboard 页面**一致 | DESIGN.md 定位 |

---

> **维护说明**：当新的设计决策产生时，先判断是否应写入 `DESIGN.md`（核心规范），只有 DESIGN.md 不覆盖的细节才写入本文。
