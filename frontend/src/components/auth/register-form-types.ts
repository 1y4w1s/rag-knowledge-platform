/** WS-1-2 · 注册三步 wizard 状态（W5+-1 UI） */

export type RegisterUsage = "personal" | "team";

export type RegisterTeamRole = "creator" | "member";

/** 1 = 用法 · 2 = 团队角色（仅 team）· 3 = 登录信息 */
export type RegisterWizardStep = 1 | 2 | 3;

export interface RegisterWizardState {
  step: RegisterWizardStep;
  usage: RegisterUsage | null;
  teamRole: RegisterTeamRole | null;
  orgName: string;
  inviteCode: string;
}
