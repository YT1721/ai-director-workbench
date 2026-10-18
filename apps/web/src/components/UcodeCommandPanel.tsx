import { CheckCircle2, PlayCircle, ScrollText } from "lucide-react";

import { ucodeActions } from "../data/actions";
import { useWorkbenchStore } from "../stores/useWorkbenchStore";
import { humanizeCopy } from "../utils/humanCopy";

export function UcodeCommandPanel() {
  const {
    activeProject,
    commandDraft,
    latestRun,
    ucodeRuns,
    isBusy,
    updateCommandDraft,
    saveManualRecord,
  } = useWorkbenchStore();

  if (!activeProject) return null;

  return (
    <section
      id="ucode-command-panel"
      className="border border-white/15 bg-[#151b21]/90 p-5"
    >
      <div className="flex items-center gap-2 text-orange-300">
        <ScrollText size={18} />
        <h2 className="font-semibold tracking-wide">
          旧操作记录（一般不用看）
        </h2>
      </div>
      <p className="mt-2 text-xs text-zinc-500">
        这里只保存人工备注和历史操作，方便以后追溯；正式创作请按页面上最醒目的主按钮继续。
      </p>
      <form
        className="mt-4 space-y-3"
        onSubmit={(event) => {
          event.preventDefault();
          void saveManualRecord();
        }}
      >
        <div className="grid grid-cols-2 gap-3">
          <label className="text-xs text-zinc-400">
            动作
            <select
              aria-label="UCODE 动作"
              value={commandDraft.action}
              onChange={(event) =>
                updateCommandDraft({ action: event.target.value })
              }
              className="mt-2 w-full border border-white/15 bg-[#11171c] px-3 py-2.5 text-sm text-zinc-100 outline-none focus:border-orange-400/70"
            >
              {ucodeActions.map((action) => (
                <option key={action.code} value={action.code}>
                  {action.label}
                </option>
              ))}
            </select>
          </label>
          <label className="text-xs text-zinc-400">
            范围
            <input
              aria-label="UCODE 范围"
              value={commandDraft.scopeCode}
              onChange={(event) =>
                updateCommandDraft({ scopeCode: event.target.value })
              }
              className="mt-2 w-full border border-white/15 bg-black/15 px-3 py-2.5 text-sm text-zinc-100 outline-none focus:border-orange-400/70"
            />
          </label>
        </div>
        <label className="block text-xs text-zinc-400">
          补充要求
          <textarea
            aria-label="UCODE 补充要求"
            value={commandDraft.additionalRequest}
            onChange={(event) =>
              updateCommandDraft({ additionalRequest: event.target.value })
            }
            placeholder="例如：先整理本集剧情和角色关系，不生成资产。"
            className="mt-2 min-h-24 w-full resize-y border border-white/15 bg-black/15 px-3 py-2.5 text-sm text-zinc-100 outline-none focus:border-orange-400/70"
          />
        </label>
        <button
          disabled={isBusy || !commandDraft.scopeCode.trim()}
          className="flex items-center gap-2 bg-orange-500 px-4 py-2.5 text-sm font-medium text-black transition hover:bg-orange-400 disabled:opacity-45"
          type="submit"
        >
          <PlayCircle size={17} />
          保存手动记录
        </button>
      </form>

      {latestRun && (
        <div className="mt-5 border-l-2 border-orange-400 bg-orange-400/7 px-4 py-3">
          <div className="flex items-center gap-2 text-sm font-medium text-orange-200">
            <CheckCircle2 size={16} />
            手动记录已保存
          </div>
          <code className="mt-2 block text-xs text-orange-300">
            {latestRun.command_text}
          </code>
          <p className="mt-2 text-sm leading-6 text-zinc-300">
            {humanizeCopy(latestRun.result_summary)}
          </p>
          {latestRun.checkpoints.map((checkpoint) => (
            <p key={checkpoint.id} className="mt-2 text-xs text-amber-200">
              待确认：{humanizeCopy(checkpoint.title)}
            </p>
          ))}
        </div>
      )}

      <div className="mt-6">
        <h3 className="text-sm font-medium text-zinc-200">最近记录</h3>
        <div className="mt-3 space-y-2">
          {ucodeRuns.length === 0 ? (
            <p className="text-sm text-zinc-500">还没有执行记录。</p>
          ) : (
            ucodeRuns.slice(0, 6).map((run) => (
              <div key={run.id} className="border border-white/10 px-3 py-2.5">
                <code className="text-xs text-orange-300">
                  {run.command_text}
                </code>
                <p className="mt-1 text-xs text-zinc-500">
                  {new Date(run.created_at).toLocaleString("zh-CN")}
                  {run.checkpoint_required ? "｜等待人工确认" : "｜已记录"}
                </p>
              </div>
            ))
          )}
        </div>
      </div>
    </section>
  );
}
