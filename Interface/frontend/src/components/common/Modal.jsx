
import { X } from "lucide-react";

export default function Modal({ open, onClose, title, children, footer }) {
  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center overflow-y-auto p-3 sm:p-4">
      <div
        className="absolute inset-0 bg-ink/40 animate-fadeIn"
        onClick={onClose}
      />

      <div className="relative my-auto flex max-h-[calc(100dvh-1.5rem)] w-full max-w-md flex-col overflow-hidden rounded-card border border-surface-border bg-white shadow-elevated animate-fadeIn sm:max-h-[calc(100dvh-2rem)]">
        <div className="flex shrink-0 items-center justify-between gap-3 border-b border-surface-border px-4 py-3 sm:px-5 sm:py-4">
          <h3 className="min-w-0 text-sm font-semibold text-ink">
            {title}
          </h3>

          <button
            type="button"
            onClick={onClose}
            className="flex h-8 w-8 shrink-0 items-center justify-center rounded text-ink-muted transition-default hover:bg-surface-page hover:text-ink"
            aria-label="Close"
          >
            <X size={16} />
          </button>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto px-4 py-4 sm:px-5">
          {children}
        </div>

        {footer && (
          <div className="flex shrink-0 flex-col-reverse gap-2 border-t border-surface-border px-4 py-3 sm:flex-row sm:justify-end sm:px-5 sm:py-4">
            {footer}
          </div>
        )}
      </div>
    </div>
  );
}
