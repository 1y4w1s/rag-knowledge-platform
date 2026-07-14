import { useCallback, useState } from "react";
import type { Dispatch, SetStateAction } from "react";

import type { ApprovalState } from "@/lib/chat-api";
import type { ChatMessage } from "@/components/chat/ChatMessageList";
import { resolveApproval as resolveApprovalApi } from "@/lib/thread-api";

export function useApprovalResolver(
  setMessages: Dispatch<SetStateAction<ChatMessage[]>>,
) {
  const [resolvingApprovalId, setResolvingApprovalId] = useState<
    string | null
  >(null);
  const [approvalError, setApprovalError] = useState<string | null>(null);

  const resolveApproval = useCallback(
    async (approvalId: string, action: "adopt" | "cancel") => {
      setResolvingApprovalId(approvalId);
      setApprovalError(null);

      try {
        const result = await resolveApprovalApi(approvalId, action);

        setMessages((prev) =>
          prev.map((msg) => {
            if (msg.role !== "assistant" || !msg.approval) return msg;
            if (msg.approval.approval_id !== approvalId) return msg;
            const updated: ApprovalState =
              action === "adopt"
                ? {
                    ...msg.approval,
                    status: "adopted",
                    filename:
                      (result.filename as string) ?? msg.approval.filename,
                  }
                : { ...msg.approval, status: "cancelled" };
            return { ...msg, approval: updated };
          }),
        );
      } catch (err) {
        const message =
          err instanceof Error ? err.message : "操作失败，请稍后重试";
        setApprovalError(message);
      } finally {
        setResolvingApprovalId(null);
      }
    },
    [setMessages],
  );

  return {
    resolvingApprovalId,
    approvalError,
    resolveApproval,
  };
}
