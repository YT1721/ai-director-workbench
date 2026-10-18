import { ChevronLeft, ChevronRight, Film } from "lucide-react";
import { useEffect, useState } from "react";
import { NavLink } from "react-router-dom";

import { navigationItems } from "../data/navigation";
import { fetchFlowNav } from "../services/api";
import { useWorkbenchStore } from "../stores/useWorkbenchStore";
import type { FlowNav, FlowNavItem } from "../types/flowNav";
import { humanizeCopy } from "../utils/humanCopy";

const statusClasses = {
  done: "border-emerald-400/70 bg-emerald-400/8 text-emerald-200",
  current: "border-orange-400 bg-orange-400/10 text-orange-200",
  blocked: "border-red-400/70 bg-red-400/8 text-red-200",
  pending:
    "border-transparent text-zinc-400 hover:bg-white/4 hover:text-zinc-100",
  optional: "border-sky-400/50 bg-sky-400/5 text-sky-200",
};

function itemForNav(flow: FlowNav | null, key: string): FlowNavItem | null {
  if (!flow) return null;
  if (key === "home") {
    return {
      key: "home",
      label: "项目总控台",
      command: "项目管理",
      marker: "可选辅助",
      status_level: "optional",
      short_status: "切换 / 新建项目",
      detail: "查看项目卡片、切换项目、新建项目和管理项目。",
      href: "/",
    };
  }
  if (key === "settings") {
    return {
      key: "settings",
      label: "成本与设置",
      command: "设置",
      marker: "可选辅助",
      status_level: "optional",
      short_status: "服务配置",
      detail: "模型服务、成本与系统状态。",
      href: "/settings",
    };
  }
  if (key === "check") {
    const check = flow.directory.find((item) => item.key === "check") ?? null;
    return check ? { ...check, label: "流程体检" } : null;
  }
  return flow.directory.find((item) => item.key === key) ?? null;
}

type NavigationItem = (typeof navigationItems)[number] & { flowKey?: string };

function navigationForFlow(flow: FlowNav | null): NavigationItem[] {
  if (!flow) return navigationItems;
  const byKey = new Map(navigationItems.map((item) => [item.key, item]));
  const draft = flow.directory.find(
    (item) => item.key === "video_package_draft",
  );
  const storyboard = flow.directory.find((item) => item.key === "storyboard");
  const visiblePromptKey =
    draft?.status_level !== "done" || storyboard?.status_level !== "done"
      ? "video_package_draft"
      : "video_package";
  const productionKeys = flow.directory
    .map((item) => item.key)
    .filter((key) =>
      [visiblePromptKey, "storyboard", "assets", "batch_video"].includes(key),
    );
  const core = productionKeys.map((flowKey) => {
    const navKey =
      flowKey === "video_package_draft" || flowKey === "video_package"
        ? "video_package"
        : flowKey;
    return { ...byKey.get(navKey)!, flowKey };
  });
  return [
    byKey.get("home")!,
    byKey.get("start")!,
    ...core,
    byKey.get("check")!,
    byKey.get("settings")!,
  ];
}

type SidebarProps = {
  collapsed: boolean;
  onToggleCollapsed: () => void;
};

export function Sidebar({ collapsed, onToggleCollapsed }: SidebarProps) {
  const activeProject = useWorkbenchStore((state) => state.activeProject);
  const [flow, setFlow] = useState<FlowNav | null>(null);

  const load = () => {
    if (!activeProject) {
      setFlow(null);
      return;
    }
    void fetchFlowNav(activeProject.id)
      .then(setFlow)
      .catch(() => setFlow(null));
  };

  useEffect(load, [activeProject?.id]);
  useEffect(() => {
    window.addEventListener("flow-nav-refresh", load);
    return () => window.removeEventListener("flow-nav-refresh", load);
  });

  return (
    <aside
      className={`fixed inset-y-0 left-0 z-40 flex flex-col border-r border-white/10 bg-[#11171c] transition-[width] duration-200 ${collapsed ? "w-[72px]" : "w-[236px]"}`}
    >
      <div
        className={`flex h-[72px] items-center gap-3 border-b border-white/10 ${collapsed ? "justify-center px-0" : "px-5"}`}
      >
        <div className="grid size-9 place-items-center rounded-md border border-orange-400/60 bg-orange-400/10 text-orange-400">
          <Film size={19} />
        </div>
        <div className={collapsed ? "hidden" : ""}>
          <p className="text-base font-semibold tracking-wide text-white">
            AI导演工作台
          </p>
          <p className="mt-0.5 text-[11px] tracking-[0.12em] text-zinc-500">
            导演创作台
          </p>
        </div>
      </div>

      <nav
        className={`flex-1 py-5 ${collapsed ? "px-2" : "px-3"}`}
        aria-label="主导航"
      >
        <ul className="space-y-1">
          {navigationForFlow(flow).map(
            ({ key, flowKey, href, label, icon: Icon }) => {
              const flowItem = itemForNav(flow, flowKey ?? key);
              const visibleLabel = humanizeCopy(flowItem?.label ?? label);
              return (
                <li key={`${href}-${flowKey ?? key}`}>
                  <NavLink
                    to={href}
                    end={href === "/"}
                    title={
                      collapsed
                        ? `${visibleLabel}｜${humanizeCopy(flowItem?.short_status ?? (activeProject ? "读取状态" : "等待项目"))}`
                        : undefined
                    }
                    className={({ isActive }) =>
                      `flex items-center rounded-md border-l-2 py-3 text-sm transition ${
                        collapsed ? "justify-center px-2" : "gap-3 px-3"
                      } ${
                        isActive
                          ? "border-orange-400 bg-orange-400/8 text-orange-300"
                          : flowItem
                            ? statusClasses[flowItem.status_level]
                            : "border-transparent text-zinc-400 hover:bg-white/4 hover:text-zinc-100"
                      }`
                    }
                  >
                    <Icon size={19} strokeWidth={1.7} />
                    <span className={collapsed ? "hidden" : "min-w-0"}>
                      <span className="block">{visibleLabel}</span>
                      <span className="mt-0.5 block truncate text-[11px] opacity-70">
                        {humanizeCopy(
                          flowItem?.short_status ??
                            (activeProject ? "读取状态" : "等待项目"),
                        )}
                      </span>
                    </span>
                  </NavLink>
                </li>
              );
            },
          )}
        </ul>
      </nav>

      <div
        className={`border-t border-white/10 py-3 ${collapsed ? "px-2" : "px-3"}`}
      >
        <button
          type="button"
          onClick={onToggleCollapsed}
          className={`flex w-full items-center rounded-md border border-white/10 py-2 text-xs text-zinc-500 transition hover:border-orange-400/30 hover:bg-orange-400/5 hover:text-zinc-200 ${
            collapsed ? "justify-center" : "justify-center gap-2"
          }`}
          aria-label={collapsed ? "展开菜单" : "收起菜单"}
          title={collapsed ? "展开菜单" : "收起菜单"}
        >
          {collapsed ? <ChevronRight size={18} /> : <ChevronLeft size={18} />}
          <span className={collapsed ? "hidden" : ""}>收起侧栏</span>
        </button>
      </div>
    </aside>
  );
}
