import { cn } from "@/lib/utils";

function getInitials(input: string): string {
  const local = input.includes("@") ? input.split("@")[0] : input;
  const parts = local.split(/[._\-]/).filter(Boolean);
  if (parts.length >= 2 && parts[0] && parts[1]) {
    return (parts[0][0] + parts[1][0]).toUpperCase();
  }
  return local.slice(0, 2).toUpperCase();
}

const sizeMap = {
  sm: "h-8 w-8 text-[0.7rem]",
  md: "h-10 w-10 text-[0.78rem]",
  lg: "h-12 w-12 text-[0.95rem]",
} as const;

export type AvatarSize = keyof typeof sizeMap;

export function Avatar({
  name,
  size = "md",
  className,
}: {
  name: string;
  size?: AvatarSize;
  className?: string;
}) {
  return (
    <span
      aria-hidden
      className={cn(
        "inline-flex shrink-0 select-none items-center justify-center rounded-full bg-[var(--action)] font-semibold leading-none text-white ring-1 ring-white/35",
        sizeMap[size],
        className,
      )}
    >
      {getInitials(name)}
    </span>
  );
}

export function displayNameFromEmail(email: string): string {
  const local = email.split("@")[0];
  return local
    .split(/[._\-]/)
    .filter(Boolean)
    .map((s) => (s ? s[0].toUpperCase() + s.slice(1) : s))
    .join(" ");
}
