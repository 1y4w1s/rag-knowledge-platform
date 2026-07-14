# 跑偏清单与修正方案 · deviation-correction v0

> 用户截图（dashboard 使用情况 4 卡挤 1 空 + sidebar 仅 1 个 ws-switch 名称）暴露了根本问题：
> **12 个预览全部背离了原系统的"个人空间/团队空间"核心概念**。
> 此前所有评分都是看着图片打分，没读原代码，所以全跑偏了也没发现。
> 本文件先把所有跑偏列清楚，再按用户拍板的"先做 1 页样板"分阶段修。

---

## 一、原系统的核心三件套（事实来源：原码）

### 1. WorkspaceSwitcher（`frontend/src/components/layout/WorkspaceSwitcher.tsx`）
- **二段切换控件** `.ws-seg`，左侧「我的空间」+ 右侧「{teamLabel} + 全称 popover 触发器」
- 当 `user.org_id` 为空（未加入团队）→ 退化为 `.ws-seg-solo` 单段「我的空间」
- 有团队 → 切到团队段时 `isTeamWorkspace = true`，**决定 admin 导航是否可见**
- `teamLabel` 来自 `formatOrgLabel(orgFullName)`（短名）；`›` 触发 popover 弹全称

### 2. DepartmentPicker（`frontend/src/components/sidebar/DepartmentPicker.tsx`）
- 紧跟 ws-seg 之后，部门下拉
- `isTeamWorkspace` 为 false 时**不显示**
- popover 内可切换部门 / 显示完整部门树

### 3. admin 权限（`AppSidebar.tsx` 第 26-37 行）
- `isTeamWorkspace && isOrgAdmin` → 显示 4 个 admin 项：组织与部门 / 成员管理 / 团队设置 / 操作审计
- `isTeamWorkspace && 有 org_id && !isOrgAdmin` → 显示「团队成员」（只读视角）
- 切换到「我的空间」后**所有 admin 项自动消失**（个人空间不应见）

---

## 二、我的跑偏（按原码对比）

| 跑偏 | 我做的 | 原系统做的 | 影响 |
|------|--------|------------|------|
| 1. ws-switch 单点 | `.ws-switch` 一个框 + 团队名 | `.ws-seg` 二段（我的空间 / 团队） | **核心功能缺失**：用户切不回个人空间，admin 权限逻辑死板 |
| 2. 无 DepartmentPicker | 没有部门下拉 | ws-seg 之后紧跟 DepartmentPicker | 个人空间内不存在，团队空间内强制显示 |
| 3. admin 硬编码可见 | 12 页侧栏 admin 4 项写死 | 根据 `isTeamWorkspace && isOrgAdmin` 条件渲染 | 我的空间也会看到团队设置/操作审计，违反"个人不应见组织" |
| 4. 成员视角 0 | 只 1 套 nav（admin 视角） | 2 套：管理员/普通成员（`showMemberNav` 走「团队成员」只读入口） | 普通成员在团队空间看到的 nav 与管理员不同 |
| 5. stat 卡的 footer link 错位 | "3 篇整理中"被踢出 grid 成第 5 个空白卡 | footer link 渲染在「已上传文件」卡内底部，pl-30px 对齐 icon | 截图 1 那个空白第 5 卡就是这个错位的产物 |
| 6. 「个人」分组硬编码 | nav-label「个人」永远在底部 | 原系统没有「个人」分组，只在底部固定一个"账号设置"+ UserBlock | 我凭空多了一个分组，违反原系统结构 |
| 7. 部门 = 工作区 | ws-name = "知岸科技"（团队=部门？错） | ws-name = 团队全称，部门是独立 DepartmentPicker | 我把两个概念揉成一坨 |

---

## 三、用户截图复盘

### 截图 1（使用情况 4 卡挤 1 空）
- 我做的是 5 卡 grid：资料库/已上传/整理中(空白)/已可提问/近 7 日
- 原系统是 4 卡：资料库/已上传/已可提问/近 7 日
- "3 篇整理中"应该是"已上传文件"卡内的 footer link 链接，不是第 3 张独立卡
- 那个空白 .stat-card + `›` 箭头 = 我把 footer link 错误提到第 3 卡位

### 截图 2（sidebar 1 个 ws-switch 框 + 单段 nav）
- 我做的：品牌 + 1 个 ws-switch（"知岸科技"）+ 工作区 nav + 个人 nav
- 原系统：品牌 + ws-seg 二段（我的空间/知岸科技 + 全称 popover）+ DepartmentPicker + 单段 nav（按权限变化）
- 右侧「管理员 admin@zhian.ai」头像块我做了，原系统是放在 ws-seg 之外、nav 底部

---

## 四、修正方案（v0 阶段 — 先做 1 页样板）

### 4.1 修正目标（Dashboard 样板）

1. **`.ws-switch` → `.ws-seg`** 二段切换
   - 左侧：`<button data-ws="personal" class="on">我的空间</button>`（active 态用 `--action`）
   - 右侧：`<button data-ws="team">知岸科技</button> + <button class="ws-fullname-btn" aria-expanded="false" aria-label="查看团队全称">›</button>`
   - JS：点击「我的空间」切 active 态 + 隐藏 admin 4 项 + 显示「个人空间」提示
   - JS：点击「知岸科技」切 active 态 + 显示 admin 4 项 + DepartmentPicker 出现
   - JS：点击 `›` 弹 popover（"知岸科技"全称 + 复制按钮）

2. **加 DepartmentPicker**（紧跟 ws-seg 之后）
   - 默认显示"未选择部门"+ chevron
   - 点击弹 popover（部门树，未加入团队时 disabled）

3. **admin nav 条件渲染**
   - 工作区 = 我的空间 → 隐藏：组织与部门/成员管理/团队设置/操作审计；只保留：概览/资料库/对话/账号设置
   - 工作区 = 团队空间 + admin → 上面 4 项全部显示
   - 工作区 = 团队空间 + 普通成员 → 显示"团队成员"（只读入口）

4. **stat 网格 4 卡**
   - 4 列（桌面） / 2×2（移动）
   - 已上传文件卡 footer 注入 "3 篇整理中"链接

5. **移除"个人"分组 + 移动"账号设置"到底部 + UserBlock**
   - nav-label 删除"个人"
   - "账号设置"作为最底 nav-item
   - 紧跟其下是 UserBlock（管理员 头像 + admin@zhian.ai）

### 4.2 验收口径（v0 样板）
- [ ] 侧栏顶部是 `.ws-seg` 二段（不再是 `.ws-switch` 单点）
- [ ] 切到「我的空间」admin 4 项消失
- [ ] 切到「知岸科技」admin 4 项出现 + DepartmentPicker 出现
- [ ] stat 网格 4 卡，无第 5 空卡
- [ ] "3 篇整理中"作为「已上传文件」卡内 footer link（不是独立卡）
- [ ] 移动端窄屏不破版
- [ ] 视觉分项：和原系统 12 页一致

### 4.3 推广规则（等样板审过再做）
- 12 页同源修改：把 `.ws-switch` 全替为 `.ws-seg`，加 DepartmentPicker，admin 条件渲染
- 复用样板 CSS/JS（写为可复用片段）
- 推广时同时给每个预览的"当前角色"打标签（admin / 普通成员 / 未加入团队），3 套 nav 都能切到

---

## 五、为什么不早发现

我犯了一个反复犯的错误：**只看 CSS/JS 校验 + 自己画的截图，没去读原 `frontend/src/components/` 源码**。原 `WorkspaceSwitcher.tsx` 27 行就把个人/团队/admin/部门 4 件事讲清楚了，我没读，所以连"有 ws-seg 二段控件"都不知道。

**根因**：我建预览时是从"好看的设计稿"出发，**没把原 `frontend/src/` 当成 SSOT**。正确做法是：先 `codebase_explore` 把原系统的核心组件树摸清，再用 HTML 预览 1:1 复刻组件树（不是凭印象画）。

---

## 六、阶段计划

| 阶段 | 内容 | 状态 |
|------|------|------|
| v0 | 跑偏清单 + Dashboard 样板修复 | 当前 |
| v1 | 审 Dashboard 样板 + 用户确认 | 待 |
| v2 | 12 页全站升级 .ws-seg + DepartmentPicker + admin 条件渲染 | 待 |
| v3 | 三角色视角（admin / 普通成员 / 未加入团队）预览各加一版 | 待 |
| v4 | 同步回代码（design-system 预览变量 → Tailwind theme 扩展） | 待 |
