import { useEffect, useRef, useState } from "react";
import { Search, X } from "lucide-react";

import { cn } from "@/lib/utils";

interface KbSearchInputProps {
  id: string;
  value: string;
  placeholder: string;
  onChange: (value: string) => void;
  className?: string;
}

export function KbSearchInput({
  id,
  value,
  placeholder,
  onChange,
  className = "max-w-sm",
}: KbSearchInputProps) {
  const [localValue, setLocalValue] = useState(value);
  const isComposingRef = useRef(false);

  useEffect(() => {
    if (!isComposingRef.current) {
      setLocalValue(value);
    }
  }, [value]);

  function handleChange(event: React.ChangeEvent<HTMLInputElement>) {
    const next = event.target.value;
    setLocalValue(next);
    const nativeEvent = event.nativeEvent as InputEvent;
    if (!isComposingRef.current && !nativeEvent.isComposing) {
      onChange(next);
    }
  }

  function handleCompositionStart() {
    isComposingRef.current = true;
  }

  function handleCompositionEnd(
    event: React.CompositionEvent<HTMLInputElement>,
  ) {
    isComposingRef.current = false;
    const next = event.currentTarget.value;
    setLocalValue(next);
    onChange(next);
  }

  function handleClear() {
    setLocalValue("");
    onChange("");
  }

  return (
    <div className={`relative w-full ${className}`}>
      <Search
        className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--mut-zinc)]"
        aria-hidden
      />
      <input
        id={id}
        type="search"
        value={localValue}
        placeholder={placeholder}
        onChange={handleChange}
        onCompositionStart={handleCompositionStart}
        onCompositionEnd={handleCompositionEnd}
        className={cn(
          "h-9 w-full rounded-[8px] border border-[var(--line2)] bg-[var(--surf)] pl-9 text-[0.8125rem] text-foreground outline-none transition-shadow placeholder:text-[var(--mut)] focus:ring-2 focus:ring-[var(--ring-action)]",
          id === "kb-list-search" && "h-10 rounded-[10px]",
          localValue ? "pr-9" : "pr-3",
        )}
        aria-label={placeholder}
      />
      {localValue && (
        <button
          type="button"
          onClick={handleClear}
          aria-label="清除搜索"
          className="absolute right-2 top-1/2 -translate-y-1/2 rounded-[8px] p-1 text-[var(--mut)] hover:bg-[var(--line)] hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--action)]"
        >
          <X className="h-3.5 w-3.5" aria-hidden />
        </button>
      )}
    </div>
  );
}
