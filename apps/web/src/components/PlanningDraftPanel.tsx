import { ClipboardList, CheckCircle2 } from "lucide-react";

import { useWorkbenchStore } from "../stores/useWorkbenchStore";

export function PlanningDraftPanel() {
  const { planningDrafts, sourceTextExtractions, isBusy, applyDraft } =
    useWorkbenchStore();
  const latestDraft = planningDrafts[0];
  const latestExtraction = sourceTextExtractions[0];
  const applied = latestDraft?.status === "applied";
  const shotCount = latestDraft?.items.length ?? 0;
  const looksIncomplete = Boolean(
    latestDraft &&
    shotCount <= 1 &&
    latestExtraction?.status === "extracted" &&
    latestExtraction.character_count > 800,
  );

  if (!latestDraft) {
    return null;
  }

  return (
    <section
      id="planning-draft-panel"
      className="mt-5 border border-white/15 bg-[#151b21]/90 p-5"
    >
      <div className="flex items-center justify-between gap-4">
        <div className="flex items-center gap-2 text-orange-300">
          <ClipboardList size={18} />
          <h2 className="font-semibold tracking-wide">
            {applied ? "已确认分镜规划" : "确认分镜规划"}
          </h2>
        </div>
        {applied ? (
          <span className="inline-flex items-center gap-1 text-xs text-emerald-300">
            <CheckCircle2 size={14} /> 已用于当前项目
          </span>
        ) : null}
      </div>

      <div className="mt-5">
        <div className="flex items-center justify-between gap-3">
          <div>
            <p className="text-sm font-medium text-zinc-100">
              AI 拆分出 {shotCount} 个镜头，请确认是否按这个顺序继续。
            </p>
            <p className="mt-1 text-xs leading-5 text-zinc-500">
              {latestDraft.summary}
            </p>
            <p className="mt-2 text-xs text-zinc-500">
              {applied
                ? "这份规划已经写入当前项目，后面的分镜提示词会按它生成。"
                : "确认后才会写入项目，系统不会自动替你覆盖。"}
              {latestDraft.applied_at
                ? `｜确认时间：${new Date(latestDraft.applied_at).toLocaleString("zh-CN")}`
                : ""}
            </p>
            {looksIncomplete ? (
              <p className="mt-3 border-l-2 border-amber-300 bg-amber-300/10 px-3 py-2 text-xs leading-5 text-amber-100">
                这份规划只拆出 1
                个镜头，但当前资料较长，通常不是完整分镜。请使用上方主按钮重新生成完整分镜规划。
              </p>
            ) : null}
          </div>
          <button
            type="button"
            disabled={isBusy || applied}
            onClick={() => void applyDraft(latestDraft.id)}
            className="shrink-0 border border-orange-400/50 px-4 py-3 text-sm font-semibold text-orange-200 transition hover:bg-orange-400/10 disabled:cursor-not-allowed disabled:opacity-45"
          >
            {applied ? "已确认使用" : "确认并使用这份规划"}
          </button>
        </div>
        <div className="mt-4 overflow-hidden border border-white/10">
          <table className="w-full text-left text-xs">
            <thead className="bg-black/20 text-zinc-500">
              <tr>
                <th className="px-3 py-2">集</th>
                <th className="px-3 py-2">场</th>
                <th className="px-3 py-2">镜头</th>
                <th className="px-3 py-2">原文片段</th>
                <th className="px-3 py-2">这一镜要拍什么</th>
                <th className="px-3 py-2">状态</th>
              </tr>
            </thead>
            <tbody>
              {latestDraft.items.map((item) => (
                <tr
                  key={item.id}
                  className="border-t border-white/10 text-zinc-300"
                >
                  <td className="px-3 py-2 text-orange-200">
                    {item.episode_code}
                  </td>
                  <td className="px-3 py-2">{item.scene_code}</td>
                  <td className="px-3 py-2">{item.shot_code}</td>
                  <td className="max-w-[260px] px-3 py-2">
                    {item.source_excerpt}
                  </td>
                  <td className="max-w-[280px] px-3 py-2">
                    {item.suggested_task}
                  </td>
                  <td className="px-3 py-2">
                    {item.status === "applied" ? "已确认" : "待确认"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  );
}
