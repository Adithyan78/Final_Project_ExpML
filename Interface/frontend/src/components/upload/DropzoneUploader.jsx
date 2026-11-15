
import { useRef, useState } from "react";
import { UploadCloud, FileSpreadsheet } from "lucide-react";
import Button from "../common/Button";

export default function DropzoneUploader({ onFileSelected }) {
  const inputRef = useRef(null);
  const [isDragging, setIsDragging] = useState(false);
  const [fileName, setFileName] = useState(null);

  const handleFiles = (files) => {
    const file = files?.[0];
    if (!file) return;
    setFileName(file.name);
    onFileSelected?.(file);
  };

  return (
    <div
      onDragOver={(e) => {
        e.preventDefault();
        setIsDragging(true);
      }}
      onDragLeave={() => setIsDragging(false)}
      onDrop={(e) => {
        e.preventDefault();
        setIsDragging(false);
        handleFiles(e.dataTransfer.files);
      }}
      className={`flex min-w-0 flex-col items-center justify-center rounded-card border-2 border-dashed px-4 py-10 text-center transition-default sm:px-6 sm:py-14 ${
        isDragging
          ? "border-orange bg-orange-50/50"
          : "border-surface-border bg-white hover:border-ink/20"
      }`}
    >
      <div className="mb-4 flex h-12 w-12 shrink-0 items-center justify-center rounded-full bg-orange-50 sm:h-14 sm:w-14">
        {fileName ? (
          <FileSpreadsheet size={21} className="text-orange sm:h-6 sm:w-6" />
        ) : (
          <UploadCloud size={21} className="text-orange sm:h-6 sm:w-6" />
        )}
      </div>

      {fileName ? (
        <>
          <p className="max-w-full break-all text-sm font-medium text-ink">
            {fileName}
          </p>
          <p className="mt-1 text-xs text-ink-secondary">
            Ready to analyze
          </p>
        </>
      ) : (
        <>
          <p className="text-sm font-medium leading-relaxed text-ink sm:text-base">
            Drag and drop your dataset here
          </p>
          <p className="mt-1 text-xs text-ink-secondary">or</p>
        </>
      )}

      <input
        ref={inputRef}
        type="file"
        accept=".csv"
        className="hidden"
        onChange={(e) => handleFiles(e.target.files)}
      />

      <Button
        size="sm"
        variant="secondary"
        className="mt-4 w-full justify-center sm:w-auto"
        onClick={() => inputRef.current?.click()}
      >
        {fileName ? "Choose a different file" : "Choose File"}
      </Button>

      <p className="mt-5 max-w-full text-[10px] leading-relaxed text-ink-muted sm:text-[11px]">
        Supported format: CSV &middot; Maximum file size: 50 MB
      </p>
    </div>
  );
}
