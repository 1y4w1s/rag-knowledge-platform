import { useEffect, useRef, useState } from "react";
import { ChevronDown } from "lucide-react";

export interface SelectOption {
  value: string;
  label: string;
}

interface SelectProps {
  id?: string;
  value: string;
  options: SelectOption[];
  onChange: (value: string) => void;
  placeholder?: string;
  className?: string;
}

export function Select({
  id,
  value,
  options,
  onChange,
  placeholder = "请选择",
  className,
}: SelectProps) {
  const [open, setOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(-1);
  const rootRef = useRef<HTMLDivElement>(null);
  const optionRefs = useRef<(HTMLDivElement | null)[]>([]);

  const selected = options.find((o) => o.value === value);
  const selectedLabel = selected ? selected.label : placeholder;

  useEffect(() => {
    if (!open) return;
    function onDocPointer(e: MouseEvent) {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", onDocPointer);
    return () => document.removeEventListener("mousedown", onDocPointer);
  }, [open]);

  useEffect(() => {
    if (open && activeIndex >= 0) {
      optionRefs.current[activeIndex]?.scrollIntoView?.({
        block: "nearest",
      });
    }
  }, [open, activeIndex]);

  function selectOption(optionValue: string) {
    onChange(optionValue);
    setOpen(false);
  }

  function openMenu() {
    const initial = Math.max(0, options.findIndex((o) => o.value === value));
    setActiveIndex(initial);
    setOpen(true);
  }

  function onTriggerKeyDown(e: React.KeyboardEvent) {
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault();
      if (!open) {
        openMenu();
      } else {
        setActiveIndex((i) =>
          e.key === "ArrowDown"
            ? Math.min(options.length - 1, i + 1)
            : Math.max(0, i - 1),
        );
      }
    } else if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      if (!open) {
        openMenu();
      } else {
        const idx =
          activeIndex >= 0
            ? activeIndex
            : Math.max(0, options.findIndex((o) => o.value === value));
        const opt = options[idx];
        if (opt) selectOption(opt.value);
      }
    } else if (e.key === "Escape") {
      setOpen(false);
    }
  }

  function onListKeyDown(e: React.KeyboardEvent) {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActiveIndex((i) => Math.min(options.length - 1, i + 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActiveIndex((i) => Math.max(0, i - 1));
    } else if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      const opt = options[activeIndex];
      if (opt) selectOption(opt.value);
    } else if (e.key === "Escape") {
      e.preventDefault();
      setOpen(false);
    } else if (e.key === "Tab") {
      setOpen(false);
    }
  }

  return (
    <div className={`select${className ? ` ${className}` : ""}`} ref={rootRef}>
      <button
        type="button"
        id={id}
        className="select-trigger"
        aria-haspopup="listbox"
        aria-expanded={open}
        onClick={() => (open ? setOpen(false) : openMenu())}
        onKeyDown={onTriggerKeyDown}
      >
        <span className="truncate">{selectedLabel}</span>
        <ChevronDown className="select-caret" size={16} strokeWidth={1.8} aria-hidden="true" />
      </button>
      {open && (
        <div
          className="select-menu"
          role="listbox"
          aria-activedescendant={
            activeIndex >= 0 ? `${id ?? "select"}-opt-${activeIndex}` : undefined
          }
          onKeyDown={onListKeyDown}
        >
          {options.map((opt, i) => {
            const isSelected = opt.value === value;
            return (
              <div
                key={opt.value}
                id={`${id ?? "select"}-opt-${i}`}
                ref={(el) => {
                  optionRefs.current[i] = el;
                }}
                role="option"
                aria-selected={isSelected}
                tabIndex={-1}
                data-active={i === activeIndex}
                className="select-option"
                onMouseEnter={() => setActiveIndex(i)}
                onClick={() => selectOption(opt.value)}
              >
                {opt.label}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
