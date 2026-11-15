
import { Menu, Search, Bell } from "lucide-react";

export default function Navbar({ onMenuClick }) {
  return (
    <header className="flex h-14 w-full shrink-0 items-center justify-between border-b border-surface-border bg-white px-3 sm:h-16 sm:px-4 md:px-6">
      <div className="flex min-w-0 flex-1 items-center gap-2 sm:gap-3">
        <button
          type="button"
          onClick={onMenuClick}
          className="-ml-1 flex h-10 w-10 shrink-0 items-center justify-center rounded-lg text-ink-secondary transition-default hover:bg-surface-page hover:text-ink sm:-ml-2"
          aria-label="Open menu"
        >
          <Menu size={20} />
        </button>

        <div className="hidden w-full max-w-xs items-center gap-2 rounded-lg border border-surface-border bg-surface-page px-3 py-2 sm:flex">
          <Search size={15} className="shrink-0 text-ink-muted" />
          <input
            type="text"
            placeholder="Search experiments, datasets..."
            className="w-full min-w-0 bg-transparent text-sm text-ink outline-none placeholder:text-ink-muted"
          />
        </div>
      </div>

      <div className="flex shrink-0 items-center gap-2 sm:gap-3">
        <button
          type="button"
          className="relative flex h-10 w-10 items-center justify-center rounded-lg text-ink-secondary transition-default hover:bg-surface-page hover:text-ink"
          aria-label="Notifications"
        >
          <Bell size={18} />
          <span className="absolute right-2 top-2 h-1.5 w-1.5 rounded-full bg-orange" />
        </button>
      </div>
    </header>
  );
}
