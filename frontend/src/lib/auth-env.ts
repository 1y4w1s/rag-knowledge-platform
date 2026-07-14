/** 本地答辩 / 开发：`.env.development` 设 `VITE_SHOW_DEMO_LOGIN=true`；生产构建默认不显示 */
export const showDemoLogin =
  import.meta.env.VITE_SHOW_DEMO_LOGIN === "true";

export const FORGOT_PASSWORD_HINT =
  "请联系团队管理员重置密码";
