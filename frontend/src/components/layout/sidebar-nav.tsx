import { Link, useLocation } from "react-router-dom";
import type { ReactNode, ReactElement } from "react";

import { cn } from "@/lib/utils";
import { RuigeLogo } from "@/components/brand/RuigeLogo";

interface SidebarNavItemProps {
  to: string;
  children: ReactNode;
  match?: (pathname: string) => boolean;
  end?: boolean;
  icon?: ReactElement;
}

export function SidebarNavItem({ to, children, match, end, icon }: SidebarNavItemProps) {
  const { pathname } = useLocation();
  const active = match ? match(pathname) : end ? pathname === to : pathname.startsWith(to);

  return (
    <Link
      to={to}
      aria-current={active ? "page" : undefined}
      className={cn(
        "nav-item relative flex items-center gap-2.5 rounded-[10px] px-3 py-[9px] text-[0.82rem] transition-colors",
        "text-[color:var(--mut)] hover:bg-[var(--nav-on)] hover:text-foreground",
        active && "nav-active-pill",
      )}
    >
      {active ? (
        <span
          className="pointer-events-none absolute bottom-2 left-0 top-2 w-[3px] rounded-full"
          style={{ backgroundImage: "var(--brand-grad)" }}
        />
      ) : null}
      {icon ? <span className="nav-item-icon h-[18px] w-[18px] shrink-0">{icon}</span> : null}
      <span className="truncate">{children}</span>
    </Link>
  );
}

export function BrandMark() {
  return <RuigeLogo size={24} />;
}

export function isKbNavActive(pathname: string): boolean {
  if (pathname === "/knowledge-bases") return true;
  return /^\/knowledge-bases\/[^/]+$/.test(pathname);
}

export function isChatNavActive(pathname: string): boolean {
  if (pathname === "/ask") return true;
  return /^\/knowledge-bases\/[^/]+\/chat$/.test(pathname);
}
