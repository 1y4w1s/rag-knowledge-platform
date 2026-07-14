import { useEffect, useState } from "react";

import {
  toolStepDetail,
  type ToolTimelineStep,
} from "@/lib/agent-stream";
import { cn } from "@/lib/utils";

interface ToolTimelineProps {
  steps: ToolTimelineStep[];
  /** 流式生成中默认展开（S4） */
  defaultOpen?: boolean;
  className?: string;
}

/**
 * G3-3.2 · 精准模式 tool 时间线（对齐 preview trace-panel · H3-2-B 不持久化）。
 */
export function ToolTimeline({
  steps,
  defaultOpen = true,
  className,
}: ToolTimelineProps) {
  const [open, setOpen] = useState(defaultOpen);

  useEffect(() => {
    if (defaultOpen) setOpen(true);
  }, [defaultOpen]);

  if (steps.length === 0) return null;

  const finishedCount = steps.filter((step) => step.status !== "running").length;

  return (
    <details
      className={cn("tool-timeline-panel", className)}
      open={open}
      onToggle={(event) => setOpen(event.currentTarget.open)}
      data-testid="tool-timeline"
    >
      <summary className="tool-timeline-summary">
        Tool 时间线 · {finishedCount}/{steps.length} 步
      </summary>
      <div className="tool-timeline-body">
        {steps.map((step) => (
          <div
            key={step.step}
            className={cn(
              "tool-timeline-step",
              step.status === "error" && "tool-timeline-step-error",
              step.status === "running" && "tool-timeline-step-running",
            )}
            data-testid={`tool-timeline-step-${step.step}`}
            data-status={step.status}
          >
            <span className="tool-timeline-dot" aria-hidden>
              {step.step}
            </span>
            <div className="min-w-0">
              <strong className="tool-timeline-tool">{step.tool}</strong>
              <p className="tool-timeline-detail">{toolStepDetail(step)}</p>
            </div>
          </div>
        ))}
      </div>
    </details>
  );
}
