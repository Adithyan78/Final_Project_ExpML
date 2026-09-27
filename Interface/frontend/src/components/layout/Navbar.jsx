import { Menu, Search, Bell } from "lucide-react";

export default function Navbar({ onMenuClick }) {
  return (
    <header className="h-16 shrink-0 bg-white border-b border-surface-border flex items-center justify-between px-4 md:px-6">
      <div className="flex items-center gap-3 flex-1 min-w-0">
        <button
          onClick={onMenuClick}
          className="lg:hidden p-2 -ml-2 text-ink-secondary hover:text-ink rounded-lg hover:bg-surface-page"
          aria-label="Open menu"
        >
          <Menu size={20} />
        </button>
        <div className="hidden sm:flex items-center gap-2 bg-surface-page border border-surface-border rounded-lg px-3 py-1.5 w-full max-w-xs">
          <Search size={15} className="text-ink-muted shrink-0" />
          <input
            type="text"
            placeholder="Search experiments, datasets..."
            className="bg-transparent text-sm text-ink placeholder:text-ink-muted outline-none w-full"
          />
        </div>
      </div>
      <div className="flex items-center gap-3 shrink-0">
        <button
          className="relative p-2 text-ink-secondary hover:text-ink rounded-lg hover:bg-surface-page transition-default"
          aria-label="Notifications"
        >
          <Bell size={18} />
          <span className="absolute top-1.5 right-1.5 w-1.5 h-1.5 rounded-full bg-orange" />
        </button>
      </div>
    </header>
  );
}
