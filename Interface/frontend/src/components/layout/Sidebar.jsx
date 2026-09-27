import { NavLink } from "react-router-dom";
import {
  LayoutGrid,
  Database,
  Cpu,
  BarChart3,
  Lightbulb,
  MessageSquare,
  History,
  Boxes,
  X,
} from "lucide-react";
import { ROUTES } from "../../constants/routes";

const ICONS = {
  LayoutGrid,
  Database,
  Cpu,
  BarChart3,
  Lightbulb,
  MessageSquare,
  History,
};

const NAV_SECTIONS = [
  {
    items: [
      { label: "Home", path: ROUTES.DASHBOARD, icon: "LayoutGrid" },
      { label: "Datasets", path: ROUTES.UPLOAD, icon: "Database" },
    ],
  },
  {
    heading: "Pipeline",
    items: [
      { label: "Training", path: ROUTES.TRAINING, icon: "Cpu" },
      { label: "Models", path: ROUTES.COMPARISON, icon: "BarChart3" },
      { label: "Explainability", path: ROUTES.EXPLAINABILITY, icon: "Lightbulb" },
    ],
  },
  {
    heading: "Workspace",
    items: [
      { label: "AI Assistant", path: ROUTES.CHAT, icon: "MessageSquare" },
      { label: "History", path: ROUTES.HISTORY, icon: "History" },
    ],
  },
];

export default function Sidebar({ onNavigate }) {
  return (
    <aside className="flex flex-col h-full w-[232px] bg-white border-r border-surface-border shrink-0">
      <div className="flex items-center gap-2 px-5 h-16 border-b border-surface-border">
        <div className="w-7 h-7 rounded-md bg-orange flex items-center justify-center shrink-0">
          <Boxes size={16} className="text-white" strokeWidth={2.25} />
        </div>
        <span className="text-[15px] font-semibold text-ink tracking-tight">
          AutoExplainAI
        </span>
      </div>

      <nav className="flex-1 overflow-y-auto px-3 py-4 space-y-5">
        {NAV_SECTIONS.map((section, i) => (
          <div key={i}>
            {section.heading && (
              <p className="px-3 mb-1.5 text-[11px] font-medium uppercase tracking-wide text-ink-muted">
                {section.heading}
              </p>
            )}
            <div className="space-y-0.5">
              {section.items.map((item) => {
                const Icon = ICONS[item.icon];
                return (
                  <NavLink
                    key={item.path}
                    to={item.path}
                    onClick={onNavigate}
                    className={({ isActive }) =>
                      `flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm transition-default ${
                        isActive
                          ? "bg-orange-50 text-orange font-medium"
                          : "text-ink-secondary hover:bg-surface-page hover:text-ink"
                      }`
                    }
                  >
                    <Icon size={16} strokeWidth={2} />
                    {item.label}
                  </NavLink>
                );
              })}
            </div>
          </div>
        ))}
      </nav>

      <div className="px-3 py-4 border-t border-surface-border">
        <div className="flex items-center gap-2.5 px-3 py-2 rounded-lg hover:bg-surface-page transition-default cursor-pointer">
          <div className="w-7 h-7 rounded-full bg-ink flex items-center justify-center text-white text-xs font-semibold shrink-0">
            M
          </div>
          <div className="min-w-0">
            <p className="text-xs font-medium text-ink truncate">Manu</p>
            <p className="text-[11px] text-ink-muted truncate">Personal workspace</p>
          </div>
        </div>
      </div>
    </aside>
  );
}
