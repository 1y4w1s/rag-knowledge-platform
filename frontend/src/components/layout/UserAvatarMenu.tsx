import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { Link, useNavigate } from "react-router-dom";

import { getDisplayName, useAuth } from "@/lib/auth-context";
import { useFloatingMenu } from "@/lib/use-floating-menu";
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
  const btnRef = useRef<HTMLButtonElement>(null);
  const wrapRef = useRef<HTMLDivElement>(null);
  const { floatingRef, style } = useFloatingMenu(btnRef, open);

  useEffect(() => {
    function onDocClick(e: MouseEvent) {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) {
        if (floatingRef.current && !floatingRef.current.contains(e.target as Node)) {
          setOpen(false);
        }
      }
    }
    document.addEventListener("click", onDocClick);
    return () => document.removeEventListener("click", onDocClick);
  }, [floatingRef]);

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
        ref={btnRef}
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

      {open && createPortal(
        <div
          ref={floatingRef}
          role="menu"
          className="popover-base z-[9999] min-w-[160px]"
          style={style}
        >
          <Link
            to="/settings/account"
            role="menuitem"
            className="flex items-center rounded-md px-3 py-2 text-[0.8125rem] text-foreground hover:bg-nav-on"
            onClick={() => setOpen(false)}
          >
            账号设置
          </Link>
          <div className="my-1 h-px bg-border" />
          <button
            type="button"
            role="menuitem"
            className="flex w-full items-center rounded-md px-3 py-2 text-[0.8125rem] text-red-600 hover:bg-nav-on"
            onClick={handleLogout}
          >
            退出登录
          </button>
        </div>,
        document.body,
      )}
    </div>
  );
}
