import {
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Clapperboard,
  Sparkles,
} from "lucide-react";
import { FormEvent, useState } from "react";

import { confirmDirectorOption } from "../services/api";
import { useWorkbenchStore } from "../stores/useWorkbenchStore";
import type { FlowNav } from "../types/flowNav";
import type { AiTextRun } from "../types/workflows";

type DirectorOptionCardProps = {
  flow: FlowNav | null;
  aiTextRuns?: AiTextRun[];
  onConfirmed?: (next: FlowNav) => void;
  onRegenerateFullOptions?: () => void;
  regenerateBusy?: boolean;
  regenerateDisabled?: boolean;
};

type SuggestedDirectorOption = {
  name: string;
  detail: string;
  fullText: string;
  sourceLabel: string;
  isRecommended: boolean;
  isFallback?: boolean;
};

type DirectorOptionExtraction = {
  options: SuggestedDirectorOption[];
  recommendation: {
    title: string;
    reason: string;
    backup: string;
    risk: string;
    rawText: string;
  } | null;
};

const optionPattern =
  /^(推荐导演方案|导演方案[一二三四五六七八九十A-Z\d]|方案[一二三四五六七八九十A-Z\d])[:：\s]/;
const looseOptionPattern =
  /(推荐导演方案|导演方案[一二三四五六七八九十A-Z\d]|方案[一二三四五六七八九十A-Z\d])/;
const canonicalDirectorOptions: SuggestedDirectorOption[] = [
  {
    name: "原剧情版",
    detail:
      "严格遵循原剧本剧情与台词，不进行剧情改编；只优化光影、构图、运镜和表演。",
    fullText:
      "方案一：原剧情版\n严格遵循原剧本剧情与台词，不进行剧情改编。可优化光影、构图、运镜、表演。",
    sourceLabel: "方案一",
    isRecommended: false,
    isFallback: true,
  },
  {
    name: "唯美画意版",
    detail:
      "强调构图、空镜、自然光影和情绪留白；适合更抒情、更有画面诗意的处理。",
    fullText:
      "方案二：唯美画意版\n强调构图、空镜、自然光影、情绪留白。可在保持核心情节不变的前提下极简精简台词。",
    sourceLabel: "方案二",
    isRecommended: false,
    isFallback: true,
  },
  {
    name: "G版打斗特效版",
    detail:
      "适用于动作密集、冲突、追逐、打斗、爆发场景；如果当前剧本不适合，应明确标注不推荐。",
    fullText:
      "方案三：G版打斗特效版\n适用于动作密集、冲突、追逐、打斗、爆发场景。必须使用动作五段式：起点、发力、轨迹、接触/结果、反应/截尾。",
    sourceLabel: "方案三",
    isRecommended: false,
    isFallback: true,
  },
  {
    name: "H解说模式",
    detail:
      "适用于旁白、回忆、内心独白和信息量大的剧情；优先使用声画分离、环境空镜和反应镜头。",
    fullText:
      "方案四：H解说模式\n适用于旁白、回忆、内心独白、信息量大的剧情。优先使用声画分离、OS、环境空镜和反应镜头。",
    sourceLabel: "方案四",
    isRecommended: false,
    isFallback: true,
  },
  {
    name: "推荐导演方案",
    detail:
      "根据当前剧本题材、情绪、节奏和人物关系自动生成定制导演风格；这是原系统最需要 AI 判断的一项。",
    fullText:
      "方案五：推荐导演方案\n根据剧本题材、情绪、节奏、人物关系自动生成定制化导演风格。不得出现真实导演名、作品名、IP名，只能用纯技术镜头语言描述。",
    sourceLabel: "方案五",
    isRecommended: true,
    isFallback: true,
  },
];

function cleanMarkdown(value: string): string {
  return value
    .replace(/\*\*/g, "")
    .replace(/`/g, "")
    .replace(/^#+\s*/, "")
    .replace(/^[-\s\d.、]+/, "")
    .trim();
}

function normalizeOptionName(raw: string): string {
  const cleaned = cleanMarkdown(raw)
    .replace(/^推荐导演方案[:：]?\s*/, "")
    .replace(/^导演方案[一二三四五六七八九十A-Z\d]*[:：]?\s*/, "")
    .replace(/^方案[一二三四五六七八九十A-Z\d]*[:：]?\s*/, "")
    .trim();
  const pipePart = cleaned.includes("｜")
    ? (cleaned.split("｜").at(-1) ?? cleaned)
    : cleaned;
  return pipePart.split(/[，。,；;。]/)[0].trim() || cleaned;
}

function extractRecommendation(
  lines: string[],
): DirectorOptionExtraction["recommendation"] {
  const startIndex = lines.findIndex((line) =>
    /AI推荐结论|推荐结论|AI\s*推荐/.test(line),
  );
  if (startIndex < 0) return null;
  const nextSectionIndex = lines.findIndex(
    (line, index) =>
      index > startIndex &&
      /^#{0,3}\s*(\d+\.|[一二三四五六七八九十]+、|[一二三四五六七八九十]+\.|##|###)/.test(
        line,
      ),
  );
  const block = lines
    .slice(
      startIndex + 1,
      nextSectionIndex > startIndex ? nextSectionIndex : lines.length,
    )
    .filter(Boolean);
  const rawText = block.join("\n");
  const field = (label: string) => {
    const found = block.find((line) => line.startsWith(label));
    return found?.replace(new RegExp(`^${label}[:：]?\\s*`), "").trim() ?? "";
  };
  const title =
    field("推荐采用") ||
    block.find((line) => /推荐采用|建议采用/.test(line)) ||
    "";
  return {
    title,
    reason: field("推荐理由"),
    backup: field("备用选择"),
    risk: field("风险提醒"),
    rawText,
  };
}

function extractSuggestedOptions(
  aiTextRuns: AiTextRun[] = [],
): DirectorOptionExtraction {
  const run = aiTextRuns.find(
    (item) =>
      item.module_type === "director_analysis" && item.status === "completed",
  );
  if (!run?.response_text) return { options: [], recommendation: null };
  const lines = run.response_text.split(/\n+/).map(cleanMarkdown);
  const options: SuggestedDirectorOption[] = [];
  const recommendationIndex = lines.findIndex((line) =>
    /AI推荐结论|推荐结论|AI\s*推荐/.test(line),
  );
  const optionIndexes = lines
    .map((line, index) => ({ line, index }))
    .filter(({ line }) => optionPattern.test(line));
  for (let i = 0; i < optionIndexes.length; i += 1) {
    const { line, index } = optionIndexes[i];
    if (!optionPattern.test(line)) continue;
    const name = normalizeOptionName(line);
    if (!name || name.length > 28 || options.some((item) => item.name === name))
      continue;
    const nextIndex =
      optionIndexes[i + 1]?.index ??
      (recommendationIndex > index ? recommendationIndex : lines.length);
    const fullText = lines.slice(index, nextIndex).filter(Boolean).join("\n");
    const detail = line.includes("，")
      ? line.slice(line.indexOf("，") + 1).trim()
      : line;
    const isRecommended = /推荐导演方案/.test(line) || /方案五/.test(line);
    options.push({
      name,
      detail:
        detail === name ? "这是本次真实 AI 导演分析给出的可选方向。" : detail,
      fullText: fullText || line,
      sourceLabel: line.match(looseOptionPattern)?.[0] ?? `方案${i + 1}`,
      isRecommended,
      isFallback: false,
    });
  }
  return {
    options: options.slice(0, 5),
    recommendation: extractRecommendation(lines),
  };
}

function optionSlotIndex(option: SuggestedDirectorOption): number {
  if (/方案一|原剧情|保持原剧情/.test(`${option.sourceLabel}${option.name}`))
    return 0;
  if (/方案二|唯美|画意/.test(`${option.sourceLabel}${option.name}`)) return 1;
  if (/方案三|G版|打斗|特效/.test(`${option.sourceLabel}${option.name}`))
    return 2;
  if (/方案四|H解说|解说模式|旁白/.test(`${option.sourceLabel}${option.name}`))
    return 3;
  if (/方案五|推荐导演方案/.test(`${option.sourceLabel}${option.name}`))
    return 4;
  return -1;
}

function mergeWithCanonicalOptions(
  options: SuggestedDirectorOption[],
): SuggestedDirectorOption[] {
  const slots = canonicalDirectorOptions.map((option) => ({
    ...option,
    detail: `本次 AI 没有展开此方案。${option.detail}`,
    fullText: `${option.fullText}\n\n提示：本次旧分析没有详细展开这个方案，建议重新生成导演分析补齐 AI 判断。`,
  }));
  const extras: SuggestedDirectorOption[] = [];
  for (const option of options) {
    const slot = optionSlotIndex(option);
    if (slot >= 0) {
      slots[slot] = option;
    } else {
      extras.push(option);
    }
  }
  return [...slots, ...extras].slice(0, 5);
}

export function DirectorOptionCard({
  flow,
  aiTextRuns = [],
  onConfirmed,
  onRegenerateFullOptions,
  regenerateBusy = false,
  regenerateDisabled = false,
}: DirectorOptionCardProps) {
  const activeProject = useWorkbenchStore((state) => state.activeProject);
  const [optionName, setOptionName] = useState("");
  const [notes, setNotes] = useState("");
  const [error, setError] = useState("");
  const [isSubmitting, setSubmitting] = useState(false);
  const [expandedOptionNames, setExpandedOptionNames] = useState<string[]>([]);

  const episodeId = activeProject?.episodes.find(
    (item) => !item.is_archived,
  )?.id;
  const confirmedOption = flow?.director_option;
  const hasDirectorRun = aiTextRuns.some(
    (item) =>
      item.module_type === "director_analysis" && item.status === "completed",
  );
  const { options: extractedOptions, recommendation } =
    extractSuggestedOptions(aiTextRuns);
  const hasIncompleteAiOptions =
    hasDirectorRun && (extractedOptions.length !== 5 || !recommendation?.title);
  const completeOptions =
    extractedOptions.length > 0
      ? mergeWithCanonicalOptions(extractedOptions)
      : [];
  const suggestedOptions =
    confirmedOption &&
    !completeOptions.some(
      (option) => option.name === confirmedOption.option_name,
    )
      ? [
          {
            name: confirmedOption.option_name,
            detail:
              confirmedOption.notes || "这是当前项目里已经保存的人工确认方案。",
            fullText: confirmedOption.notes || confirmedOption.option_name,
            sourceLabel: "当前采用",
            isRecommended: false,
          },
          ...completeOptions,
        ]
      : completeOptions;
  const recommendedOption =
    suggestedOptions.find(
      (option) => option.isRecommended && !option.isFallback,
    ) ??
    suggestedOptions.find((option) =>
      recommendation?.title.includes(option.name),
    ) ??
    null;
  const selectOption = (option: SuggestedDirectorOption) => {
    setOptionName(option.name);
    setNotes(option.detail);
  };
  const toggleExpanded = (name: string) => {
    setExpandedOptionNames((current) =>
      current.includes(name)
        ? current.filter((item) => item !== name)
        : [...current, name],
    );
  };

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (!episodeId || !optionName.trim()) return;
    setSubmitting(true);
    setError("");
    try {
      const next = await confirmDirectorOption(
        episodeId,
        optionName.trim(),
        notes.trim(),
      );
      setOptionName("");
      setNotes("");
      onConfirmed?.(next);
    } catch (cause) {
      setError((cause as Error).message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <section
      id="director-option-panel"
      className={`border p-6 shadow-2xl shadow-orange-950/10 ${
        confirmedOption
          ? "border-emerald-400/25 bg-emerald-400/7"
          : "border-orange-400/35 bg-[#151b21]"
      }`}
    >
      <div className="grid grid-cols-[minmax(0,1fr)_300px] gap-6">
        <div>
          <div
            className={`flex items-center gap-2 ${confirmedOption ? "text-emerald-300" : "text-orange-300"}`}
          >
            {confirmedOption ? (
              <CheckCircle2 size={18} />
            ) : (
              <Clapperboard size={18} />
            )}
            <p className="text-xs tracking-[0.18em]">
              {confirmedOption ? "已确认，可查看详情" : "当前主任务"}
            </p>
          </div>
          <h2 className="mt-3 text-2xl font-semibold text-zinc-100">
            {confirmedOption ? "已确认导演方案" : "确认这一集采用的导演方案"}
          </h2>
          <p className="mt-3 text-sm leading-6 text-zinc-400">
            {confirmedOption
              ? "这里保留当时真实 AI 给出的方案和你最终确认的方向。它不是系统自动替你选的，而是当前项目里已经保存的人工确认记录。"
              : "系统已经完成 AI 导演分析。请从下面的方案卡里选一个方向；选中后会自动填到确认表单里，后续“分镜提示词、故事板、资产图、批量视频”都会沿着这个方向推进。"}
          </p>
          {confirmedOption ? (
            <p className="mt-3 border border-emerald-400/25 bg-black/15 px-3 py-2 text-sm text-emerald-100">
              当前采用：
              <span className="font-semibold">
                {confirmedOption.option_name}
              </span>
              {confirmedOption.notes ? (
                <span className="ml-2 text-emerald-100/70">
                  ｜{confirmedOption.notes}
                </span>
              ) : null}
            </p>
          ) : null}
        </div>
        <div className="border border-white/10 bg-black/15 p-4">
          <div className="flex items-center gap-2 text-emerald-300">
            <Sparkles size={15} />
            <p className="text-xs font-medium">
              人工确认｜本步骤不新增模型请求
            </p>
          </div>
          <p className="mt-3 text-xs leading-5 text-zinc-500">
            原系统一般会给出五大导演方案：原剧情版、唯美画意版、G版打斗特效版、H解说模式和推荐导演方案。你最终选择哪一个，由你确认。
          </p>
        </div>
      </div>

      <div className="mt-6">
        <p className="text-xs tracking-[0.18em] text-orange-300">
          真实 AI 给出的全部可选导演方案
        </p>
        <section className="mt-3 border border-cyan-400/30 bg-cyan-400/7 p-4">
          <div className="flex items-center gap-2 text-cyan-200">
            <Sparkles size={16} />
            <p className="text-sm font-semibold">AI 推荐结论</p>
          </div>
          {recommendation?.title ? (
            <div className="mt-3 grid grid-cols-[minmax(0,1fr)_220px] gap-4">
              <div className="text-sm leading-6 text-zinc-300">
                <p>
                  推荐采用：
                  <span className="font-semibold text-cyan-100">
                    {recommendation.title}
                  </span>
                </p>
                {recommendation?.reason ? (
                  <p className="mt-1 text-zinc-400">
                    推荐理由：{recommendation.reason}
                  </p>
                ) : null}
                {recommendation?.backup ? (
                  <p className="mt-1 text-zinc-500">
                    备用选择：{recommendation.backup}
                  </p>
                ) : null}
                {recommendation?.risk ? (
                  <p className="mt-1 text-amber-100">
                    风险提醒：{recommendation.risk}
                  </p>
                ) : null}
              </div>
              {recommendedOption && !confirmedOption ? (
                <button
                  className="self-start border border-cyan-300/45 px-4 py-2 text-sm font-medium text-cyan-100 transition hover:bg-cyan-300/10"
                  onClick={() => selectOption(recommendedOption)}
                  type="button"
                >
                  采用 AI 推荐方案
                </button>
              ) : null}
            </div>
          ) : (
            <div className="mt-3 grid grid-cols-[minmax(0,1fr)_230px] gap-4">
              <p className="text-sm leading-6 text-amber-100">
                这条旧分析没有明确写出推荐结论。你仍可以查看下方方案；如果想严格还原原系统，请重新生成导演分析，新版会要求输出“五大方案
                + AI推荐结论”。
              </p>
              {onRegenerateFullOptions ? (
                <button
                  className="self-start border border-cyan-300/45 bg-cyan-300/10 px-4 py-2 text-sm font-medium text-cyan-100 transition hover:bg-cyan-300/18 disabled:cursor-not-allowed disabled:opacity-45"
                  disabled={regenerateBusy || regenerateDisabled}
                  onClick={onRegenerateFullOptions}
                  type="button"
                >
                  重新生成完整五方案
                </button>
              ) : null}
            </div>
          )}
        </section>
        {suggestedOptions.length > 0 ? (
          <div className="mt-3 grid grid-cols-2 gap-3 xl:grid-cols-3">
            {suggestedOptions.map((option, index) => {
              const confirmed = confirmedOption?.option_name === option.name;
              const selected = !confirmedOption && optionName === option.name;
              return (
                <div
                  className={`min-h-36 border p-4 text-left transition ${
                    confirmed
                      ? "border-emerald-400/55 bg-emerald-400/12 shadow-lg shadow-emerald-950/20"
                      : selected
                        ? "border-orange-400 bg-orange-400/12 shadow-lg shadow-orange-950/20"
                        : "border-white/10 bg-black/15 hover:border-orange-400/45 hover:bg-orange-400/7"
                  }`}
                  key={option.name}
                >
                  <div className="flex items-center justify-between gap-3">
                    <p className="text-xs text-orange-300">
                      {option.sourceLabel || `方案 ${index + 1}`}
                    </p>
                    {(option.isRecommended && !option.isFallback) ||
                    recommendation?.title.includes(option.name) ? (
                      <span className="border border-cyan-300/35 bg-cyan-300/10 px-2 py-1 text-[11px] text-cyan-100">
                        AI推荐
                      </span>
                    ) : option.isFallback ? (
                      <span className="border border-white/10 bg-white/5 px-2 py-1 text-[11px] text-zinc-500">
                        原系统槽位
                      </span>
                    ) : null}
                  </div>
                  <h3 className="mt-2 text-lg font-semibold text-zinc-100">
                    {option.name}
                  </h3>
                  <p className="mt-3 text-xs leading-5 text-zinc-400">
                    {option.detail}
                  </p>
                  {expandedOptionNames.includes(option.name) ? (
                    <pre className="mt-3 max-h-72 overflow-auto whitespace-pre-wrap border border-white/10 bg-black/20 p-3 font-sans text-xs leading-5 text-zinc-200">
                      {option.fullText}
                    </pre>
                  ) : null}
                  <div className="mt-4 flex flex-wrap items-center gap-2">
                    {!confirmedOption ? (
                      <button
                        aria-label={`选择导演方案：${option.name}`}
                        className={`border px-3 py-2 text-xs transition ${
                          selected
                            ? "border-orange-300 bg-orange-400/15 text-orange-100"
                            : "border-orange-400/45 text-orange-200 hover:bg-orange-400/10"
                        }`}
                        onClick={() => selectOption(option)}
                        type="button"
                      >
                        {selected ? "已选择，会写入确认表单" : "选择这个方向"}
                      </button>
                    ) : (
                      <span
                        className={`text-xs ${confirmed ? "text-emerald-300" : "text-zinc-500"}`}
                      >
                        {confirmed ? "当前采用" : "备选方案，供复查"}
                      </span>
                    )}
                    <button
                      aria-label={`${expandedOptionNames.includes(option.name) ? "收起方案全文" : "查看方案全文"}：${option.name}`}
                      className="inline-flex items-center gap-1 border border-white/10 px-3 py-2 text-xs text-zinc-300 transition hover:border-white/25 hover:bg-white/5"
                      onClick={() => toggleExpanded(option.name)}
                      type="button"
                    >
                      {expandedOptionNames.includes(option.name) ? (
                        <ChevronUp size={13} />
                      ) : (
                        <ChevronDown size={13} />
                      )}
                      {expandedOptionNames.includes(option.name)
                        ? "收起全文"
                        : "查看方案全文"}
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        ) : (
          <div className="mt-3 border border-amber-400/25 bg-amber-400/8 p-4">
            <p className="text-sm font-medium text-amber-100">
              还没有识别到明确方案卡
            </p>
            <p className="mt-2 text-xs leading-5 text-zinc-400">
              可能是旧分析记录没有按方案卡格式输出。你可以先手动填写，或重新运行一次真实
              AI 导演分析；新版提示会要求模型给出原系统五大导演方案。
            </p>
          </div>
        )}
        {hasIncompleteAiOptions ? (
          <div className="mt-3 border border-amber-400/25 bg-amber-400/8 p-4">
            <p className="text-sm font-medium text-amber-100">
              这条导演分析还不完整
            </p>
            <p className="mt-2 text-xs leading-5 text-zinc-400">
              原系统一般应展示 5 个导演方案，并给出 AI 推荐结论。本次记录识别到{" "}
              {extractedOptions.length} 个方案
              {recommendation?.title ? "，已有推荐结论" : "，但没有推荐结论"}
              。页面已补齐五个方案槽位，但缺失项不是本次 AI 的完整判断。
            </p>
            {onRegenerateFullOptions ? (
              <button
                className="mt-3 border border-orange-400/50 px-4 py-2 text-sm text-orange-100 transition hover:bg-orange-400/10 disabled:cursor-not-allowed disabled:opacity-45"
                disabled={regenerateBusy || regenerateDisabled}
                onClick={onRegenerateFullOptions}
                type="button"
              >
                {regenerateBusy
                  ? "正在重新生成..."
                  : "重新生成完整五方案和推荐结论"}
              </button>
            ) : null}
          </div>
        ) : null}
      </div>

      {!confirmedOption ? (
        <form
          className="mt-6 grid grid-cols-[330px_minmax(0,1fr)_150px] items-end gap-4"
          onSubmit={submit}
        >
          <label className="text-xs text-zinc-400">
            导演方案名称
            <input
              aria-label="导演方案名称"
              className="mt-2 w-full border border-white/15 bg-black/20 px-3 py-3 text-sm text-white outline-none transition focus:border-orange-400/70"
              placeholder="例如：克制压迫版"
              required
              value={optionName}
              onChange={(event) => setOptionName(event.target.value)}
            />
          </label>
          <label className="text-xs text-zinc-400">
            人工备注（可选）
            <input
              aria-label="导演方案备注"
              className="mt-2 w-full border border-white/15 bg-black/20 px-3 py-3 text-sm text-white outline-none transition focus:border-orange-400/70"
              placeholder="例如：节奏偏慢，强调压迫感和留白"
              value={notes}
              onChange={(event) => setNotes(event.target.value)}
            />
          </label>
          <button
            className="bg-orange-500 px-4 py-3 text-sm font-semibold text-black transition hover:bg-orange-400 disabled:opacity-45"
            disabled={isSubmitting || !episodeId}
            type="submit"
          >
            确认方案
          </button>
        </form>
      ) : (
        <p className="mt-5 border border-white/10 bg-black/15 px-4 py-3 text-xs leading-5 text-zinc-400">
          如果这个方向不是你想要的，请先重新生成导演分析并另存新版；这里不会直接覆盖已确认方案，避免破坏后续分镜提示词、故事板、资产图和批量视频的版本链。
        </p>
      )}
      {error ? <p className="mt-3 text-sm text-red-300">{error}</p> : null}
    </section>
  );
}
