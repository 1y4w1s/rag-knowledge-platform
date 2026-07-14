export type FieldErrors = Record<string, string>;

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export function validateLoginFields(
  identifier: string,
  password: string,
): FieldErrors {
  const errors: FieldErrors = {};
  if (!identifier.trim()) {
    errors.identifier = "请输入邮箱或用户名";
  }
  if (!password) {
    errors.password = "请输入密码";
  }
  return errors;
}

/** 组织名 trim 后长度（WS-1-2 §2.1） */
export function orgNameTrimLen(orgName: string): number {
  return orgName.trim().length;
}

export function needsLongOrgNameConfirm(orgName: string): boolean {
  return orgNameTrimLen(orgName) > 80;
}

/** >80 字确认框（E3/E4 · 与预览一致） */
export function confirmLongOrgName(actionLabel: string): boolean {
  return window.confirm(
    `名称较长，侧栏可能显示不全。\n\n确定${actionLabel}吗？`,
  );
}

/** 注册第 3 步：用户名 + 邮箱 + 密码 */
export function validateRegisterCredentials(
  username: string,
  email: string,
  password: string,
  confirmPassword: string,
  usernameValidator: (value: string) => string | null,
): FieldErrors {
  const errors: FieldErrors = {};
  const usernameError = usernameValidator(username);
  if (usernameError) errors.username = usernameError;

  const normalizedEmail = email.trim();
  if (!normalizedEmail) {
    errors.email = "请输入邮箱";
  } else if (!EMAIL_PATTERN.test(normalizedEmail)) {
    errors.email = "邮箱格式不正确";
  }

  if (!password) {
    errors.password = "请输入密码";
  } else if (password.length < 8) {
    errors.password = "密码至少 8 位";
  }

  if (!confirmPassword) {
    errors.confirmPassword = "请再次输入密码";
  } else if (password !== confirmPassword) {
    errors.confirmPassword = "两次输入的密码不一致";
  }

  return errors;
}

/** 注册第 2 步：团队角色 + 组织名 / 邀请码（WS-1-2） */
export function validateRegisterTeamRole(input: {
  teamRole: "creator" | "member" | null;
  orgName: string;
  inviteCode: string;
}): FieldErrors {
  const errors: FieldErrors = {};

  if (!input.teamRole) {
    errors.teamRole = "请选择团队角色";
    return errors;
  }

  if (input.teamRole === "creator") {
    const trimmed = input.orgName.trim();
    if (!trimmed) {
      errors.orgName = "请填写团队显示名称";
    } else if (trimmed.length > 255) {
      errors.orgName = "名称不能超过 255 个字符";
    }
  }

  if (input.teamRole === "member") {
    const code = input.inviteCode.trim();
    if (code.length < 4) {
      errors.inviteCode = "请填写有效邀请码";
    }
  }

  return errors;
}

/** @deprecated 单页注册用；三步 UI 请用 validateRegisterCredentials + validateRegisterTeamRole */
export function validateRegisterStep1(
  username: string,
  email: string,
  password: string,
  confirmPassword: string,
  usernameValidator: (value: string) => string | null,
): FieldErrors {
  return validateRegisterCredentials(
    username,
    email,
    password,
    confirmPassword,
    usernameValidator,
  );
}

/** @deprecated 单页注册用 */
export function validateRegisterStep2(input: {
  accountType: "personal" | "enterprise";
  orgName: string;
}): FieldErrors {
  const errors: FieldErrors = {};

  if (input.accountType === "enterprise" && !input.orgName.trim()) {
    errors.orgName = "请填写团队显示名称";
  }

  return errors;
}

export function validateRegisterFields(input: {
  username: string;
  email: string;
  password: string;
  confirmPassword: string;
  accountType: "personal" | "enterprise";
  orgName: string;
  usernameValidator: (value: string) => string | null;
}): FieldErrors {
  return {
    ...validateRegisterCredentials(
      input.username,
      input.email,
      input.password,
      input.confirmPassword,
      input.usernameValidator,
    ),
    ...validateRegisterStep2({
      accountType: input.accountType,
      orgName: input.orgName,
    }),
  };
}

export function firstFieldError(errors: FieldErrors): string | null {
  const values = Object.values(errors);
  return values.length > 0 ? values[0] : null;
}
