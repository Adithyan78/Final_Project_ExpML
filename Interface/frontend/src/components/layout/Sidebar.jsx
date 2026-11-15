
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
      { label: "Analyzes", path: ROUTES.TRAINING, icon: "Cpu" },
      { label: "Preprocessing", path: ROUTES.PREPROCESSING, icon: "Workflow" },
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
    <aside className="flex h-full w-full min-w-0 shrink-0 flex-col border-r border-surface-border bg-white sm:w-[232px]">
      {/* Brand */}
      <div className="flex h-16 shrink-0 items-center gap-2 border-b border-surface-border px-4 sm:px-5">
        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-orange">
          <Boxes size={17} className="text-white" strokeWidth={2.25} />
        </div>
        <span className="truncate text-[15px] font-semibold tracking-tight text-ink">
          AutoExplainAI
        </span>
      </div>

      {/* Navigation */}
      <nav className="min-h-0 flex-1 space-y-5 overflow-y-auto overscroll-contain px-3 py-4">
        {NAV_SECTIONS.map((section, i) => (
          <div key={i}>
            {section.heading && (
              <p className="mb-2 px-3 text-[10px] font-semibold uppercase tracking-wider text-ink-muted sm:text-[11px]">
                {section.heading}
              </p>
            )}

            <div className="space-y-1">
              {section.items.map((item) => {
                const Icon = ICONS[item.icon];

                return (
                  <NavLink
                    key={item.path}
                    to={item.path}
                    onClick={onNavigate}
                    className={({ isActive }) =>
                      `flex min-h-10 items-center gap-3 rounded-lg px-3 py-2.5 text-sm transition-default ${
                        isActive
                          ? "bg-orange-50 font-medium text-orange"
                          : "text-ink-secondary hover:bg-surface-page hover:text-ink"
                      }`
                    }
                  >
                    <Icon size={17} strokeWidth={2} className="shrink-0" />
                    <span className="min-w-0 truncate">{item.label}</span>
                  </NavLink>
                );
              })}
            </div>
          </div>
        ))}
      </nav>

      {/* User Profile and Logout */}
      <div className="shrink-0 border-t border-surface-border px-3 py-3 sm:py-4">
        <div className="flex min-w-0 items-center gap-2.5 px-2 py-2">
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-ink text-xs font-semibold text-white">
            {getInitials(user?.name)}
          </div>

          <div className="min-w-0 flex-1">
            <p className="truncate text-xs font-medium text-ink">
              {profileLoading ? "Loading profile..." : user?.name || "Account"}
            </p>
            <p className="truncate text-[11px] text-ink-muted">
              {user?.email || "Signed-in workspace"}
            </p>
          </div>
        </div>

        {logoutError && (
          <p
            role="alert"
            className="mt-1 break-words px-2 text-xs leading-relaxed text-state-error"
          >
            {logoutError}
          </p>
        )}

        <button
          type="button"
          onClick={handleLogout}
          disabled={loggingOut}
          className="mt-2 flex min-h-10 w-full items-center gap-2.5 rounded-lg px-3 py-2 text-sm text-ink-secondary transition-default hover:bg-red-50 hover:text-red-600 disabled:opacity-50"
        >
          {loggingOut ? (
            <LoaderCircle size={17} className="shrink-0 animate-spin" />
          ) : (
            <LogOut size={17} className="shrink-0" />
          )}
          <span>{loggingOut ? "Logging out..." : "Log out"}</span>
        </button>
      </div>
    </aside>
  );
}
