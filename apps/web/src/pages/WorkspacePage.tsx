import { ArrowRight, CheckCircle2 } from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { ErrorBanner } from "../components/ErrorBanner";
import { CreativeIntakePanel } from "../components/CreativeIntakePanel";
import { CreativeGoalPanel } from "../components/CreativeGoalPanel";
import { DirectorOptionCard } from "../components/DirectorOptionCard";
import {
  DirectorStatusPanel,
  DirectorWorkbenchFrame,
  GuideActionCard,
  GuidePrimaryButton,
  GuideProgressToast,
  TechDetails,
  type DirectorStageItem,
} from "../components/Guide";
import { AiDirectorRunPanel } from "../components/AiDirectorRunPanel";
import { useConfirmAction } from "../components/ConfirmDialog";
import { AiRunEvidenceCard } from "../components/AiRunEvidenceCard";
import { PlanningDraftPanel } from "../components/PlanningDraftPanel";
import {
  createAiPlanningDraft,
  createDirectorAnalysis,
  fetchAiTextRuns,
  fetchFlowNav,
  fetchTextProviderStatus,
} from "../services/api";
import { useWorkbenchStore } from "../stores/useWorkbenchStore";
import { workbenchPageClass } from "../styles/layout";
import type { FlowNav } from "../types/flowNav";
import type { AiTextRun, TextProviderStatus } from "../types/workflows";
import { humanizeCopy } from "../utils/humanCopy";
import { textProviderConfirmationNotice } from "../utils/textProviderCopy";

const aiModuleNames: Record<string, string> = {
  director_analysis: "导演启动分析",
  planning_draft: "分镜规划",
  asset_brief: "资产文字建议",
  storyboard_brief: "故事板文字拆解",
  vp_precision_18: "分镜提示词",
  workflow_check_summary: "检查摘要",
};

export function WorkspacePage() {
  const {
    projects,
    activeProject,
    sourceFiles,
    sourceTextExtractions,
    planningDrafts,
    error,
    clearError,
    loadProjects,
    loadPlanningData,
  } = useWorkbenchStore();
  const [flow, setFlow] = useState<FlowNav | null>(null);
  const [textStatus, setTextStatus] = useState<TextProviderStatus | null>(null);
  const [aiTextRuns, setAiTextRuns] = useState<AiTextRun[]>([]);
  const [guideBusy, setGuideBusy] = useState(false);
  const [guideError, setGuideError] = useState("");
  const [guideResult, setGuideResult] = useState("");
  const confirmAction = useConfirmAction();

  useEffect(() => {
    if (projects.length === 0) void loadProjects();
  }, [loadProjects, projects.length]);

  const loadFlow = () => {
    if (!activeProject) {
      setFlow(null);
      return;
    }
    void fetchFlowNav(activeProject.id)
      .then(setFlow)
      .catch(() => setFlow(null));
  };

  useEffect(loadFlow, [activeProject?.id]);
  useEffect(() => {
    window.addEventListener("flow-nav-refresh", loadFlow);
    return () => window.removeEventListener("flow-nav-refresh", loadFlow);
  });
  useEffect(() => {
    void fetchTextProviderStatus()
      .then(setTextStatus)
      .catch(() => setTextStatus(null));
  }, []);
  const loadAiTextRuns = async () => {
    if (!activeProject) {
      setAiTextRuns([]);
      return;
    }
    await fetchAiTextRuns(activeProject.id)
      .then(setAiTextRuns)
      .catch(() => setAiTextRuns([]));
  };
  useEffect(() => {
    void loadAiTextRuns();
  }, [activeProject?.id]);
  useEffect(() => {
    const hash = window.location.hash;
    if (!hash) return;
    const timer = window.setTimeout(() => {
      document
        .querySelector(hash)
        ?.scrollIntoView({ behavior: "smooth", block: "start" });
    }, 150);
    return () => window.clearTimeout(timer);
  }, [activeProject?.id, sourceTextExtractions.length, planningDrafts.length]);

  const hasSourceMaterial = sourceFiles.some((item) =>
    [
      "script",
      "script_text",
      "storyboard_table",
      "storyboard_table_image",
    ].includes(item.category),
  );
  const startDoneByFlow =
    flow?.directory.find((item) => item.key === "start")?.status_level ===
    "done";
  const hasStartAnalysis = Boolean(startDoneByFlow);
  const hasExtractedText = sourceTextExtractions.some(
    (item) => item.status === "extracted",
  );
  const latestExtraction = sourceTextExtractions[0];
  const latestPlanningDraft = planningDrafts[0];
  const hasAppliedDraft = planningDrafts.some(
    (item) => item.status === "applied",
  );
  const hasPlanningDraft = planningDrafts.length > 0;
  const planningLooksIncomplete = Boolean(
    latestPlanningDraft &&
    latestPlanningDraft.items.length <= 1 &&
    latestExtraction?.status === "extracted" &&
    latestExtraction.character_count > 800,
  );
  const hasDirectorOption = Boolean(flow?.director_option);
  const latestCompletedAiRuns = aiTextRuns
    .filter((run) => run.status === "completed" && run.response_text.trim())
    .reduce<AiTextRun[]>((items, run) => {
      return items.some((item) => item.module_type === run.module_type)
        ? items
        : [...items, run];
    }, []);
  const latestCompletedRunIds = new Set(
    latestCompletedAiRuns.map((run) => run.id),
  );
  const historicalAiRuns = aiTextRuns.filter(
    (run) => !latestCompletedRunIds.has(run.id),
  );
  const latestDirectorRun = aiTextRuns.find(
    (run) =>
      run.module_type === "director_analysis" && run.status === "completed",
  );
  const latestPlanningRun = aiTextRuns.find(
    (run) => run.module_type === "planning_draft" && run.status === "completed",
  );
  const currentStepIndex = !hasSourceMaterial
    ? 0
    : !hasStartAnalysis
      ? 1
      : !hasExtractedText
        ? 0
        : planningLooksIncomplete || !hasPlanningDraft
          ? 2
          : !hasDirectorOption
            ? 3
            : !hasAppliedDraft
              ? 4
              : 5;
  const planningStepTitle = planningLooksIncomplete
    ? "重新生成完整分镜规划"
    : "生成分镜规划";
  const planningStepHelper = planningLooksIncomplete
    ? "当前规划只拆出 1 个镜头，和你的文本长度不匹配。请重新生成，系统会要求 AI 按整份文本一次性拆出所有场和镜头。"
    : "导演分析完成后，先生成可编辑的 EP / SC / SH 分镜规划表，让你看清楚要拆成哪些场和镜头。";
  const primaryTitle = [
    "上传或输入剧本",
    "用 AI 做导演分析",
    planningStepTitle,
    "选择导演方案",
    "确认分镜规划",
    "生成分镜提示词",
  ][currentStepIndex];
  const primaryHelper = [
    "你不用先理解项目树。把文本粘贴进来，或上传 TXT / MD / DOCX / XLSX，系统会先保存并提取正文；PDF 和图片会先保存。",
    "资料已保存。下一步是用 AI 执行 V7｜开始｜EP01 导演分析，输出题材判断、人物关系、视觉方向和可选导演方案。",
    planningStepHelper,
    "请从 AI 给出的导演方案中选一个方向。后续分镜提示词和故事板都会沿着这个方向走。",
    "确认 AI 拆出来的场和镜头顺序。确认后，后面的分镜提示词会按这份规划生成。",
    "开始和规划闭环已经完成。下一步先生成分镜提示词，再生成黑白故事板草稿；正式资产图可以后做。",
  ][currentStepIndex];

  const refreshGuideState = async () => {
    await loadPlanningData();
    await loadAiTextRuns();
    if (activeProject) {
      await fetchFlowNav(activeProject.id)
        .then(setFlow)
        .catch(() => setFlow(null));
    }
    window.dispatchEvent(new CustomEvent("flow-nav-refresh"));
  };

  const confirmTextRequest = (taskName: string) => {
    return confirmAction({
      title: "确认使用 AI 分析文字",
      message: textProviderConfirmationNotice(
        textStatus,
        taskName,
        "只生成文字分析/规划，不生成图片，不提交视频。",
      ),
      confirmLabel: "确认，开始分析",
      tone: "cost",
    });
  };

  const runGuideDirectorAnalysis = async (forceRegenerate = false) => {
    if (!activeProject || !latestExtraction) return;
    if (
      !(await confirmTextRequest(
        forceRegenerate ? "V7｜开始｜重新生成完整五方案" : "V7｜开始｜导演分析",
      ))
    )
      return;
    setGuideBusy(true);
    setGuideError("");
    setGuideResult("");
    try {
      const result = await createDirectorAnalysis(activeProject.id, {
        module_type: "director_analysis",
        source_extraction_id: latestExtraction.id,
        provider_mode: textStatus?.mode ?? null,
        confirm_live_request: true,
        force_regenerate: forceRegenerate,
      });
      setAiTextRuns((current) => [
        result,
        ...current.filter((item) => item.id !== result.id),
      ]);
      setGuideResult(
        `${forceRegenerate ? "完整五方案已重新生成" : "导演分析已生成"}：${result.model_name}`,
      );
      await refreshGuideState();
    } catch (cause) {
      setGuideError(
        cause instanceof Error ? cause.message : "真实 AI 导演分析失败。",
      );
    } finally {
      setGuideBusy(false);
    }
  };

  const runGuidePlanningDraft = async () => {
    if (!activeProject || !latestExtraction) return;
    if (!(await confirmTextRequest("V7｜规划｜生成分镜规划"))) return;
    setGuideBusy(true);
    setGuideError("");
    setGuideResult("");
    try {
      const result = await createAiPlanningDraft(activeProject.id, {
        module_type: "planning_draft",
        source_extraction_id: latestExtraction.id,
        provider_mode: textStatus?.mode ?? null,
        confirm_live_request: true,
        force_regenerate: planningLooksIncomplete,
      });
      setGuideResult(
        `分镜规划已生成：V${String(result.version_number).padStart(3, "0")}，请检查后点击“确认并使用这份规划”。`,
      );
      await refreshGuideState();
    } catch (cause) {
      setGuideError(
        cause instanceof Error ? cause.message : "AI 分镜规划生成失败。",
      );
    } finally {
      setGuideBusy(false);
    }
  };

  const textBlocked = !textStatus || !textStatus.ready;
  const primaryAction =
    currentStepIndex === 0 ? (
      <p className="border border-orange-400/25 bg-orange-400/8 px-3 py-2 text-xs leading-5 text-orange-100">
        上传表单就在下方第一步区域，直接粘贴或选择文件即可。
      </p>
    ) : currentStepIndex === 1 ? (
      <GuidePrimaryButton
        disabled={guideBusy || textBlocked}
        loading={guideBusy}
        loadingLabel="AI 正在分析剧本…"
        onClick={() => void runGuideDirectorAnalysis()}
      >
        用 AI 分析剧本
      </GuidePrimaryButton>
    ) : currentStepIndex === 2 ? (
      <GuidePrimaryButton
        disabled={guideBusy || textBlocked}
        loading={guideBusy}
        loadingLabel="正在生成分镜规划…"
        onClick={() => void runGuidePlanningDraft()}
      >
        {planningLooksIncomplete ? "重新生成完整分镜规划" : "生成分镜规划"}
      </GuidePrimaryButton>
    ) : currentStepIndex === 3 ? (
      <GuidePrimaryButton href="#director-option-panel">
        去选导演方案
      </GuidePrimaryButton>
    ) : currentStepIndex === 4 ? (
      <GuidePrimaryButton href="#planning-draft-panel">
        确认分镜规划
      </GuidePrimaryButton>
    ) : (
      <GuidePrimaryButton href="/video-package">
        生成分镜提示词
      </GuidePrimaryButton>
    );
  const stageItems: DirectorStageItem[] = [
    {
      title: "上传资料",
      detail: hasSourceMaterial ? "剧本或分镜资料已保存" : "先粘贴或上传剧本",
      status: hasSourceMaterial ? "done" : "current",
    },
    {
      title: "AI 导演分析",
      detail: hasStartAnalysis ? "已生成导演分析" : "用 AI 理解剧情和视觉方向",
      status: !hasSourceMaterial
        ? "pending"
        : hasStartAnalysis
          ? "done"
          : "current",
    },
    {
      title: "选择导演方案",
      detail: hasDirectorOption ? "已确认本集方向" : "从 AI 给出的方案中选一个",
      status: !hasStartAnalysis
        ? "pending"
        : hasDirectorOption
          ? "done"
          : currentStepIndex === 3
            ? "current"
            : "pending",
    },
    {
      title: "分镜规划",
      detail: hasAppliedDraft
        ? "规划已应用到项目"
        : hasPlanningDraft
          ? "草案已生成，等待确认"
          : "拆出场次和镜头",
      status: planningLooksIncomplete
        ? "blocked"
        : hasAppliedDraft
          ? "done"
          : currentStepIndex === 2 || currentStepIndex === 4
            ? "current"
            : "pending",
    },
    {
      title: "下一步产出",
      detail: hasAppliedDraft ? "去生成分镜提示词" : "完成前面步骤后再继续",
      status: hasAppliedDraft ? "current" : "pending",
    },
  ];

  if (!activeProject && projects.length === 0) {
    return (
      <div className={workbenchPageClass}>
        <section className="relative overflow-hidden border border-orange-400/25 bg-[#151b21] p-8 shadow-2xl shadow-black/20">
          <div className="absolute right-0 top-0 h-40 w-80 bg-orange-400/8 blur-3xl" />
          <p className="text-xs tracking-[0.2em] text-orange-400">
            V7 创作向导
          </p>
          <h1 className="mt-3 text-4xl font-semibold tracking-wide text-zinc-100">
            上传资料开始第一个项目
          </h1>
          <p className="mt-4 max-w-3xl text-base leading-7 text-zinc-400">
            第一件事只有一个：给系统一份剧本、分镜表或创意文本。系统会自动创建项目、保存资料；随后用
            AI 执行 V7｜开始分析。
          </p>
          <div className="mt-6 flex gap-3 text-xs">
            <span className="border border-cyan-400/30 bg-cyan-400/8 px-3 py-1 text-cyan-200">
              AI 分析优先｜逐次确认
            </span>
            <span className="border border-white/10 bg-black/15 px-3 py-1 text-zinc-500">
              自动生成 EP01 / SC01 / SH001
            </span>
          </div>
        </section>
        <div className="mt-7">
          <ErrorBanner message={error} onClose={clearError} />
          <CreativeIntakePanel mode="create" />
        </div>
      </div>
    );
  }

  return (
    <div className={workbenchPageClass}>
      {guideBusy ? (
        <GuideProgressToast label="AI 正在处理当前步骤，完成后会自动显示结果。" />
      ) : null}
      <div>
        <ErrorBanner message={error} onClose={clearError} />
      </div>

      <DirectorWorkbenchFrame
        main={
          <GuideActionCard
            eyebrow="当前主任务"
            title={primaryTitle}
            description={primaryHelper}
            progressLabel={
              guideBusy
                ? "AI 正在处理当前步骤，完成后会在下方显示结果。"
                : undefined
            }
          >
            <div className="mb-1 flex flex-wrap gap-2 text-xs">
              <span className="border border-white/10 bg-black/15 px-3 py-1 text-zinc-400">
                {activeProject?.project_code}｜{activeProject?.name}
              </span>
              <span className="border border-emerald-400/30 bg-emerald-400/8 px-3 py-1 text-emerald-300">
                AI 分析会先确认
              </span>
              {hasExtractedText ? (
                <span className="border border-sky-400/30 bg-sky-400/8 px-3 py-1 text-sky-300">
                  已解析文本资料
                </span>
              ) : null}
            </div>
            {primaryAction}
            {textBlocked &&
            (currentStepIndex === 1 || currentStepIndex === 2) ? (
              <Link
                className="text-sm text-cyan-200 underline decoration-cyan-300/50 underline-offset-4"
                to="/settings"
              >
                去设置 AI 服务
              </Link>
            ) : null}
          </GuideActionCard>
        }
        aside={
          <div className="space-y-4">
            <DirectorStatusPanel
              title="这一页怎么走"
              description="只按当前主任务往下做。右边显示你走到了哪一步，不需要理解后台项目结构。"
              items={stageItems}
            />
          </div>
        }
      />
      {guideError ? (
        <p className="mt-4 border-l-2 border-red-400 bg-red-400/8 px-3 py-2 text-sm text-red-200">
          {guideError}
        </p>
      ) : null}
      {guideResult ? (
        <p className="mt-4 border-l-2 border-emerald-400 bg-emerald-400/8 px-3 py-2 text-sm text-emerald-200">
          {guideResult}
        </p>
      ) : null}

      <div className="mt-5">
        <main className="min-w-0">
          {!hasSourceMaterial ? (
            <CreativeIntakePanel mode="attach" />
          ) : !hasStartAnalysis ? (
            <section className="border border-cyan-400/30 bg-cyan-400/7 p-6">
              <p className="text-xs tracking-[0.18em] text-cyan-200">
                等待 AI 分析
              </p>
              <h2 className="mt-2 text-2xl font-semibold text-zinc-100">
                请点击上方“用 AI 分析剧本”
              </h2>
              <p className="mt-3 text-sm leading-6 text-zinc-400">
                这一步会把剧本交给你配置好的 AI
                文本服务，生成导演分析、人物关系、视觉方向和可选导演方案。未配置密钥时，请先到“成本与设置”填写慧梦或
                OpenAI。
              </p>
              <Link
                className="mt-5 inline-flex items-center gap-2 border border-cyan-300/50 px-4 py-2 text-sm text-cyan-100"
                to="/settings"
              >
                去配置 AI 大脑
                <ArrowRight size={16} />
              </Link>
            </section>
          ) : !hasExtractedText ? (
            <div className="space-y-5">
              {latestExtraction ? (
                <section className="border border-amber-400/30 bg-amber-400/8 p-5">
                  <p className="text-xs tracking-[0.18em] text-amber-300">
                    资料已保存
                  </p>
                  <h2 className="mt-2 text-xl font-semibold text-zinc-100">
                    已保存，暂未解析正文
                  </h2>
                  <p className="mt-3 text-sm leading-6 text-zinc-400">
                    {latestExtraction.error ||
                      "现在支持解析粘贴文本、TXT、MD、DOCX 和 XLSX。PDF / 图片会先保存到本地，后续再开放解析。"}
                  </p>
                </section>
              ) : null}
              <CreativeIntakePanel mode="attach" />
            </div>
          ) : (
            <div className="space-y-5">
              <AiDirectorRunPanel
                directorRun={latestDirectorRun}
                planningRun={latestPlanningRun}
                extraction={latestExtraction}
                textStatus={textStatus}
              />
              <DirectorOptionCard
                flow={flow}
                aiTextRuns={aiTextRuns}
                onConfirmed={setFlow}
                onRegenerateFullOptions={() =>
                  void runGuideDirectorAnalysis(true)
                }
                regenerateBusy={guideBusy}
                regenerateDisabled={textBlocked || !latestExtraction}
              />
              <PlanningDraftPanel />
              {hasDirectorOption &&
              hasAppliedDraft &&
              !planningLooksIncomplete ? (
                <section className="border border-emerald-400/25 bg-emerald-400/7 p-6">
                  <div className="flex items-start gap-4">
                    <div className="grid size-11 shrink-0 place-items-center border border-emerald-400/35 bg-emerald-400/10 text-emerald-300">
                      <CheckCircle2 size={22} />
                    </div>
                    <div>
                      <p className="text-xs tracking-[0.18em] text-emerald-300">
                        开始 / 规划已闭环
                      </p>
                      <h2 className="mt-2 text-2xl font-semibold text-zinc-100">
                        你刚才确认和应用的内容已在上方保留
                      </h2>
                      <p className="mt-3 text-sm leading-6 text-zinc-400">
                        上面可以复查所有导演方案、当前采用方案，以及已经确认的分镜规划。确认没问题后，下一步先去生成分镜提示词。
                      </p>
                      <p className="mt-4 border border-orange-400/25 bg-orange-400/8 px-3 py-2 text-xs leading-5 text-orange-100">
                        请使用上方主线卡片里的“生成分镜提示词”按钮，或直接点击左侧导航进入分镜提示词页。
                      </p>
                    </div>
                  </div>
                </section>
              ) : null}
            </div>
          )}
        </main>
      </div>

      <TechDetails title="可选：这次只做到哪里">
        <CreativeGoalPanel flow={flow} compact />
      </TechDetails>

      <details className="mt-8 border border-white/10 bg-[#11171c]/80">
        <summary className="cursor-pointer px-5 py-4 text-sm font-medium text-zinc-300">
          可选：查看 AI 原文
        </summary>
        <div className="space-y-5 border-t border-white/10 p-5">
          <p className="border border-white/10 bg-black/15 px-4 py-3 text-sm leading-6 text-zinc-400">
            这里用来复查 AI
            返回的原文、模型名称和生成记录。正常创作只看上面的导演方案、分镜规划和下一步按钮就够了。
          </p>
          {activeProject && latestCompletedAiRuns.length > 0 ? (
            <section className="border border-emerald-400/25 bg-emerald-400/5 p-5">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <p className="text-xs tracking-[0.18em] text-emerald-300">
                    AI 产出记录
                  </p>
                  <h2 className="mt-2 text-xl font-semibold text-zinc-100">
                    最新 AI 分析结果
                  </h2>
                  <p className="mt-2 text-sm leading-6 text-zinc-400">
                    这里用于复查模型给过的完整原文。主流程只展示最新结论，不需要你反复阅读这些记录。
                  </p>
                </div>
                <button
                  className="border border-emerald-400/40 px-3 py-2 text-xs text-emerald-200 transition hover:bg-emerald-400/10"
                  onClick={() => void loadAiTextRuns()}
                  type="button"
                >
                  刷新记录
                </button>
              </div>
              <div className="mt-4 space-y-3">
                {latestCompletedAiRuns.map((run) => {
                  return (
                    <details
                      className="border border-white/10 bg-black/18"
                      key={run.id}
                    >
                      <summary className="cursor-pointer px-4 py-3 text-sm text-zinc-200">
                        {aiModuleNames[run.module_type] ?? run.module_type}｜
                        {run.model_name}｜
                        {new Date(run.created_at).toLocaleString("zh-CN")}
                      </summary>
                      <div className="border-t border-white/10 p-4">
                        <AiRunEvidenceCard run={run} status={textStatus} />
                        <pre className="mt-3 max-h-72 overflow-auto whitespace-pre-wrap font-sans text-sm leading-6 text-zinc-200">
                          {humanizeCopy(run.response_text)}
                        </pre>
                      </div>
                    </details>
                  );
                })}
              </div>
              {historicalAiRuns.length > 0 ? (
                <details className="mt-4 border border-white/10 bg-black/15">
                  <summary className="cursor-pointer px-4 py-3 text-sm text-zinc-300">
                    查看历史生成记录（{historicalAiRuns.length}{" "}
                    条，含重复生成或失败记录）
                  </summary>
                  <div className="space-y-2 border-t border-white/10 p-4">
                    {historicalAiRuns.slice(0, 8).map((run) => (
                      <div
                        className="flex flex-wrap items-center gap-2 border border-white/10 bg-black/15 px-3 py-2 text-xs text-zinc-400"
                        key={run.id}
                      >
                        <span>
                          {aiModuleNames[run.module_type] ?? run.module_type}
                        </span>
                        <span>
                          ｜{run.status === "completed" ? "成功旧版" : "失败"}
                        </span>
                        <span>｜{run.model_name}</span>
                        <span>｜已记录输出长度</span>
                        {run.error_message ? (
                          <span className="text-red-300">
                            ｜{humanizeCopy(run.error_message).slice(0, 80)}
                          </span>
                        ) : null}
                        <span>
                          ｜{new Date(run.created_at).toLocaleString("zh-CN")}
                        </span>
                      </div>
                    ))}
                  </div>
                </details>
              ) : null}
            </section>
          ) : null}

          <p className="mt-4 border border-white/10 bg-black/15 px-4 py-3 text-sm leading-6 text-zinc-400">
            这里现在只保留 AI
            原文、模型和生成记录。重新生成导演分析、生成分镜规划等创作动作，统一使用页面上方的主按钮或导演方案卡片，避免同一个动作出现两个入口。
          </p>
        </div>
      </details>
    </div>
  );
}
