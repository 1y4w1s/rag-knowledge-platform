import "@/components/ui/EmptyState/empty-state.css";
export { EmptyStateV44 } from "./EmptyStateV44";
export type { EmptyStateScene, EmptyStep, EmptyMetric } from "./types";
export { PATHS, DEFAULT_INVITE_ROLES } from "./types";

import type { EmptyStateScene } from "./types";
import { PATHS } from "./types";

function createScene(
  v: Omit<EmptyStateScene, "inviteRoles">
): EmptyStateScene {
  return { ...v, inviteRoles: ["admin", "editor", "viewer", "collaborator"] };
}

/** Dashboard v4.4 空态场景配置 */
export const DASHBOARD_SCENE: EmptyStateScene = createScene({
  idPrefix: "dash",
  eyebrow: "0 资料库 · 0 篇文档",
  title: (
    <>
      把散落的资料，<em>串成可被问的知识</em>
    </>
  ),
  desc: (
    <>
      建一个资料库，上传 PDF / Word / 飞书文档 / 链接，几分钟后你就能像问同事一样问它：
      <b>出处</b>·<b>时效</b>·<b>关联</b>·<b>引用</b>，全部带在身上。
    </>
  ),
  ctaPrimary: { label: "新建第一个资料库", iconPath: PATHS.plus },
  ctaSecondary: { label: "批量上传文档", iconPath: PATHS.upload },
  ctaInvite: { label: "邀请同事", iconPath: PATHS.userPlus },
  stats: [
    ["≈ 30 秒", "开始整理"],
    ["10 格式", "原生支持"],
    ["50+", "问答模板"],
    ["端到端", "出处溯源"],
  ],
  steps: [
    {
      title: "新建资料库",
      desc: "给一组相关文档起个名字。比如「Q3 战略」、「产品规范」、「客户案例」。",
      meta: "30 秒即可完成",
      iconPath: PATHS.plus,
    },
    {
      title: "批量上传文档",
      desc: "拖入或选择文件，支持 PDF / Word / 飞书 / 链接 / Notion 页面。每批最多 50 个。",
      meta: "平均 30 秒开始整理",
      iconPath: PATHS.upload,
    },
    {
      title: "开始带引用的对话",
      desc: "用自然语言问任何问题，答案带原文出处 + 段落定位 + 关联文档。",
      meta: "50+ 模板可直接套用",
      iconPath: PATHS.message,
    },
  ],
  metrics: [
    {
      title: "资料库数",
      desc: "用来组织同一主题的文档集合。比如「Q3 战略」、「产品规范」、「客户案例」。",
      cta: "创建第一个资料库",
      iconPath: PATHS.doc,
    },
    {
      title: "已上传文档",
      desc: "上传后系统会立即开始整理，平均 30 秒一篇。整理中会显示在「整理中」列表。",
      cta: "上传第一份文档",
      iconPath: PATHS.folder,
    },
    {
      title: "可问答文档",
      desc: "整理完成的文件会被索引到问答系统，所有答案都带原文出处，可点击跳转回段落。",
      cta: "先体验一下问答",
      iconPath: PATHS.question,
    },
    {
      title: "本周提问",
      desc: "记录你和团队的提问历史，统计谁在问什么、哪些问题被多次问过，辅助选题。",
      cta: "看看历史对话",
      iconPath: PATHS.message,
    },
  ],
  ragTitle: "可读段落数 · 出处附带率 · 找资料耗时 · 上次质量评估",
  ragDesc: "所有指标均可追溯到具体文档与整理批次。准备好后，4 个数字会出现在这里。",
  ragCta: "先看看问答长什么样",
  inviteLabel: "邀请同事一起用",
  inviteSub: "生成一个邀请链接，提供 50+ 邀请模板，按团队 / 部门 / 角色自动填好。",
  inviteLink: "zhi-an.cn/i/8K2F-3N9P",
});

/** KBs v4.4 空态场景配置（与 DASHBOARD 同源，文案适配资料库列表） */
export const KBS_SCENE: EmptyStateScene = createScene({
  idPrefix: "kbs",
  eyebrow: "0 资料库 · 0 篇文档",
  title: (
    <>
      把散落的资料，<em>串成可被问的知识</em>
    </>
  ),
  desc: (
    <>
      建一个资料库，上传 PDF / Word / 飞书文档 / 链接，几分钟后你就能像问同事一样问它：
      <b>出处</b>·<b>时效</b>·<b>关联</b>·<b>引用</b>，全部带在身上。
    </>
  ),
  ctaPrimary: { label: "新建第一个资料库", iconPath: PATHS.plus },
  ctaSecondary: { label: "批量上传文档", iconPath: PATHS.upload },
  ctaInvite: { label: "邀请同事", iconPath: PATHS.userPlus },
  stats: [
    ["≈ 30 秒", "开始整理"],
    ["10 格式", "原生支持"],
    ["50+", "问答模板"],
    ["端到端", "出处溯源"],
  ],
  steps: [
    {
      title: "新建资料库",
      desc: "给一组相关文档起个名字。比如「Q3 战略」、「产品规范」、「客户案例」。",
      meta: "30 秒即可完成",
      iconPath: PATHS.plus,
    },
    {
      title: "批量上传文档",
      desc: "拖入或选择文件，支持 PDF / Word / 飞书 / 链接 / Notion 页面。每批最多 50 个。",
      meta: "平均 30 秒开始整理",
      iconPath: PATHS.upload,
    },
    {
      title: "开始带引用的对话",
      desc: "用自然语言问任何问题，答案带原文出处 + 段落定位 + 关联文档。",
      meta: "50+ 模板可直接套用",
      iconPath: PATHS.message,
    },
  ],
  metrics: [
    {
      title: "本地知识库",
      desc: "你创建的所有资料库都在这里。支持替换、版本对比、按标签筛选。",
      cta: "创建第一个知识库",
      iconPath: PATHS.folder,
    },
    {
      title: "团队空间",
      desc: "切换到团队工作区后，可看到团队共享的资料库，按角色授权访问。",
      cta: "进入团队空间",
      iconPath: PATHS.userPlus,
    },
    {
      title: "模板库",
      desc: "所有提问模板（按角色 / 按时效 / 对比 / 翻译）都可在这里查看与复用。",
      cta: "看看模板库",
      iconPath: PATHS.list,
    },
    {
      title: "智能问答",
      desc: "选中资料库后，答案带原文出处，可点击跳转到具体段落。",
      cta: "先体验问答",
      iconPath: PATHS.question,
    },
  ],
  ragTitle: "可读段落数 · 出处附带率 · 找资料耗时 · 上次质量评估",
  ragDesc: "所有指标均可追溯到具体文档与整理批次。准备好后，4 个数字会出现在这里。",
  ragCta: "先看看问答长什么样",
  inviteLabel: "邀请同事一起用",
  inviteSub: "生成一个邀请链接，提供 50+ 邀请模板，按团队 / 部门 / 角色自动填好。",
  inviteLink: "zhi-an.cn/i/8K2F-3N9P",
});

/** KB 详情 v4.4 空态（无文档） */
export const KBDETAIL_SCENE: EmptyStateScene = createScene({
  idPrefix: "kd",
  eyebrow: "0 文档 · 0 段已索引",
  title: (
    <>
      把这一份资料，<em>做成可被问的知识</em>
    </>
  ),
  desc: (
    <>
      新建的资料库还没有文档。拖入 PDF / Word / 飞书链接，几分钟后这里就会出现
      <b>可问</b>的章节、可点的出处、可对照的版本。
    </>
  ),
  ctaPrimary: { label: "上传第一份文档", iconPath: PATHS.upload },
  ctaSecondary: { label: "批量上传", iconPath: PATHS.plus },
  ctaInvite: { label: "邀请协作者", iconPath: PATHS.userPlus },
  stats: [
    ["30 秒", "开始整理"],
    ["10 格式", "原生支持"],
    ["自动分段", "智能识别"],
    ["可回滚", "版本管理"],
  ],
  steps: [
    {
      title: "拖入或选择文件",
      desc: "支持 PDF / Word / 飞书 / Notion / 链接，每批最多 50 个。",
      meta: "智能识别目录结构",
      iconPath: PATHS.plus,
    },
    {
      title: "等待自动整理",
      desc: "平均 30 秒一篇，会显示在「整理中」列表。",
      meta: "整理完成自动通知",
      iconPath: PATHS.upload,
    },
    {
      title: "开始带引用的对话",
      desc: "每个答案都带原文段落定位，可点击跳回原文档。",
      meta: "50+ 模板可直接套用",
      iconPath: PATHS.message,
    },
  ],
  metrics: [
    {
      title: "文档数",
      desc: "你上传的所有文件都在这里。支持替换、版本对比、按标签筛选。",
      cta: "上传第一份文档",
      iconPath: PATHS.doc,
    },
    {
      title: "已索引段落",
      desc: "整理完成的段落会被索引到问答系统；准备中显示在「整理中」列表。",
      cta: "看整理进度",
      iconPath: PATHS.list,
    },
    {
      title: "本周提问",
      desc: "你和团队对这个 KB 的提问会留在这里，可按时间 / 提问人筛选。",
      cta: "先体验问答",
      iconPath: PATHS.question,
    },
    {
      title: "协作者",
      desc: "可邀请其他成员按角色加入：管理员 / 编辑者 / 访客 / 协作者。",
      cta: "邀请协作者",
      iconPath: PATHS.userPlus,
    },
  ],
  ragTitle: "整理完成度 · 段落命中率 · 提问速度",
  ragDesc: "所有指标都可追溯到具体文档与整理批次，准备好后 3 个数字会显示在这里。",
  ragCta: "先看看整理后的样子",
  inviteLabel: "邀请协作者一起整理",
  inviteSub: "可按角色（管理员 / 编辑者 / 访客 / 协作者）发送；也可生成链接让对方在 7 天内自助加入。",
  inviteLink: "zhi-an.cn/kb/q3/8K2F-3N9P",
});

/** Ask v4.4 空态（暂无可用资料库） */
export const ASK_SCENE: EmptyStateScene = createScene({
  idPrefix: "ask",
  eyebrow: "0 资料库已选 · 0 段可查",
  title: (
    <>
      把问题<em>问给正确的资料库</em>
    </>
  ),
  desc: (
    <>
      选一个资料库，提问会<b>只在那里面找</b>；选多个就能跨库对比；一个都不选就用
      <b>全局</b>检索（仍然带出处）。
    </>
  ),
  ctaPrimary: { label: "选择资料库", iconPath: PATHS.folder },
  ctaSecondary: { label: "导入新资料库", iconPath: PATHS.plus },
  ctaInvite: { label: "把资料库分享给团队", iconPath: PATHS.userPlus },
  stats: [
    ["1 步", "选资料库"],
    ["10 模板", "直接套用"],
    ["出处", "段落级"],
    ["30 秒", "平均响应"],
  ],
  steps: [
    {
      title: "选资料库",
      desc: "从左侧抽屉勾选 1 个或多个资料库；不选就用全局检索。",
      meta: "支持 1-20 个资料库",
      iconPath: PATHS.plus,
    },
    {
      title: "写提示词",
      desc: "顶部模板一键填入；支持「按角色」「按时效」「对比 2 份」等预设。",
      meta: "可保存为团队共享模板",
      iconPath: PATHS.upload,
    },
    {
      title: "看答案 + 出处",
      desc: "答案会列出引用段落，鼠标悬停高亮原文，点击跳转到对应位置。",
      meta: "出处永久可回链",
      iconPath: PATHS.message,
    },
  ],
  metrics: [
    {
      title: "已选资料库",
      desc: "选中的资料库会出现在这里，可拖动排序改变检索权重。",
      cta: "去选择资料库",
      iconPath: PATHS.folder,
    },
    {
      title: "模板库",
      desc: "所有提问模板（按角色 / 按时效 / 对比 / 翻译）都可在这里查看与复用。",
      cta: "看模板库",
      iconPath: PATHS.list,
    },
    {
      title: "本周提问",
      desc: "你和团队最近的提问都会留在这里，可按时间 / 资料库 / 提问人筛选。",
      cta: "看历史提问",
      iconPath: PATHS.question,
    },
    {
      title: "引用率",
      desc: "答案带原文出处的比例。100% 表示每个回答都能跳回原文。",
      cta: "了解出处机制",
      iconPath: PATHS.message,
    },
  ],
  ragTitle: "提问质量 · 答案命中率 · 出处完备率",
  ragDesc: "所有指标都可追溯到具体资料库与提问，准备好后 3 个数字会显示在这里。",
  ragCta: "先看看问答长什么样",
  inviteLabel: "把资料库分享给团队",
  inviteSub: "把某个资料库单独共享给同事或部门，对方只能看到这个 KB，无法访问其他内容。",
  inviteLink: "zhi-an.cn/share/kb/9X7Y-2K4M",
});

/** 成员 v4.4 空态（仅自己一人） */
export const MEMBERS_SCENE: EmptyStateScene = createScene({
  idPrefix: "mb",
  eyebrow: "1 成员 · 0 邀请中",
  title: (
    <>
      现在就你一个，<em>把同事拉进来</em>
    </>
  ),
  desc: (
    <>
      团队刚建好，<b>只有你</b>。把同事加进来后，可以按角色分配权限、批量导入、
      <b>同步到飞书 / 钉钉 / 企微</b>。
    </>
  ),
  ctaPrimary: { label: "邀请第一位成员", iconPath: PATHS.userPlus },
  ctaSecondary: { label: "刷新成员列表", iconPath: PATHS.refresh },
  ctaInvite: { label: "邀请同事", iconPath: PATHS.userPlus },
  stats: [
    ["30 秒", "发一个邀请"],
    ["3 角色", "管理员/成员/访客"],
    ["SSO", "飞书/钉钉/企微"],
    ["审计", "操作留痕"],
  ],
  steps: [
    {
      title: "生成邀请码",
      desc: "一键生成邀请码或链接，可设有效期 1 / 7 / 30 天，或永久有效。",
      meta: "支持批量导入",
      iconPath: PATHS.plus,
    },
    {
      title: "同事扫码加入",
      desc: "同事在注册页选择「团队 · 成员」并填写邀请码即可加入。",
      meta: "可对接 SSO",
      iconPath: PATHS.upload,
    },
    {
      title: "按角色分配权限",
      desc: "支持管理员 / 成员 / 访客 3 角色；可按部门 / 资料库精细授权。",
      meta: "审计日志可导出",
      iconPath: PATHS.message,
    },
  ],
  metrics: [
    {
      title: "成员数",
      desc: "你团队里所有成员都会出现在这里，支持按角色 / 部门 / 状态筛选。",
      cta: "邀请第一位成员",
      iconPath: PATHS.userPlus,
    },
    {
      title: "邀请中",
      desc: "已发但还没被接受的邀请；可撤销、重新发送、或延长有效期。",
      cta: "看邀请记录",
      iconPath: PATHS.list,
    },
    {
      title: "角色配置",
      desc: "所有角色的权限矩阵在这里管理；可按资料库 / 部门 / 操作类型精细授权。",
      cta: "配置角色",
      iconPath: PATHS.shield,
    },
    {
      title: "SSO 接入",
      desc: "一键接入飞书 / 钉钉 / 企微 / Azure AD，新员工自动同步。",
      cta: "接 SSO",
      iconPath: PATHS.settings,
    },
  ],
  ragTitle: "成员增长率 · SSO 覆盖率 · 操作审计完整度",
  ragDesc: "所有指标都可追溯到具体成员与时间点，准备好后 3 个数字会显示在这里。",
  ragCta: "看成员管理长什么样",
  inviteLabel: "把同事拉进来",
  inviteSub: "输入邮箱生成邀请链接；或一键从飞书 / 钉钉 / 企微导入通讯录。",
  inviteLink: "zhi-an.cn/i/8K2F-3N9P-ZR99",
});

/** 账号设置 v4.4 空态（新账号首设引导） */
export const ACCOUNT_SCENE: EmptyStateScene = createScene({
  idPrefix: "ac",
  eyebrow: "新账号 · 0 设置项",
  title: (
    <>
      第一次设置，<em>3 分钟搞定</em>
    </>
  ),
  desc: (
    <>
      欢迎来到知岸。<b>个人资料、安全选项、通知偏好</b>都还没填。跟着下面 3 步走，未来所有功能都会按你的选择跑。
    </>
  ),
  ctaPrimary: { label: "完善个人资料", iconPath: PATHS.userPlus },
  ctaSecondary: { label: "设置安全选项", iconPath: PATHS.shield },
  ctaInvite: { label: "把设置同步到其他账号", iconPath: PATHS.userPlus },
  stats: [
    ["3 分钟", "全部完成"],
    ["4 项", "必填设置"],
    ["随时可改", "设置中心"],
    ["导入", "从飞书/钉钉"],
  ],
  steps: [
    {
      title: "填个人资料",
      desc: "昵称、头像、个人简介——其他成员会看到这些。",
      meta: "可随时修改",
      iconPath: PATHS.plus,
    },
    {
      title: "设置安全选项",
      desc: "登录密码、2FA、登录设备管理——这是账号安全的基础。",
      meta: "推荐开启 2FA",
      iconPath: PATHS.upload,
    },
    {
      title: "配置通知偏好",
      desc: "邮件、站内、微信——只选你想收到的，其余全部关掉。",
      meta: "支持 Do-Not-Disturb 时段",
      iconPath: PATHS.message,
    },
  ],
  metrics: [
    {
      title: "个人资料",
      desc: "昵称、头像、个人简介——其他成员会看到这些信息。",
      cta: "去填资料",
      iconPath: PATHS.userPlus,
    },
    {
      title: "安全设置",
      desc: "密码、2FA、登录设备、API 密钥——账号安全的全部入口。",
      cta: "去设置安全",
      iconPath: PATHS.shield,
    },
    {
      title: "通知偏好",
      desc: "邮件 / 站内 / 微信 / 飞书 / 钉钉——每个频道可单独开关。",
      cta: "配置通知",
      iconPath: PATHS.bell,
    },
    {
      title: "订阅计费",
      desc: "免费版 / 团队版 / 企业版的用量、配额、账单与发票管理。",
      cta: "看订阅方案",
      iconPath: PATHS.credit,
    },
  ],
  ragTitle: "资料完整度 · 2FA 开启率 · 通知打开率",
  ragDesc: "所有指标都可追溯到具体设置项，准备好后 3 个数字会显示在这里。",
  ragCta: "看设置中心长什么样",
  inviteLabel: "把设置同步到其他账号",
  inviteSub: "如果你同时管多个团队 / 账号，可把通知偏好和安全选项一键同步过去。",
  inviteLink: "zhi-an.cn/sync/8K2F-3N9P",
});

/** 对话 v4.4 空态（首次对话） */
export const CHAT_SCENE: EmptyStateScene = createScene({
  idPrefix: "ct",
  eyebrow: "0 对话 · 0 提问",
  title: (
    <>
      第一次对话，<em>就从一个真实问题开始</em>
    </>
  ),
  desc: (
    <>
      你还没有任何对话记录。新建一个会话，<b>带出处的答案</b>会留在这里；
      <b>同一资料库的对话</b>会自动归类；可分享给同事继续问下去。
    </>
  ),
  ctaPrimary: { label: "开始第一次对话", iconPath: PATHS.message },
  ctaSecondary: { label: "选一个资料库", iconPath: PATHS.folder },
  ctaInvite: { label: "把对话分享给同事", iconPath: PATHS.userPlus },
  stats: [
    ["30 秒", "开始第一次"],
    ["50+ 模板", "直接套用"],
    ["出处", "段落级"],
    ["团队共享", "无缝衔接"],
  ],
  steps: [
    {
      title: "选资料库",
      desc: "决定答案在哪些文档里找。1 个、多个、或全部——选错也不怕，可随时切换。",
      meta: "支持 1-20 个资料库",
      iconPath: PATHS.plus,
    },
    {
      title: "输入问题",
      desc: "顶部直接打字或选模板。支持「按角色」「按时效」「对比 2 份」等预设。",
      meta: "支持 50+ 模板",
      iconPath: PATHS.upload,
    },
    {
      title: "查看带出处的答案",
      desc: "答案会列出引用段落，鼠标悬停高亮原文，点击跳转到对应位置。",
      meta: "段落级出处",
      iconPath: PATHS.message,
    },
  ],
  metrics: [
    {
      title: "对话数",
      desc: "你和团队的对话都会留在这里；支持按资料库 / 时间 / 提问人筛选。",
      cta: "去问第一个问题",
      iconPath: PATHS.message,
    },
    {
      title: "提问数",
      desc: "所有提问会留底，可看「被多次问的问题」辅助团队选题。",
      cta: "看热门问题",
      iconPath: PATHS.question,
    },
    {
      title: "本周热门",
      desc: "按提问频次排序的真实问题，帮团队找到大家都关心的内容。",
      cta: "看提问分布",
      iconPath: PATHS.list,
    },
    {
      title: "团队分享",
      desc: "可把对话分享给同事继续问；可一键转为知识库文章。",
      cta: "把对话转文章",
      iconPath: PATHS.userPlus,
    },
  ],
  ragTitle: "对话轮次 · 提问速度 · 答案命中率",
  ragDesc: "所有指标都可追溯到具体对话与提问，准备好后 3 个数字会显示在这里。",
  ragCta: "先看看对话长什么样",
  inviteLabel: "把对话分享给同事",
  inviteSub: "把这次问答的链接发给同事，对方可直接接着问；权限可设为「只读」或「可继续」。",
  inviteLink: "zhi-an.cn/c/8K2F-3N9P-X7YQ",
});
