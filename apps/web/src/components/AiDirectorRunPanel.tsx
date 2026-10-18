import {
  BadgeCheck,
  BrainCircuit,
  FileText,
  ListChecks,
  Sparkles,
} from "lucide-react";

import type { SourceTextExtraction } from "../types/planning";
import type { AiTextRun, TextProviderStatus } from "../types/workflows";
import { humanizeCopy } from "../utils/humanCopy";
import { AiRunEvidenceCard } from "./AiRunEvidenceCard";

type AiDirectorRunPanelProps = {
  directorRun?: AiTextRun;
  planningRun?: AiTextRun;
  extraction?: SourceTextExtraction;
  textStatus?: TextProviderStatus | null;
};

function compactText(value: string, limit = 220) {
  const normalized = value.replace(/\s+/g, " ").trim();
  return normalized.length > limit
    ? `${normalized.slice(0, limit)}...`
    : normalized;
}

function sectionFound(text: string, patterns: RegExp[]) {
  return patterns.some((pattern) => pattern.test(text));
}

function processRows(run?: AiTextRun, extraction?: SourceTextExtraction) {
  const text = run?.response_text ?? "";
  return [
    {
      label: "读取资料",
      done: Boolean(extraction),
      detail: extraction
        ? `已读取 ${extraction.character_count} 字 / ${extraction.line_count} 行。`
        : "等待上传或粘贴剧本资料。",
    },
    {
      label: "剧情理解",
      done: Boolean(
        run && sectionFound(text, [/剧情|故事|冲突|人物|世界观|题材/]),
      ),
      detail: run ? "模型已输出剧情、人物或冲突相关判断。" : "等待 AI 分析。",
    },
    {
      label: "视觉方向",
      done: Boolean(
        run && sectionFound(text, [/视觉|镜头|光线|氛围|景别|调度|空间/]),
      ),
      detail: run
        ? "模型已输出镜头、光线、空间或氛围相关判断。"
        : "等待 AI 分析。",
    },
    {
      label: "导演方案",
      done: Boolean(
        run &&
        sectionFound(text, [/可选导演方案|方案一|方案二|方案三|导演方案/]),
      ),
      detail: run ? "模型已给出可供人工选择的导演方案。" : "等待 AI 分析。",
    },
  ];
}

function RunStatusPill({ run }: { run?: AiTextRun }) {
  if (!run) {
    return (
      <span className="border border-zinc-600/60 bg-black/20 px-3 py-1 text-xs text-zinc-400">
        等待生成
      </span>
    );
  }
  return (
    <span className="border border-emerald-400/35 bg-emerald-400/8 px-3 py-1 text-xs text-emerald-200">
      {run.cache_hit ? "复用历史 AI 结果" : "真实 AI 新生成"}
    </span>
  );
}

function OutputPreview({
  run,
  title,
  textStatus,
}: {
  run?: AiTextRun;
  title: string;
  textStatus?: TextProviderStatus | null;
}) {
  if (!run) {
    return null;
  }
  return (
    <div className="ai-director-console__output">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-sm font-semibold text-zinc-100">{title}</p>
          <p className="mt-2 text-sm leading-6 text-zinc-300">
            {humanizeCopy(compactText(run.response_text, 360))}
          </p>
        </div>
        <RunStatusPill run={run} />
      </div>
      <AiRunEvidenceCard run={run} status={textStatus} />
    </div>
  );
}

export function AiDirectorRunPanel({
  directorRun,
  planningRun,
  extraction,
  textStatus,
}: AiDirectorRunPanelProps) {
  const rows = processRows(directorRun, extraction);
  return (
    <section id="ai-director-run-panel" className="ai-director-console">
      <div className="ai-director-console__header">
        <div>
          <div className="ai-director-console__badge">
            <BrainCircuit size={19} />
            <p>AI 导演运行台</p>
          </div>
          <h2 className="ai-director-console__title">
            像对话一样，看见 AI 做了什么
          </h2>
          <p className="ai-director-console__copy">
            这里展示的是可复查的工作过程：读了什么资料、用了哪个 AI
            服务、是否重新请求、最后生成了什么。不会展示模型隐藏思维链，但会让你知道结果是不是按
            V7 主系统生成。
          </p>
        </div>
        <div className="ai-director-console__service">
          <p className="font-medium">当前 AI 分析服务</p>
          <p className="mt-1 text-cyan-100/75">
            {textStatus?.mode_label ?? "正在读取配置"}
          </p>
          <p className="text-cyan-100/75">
            {textStatus?.ready
              ? "已就绪，每次请求都会确认"
              : textStatus?.blocking_reason || "等待配置"}
          </p>
        </div>
      </div>

      <div className="ai-director-console__steps">
        {rows.map((row) => (
          <article
            className={`ai-director-console__step ${row.done ? "ai-director-console__step--done" : ""}`}
            key={row.label}
          >
            <div className="ai-director-console__step-title">
              {row.done ? <BadgeCheck size={14} /> : <ListChecks size={14} />}
              {row.label}
            </div>
            <p className="ai-director-console__step-detail">{row.detail}</p>
          </article>
        ))}
      </div>

      {extraction ? (
        <div className="ai-director-console__source">
          <div className="flex items-center gap-2 text-zinc-200">
            <FileText size={16} className="text-orange-300" />
            <p className="text-sm font-medium">本次输入资料</p>
          </div>
          <p className="mt-2 text-xs text-zinc-500">
            {extraction.character_count} 字｜{extraction.line_count}{" "}
            行｜资料正文只保存在本地，不在页面暴露完整大文本。
          </p>
          {extraction.preview ? (
            <p className="mt-3 text-sm leading-6 text-zinc-300">
              {extraction.preview}
            </p>
          ) : null}
        </div>
      ) : null}

      <div
        className={`ai-director-console__outputs ${planningRun ? "ai-director-console__outputs--two" : ""}`}
      >
        <OutputPreview
          run={directorRun}
          title="V7｜开始｜导演分析结果"
          textStatus={textStatus}
        />
        {planningRun ? (
          <OutputPreview
            run={planningRun}
            title="V7｜规划｜分镜规划结果"
            textStatus={textStatus}
          />
        ) : null}
      </div>

      <p className="ai-director-console__note">
        <Sparkles size={15} />
        如果这里显示“复用历史 AI 结果”，说明本次没有再次花费请求；如果显示“真实
        AI 新生成”，说明刚刚确实向你配置的文本模型发送过一次受控请求。
      </p>
    </section>
  );
}
