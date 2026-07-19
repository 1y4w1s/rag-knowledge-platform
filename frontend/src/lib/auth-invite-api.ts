const API_BASE = "/api/v1";

export const INVITE_INVALID_MSG =
  "邀请码无效或已过期，请核对或联系管理员";

export interface InviteValidateResult {
  org_id: string;
  org_name: string;
}

export async function validateInviteCode(
  code: string,
): Promise<InviteValidateResult> {
  const res = await fetch(`${API_BASE}/auth/invites/validate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ code: code.trim() }),
  });

  if (!res.ok) {
    try {
      const data = (await res.json()) as { detail?: string };
      if (typeof data.detail === "string" && data.detail.includes("邀请码")) {
        throw new Error(INVITE_INVALID_MSG);
      }
    } catch (err) {
      if (err instanceof Error && err.message === INVITE_INVALID_MSG) {
        throw err;
      }
    }
    throw new Error(INVITE_INVALID_MSG);
  }

  return (await res.json()) as InviteValidateResult;
}
