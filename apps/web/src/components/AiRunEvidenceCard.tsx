import { BadgeCheck, BrainCircuit, FileClock } from "lucide-react";
import type { AiTextRun, TextProviderStatus } from "../types/workflows";
import { humanizeCopy } from "../utils/humanCopy";

function parseRunMeta(run: AiTextRun): {
  system_version?: string;
  system_prompt_sha256?: string;
} {
  try {
    const parsed = JSON.parse(run.response_json) as {
      system_version?: string;
      system_prompt_sha256?: string;
    };
    return parsed;
  } catch {
    return {};
  }
}

export function AiRunEvidenceCard({
  run,
  status,
}: {
  run: AiTextRun;
  status?: TextProviderStatus | null;
}) {
  const meta = parseRunMeta(run);
  const systemVersion =
    meta.system_version || status?.system_prompt_version || "V7 主系统";
  return (
    <div className="mt-3 grid grid-cols-3 gap-2 text-xs">
      <div className="border border-emerald-400/25 bg-emerald-400/7 p-3 text-emerald-100">
        <div className="flex items-center gap-2 font-medium">
          <BadgeCheck size={14} />
          AI 生成证据
        </div>
        <p className="mt-2 leading-5 text-emerald-100/80">
          服务：{humanizeCopy(run.provider)}｜模型：{run.model_name}
        </p>
      </div>
      <div className="border border-cyan-400/25 bg-cyan-400/7 p-3 text-cyan-100">
        <div className="flex items-center gap-2 font-medium">
          <BrainCircuit size={14} />
          使用的系统规则
        </div>
        <p className="mt-2 leading-5 text-cyan-100/80">{systemVersion}</p>
      </div>
      <div className="border border-orange-400/25 bg-orange-400/7 p-3 text-orange-100">
        <div className="flex items-center gap-2 font-medium">
          <FileClock size={14} />
          请求记录
        </div>
        <p className="mt-2 leading-5 text-orange-100/80">
          {run.cache_hit
            ? "复用历史结果，没有重复请求"
            : "本次新生成，已保存记录"}
        </p>
      </div>
    </div>
  );
}
