/**
 * NW-10：消息级反馈（默认隐藏 · Lucide SVG · 无 emoji）。
 */
import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { MoreHorizontal, ThumbsDown, ThumbsUp } from "lucide-react";

import {
  deleteFeedback,
  getMessageFeedback,
  submitFeedback,
  type FeedbackRating,
  type FeedbackRecord,
} from "@/lib/feedback-api";
import {
  FEEDBACK_MENU_LABEL,
  lightFeedbackPromptLabel,
  shouldShowLightFeedbackPrompt,
  type CitationStatusLike,
} from "@/lib/message-feedback";
import { useFloatingMenu } from "@/lib/use-floating-menu";

interface MessageFeedbackProps {
  messageId?: string;
  content: string;
  citations: CitationStatusLike[];
  streaming?: boolean;
  /** I-2：Admin 评测模式 — 默认展开 SVG 面板（非强制催评）。 */
  evalMode?: boolean;
}

export function MessageFeedback({
  messageId,
  content,
  citations,
  streaming,
  evalMode = false,
}: MessageFeedbackProps) {
  const [menuOpen, setMenuOpen] = useState(false);
  const [panelOpen, setPanelOpen] = useState(evalMode);
  const [record, setRecord] = useState<FeedbackRecord | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const anchorRef = useRef<HTMLButtonElement | null>(null);
  const { floatingRef, style } = useFloatingMenu(anchorRef, menuOpen);

  const light = shouldShowLightFeedbackPrompt({
    streaming,
    messageId,
    content,
    citations,
  });
  const canShow = Boolean(messageId) && !streaming;

  useEffect(() => {
    if (evalMode) setPanelOpen(true);
  }, [evalMode, messageId]);

  useEffect(() => {
    if (!panelOpen || !messageId) return;
    let cancelled = false;
    void (async () => {
      try {
        const fb = await getMessageFeedback(messageId);
        if (!cancelled) setRecord(fb);
      } catch {
        if (!cancelled) setRecord(null);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [panelOpen, messageId]);

  useEffect(() => {
    if (!menuOpen) return;
    function onDoc(e: MouseEvent) {
      const t = e.target as Node;
      if (anchorRef.current?.contains(t)) return;
      if (floatingRef.current?.contains(t)) return;
      setMenuOpen(false);
    }
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, [menuOpen, floatingRef]);

  if (!canShow) return null;

  async function rate(rating: FeedbackRating) {
    if (!messageId || busy) return;
    setBusy(true);
    setError(null);
    try {
      if (record?.rating === rating) {
        await deleteFeedback(record.id);
        setRecord(null);
      } else {
        const next = await submitFeedback({ messageId, rating });
        setRecord(next);
      }
      setMenuOpen(false);
      setPanelOpen(true);
    } catch (e) {
      setError(e instanceof Error ? e.message : "反馈失败");
    } finally {
      setBusy(false);
    }
  }

  function openPanelFromMenu() {
    setMenuOpen(false);
    setPanelOpen(true);
  }

  function openPanelFromLight() {
    setPanelOpen(true);
  }

  return (
    <div className="mt-2 flex flex-col items-end gap-1" data-testid="message-feedback">
      <div className="flex items-center gap-2">
        {light && !panelOpen && (
          <button
            type="button"
            className="text-[0.72rem] text-[var(--mut)] hover:text-[var(--text)] underline-offset-2 hover:underline"
            onClick={openPanelFromLight}
            data-testid="feedback-light-prompt"
          >
            {lightFeedbackPromptLabel({ content, citations })}
          </button>
        )}

        <button
          ref={anchorRef}
          type="button"
          className="msg-action-btn"
          aria-label="更多操作"
          aria-expanded={menuOpen}
          title="更多"
          onClick={() => setMenuOpen((v) => !v)}
          data-testid="feedback-more-btn"
        >
          <MoreHorizontal className="h-3.5 w-3.5" aria-hidden />
        </button>
      </div>

      {menuOpen &&
        createPortal(
          <div
            ref={floatingRef}
            style={style}
            className="z-[9999] min-w-[11rem] rounded-lg border border-[var(--line2)] bg-[var(--bg)] p-1 shadow-md"
            role="menu"
            data-testid="feedback-more-menu"
          >
            <button
              type="button"
              role="menuitem"
              className="w-full rounded-md px-3 py-2 text-left text-sm text-[var(--text)] hover:bg-[var(--surf2)]"
              onClick={openPanelFromMenu}
            >
              {FEEDBACK_MENU_LABEL}
            </button>
          </div>,
          document.body,
        )}

      {panelOpen && (
        <div
          className="flex items-center gap-1"
          data-testid="feedback-thumbs"
          role="group"
          aria-label="这条回答是否有帮助"
        >
          <button
            type="button"
            className="msg-action-btn"
            disabled={busy}
            aria-label="有帮助"
            aria-pressed={record?.rating === 1}
            title="有帮助"
            onClick={() => void rate(1)}
            data-testid="feedback-up"
          >
            <ThumbsUp
              className="h-3.5 w-3.5"
              aria-hidden
              fill={record?.rating === 1 ? "currentColor" : "none"}
            />
          </button>
          <button
            type="button"
            className="msg-action-btn"
            disabled={busy}
            aria-label="没帮助"
            aria-pressed={record?.rating === 0}
            title="没帮助"
            onClick={() => void rate(0)}
            data-testid="feedback-down"
          >
            <ThumbsDown
              className="h-3.5 w-3.5"
              aria-hidden
              fill={record?.rating === 0 ? "currentColor" : "none"}
            />
          </button>
        </div>
      )}

      {error && (
        <p className="text-[0.72rem] text-[var(--status-err-text)]" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}
