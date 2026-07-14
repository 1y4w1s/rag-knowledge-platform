import type { RegisterUsage, RegisterWizardStep } from "@/components/auth/register-form-types";

interface StepLabel {
  key: string;
  label: string;
  active: boolean;
  done: boolean;
}

function buildLabels(
  step: RegisterWizardStep,
  usage: RegisterUsage | null,
): StepLabel[] {
  if (usage !== "team") {
    return [
      {
        key: "usage",
        label: "选择用法",
        active: step === 1,
        done: step > 1,
      },
      {
        key: "credentials",
        label: "登录信息",
        active: step === 3,
        done: false,
      },
    ];
  }

  return [
    {
      key: "usage",
      label: "选择用法",
      active: step === 1,
      done: step > 1,
    },
    {
      key: "role",
      label: "团队角色",
      active: step === 2,
      done: step > 2,
    },
    {
      key: "credentials",
      label: "登录信息",
      active: step === 3,
      done: false,
    },
  ];
}

function fillWidth(step: RegisterWizardStep, usage: RegisterUsage | null): string {
  if (step === 1) return "0%";
  if (usage !== "team") return step === 3 ? "calc(50% - 1.75rem)" : "0%";
  if (step === 2) return "0%";
  return "calc(66% - 2rem)";
}

interface RegisterStepsIndicatorProps {
  step: RegisterWizardStep;
  usage: RegisterUsage | null;
}

export function RegisterStepsIndicator({
  step,
  usage,
}: RegisterStepsIndicatorProps) {
  const labels = buildLabels(step, usage);

  return (
    <div className="register-steps" aria-label="注册进度">
      <div className="register-steps-line" aria-hidden />
      <div
        className="register-steps-fill"
        style={{ width: fillWidth(step, usage) }}
        aria-hidden
      />
      <div className="register-steps-row">
        {labels.map((item) => (
          <div key={item.key} className="register-step-item">
            <div
              className={[
                "register-step-dot",
                item.active ? "on" : "",
                item.done ? "done" : "",
              ]
                .filter(Boolean)
                .join(" ")}
              aria-hidden
            />
            <span
              className={[
                "register-step-label",
                item.active ? "on" : "",
              ]
                .filter(Boolean)
                .join(" ")}
            >
              {item.label}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
