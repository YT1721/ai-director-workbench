import { ChevronDown, ChevronUp, Compass, RefreshCw } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useLocation } from "react-router-dom";

import { fetchFlowNav } from "../services/api";
import { useWorkbenchStore } from "../stores/useWorkbenchStore";
import type { FlowNav } from "../types/flowNav";
import { creativeGoalOptions, goalTargetReached } from "../utils/creativeGoal";
import { humanizeCopy } from "../utils/humanCopy";

const markerClass: Record<string, string> = {
  已完成: "text-emerald-300",
  当前建议: "text-orange-300",
  待进行: "text-zinc-500",
  可选辅助: "text-sky-300",
};

const statusBorder = {
  done: "border-emerald-400/40 bg-emerald-400/8",
  current: "border-orange-400/50 bg-orange-400/8",
  blocked: "border-red-400/45 bg-red-400/8",
  pending: "border-white/10 bg-black/10",
  optional: "border-sky-400/30 bg-sky-400/5",
};

export function FlowNavPanel() {
  const { activeProject, creativeGoal } = useWorkbenchStore();
  const location = useLocation();
  const [data, setData] = useState<FlowNav | null>(null);
  const [expanded, setExpanded] = useState(false);
  const [error, setError] = useState("");

  const load = () => {
    if (!activeProject) return;
    void fetchFlowNav(activeProject.id)
      .then(setData)
      .catch((cause: Error) => setError(cause.message));
  };

  useEffect(load, [activeProject?.id, location.pathname]);
  useEffect(() => {
    window.addEventListener("flow-nav-refresh", load);
    return () => window.removeEventListener("flow-nav-refresh", load);
  });

  if (!activeProject || !data) return null;
  const currentItem = data.directory.find(
    (item) => item.status_level === "current",
  );
  const targetReached = goalTargetReached(creativeGoal, data);

  return (
    <section className="mx-10 mt-6 overflow-hidden rounded-[28px] border border-white/10 bg-[#12181e]/90 shadow-xl shadow-black/15 backdrop-blur">
      <div className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-4 px-5 py-4">
        <div className="min-w-0">
          <div className="flex items-center gap-3">
            <Compass size={18} className="text-orange-400" />
            <p className="text-sm font-semibold text-zinc-100">下一步</p>
            <span className="border border-white/10 bg-black/15 px-2 py-0.5 text-[11px] text-zinc-500">
              {data.project_code}｜{data.scope_code}
            </span>
          </div>
          <p className="mt-2 truncate text-sm text-zinc-400">
            现在该做：
            <span className="font-medium text-orange-200">
              {humanizeCopy(data.current_stage)}
            </span>
            <span className="mx-2 text-zinc-700">/</span>
            {targetReached
              ? `本次目标已完成：${creativeGoalOptions[creativeGoal].stopAfter}`
              : humanizeCopy(data.blocking_reason || data.next_reason)}
          </p>
        </div>
        <button
          className="flex items-center gap-2 border border-white/10 px-3 py-2 text-xs text-zinc-400 transition hover:border-white/20 hover:text-zinc-200"
          onClick={() => setExpanded(!expanded)}
          type="button"
        >
          {expanded ? "收起流程" : "展开流程"}
          {expanded ? <ChevronUp size={15} /> : <ChevronDown size={15} />}
        </button>
      </div>
      {expanded && (
        <div className="border-t border-white/10 px-5 py-5">
          <div className="grid grid-cols-[minmax(0,1fr)_320px] gap-5">
            <div>
              <div className="mb-3 flex items-center justify-between">
                <p className="text-xs tracking-wide text-orange-300">
                  流程进度
                </p>
                <button aria-label="刷新流程导航" onClick={load} type="button">
                  <RefreshCw size={14} className="text-zinc-500" />
                </button>
              </div>
              <div className="grid grid-cols-4 gap-2">
                {data.directory.map((item) => (
                  <Link
                    className={`min-h-16 border px-3 py-2 text-xs ${markerClass[item.marker]} ${statusBorder[item.status_level]}`}
                    key={item.key}
                    to={item.href}
                  >
                    <span className="block truncate">
                      [{item.marker}] {humanizeCopy(item.label)}
                    </span>
                    <span className="mt-1 block truncate text-[11px] opacity-70">
                      {humanizeCopy(item.short_status)}
                    </span>
                  </Link>
                ))}
              </div>
            </div>
            <aside className="border border-white/10 bg-black/15 p-4">
              <p className="text-xs tracking-wide text-orange-300">
                为什么现在做它
              </p>
              <p className="mt-3 text-sm font-medium text-zinc-100">
                {targetReached
                  ? creativeGoalOptions[creativeGoal].title
                  : humanizeCopy(currentItem?.label ?? data.current_stage)}
              </p>
              <p className="mt-2 text-xs leading-5 text-zinc-500">
                {humanizeCopy(currentItem?.detail ?? data.next_reason)}
              </p>
              {targetReached ? (
                <p className="mt-3 border border-emerald-400/25 bg-emerald-400/6 px-3 py-2 text-xs leading-5 text-emerald-100">
                  你已经拿到本次目标需要的内容。可以停在这里整理输出，也可以切到“完整生产流程”继续做批量视频。
                </p>
              ) : null}
              <details className="mt-4 border border-white/10 bg-black/15">
                <summary className="cursor-pointer px-3 py-2 text-xs text-zinc-500 hover:text-zinc-300">
                  可选：查看完整指令
                </summary>
                <code className="block border-t border-white/10 px-3 py-2 text-xs leading-5 text-zinc-400">
                  {humanizeCopy(data.next_command)}
                </code>
              </details>
              {data.director_option ? (
                <p className="mt-3 text-xs text-emerald-300">
                  导演方案：{data.director_option.option_name}｜已确认
                </p>
              ) : null}
              {error ? (
                <p className="mt-2 text-xs text-red-300">{error}</p>
              ) : null}
            </aside>
          </div>
        </div>
      )}
    </section>
  );
}
