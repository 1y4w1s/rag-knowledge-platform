import type { ReactNode } from "react";
import { useId } from "react";

import { cn } from "@/lib/utils";

const STEPS = [
  { id: 1 as const, label: "创建资料库" },
  { id: 2 as const, label: "上传文档" },
  { id: 3 as const, label: "开始对话" },
];

interface KbOnboardingStepsProps {
  /** 当前高亮步骤（已完成步骤 id 更小） */
  activeStep: 1 | 2 | 3;
  /** 团队成员：第一步文案调整 */
  isMember?: boolean;
  className?: string;
}

function stepLabel(stepId: 1 | 2 | 3, isMember: boolean): string {
  if (stepId === 1 && isMember) return "管理员建库";
  if (stepId === 2 && isMember) return "等待上传";
  return STEPS[stepId - 1].label;
}

/** 建库 → 上传 → 对话 · 细线 + 赤陶橙圆点（应用内 token，非 auth 页） */
export function KbOnboardingSteps({
  activeStep,
  isMember = false,
  className,
}: KbOnboardingStepsProps) {
  return (
    <div className={cn("relative mx-auto w-full max-w-md px-2", className)}>
      <div
        aria-hidden
        className="absolute left-[calc(16.67%-0.5rem)] right-[calc(16.67%-0.5rem)] top-[7px] h-px bg-[var(--line2)]"
      />
      <div
        aria-hidden
        className="absolute left-[calc(16.67%-0.5rem)] top-[7px] h-px bg-[var(--action)] transition-all duration-300"
        style={{
          width:
            activeStep <= 1
              ? "0%"
              : activeStep === 2
                ? "calc(33.33% - 0.5rem)"
                : "calc(66.66% - 0.5rem)",
        }}
      />
      <ol className="relative flex justify-between" aria-label="入门步骤">
        {STEPS.map((step) => {
          const state =
            activeStep > step.id
              ? "done"
              : activeStep === step.id
                ? "active"
                : "pending";
          return (
            <li
              key={step.id}
              className="flex min-w-[4.5rem] flex-col items-center gap-2"
            >
              <div
                className={cn(
                  "flex h-3.5 w-3.5 items-center justify-center rounded-full border-2 bg-[var(--surf)] transition-all",
                  state === "pending" && "border-[var(--line2)]",
                  state === "active" &&
                    "border-[var(--action)] bg-[var(--action)] shadow-[0_0_0_3px_rgb(203_107_61/0.15)]",
                  state === "done" &&
                    "border-[var(--action)] bg-[var(--action)]",
                )}
                aria-hidden
              >
                {state === "done" && (
                  <span className="text-[0.5rem] font-bold leading-none text-white">
                    ✓
                  </span>
                )}
              </div>
              <span
                className={cn(
                  "text-center text-[0.72rem] leading-snug",
                  state === "pending"
                    ? "font-medium text-muted"
                    : "font-semibold text-foreground",
                )}
              >
                {stepLabel(step.id, isMember)}
              </span>
            </li>
          );
        })}
      </ol>
    </div>
  );
}

interface KbOnboardingEmptyPanelProps {
  title: string;
  description: string;
  activeStep: 1 | 2 | 3;
  isMember?: boolean;
  children?: ReactNode;
}

export function KbOnboardingEmptyPanel({
  title,
  description,
  activeStep,
  isMember,
  children,
}: KbOnboardingEmptyPanelProps) {
  const titleId = useId();
  const descId = useId();

  return (
    <div
      className="kb-result-empty"
      role="region"
      aria-labelledby={titleId}
      aria-describedby={descId}
    >
      <p id={titleId} className="kb-result-empty-title">
        {title}
      </p>
      <p id={descId} className="kb-result-empty-desc">
        {description}
      </p>
      <KbOnboardingSteps
        activeStep={activeStep}
        isMember={isMember}
        className="mt-8"
      />
      {children && <div className="kb-result-empty-action">{children}</div>}
    </div>
  );
}
