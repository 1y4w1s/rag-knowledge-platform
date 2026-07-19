export type PasswordStrengthLevel = 0 | 1 | 2 | 3;

export interface PasswordStrengthResult {
  level: PasswordStrengthLevel;
  label: string;
  tone: "weak" | "mid" | "strong" | "";
}

export function calcPasswordStrength(password: string): PasswordStrengthResult {
  if (!password) {
    return { level: 0, label: "", tone: "" };
  }

  let score = 0;
  if (password.length >= 8) score++;
  if (/[A-Z]/.test(password) && /[a-z]/.test(password)) score++;
  if (/\d/.test(password)) score++;
  if (/[^A-Za-z0-9]/.test(password)) score++;
  if (password.length >= 12) score++;

  if (score <= 2) {
    return {
      level: 1,
      label: "弱 — 建议增加长度与混合字符",
      tone: "weak",
    };
  }
  if (score <= 3) {
    return {
      level: 2,
      label: "中等 — 可再加强符号或长度",
      tone: "mid",
    };
  }
  return {
    level: 3,
    label: "强 — 密码强度良好",
    tone: "strong",
  };
}
