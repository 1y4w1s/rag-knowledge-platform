/** NW-10：对话反馈 API 客户端。 */

import { apiFetch, apiGet, apiPost, ApiError, parseApiError } from "@/lib/api-client";

export type FeedbackRating = 0 | 1;

export interface FeedbackRecord {
  id: string;
  message_id: string;
  rating: FeedbackRating;
  feedback_text: string | null;
  created_at: string;
  updated_at: string | null;
}

export interface FeedbackStats {
  total: number;
  thumbs_up: number;
  thumbs_down: number;
  approval_rate: number;
}

export async function submitFeedback(opts: {
  messageId: string;
  rating: FeedbackRating;
  feedbackText?: string | null;
}): Promise<FeedbackRecord> {
  return apiPost<FeedbackRecord>("/api/v1/feedback", {
    message_id: opts.messageId,
    rating: opts.rating,
    feedback_text: opts.feedbackText ?? null,
  });
}

export async function getMessageFeedback(
  messageId: string,
): Promise<FeedbackRecord | null> {
  return apiGet<FeedbackRecord | null>(
    `/api/v1/feedback/messages/${messageId}`,
  );
}

export async function deleteFeedback(feedbackId: string): Promise<void> {
  const res = await apiFetch(`/api/v1/feedback/${feedbackId}`, {
    method: "DELETE",
  });
  if (!res.ok) throw new ApiError(await parseApiError(res), res.status);
}

export async function fetchFeedbackStats(opts?: {
  kbId?: string;
}): Promise<FeedbackStats> {
  const qs = opts?.kbId
    ? `?kb_id=${encodeURIComponent(opts.kbId)}`
    : "";
  return apiGet<FeedbackStats>(`/api/v1/feedback/stats${qs}`);
}
