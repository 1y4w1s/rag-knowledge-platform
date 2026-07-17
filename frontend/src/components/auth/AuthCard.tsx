import type { ReactNode } from "react";

import { RuigeLogo } from "@/components/brand/RuigeLogo";

interface AuthCardProps {
  children: ReactNode;
}

/**
 * 认证表单壳（v4）：窄栏居中漂浮，无厚重白卡片边框/投影。
 * 路由与字段逻辑仍由各 Page / Form 负责。
 */
export function AuthCard({ children }: AuthCardProps) {
  return (
    <div className="relative flex w-full max-w-[380px] flex-col">{children}</div>
  );
}

/** Logo + 字标；不再附产品说明书（v4 安静气质）。 */
export function AuthCardBrand() {
  return (
    <header className="mb-8">
      <RuigeLogo size={36} withWordmark />
    </header>
  );
}

interface AuthCardBodyProps {
  children: ReactNode;
}

/** 表单主体：固定最小高度，登录/注册切换少跳动 */
export function AuthCardBody({ children }: AuthCardBodyProps) {
  return (
    <div className="flex min-h-[360px] flex-1 flex-col">{children}</div>
  );
}
