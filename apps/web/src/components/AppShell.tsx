import { Clapperboard, PanelLeftClose } from "lucide-react";
import { useState } from "react";
import { Outlet, useLocation } from "react-router-dom";

import { Sidebar } from "./Sidebar";
import { FlowNavPanel } from "./FlowNavPanel";

export function AppShell() {
  const location = useLocation();
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const isProjectConsole = location.pathname === "/";
  const sidebarWidthClass = sidebarCollapsed ? "left-[72px]" : "left-[236px]";
  const mainPaddingClass = sidebarCollapsed ? "pl-[72px]" : "pl-[236px]";
  return (
    <div className="min-h-screen min-w-[1440px] bg-[#0e1318]/90 text-zinc-100">
      <header
        className={`fixed right-0 top-0 ${sidebarWidthClass} z-30 flex h-[72px] items-center border-b border-white/10 bg-[#11171c]/95 backdrop-blur transition-[left] duration-200`}
      >
        <div className="flex w-full items-center justify-between px-8">
          <div className="flex items-center gap-3 text-sm text-zinc-500">
            <PanelLeftClose size={19} />
            <span>导演工作台</span>
          </div>
          <div className="flex items-center gap-2 text-sm text-zinc-400">
            <Clapperboard size={17} className="text-orange-400" />
            <span>V7｜创作向导 + 分镜提示词</span>
          </div>
        </div>
      </header>

      <Sidebar
        collapsed={sidebarCollapsed}
        onToggleCollapsed={() => setSidebarCollapsed((value) => !value)}
      />

      <main
        className={`min-h-screen ${mainPaddingClass} pt-[72px] transition-[padding] duration-200`}
      >
        {isProjectConsole ? null : <FlowNavPanel />}
        <Outlet />
      </main>
    </div>
  );
}
