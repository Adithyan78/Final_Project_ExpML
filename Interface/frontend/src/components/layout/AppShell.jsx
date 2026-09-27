import { useState } from "react";
import Sidebar from "./Sidebar";
import Navbar from "./Navbar";

export default function AppShell({ children }) {
  const [drawerOpen, setDrawerOpen] = useState(false);

  return (
    <div className="flex h-screen bg-surface-page overflow-hidden">
      {/* Desktop sidebar */}
      <div className="hidden lg:block">
        <Sidebar />
      </div>

      {/* Mobile drawer */}
      {drawerOpen && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <div
            className="absolute inset-0 bg-ink/40"
            onClick={() => setDrawerOpen(false)}
          />
          <div className="relative h-full animate-fadeIn">
            <Sidebar onNavigate={() => setDrawerOpen(false)} />
          </div>
        </div>
      )}

      <div className="flex-1 flex flex-col min-w-0">
        <Navbar onMenuClick={() => setDrawerOpen(true)} />
        <main className="flex-1 overflow-y-auto">
          <div className="max-w-[1400px] mx-auto px-4 md:px-8 py-6 md:py-8">
            {children}
          </div>
        </main>
      </div>
    </div>
  );
}
