import { useEffect, useState } from "react";
import { BrainCircuit, RefreshCw, Sparkles } from "lucide-react";
import { Link } from "react-router-dom";
import { AiRunEvidenceCard } from "./AiRunEvidenceCard";
import { GuideProgress } from "./Guide";
import type {
  AiTextRun,
  AiTextRunCreate,
  TextProviderStatus,
} from "../types/workflows";
import { fetchTextProviderStatus } from "../services/api";
import { humanizeCopy } from "../utils/humanCopy";
import { systemPromptTraceLine } from "../utils/textProviderCopy";

type ControlledTextPanelProps = {
  title: string;
  description: string;
  liveLabel?: string;
  moduleType: string;
  panelId?: string;
  disabled?: boolean;
  disabledReason?: string;
  onLive: (payload: AiTextRunCreate) => Promise<AiTextRun | unknown>;
};

const button =
  "inline-flex items-center gap-2 border border-orange-400/50 px-4 py-2 text-sm text-orange-200 disabled:cursor-not-allowed disabled:opacity-45";

function isTextRun(value: unknown): value is AiTextRun {
  return Boolean(
    value &&
    typeof value === "object" &&
    "response_text" in value &&
    "provider" in value,
  );
}

export function ControlledTextPanel({
  title,
  description,
  liveLabel = "用 AI 生成文字（需确认）",
  moduleType,
  panelId,
  disabled,
  disabledReason,
  onLive,
}: ControlledTextPanelProps) {
  const [status, setStatus] = useState<TextProviderStatus | null>(null);
  const [run, setRun] = useState<AiTextRun | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [pendingForceRegenerate, setPendingForceRegenerate] = useState<
    boolean | null
  >(null);

  useEffect(() => {
    void fetchTextProviderStatus()
      .then(setStatus)
      .catch(() => setStatus(null));
  }, []);

  async function perform(forceRegenerate = false) {
    setBusy(true);
    setError("");
    try {
      const result = await onLive({
        module_type: moduleType,
        provider_mode: status?.mode ?? null,
        confirm_live_request: true,
        force_regenerate: forceRegenerate,
      });
      if (isTextRun(result)) setRun(result);
      window.dispatchEvent(new CustomEvent("flow-nav-refresh"));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "文本分析失败。");
    } finally {
      setBusy(false);
    }
  }

  function requestLive(forceRegenerate = false) {
    setError("");
    setPendingForceRegenerate(forceRegenerate);
  }

  const liveBlocked = disabled || !status || !status.ready;

  return (
    <section
      id={panelId}
      className="mt-5 border border-cyan-400/25 bg-cyan-400/5 p-4"
    >
      <div className="flex items-start justify-between gap-5">
        <div>
          <div className="flex items-center gap-2 text-cyan-200">
            <BrainCircuit size={17} />
            <h2 className="font-semibold">{title}</h2>
          </div>
          <p className="mt-2 text-sm leading-6 text-zinc-400">{description}</p>
          <p className="mt-2 text-xs text-zinc-500">
            当前 AI 分析服务：{status?.mode_label ?? "读取中"}｜
            {status?.real_text_enabled
              ? "文字生成开关已开启"
              : "等待配置 AI 分析服务"}
          </p>
          <p className="mt-2 text-xs leading-5 text-emerald-100/80">
            {systemPromptTraceLine(status)}
          </p>
          <p className="mt-2 text-xs leading-5 text-cyan-100/80">
            文字创作结果只走已配置的 AI
            文字模型；已移除本地草稿入口，避免把规则占位误当成导演级分析。
          </p>
          {(disabledReason || status?.blocking_reason) && (
            <p className="mt-2 text-xs text-amber-200">
              {disabledReason || status?.blocking_reason}
            </p>
          )}
        </div>
        <div className="flex flex-wrap justify-end gap-2">
          <button
            className={`${button} bg-orange-400/10 text-orange-100 hover:bg-orange-400/18`}
            disabled={busy || liveBlocked}
            onClick={() => requestLive()}
            type="button"
          >
            <Sparkles size={14} />
            {liveLabel}
          </button>
          {liveBlocked && (
            <Link
              className="inline-flex items-center gap-2 border border-cyan-300/50 px-4 py-2 text-sm text-cyan-100"
              to="/settings"
            >
              配置 AI 大脑
            </Link>
          )}
          {run && (
            <button
              className={button}
              disabled={busy || liveBlocked}
              onClick={() => requestLive(true)}
              type="button"
            >
              <RefreshCw size={14} />
              重新生成
            </button>
          )}
        </div>
      </div>
      {pendingForceRegenerate !== null ? (
        <div className="mt-4 border border-orange-400/35 bg-[#1b1712] p-4">
          <div className="flex items-start justify-between gap-5">
            <div>
              <p className="text-sm font-semibold text-orange-100">
                确认发送给 AI 分析服务吗？
              </p>
              <p className="mt-2 text-xs leading-5 text-zinc-300">
                这一步是防误触保险：会把当前页面需要处理的文字发送到
                <span className="mx-1 text-orange-200">
                  {status?.mode_label ?? "已配置的 AI 分析服务"}
                </span>
                ，只生成文字分析或建议，不生成图片，也不会提交视频。
              </p>
              <p className="mt-2 text-xs leading-5 text-emerald-100/80">
                {systemPromptTraceLine(status)}
              </p>
              <p className="mt-2 text-xs leading-5 text-zinc-500">
                {pendingForceRegenerate
                  ? "本次会重新生成，不复用缓存；可能产生一次新的文本模型费用。"
                  : "如果已有相同缓存，系统会优先复用；没有缓存才会产生一次新请求。"}
              </p>
            </div>
            <div className="flex shrink-0 gap-2">
              <button
                className="border border-white/15 px-4 py-2 text-sm text-zinc-300 transition hover:bg-white/5"
                disabled={busy}
                onClick={() => setPendingForceRegenerate(null)}
                type="button"
              >
                先不发送
              </button>
              <button
                className="border border-orange-300 bg-orange-400/12 px-4 py-2 text-sm font-semibold text-orange-100 transition hover:bg-orange-400/20 disabled:opacity-45"
                disabled={busy}
                onClick={() => {
                  const force = Boolean(pendingForceRegenerate);
                  setPendingForceRegenerate(null);
                  void perform(force);
                }}
                type="button"
              >
                确认发送
              </button>
            </div>
          </div>
        </div>
      ) : null}
      {busy ? <GuideProgress label="AI 正在生成文字，请稍等…" /> : null}
      {error && (
        <p className="mt-3 border-l-2 border-red-400 bg-red-400/8 px-3 py-2 text-sm text-red-200">
          {humanizeCopy(error)}
        </p>
      )}
      {run && (
        <div className="mt-4 border border-white/10 bg-black/20 p-4">
          <AiRunEvidenceCard run={run} status={status} />
          <pre className="mt-3 whitespace-pre-wrap text-sm leading-6 text-zinc-200">
            {humanizeCopy(run.response_text)}
          </pre>
        </div>
      )}
    </section>
  );
}
