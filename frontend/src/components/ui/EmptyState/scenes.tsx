import "@/components/ui/EmptyState/empty-state.css";
export { EmptyStateV44 } from "./EmptyStateV44";
export type { EmptyStateScene, EmptyStep, EmptyMetric } from "./types";
export { PATHS, DEFAULT_INVITE_ROLES } from "./types";

import type { EmptyStateScene } from "./types";
import { PATHS } from "./types";

function createScene(
  v: Omit<EmptyStateScene, "inviteRoles">
): EmptyStateScene {
  return { ...v, inviteRoles: ["admin", "member"] };
}

/** Dashboard 空态 */
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
      建一个资料库，上传 PDF / Word / Markdown 文档，几分钟后就能像问同事一样问它：
      <b>出处</b>·<b>引用</b>，全部带在身上。
    </>
  ),
  ctaPrimary: { label: "新建第一个资料库", iconPath: PATHS.plus },
  ctaSecondary: { label: "批量上传文档", iconPath: PATHS.upload },
  ctaInvite: { label: "邀请同事", iconPath: PATHS.userPlus },
  stats: [
    ["30 秒", "开始整理"],
    ["10 格式", "原生支持"],
    ["出处", "引用溯源"],
    ["RAG", "智能问答"],
  ],
  steps: [
    {
      title: "新建资料库",
      desc: "给一组相关文档起个名字。比如「Q3 战略」、「产品规范」。",
      meta: "30 秒即可完成",
      iconPath: PATHS.plus,
    },
    {
      title: "上传文档",
      desc: "拖入或选择文件，支持 PDF / Word / Markdown / Excel / PPT。",
      meta: "平均 30 秒开始整理",
      iconPath: PATHS.upload,
    },
    {
      title: "开始带引用的对话",
      desc: "用自然语言提问，答案带原文出处 + 段落定位。",
      meta: "出处可点击跳转",
      iconPath: PATHS.message,
    },
  ],
  metrics: [],
  ragTitle: "",
  ragDesc: "",
  ragCta: "",
  inviteLabel: "邀请同事",
  inviteSub: "生成邀请链接，同事注册后加入团队空间。",
  inviteLink: "",
});

/** KBs 列表空态 */
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
      建一个资料库，上传 PDF / Word / Markdown 文档，几分钟后你就能像问同事一样问它：
      <b>出处</b>·<b>引用</b>，全部带在身上。
    </>
  ),
  ctaPrimary: { label: "新建第一个资料库", iconPath: PATHS.plus },
  ctaSecondary: { label: "批量上传文档", iconPath: PATHS.upload },
  ctaInvite: { label: "邀请同事", iconPath: PATHS.userPlus },
  stats: [
    ["30 秒", "开始整理"],
    ["10 格式", "原生支持"],
    ["出处", "引用溯源"],
    ["RAG", "智能问答"],
  ],
  steps: [
    {
      title: "新建资料库",
      desc: "给一组相关文档起个名字。比如「Q3 战略」、「产品规范」。",
      meta: "30 秒即可完成",
      iconPath: PATHS.plus,
    },
    {
      title: "上传文档",
      desc: "拖入或选择文件，支持 PDF / Word / Markdown / Excel / PPT。",
      meta: "平均 30 秒开始整理",
      iconPath: PATHS.upload,
    },
    {
      title: "开始带引用的对话",
      desc: "用自然语言提问，答案带原文出处 + 段落定位。",
      meta: "出处可点击跳转",
      iconPath: PATHS.message,
    },
  ],
  metrics: [],
  ragTitle: "",
  ragDesc: "",
  ragCta: "",
  inviteLabel: "邀请同事",
  inviteSub: "生成邀请链接，同事注册后加入团队空间。",
  inviteLink: "",
});

/** KB 详情空态（无文档） */
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
      新建的资料库还没有文档。拖入 PDF / Word / Markdown，几分钟后这里就会出现
      <b>可问</b>的章节、可点的出处。
    </>
  ),
  ctaPrimary: { label: "上传第一份文档", iconPath: PATHS.upload },
  ctaSecondary: { label: "批量上传", iconPath: PATHS.plus },
  ctaInvite: { label: "邀请协作者", iconPath: PATHS.userPlus },
  stats: [
    ["30 秒", "开始整理"],
    ["10 格式", "原生支持"],
    ["自动分段", "智能识别"],
    ["出处", "段落级"],
  ],
  steps: [
    {
      title: "拖入或选择文件",
      desc: "支持 PDF / Word / Markdown / Excel / PPT。",
      meta: "自动识别文档结构",
      iconPath: PATHS.plus,
    },
    {
      title: "等待自动整理",
      desc: "平均 30 秒一篇，整理完成即可提问。",
      meta: "整理完成后自动索引",
      iconPath: PATHS.upload,
    },
    {
      title: "开始带引用的对话",
      desc: "每个答案都带原文段落定位，可点击跳回原文档。",
      meta: "出处可点击跳转",
      iconPath: PATHS.message,
    },
  ],
  metrics: [],
  ragTitle: "",
  ragDesc: "",
  ragCta: "",
  inviteLabel: "邀请协作者",
  inviteSub: "生成邀请链接，对方加入后可在该资料库协作。",
  inviteLink: "",
});

/** Ask 空态（暂无可用资料库） */
export const ASK_SCENE: EmptyStateScene = createScene({
  idPrefix: "ask",
  eyebrow: "0 对话 · 0 提问",
  title: (
    <>
      第一次对话，<em>就从一个真实问题开始</em>
    </>
  ),
  desc: (
    <>
      选一个资料库，提问会<b>只在那里面找</b>；不选资料库就用<b>全局</b>检索。
      每个答案都带原文出处。
    </>
  ),
  ctaPrimary: { label: "开始第一次对话", iconPath: PATHS.message },
  ctaSecondary: { label: "选一个资料库", iconPath: PATHS.folder },
  ctaInvite: { label: "把对话分享给同事", iconPath: PATHS.userPlus },
  stats: [
    ["1 步", "选资料库"],
    ["出处", "段落级"],
    ["全局", "跨库检索"],
    ["溯源", "可点击跳转"],
  ],
  steps: [
    {
      title: "选资料库",
      desc: "从左侧抽屉勾选 1 个或多个资料库；不选就用全局检索。",
      meta: "可随时切换",
      iconPath: PATHS.plus,
    },
    {
      title: "输入问题",
      desc: "直接打字提问，答案基于选中资料库的内容生成。",
      meta: "自然语言提问",
      iconPath: PATHS.upload,
    },
    {
      title: "看答案 + 出处",
      desc: "答案会列出引用段落，点击可跳转到原文对应位置。",
      meta: "段落级出处",
      iconPath: PATHS.message,
    },
  ],
  metrics: [],
  ragTitle: "",
  ragDesc: "",
  ragCta: "",
  inviteLabel: "把对话分享给同事",
  inviteSub: "分享对话链接，对方可直接查看。",
  inviteLink: "",
});

/** 成员空态（仅自己一人） */
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
      团队刚建好。<b>目前只有你</b>。通过邀请码添加同事后，可按角色分配资料库权限。
    </>
  ),
  ctaPrimary: { label: "邀请第一位成员", iconPath: PATHS.userPlus },
  ctaSecondary: { label: "刷新成员列表", iconPath: PATHS.refresh },
  ctaInvite: { label: "邀请同事", iconPath: PATHS.userPlus },
  stats: [
    ["30 秒", "发一个邀请"],
    ["3 角色", "管理员/成员/访客"],
    ["审计", "操作留痕"],
    ["个人版", "免费使用"],
  ],
  steps: [
    {
      title: "生成邀请码",
      desc: "生成邀请码，同事在注册页选择「团队·成员」并填写即可加入。",
      meta: "支持管理员邀请",
      iconPath: PATHS.plus,
    },
    {
      title: "同事注册加入",
      desc: "对方填写邀请码完成注册，自动成为团队成员。",
      meta: "无需审核",
      iconPath: PATHS.upload,
    },
    {
      title: "按角色分配权限",
      desc: "支持管理员 / 成员 / 访客 3 种角色，可按资料库粒度授权。",
      meta: "权限即时生效",
      iconPath: PATHS.message,
    },
  ],
  metrics: [],
  ragTitle: "",
  ragDesc: "",
  ragCta: "",
  inviteLabel: "邀请同事",
  inviteSub: "生成邀请码，对方注册后自动加入团队。",
  inviteLink: "",
});

/** 账号设置空态（新账号首设引导） */
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
      欢迎来到睿阁。<b>昵称、密码</b>都还没填。完成下面几项即可开始使用。
    </>
  ),
  ctaPrimary: { label: "完善个人资料", iconPath: PATHS.userPlus },
  ctaSecondary: { label: "修改密码", iconPath: PATHS.shield },
  ctaInvite: { label: "加入团队", iconPath: PATHS.userPlus },
  stats: [
    ["3 分钟", "全部完成"],
    ["2 项", "必填设置"],
    ["随时可改", "设置中心"],
    ["个人版", "免费使用"],
  ],
  steps: [
    {
      title: "填昵称",
      desc: "设置显示在侧栏的昵称。",
      meta: "可随时修改",
      iconPath: PATHS.plus,
    },
    {
      title: "修改密码",
      desc: "设置登录密码。",
      meta: "推荐使用强密码",
      iconPath: PATHS.upload,
    },
    {
      title: "加入团队（可选）",
      desc: "如果有团队邀请码，可在此加入团队空间查看共享资料库。",
      meta: "个人版无需此步",
      iconPath: PATHS.message,
    },
  ],
  metrics: [],
  ragTitle: "",
  ragDesc: "",
  ragCta: "",
  inviteLabel: "加入团队",
  inviteSub: "输入团队邀请码，加入后可与同事共享资料库。",
  inviteLink: "",
});

/** ASK_SCENE 别名（兼容旧引用） */
export const CHAT_SCENE = ASK_SCENE;
