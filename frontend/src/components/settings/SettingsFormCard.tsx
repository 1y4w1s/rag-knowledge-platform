import type { ReactNode } from "react";

interface SettingsFormCardProps {
  title: string;
  children: ReactNode;
  className?: string;
}

export function SettingsFormCard({
  title,
  children,
  className,
}: SettingsFormCardProps) {
  return (
    <section className={className ?? "settings-card"}>
      <h3>{title}</h3>
      {children}
    </section>
  );
}

interface SettingsReadonlyFieldProps {
  id: string;
  label: string;
  value: string;
}

export function SettingsReadonlyField({
  id,
  label,
  value,
}: SettingsReadonlyFieldProps) {
  return (
    <div className="flex items-baseline gap-3">
      <label htmlFor={id} className="settings-field-label w-20 shrink-0">
        {label}
      </label>
      <input
        id={id}
        type="text"
        readOnly
        value={value}
        className="settings-field-input settings-field-input-readonly flex-1"
      />
    </div>
  );
}
