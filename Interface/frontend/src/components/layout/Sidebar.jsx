
import { useEffect, useState } from "react";
import { NavLink, useNavigate } from "react-router-dom";
import {
  LayoutGrid,
  Database,
  Cpu,
  BarChart3,
  Lightbulb,
  MessageSquare,
  History,
  Boxes,
  Workflow,
  LogOut,
  LoaderCircle,
} from "lucide-react";

import { ROUTES } from "../../constants/routes";
import { getCurrentUser, logout } from "../../services/auth";

const ICONS = {
  LayoutGrid,
  Database,
  Cpu,
  BarChart3,
  Lightbulb,
  MessageSquare,
  History,
  Workflow,
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
      { label: "Preprocessing", path: ROUTES.PREPROCESSING, icon: "Workflow" },
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

function getInitials(name = "") {
  return name
    .trim()
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0].toUpperCase())
    .join("") || "U";
}

export default function Sidebar({ onNavigate }) {
  const navigate = useNavigate();
  const [user, setUser] = useState(null);
  const [loggingOut, setLoggingOut] = useState(false);
  const [profileLoading, setProfileLoading] = useState(true);
  const [logoutError, setLogoutError] = useState("");

  useEffect(() => {
    let active = true;

    getCurrentUser()
      .then((data) => {
        if (active) setUser(data?.user ?? data ?? null);
      })
      .catch(() => {
        if (active) setUser(null);
      })
      .finally(() => {
        if (active) setProfileLoading(false);
      });

    return () => {
      active = false;
    };
  }, []);

  const handleLogout = async () => {
    if (loggingOut) return;

    setLoggingOut(true);
    setLogoutError("");

    try {
      await logout();
      setUser(null);
      navigate(ROUTES.LOGIN, { replace: true });
    } catch (error) {
      setLogoutError(error?.message || "Logout failed. Please try again.");
      setLoggingOut(false);
    }
  };

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
        <div className="flex items-center gap-2.5 px-2 py-2">
          <div className="w-8 h-8 rounded-full bg-ink flex items-center justify-center text-white text-xs font-semibold shrink-0">
            {getInitials(user?.name)}
          </div>

          <div className="min-w-0 flex-1">
            <p className="text-xs font-medium text-ink truncate">
              {profileLoading ? "Loading profile..." : user?.name || "Account"}
            </p>
            <p className="text-[11px] text-ink-muted truncate">
              {user?.email || "Signed-in workspace"}
            </p>
          </div>
        </div>

        {logoutError && (
          <p role="alert" className="px-2 mt-1 text-xs text-state-error">
            {logoutError}
          </p>
        )}

        <button
          type="button"
          onClick={handleLogout}
          disabled={loggingOut}
          className="mt-2 flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-sm text-ink-secondary hover:bg-red-50 hover:text-red-600 disabled:opacity-50 transition-default"
        >
          {loggingOut ? (
            <LoaderCircle size={16} className="animate-spin" />
          ) : (
            <LogOut size={16} />
          )}
          {loggingOut ? "Logging out..." : "Log out"}
        </button>
      </div>
    </aside>
  );
}
