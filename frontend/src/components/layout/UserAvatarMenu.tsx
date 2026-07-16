import { useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { getDisplayName, useAuth } from "@/lib/auth-context";
import { cn } from "@/lib/utils";

function initials(name: string): string {
  const trimmed = name.trim();
  if (!trimmed) return "U";
  return trimmed.slice(0, 2).toUpperCase();
}

interface UserAvatarMenuProps {
  size?: "sm" | "md";
  className?: string;
}

export function UserAvatarMenu({ size = "md", className }: UserAvatarMenuProps) {
  const navigate = useNavigate();
  const { user, logout } = useAuth();
  const [open, setOpen] = useState(false);
  const wrapRef = useRef<HTMLDivElement>(null);
  const [upward, setUpward] = useState(false);

  useEffect(() => {
    function onDocClick(e: MouseEvent) {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("click", onDocClick);
    return () => document.removeEventListener("click", onDocClick);
  }, []);

  useEffect(() => {
    if (!open) return;
    // 检测视口剩余空间，决定菜单向上还是向下弹出
    const el = wrapRef.current;
    if (el) {
      const rect = el.getBoundingClientRect();
      const spaceBelow = window.innerHeight - rect.bottom;
      setUpward(spaceBelow < 160);
    }
  }, [open]);

  if (!user) return null;

  const label = getDisplayName(user);
  const dim = size === "sm" ? "h-8 w-8 text-[0.72rem]" : "h-9 w-9 text-[0.78rem]";

  function handleLogout() {
    logout();
    navigate("/login", { replace: true });
  }

  return (
    <div ref={wrapRef} className={cn("relative", className)}>
      <button
        type="button"
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
        className={cn(
          "flex items-center justify-center rounded-full border border-border bg-white font-semibold text-[#52525B] transition-colors hover:border-[color:rgb(203_107_61/0.45)]",
          dim,
        )}
      >
        {initials(label)}
      </button>
      {open && (
        <div
          role="menu"
          className={`popover-base absolute left-0 z-50 min-w-[160px] ${upward ? "bottom-[calc(100%+8px)]" : "top-[calc(100%+8px)]"}`}
        >
          <Link
            role="menuitem"
            to="/settings/account"
            className="block rounded-md px-3 py-2 text-[0.8125rem] text-foreground hover:bg-nav-on"
            onClick={() => setOpen(false)}
          >
            账号设置
          </Link>
          <div className="my-1 h-px bg-border" />
          <button
            type="button"
            role="menuitem"
            className="block w-full rounded-md px-3 py-2 text-left text-[0.8125rem] text-red-600 hover:bg-nav-on"
            onClick={handleLogout}
          >
            退出登录
          </button>
        </div>
      )}
    </div>
  );
}

export function SidebarUserBlock() {
  const { user } = useAuth();
  if (!user) return null;

  const label = getDisplayName(user);
  const typeLabel =
    user.account_type === "personal"
      ? "个人版"
      : user.org_role === "admin"
        ? "团队管理员"
        : "团队成员";

  return (
    <div className="mt-3 flex items-center gap-2.5 px-2 py-1">
      <div
        className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-border bg-white text-[0.72rem] font-semibold text-[#52525B]"
        aria-hidden
      >
        {initials(label)}
      </div>
      <div className="min-w-0 flex-1">
        <p className="truncate text-[0.78rem] font-semibold text-foreground">
          {label}
        </p>
        <span className="mt-0.5 inline-block rounded-full bg-[#F4F4F5] px-2 py-0.5 text-[0.65rem] font-medium text-[#71717A]">
          {typeLabel}
        </span>
      </div>
    </div>
  );
}
