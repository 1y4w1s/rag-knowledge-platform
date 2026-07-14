import { type FormEvent, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Send, Upload, Plus } from "lucide-react";

import { Button } from "@/components/ui/button";
import { MemberWriteBlockedButton } from "@/components/knowledge-bases/MemberWriteBlockedButton";
import { cn } from "@/lib/utils";

interface DashboardZoneAProps {
  isEmpty: boolean;
  recentKbId: string | null;
  memberCount?: number | null;
  statsScope?: "personal" | "organization";
  isOrgAdmin?: boolean;
  canWriteKb?: boolean;
  canUseTeamBusiness?: boolean;
  onMemberWriteBlocked?: () => void;
}

export function DashboardZoneA({
  isEmpty,
  recentKbId,
  memberCount,
  statsScope,
  isOrgAdmin = false,
  canWriteKb = true,
  canUseTeamBusiness = true,
  onMemberWriteBlocked,
}: DashboardZoneAProps) {
  const navigate = useNavigate();
  const [question, setQuestion] = useState("");

  const title = isEmpty ? "开始整理您的资料" : "欢迎回来";
  const meta = isEmpty
    ? "上传 PDF、Word 等文档，系统会自动整理并支持带出处的问答。"
    : "在资料库中上传文档，即可开始带引用来源的智能问答。";

  const uploadHref = recentKbId
    ? `/knowledge-bases/${recentKbId}`
    : "/knowledge-bases";
  const browseHref = recentKbId ? uploadHref : "/knowledge-bases";

  function submitQuestion() {
    const q = question.trim();
    if (!q || isEmpty || !canUseTeamBusiness) return;

    navigate(`/ask?q=${encodeURIComponent(q)}`);
  }

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    submitQuestion();
  }

  const showMemberBadge =
    statsScope === "organization" && memberCount != null;
  const memberBadgeTooltip = isOrgAdmin ? "查看成员管理" : "查看团队成员";

  const questionDisabled = isEmpty || !canUseTeamBusiness;
  const questionPlaceholder = !canUseTeamBusiness
    ? "分配部门后即可在此提问…"
    : isEmpty
      ? "上传文档后即可在此提问…"
      : "输入问题，在全部资料库中检索…";

  return (
    <section className="v6-rise rounded-xl border border-border bg-white/[0.96] p-[18px_22px] shadow-[0_1px_2px_rgba(0,0,0,0.03)]">
      <div className="grid items-start gap-x-5 gap-y-4 md:grid-cols-[1fr_auto]">
        <div className="min-w-0">
          <div className="flex flex-wrap items-start justify-between gap-x-3 gap-y-2">
            <h2 className="font-serif text-[1.05rem] font-semibold tracking-[0.02em] text-[#18181B]">
              {title}
            </h2>
            {showMemberBadge ? (
              <Link
                to="/organization/members"
                className="team-badge"
                title={`${memberBadgeTooltip} · ${memberCount} 名成员`}
                aria-label={`${memberCount} 名成员，查看团队`}
              >
                {memberCount} 名成员 ›
              </Link>
            ) : null}
          </div>
          <p className="mt-1.5 text-[0.8125rem] leading-relaxed text-[#7A6E6A]">
            {meta}
          </p>
        </div>
        <div className="flex min-w-[148px] flex-col gap-2">
          {canWriteKb ? (
            <>
              <Button asChild variant="brand" className="rounded-[10px] px-[18px]">
                <Link to={uploadHref}>
                  <Upload className="mr-1.5 h-4 w-4" />
                  上传文档
                </Link>
              </Button>
              <Button
                asChild
                variant="outline"
                className="rounded-[10px] border-border bg-white px-4 text-[0.8125rem] text-[#7A6E6A] hover:bg-nav-on"
              >
                <Link to="/knowledge-bases">
                  <Plus className="mr-1.5 h-4 w-4" />
                  创建资料库
                </Link>
              </Button>
            </>
          ) : onMemberWriteBlocked ? (
            <>
              <MemberWriteBlockedButton
                variant="brand"
                className="rounded-[10px] px-[18px]"
                onBlocked={onMemberWriteBlocked}
              >
                <Upload className="mr-1.5 h-4 w-4" />
                上传文档
              </MemberWriteBlockedButton>
              <MemberWriteBlockedButton
                variant="outline"
                className="rounded-[10px] border-border bg-white px-4 text-[0.8125rem] text-[#7A6E6A]"
                onBlocked={onMemberWriteBlocked}
              >
                <Plus className="mr-1.5 h-4 w-4" />
                创建资料库
              </MemberWriteBlockedButton>
              <Button
                asChild
                variant="outline"
                className="rounded-[10px] border-border bg-white px-4 text-[0.8125rem] text-[#7A6E6A] hover:bg-nav-on"
              >
                <Link to={browseHref}>查看资料库</Link>
              </Button>
            </>
          ) : (
            <Button asChild variant="brand" className="rounded-[10px] px-[18px]">
              <Link to={browseHref}>
                <Upload className="mr-1.5 h-4 w-4" />
                查看资料库
              </Link>
            </Button>
          )}
        </div>
      </div>

      <hr className="hairline-gradient mt-3.5" />
      <form className="mt-2 flex gap-2" onSubmit={handleSubmit}>
        <input
          type="text"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          disabled={questionDisabled}
          placeholder={questionPlaceholder}
          className={cn(
            "min-w-0 flex-1 rounded-[10px] border border-border bg-white px-3.5 py-2.5 text-[0.8125rem] text-foreground outline-none",
            "placeholder:text-muted focus-visible:border-[#E8C4B0] focus-visible:ring-2 focus-visible:ring-[rgba(203,107,61,0.12)]",
            "disabled:cursor-not-allowed disabled:opacity-60",
          )}
        />
        <button
          type="submit"
          disabled={questionDisabled}
          aria-label="发送"
          className="flex h-10 w-10 shrink-0 items-center justify-center rounded-[10px] bg-[var(--action)] text-white disabled:cursor-not-allowed disabled:opacity-40"
        >
          <Send className="h-4 w-4" strokeWidth={2} />
        </button>
      </form>
    </section>
  );
}
