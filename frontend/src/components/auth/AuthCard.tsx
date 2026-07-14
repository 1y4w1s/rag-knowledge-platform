import type { ReactNode } from "react";

import { RuigeLogo } from "@/components/brand/RuigeLogo";

interface AuthCardProps {
  children: ReactNode;
}

/** 登录/注册统一卡片：560×640 · 暖白 + 赤陶橙阴影（DESIGN-4） */
export function AuthCard({ children }: AuthCardProps) {
  return (
    <div
      className="relative flex w-[560px] min-h-[640px] max-w-[calc(100vw-3rem)] flex-col rounded-2xl border p-10"
      style={{
        backgroundColor: "var(--auth-card)",
        borderColor: "var(--auth-card-border)",
        boxShadow: "var(--auth-shadow)",
      }}
    >
      <span
        aria-hidden
        className="pointer-events-none absolute inset-x-0 top-0 h-[3px] rounded-t-2xl"
        style={{ backgroundImage: "var(--brand-grad)" }}
      />
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 rounded-2xl ring-1 ring-inset ring-[color:rgb(203_107_61/0.06)]"
      />
      {children}
    </div>
  );
}

export function AuthCardBrand() {
  return (
    <header className="mb-7 flex flex-col items-center text-center">
      <RuigeLogo size={44} withWordmark className="justify-center" />
      <span
        aria-hidden
        className="mt-3 h-[3px] w-9 rounded-full"
        style={{ backgroundImage: "var(--brand-grad)" }}
      />
      <p className="mx-auto mt-4 max-w-[420px] text-sm leading-relaxed text-[var(--auth-muted)]">
        团队资料库智能问答。上传文档、按库对话，每条回答附带可展开的引用来源与页码定位。
      </p>
    </header>
  );
}

interface AuthCardBodyProps {
  children: ReactNode;
}

/** 表单主体区：固定最小高度，登录/注册切换不跳动 */
export function AuthCardBody({ children }: AuthCardBodyProps) {
  return (
    <div className="flex min-h-[420px] flex-1 flex-col">{children}</div>
  );
}
