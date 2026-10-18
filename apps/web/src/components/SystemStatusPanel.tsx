import { AlertTriangle, Check, LoaderCircle } from "lucide-react";

import type { SystemPromptStatus } from "../types/system";

type SystemStatusPanelProps = {
  status: SystemPromptStatus | null;
  isLoading: boolean;
};

export function SystemStatusPanel({
  status,
  isLoading,
}: SystemStatusPanelProps) {
  const loaded = status?.loaded ?? false;
  const Icon = isLoading ? LoaderCircle : loaded ? Check : AlertTriangle;
  const title = isLoading
    ? "正在载入系统规则"
    : loaded
      ? "系统规则已载入"
      : "系统规则未载入";
  const friendlyVersion = "V7 主系统｜流程导航｜分镜提示词";

  return (
    <section className="flex items-center justify-between gap-5 border border-white/15 bg-[#151b21]/85 p-7 shadow-2xl shadow-black/15">
      <div className="flex items-center gap-5">
        <div
          className={`grid size-16 shrink-0 place-items-center rounded-full border-2 ${
            loaded
              ? "border-orange-400 text-orange-400"
              : "border-zinc-600 text-zinc-400"
          }`}
        >
          <Icon
            size={34}
            strokeWidth={1.8}
            className={isLoading ? "animate-spin" : ""}
          />
        </div>
        <div>
          <h2 className="text-2xl font-semibold tracking-wide text-zinc-100">
            {title}
          </h2>
          <p className="mt-2 text-base text-zinc-400">{friendlyVersion}</p>
          {status?.filename ? (
            <p className="mt-1 text-xs text-zinc-600">
              已连接当前主系统文件，详细版本可在“成本与设置”核对。
            </p>
          ) : null}
          {status?.error && (
            <p className="mt-2 text-xs text-amber-300">{status.error}</p>
          )}
        </div>
      </div>

      <div className="flex items-center gap-2 rounded-md border border-white/15 bg-black/10 px-4 py-3 text-sm text-zinc-300">
        <span className="size-2.5 rounded-full bg-orange-400" />
        <span>AI 逐次确认</span>
      </div>
    </section>
  );
}
