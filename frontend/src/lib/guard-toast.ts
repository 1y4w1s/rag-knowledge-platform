/** Guard redirect toasts (T1～T3). T4 lives in workspace-context. */

export const GUARD_TOAST = {
  T1: "无权限访问该页面",
  T2: "请先切换到团队工作区",
  T3: "该资源不在当前工作区",
} as const;
