/** NW-10：消息级反馈判定（默认隐藏 · 与后端拒答话术对齐）。 */

import type { StoredUser } from "@/lib/auth-storage";

export const NO_CONTEXT_REPLY_ZH =
  "知识库中未找到相关内容，无法根据文档回答您的问题。";

export const NO_CONTEXT_REPLY_EN =
  "No relevant content was found in the knowledge base to answer your question.";

export const FEEDBACK_PROMPT_REFUSE = "没帮上忙？";
export const FEEDBACK_PROMPT_STALE = "引用不可用，这条回答有帮助吗？";
export const FEEDBACK_MENU_LABEL = "这条回答有帮助吗？";
/** I-2：评测模式顶栏轻提示（非催评）。 */
export const FEEDBACK_EVAL_MODE_HINT =
  "评测模式 · 助手消息已展开反馈入口 · 👎 审题见 About「运维入口」";

export type CitationStatusLike = {
  source_status?: string | null;
};

/** URL `?eval=1`（仅此值；其它一律不算开）。 */
export function isEvalQueryParam(
  search: string | URLSearchParams | null | undefined,
): boolean {
  if (search == null) return false;
  const params =
    typeof search === "string"
      ? new URLSearchParams(
          search.startsWith("?") ? search.slice(1) : search,
        )
      : search;
  return params.get("eval") === "1";
}

/**
 * 评测模式角色闸：个人版本人 · 企业 Owner/Admin。
 * Member 无特权（即使 URL 带 eval）。
 */
export function canUseFeedbackEvalMode(
  user: Pick<StoredUser, "account_type" | "org_role" | "is_owner"> | null,
): boolean {
  if (!user) return false;
  if (user.account_type === "personal") return true;
  if (user.account_type === "enterprise") {
    return user.org_role === "admin" || Boolean(user.is_owner);
  }
  return false;
}

/** 同时满足 URL + 角色才开评测加速入口。 */
export function isFeedbackEvalModeActive(opts: {
  search?: string | URLSearchParams | null;
  user: Pick<StoredUser, "account_type" | "org_role" | "is_owner"> | null;
}): boolean {
  return isEvalQueryParam(opts.search) && canUseFeedbackEvalMode(opts.user);
}

export function isRefuseAnswer(
  content: string,
  citationCount: number,
): boolean {
  if (citationCount > 0) return false;
  const text = content.trim();
  return text === NO_CONTEXT_REPLY_ZH || text === NO_CONTEXT_REPLY_EN;
}

export function areAllCitationsUnavailable(
  citations: CitationStatusLike[],
): boolean {
  if (citations.length === 0) return false;
  return citations.every(
    (c) =>
      c.source_status === "source_inaccessible" ||
      c.source_status === "document_deleted" ||
      c.source_status === "chunk_stale",
  );
}

/** 是否显示拒答/全灰轻量入口（非常驻双按钮）。 */
export function shouldShowLightFeedbackPrompt(opts: {
  streaming?: boolean;
  messageId?: string;
  content: string;
  citations: CitationStatusLike[];
}): boolean {
  if (opts.streaming || !opts.messageId) return false;
  if (isRefuseAnswer(opts.content, opts.citations.length)) return true;
  return areAllCitationsUnavailable(opts.citations);
}

export function lightFeedbackPromptLabel(opts: {
  content: string;
  citations: CitationStatusLike[];
}): string {
  if (isRefuseAnswer(opts.content, opts.citations.length)) {
    return FEEDBACK_PROMPT_REFUSE;
  }
  return FEEDBACK_PROMPT_STALE;
}
