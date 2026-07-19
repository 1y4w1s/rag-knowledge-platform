export interface EmptyStep {
  title: string;
  desc: string;
  meta: string;
  /** lucide icon name or inline svg path */
  iconPath: string;
}

export interface EmptyMetric {
  title: string;
  desc: string;
  cta: string;
  iconPath: string;
}

export interface EmptyStateScene {
  /** 唯一前缀，用于生成 id 避免冲突 */
  idPrefix: string;
  eyebrow: string;
  title: React.ReactNode;
  desc: React.ReactNode;
  ctaPrimary: { label: string; iconPath: string; onClick?: () => void };
  ctaSecondary: { label: string; iconPath: string; onClick?: () => void };
  ctaInvite: { label: string; iconPath: string };
  stats: [string, string][];
  steps: EmptyStep[];
  metrics: EmptyMetric[];
  ragTitle: string;
  ragDesc: string;
  ragCta: string;
  inviteLabel: string;
  inviteSub: string;
  inviteLink: string;
  /** 邀请弹窗是否需要"协作"角色 */
  inviteRoles?: ("admin" | "member")[];
  showSimpleToggle?: boolean;
}

export const PATHS = {
  plus: "M12 5v14M5 12h14",
  upload: "M14 3v5h5M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8Z",
  doc: "M12 3 3 7.5 12 12l9-4.5L12 3Z",
  message: "M21 12a8 8 0 0 1-11.5 7.2L4 21l1.8-5.5A8 8 0 1 1 21 12Z",
  userPlus:
    "M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2M9 7a4 4 0 1 0 0-8 4 4 0 0 0 0 8M22 11h-6M19 8v6",
  search: "M21 21l-4.3-4.3M11 19a8 8 0 1 0 0-16 8 8 0 0 0 0 16Z",
  settings: "M12 5v14M5 12h14",
  shield: "M9 5H7a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2h-2",
  bell: "M3 8l9 6 9-6M3 8v10a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V8",
  credit: "M3 7a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2zM3 11h18",
  refresh: "M21 12a9 9 0 1 1-3-6.7L21 8M21 3v5h-5",
  folder: "M4 7a2 2 0 0 1 2-2h5l2 2h5a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2z",
  list: "M9 5H7a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2h-2",
  question: "M9.2 9a3 3 0 0 1 5.5 1.5c0 2-2.7 2.5-2.7 2.5M12 17h.01",
  arrowRight: "M5 12h14M12 5l7 7-7 7",
  spark: "M12 3v4M12 17v4M3 12h4M17 12h4",
};

export const DEFAULT_INVITE_ROLES = [
  { key: "admin", label: "管理员" },
  { key: "member", label: "成员" },
] as const;
