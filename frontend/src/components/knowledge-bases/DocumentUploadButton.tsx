import { useRef } from "react";
import { Upload } from "lucide-react";

import { Button } from "@/components/ui/button";

const ACCEPTED_EXTENSIONS = ".pdf,.txt,.md,.docx";

interface DocumentUploadButtonProps {
  disabled?: boolean;
  uploading?: boolean;
  onFilesSelected: (files: File[]) => void;
}

export function DocumentUploadButton({
  disabled = false,
  uploading = false,
  onFilesSelected,
}: DocumentUploadButtonProps) {
  const inputRef = useRef<HTMLInputElement>(null);

  function handleChange(event: React.ChangeEvent<HTMLInputElement>) {
    const files = Array.from(event.target.files ?? []);
    event.target.value = "";
    if (files.length > 0) {
      onFilesSelected(files);
    }
  }

  return (
    <>
      <input
        ref={inputRef}
        type="file"
        accept={ACCEPTED_EXTENSIONS}
        multiple
        className="hidden"
        onChange={handleChange}
      />
      <Button
        type="button"
        variant="outline"
        size="sm"
        disabled={disabled || uploading}
        onClick={() => inputRef.current?.click()}
      >
        <Upload className="h-3.5 w-3.5" aria-hidden />
        {uploading ? "上传中…" : "上传文档"}
      </Button>
    </>
  );
}
