import { X } from "lucide-react";

export default function Modal({ open, onClose, title, children, footer }) {
  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div
        className="absolute inset-0 bg-ink/40 animate-fadeIn"
        onClick={onClose}
      />
      <div className="relative bg-white rounded-card border border-surface-border shadow-elevated w-full max-w-md animate-fadeIn">
        <div className="flex items-center justify-between px-5 py-4 border-b border-surface-border">
          <h3 className="text-sm font-semibold text-ink">{title}</h3>
          <button
            onClick={onClose}
            className="text-ink-muted hover:text-ink transition-default rounded p-1"
            aria-label="Close"
          >
            <X size={16} />
          </button>
        </div>
        <div className="px-5 py-4">{children}</div>
        {footer && (
          <div className="px-5 py-4 border-t border-surface-border flex justify-end gap-2">
            {footer}
          </div>
        )}
      </div>
    </div>
  );
}
