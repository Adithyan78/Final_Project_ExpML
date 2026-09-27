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
      className={`flex flex-col items-center justify-center text-center border-2 border-dashed rounded-card py-14 px-6 transition-default ${
        isDragging
          ? "border-orange bg-orange-50/50"
          : "border-surface-border bg-white hover:border-ink/20"
      }`}
    >
      <div className="w-12 h-12 rounded-full bg-orange-50 flex items-center justify-center mb-4">
        {fileName ? (
          <FileSpreadsheet size={20} className="text-orange" />
        ) : (
          <UploadCloud size={20} className="text-orange" />
        )}
      </div>

      {fileName ? (
        <>
          <p className="text-sm font-medium text-ink">{fileName}</p>
          <p className="text-xs text-ink-secondary mt-1">
            Ready to analyze
          </p>
        </>
      ) : (
        <>
          <p className="text-sm font-medium text-ink">
            Drag and drop your dataset here
          </p>
          <p className="text-xs text-ink-secondary mt-1">or</p>
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
        className="mt-3"
        onClick={() => inputRef.current?.click()}
      >
        {fileName ? "Choose a different file" : "Choose File"}
      </Button>

      <p className="text-[11px] text-ink-muted mt-5">
        Supported format: CSV &middot; Maximum file size: 50 MB
      </p>
    </div>
  );
}
