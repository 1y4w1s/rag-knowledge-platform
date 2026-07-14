import { Send } from "lucide-react";
import { useLayoutEffect, useState, type FormEvent } from "react";

export interface ChatInputDraftRestore {
  /** Bumps when a new draft should be applied (same text twice still works). */
  nonce: number;
  text: string;
}

interface ChatInputProps {
  disabled?: boolean;
  placeholder?: string;
  onSend: (message: string) => void;
  /** G3-E1 · mode-switch abort puts the rolled-back question back in the box. */
  draftRestore?: ChatInputDraftRestore;
}

export function ChatInput({
  disabled,
  placeholder = "提问，答案将附带引用来源…",
  onSend,
  draftRestore,
}: ChatInputProps) {
  const [value, setValue] = useState("");

  useLayoutEffect(() => {
    if (draftRestore?.text) {
      setValue(draftRestore.text);
    }
  }, [draftRestore?.nonce, draftRestore?.text]);

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    const trimmed = value.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed);
    setValue("");
  }

  return (
    <div className="chat-input-wrap">
      <form className="chat-input-box" onSubmit={handleSubmit}>
        <input
          id="chat-input"
          value={value}
          onChange={(event) => setValue(event.target.value)}
          placeholder={placeholder}
          disabled={disabled}
          aria-label="向资料库提问"
        />
        <button
          type="submit"
          className="chat-send-btn"
          disabled={disabled || !value.trim()}
          aria-label="发送"
        >
          <Send className="h-4 w-4" />
        </button>
      </form>
    </div>
  );
}
