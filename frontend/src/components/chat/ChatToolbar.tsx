import { History, MessageSquarePlus } from "lucide-react";
import { Link, useNavigate } from "react-router-dom";

import { Button } from "@/components/ui/button";
import type { KnowledgeBase } from "@/lib/knowledge-base-api";
import { cn } from "@/lib/utils";

interface ChatToolbarProps {
  kbId: string;
  kbName: string;
  knowledgeBases: KnowledgeBase[];
  onNewChat: () => void;
  creatingThread?: boolean;
  threadPanelCollapsed?: boolean;
  onToggleThreadPanel?: () => void;
}

export function ChatToolbar({
  kbId,
  kbName,
  knowledgeBases,
  onNewChat,
  creatingThread = false,
  threadPanelCollapsed = false,
  onToggleThreadPanel,
}: ChatToolbarProps) {
  const navigate = useNavigate();

  return (
    <div className="chat-toolbar">
      <div className="flex items-center gap-2">
        {onToggleThreadPanel ? (
          <button
            type="button"
            className={cn(
              "thread-history-toggle",
              !threadPanelCollapsed && "thread-history-toggle-on",
            )}
            aria-expanded={!threadPanelCollapsed}
            aria-controls="thread-list-panel"
            onClick={onToggleThreadPanel}
            data-testid="thread-history-toggle"
          >
            <History className="h-3.5 w-3.5" aria-hidden />
            历史
          </button>
        ) : null}
        <span className="chat-toolbar-pill">引用溯源</span>
      </div>

      <div className="flex min-w-0 flex-1 items-center gap-2 sm:gap-2">
        <span className="hidden shrink-0 text-[0.75rem] text-muted sm:inline">
          当前资料库
        </span>
        <select
          className="chat-kb-select min-w-0 truncate"
          value={kbId}
          onChange={(event) => {
            const nextId = event.target.value;
            if (nextId && nextId !== kbId) {
              navigate(`/knowledge-bases/${nextId}/chat`);
            }
          }}
          aria-label="切换资料库"
        >
          {knowledgeBases.map((kb) => (
            <option key={kb.id} value={kb.id}>
              {kb.name}
            </option>
          ))}
          {knowledgeBases.length === 0 && (
            <option value={kbId}>{kbName}</option>
          )}
        </select>
      </div>

      <div className="flex items-center gap-2">
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={onNewChat}
          disabled={creatingThread}
          data-testid="toolbar-new-chat-btn"
          className="gap-1 px-2 sm:px-3"
        >
          <MessageSquarePlus className="h-4 w-4 sm:hidden" aria-hidden />
          <span className="hidden sm:inline">
            {creatingThread ? "创建中…" : "+ 新建对话"}
          </span>
          <span className="sm:hidden">
            {creatingThread ? "…" : "新建"}
          </span>
        </Button>
        <Button asChild variant="outline" size="sm" className="hidden sm:inline-flex">
          <Link to={`/knowledge-bases/${kbId}`}>资料库详情</Link>
        </Button>
      </div>
    </div>
  );
}
