import { useEffect, useMemo, useState } from "react";
import { Clipboard, ShieldCheck, Square } from "lucide-react";
import { Link, useLocation } from "react-router-dom";

import { useConfirmAction } from "../components/ConfirmDialog";
import {
  DirectorStatusPanel,
  DirectorWorkbenchFrame,
  GuideActionCard,
  GuidePrimaryButton,
  GuideProgressToast,
  TechDetails,
  type DirectorStageItem,
} from "../components/Guide";
import {
  cancelVpGenerationJob,
  fetchLatestVpGenerationJob,
  fetchTextProviderStatus,
  fetchVideoPackages,
  generateAiVpBlock,
  retryVpGenerationJob,
  startVpDurationRebuild,
  transitionVpBlock,
} from "../services/api";
import { useWorkbenchStore } from "../stores/useWorkbenchStore";
import { workbenchPageClass } from "../styles/layout";
import type {
  VideoPackageWorkspace,
  VpBlock,
  VpGenerationJob,
} from "../types/videos";
import type { TextProviderStatus } from "../types/workflows";
import { humanizeCopy, stageName, versionStateName } from "../utils/humanCopy";
import { textProviderConfirmationNotice } from "../utils/textProviderCopy";

const button =
  "inline-flex items-center gap-2 border border-white/15 px-3 py-2 text-xs text-zinc-300 hover:border-orange-400/40 hover:text-orange-200 disabled:opacity-40";

function PrecisionDetails({ block }: { block: VpBlock }) {
  const providerPrompt = block.provider_prompt_preview || block.prompt_copy;
  const referenceBindings = block.reference_bindings ?? [];
  const hasDirectorTech = Boolean(
    block.director_technique ||
    block.selected_detail_shot ||
    block.montage_type ||
    block.symbolic_object ||
    Object.keys(block.meaning_chain || {}).length,
  );
  return (
    <div className="mt-4 border-t border-white/10 pt-4">
      <div className="flex items-center justify-between">
        <p className="text-xs text-orange-300">
          Seedance 2.0 全能参考执行稿｜实际提交版本
        </p>
        <button
          className={button}
          onClick={() => void navigator.clipboard?.writeText(providerPrompt)}
          type="button"
        >
          <Clipboard size={13} />
          复制含 @ 引用提示词
        </button>
      </div>
      {referenceBindings.length ? (
        <section className="mt-3 border border-cyan-400/25 bg-cyan-400/[0.04] p-3">
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="text-sm font-semibold text-cyan-100">
                参考图上传顺序与用途
              </p>
              <p className="mt-1 text-xs leading-5 text-zinc-500">
                下列顺序同时决定 CLI 的图片上传顺序和提示词中的
                @图片N。两者由系统一起生成，不允许错位。
              </p>
            </div>
            <span className="shrink-0 text-xs text-cyan-300">
              {referenceBindings.length}/9 张
            </span>
          </div>
          <div className="mt-3 grid grid-cols-2 gap-2">
            {referenceBindings.map((binding) => (
              <div
                className="flex min-h-24 gap-3 border border-white/10 bg-black/15 p-2"
                key={`${binding.token}-${binding.asset_id}`}
              >
                {binding.asset_url ? (
                  <img
                    alt={`${binding.token} ${binding.label}`}
                    className="h-20 w-28 shrink-0 object-cover"
                    src={binding.asset_url}
                  />
                ) : null}
                <div className="min-w-0">
                  <p className="text-xs font-semibold text-cyan-200">
                    {binding.token}｜{binding.label}
                  </p>
                  <p className="mt-1 text-xs leading-5 text-zinc-400">
                    {binding.purpose}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </section>
      ) : (
        <p className="mt-3 border border-red-400/25 bg-red-400/5 px-3 py-2 text-xs text-red-200">
          当前没有建立全能参考绑定。不要直接提交多图生成，请先补齐正式参考资产。
        </p>
      )}
      <details className="mt-3 border border-white/10 bg-black/10">
        <summary className="cursor-pointer px-3 py-2 text-xs text-zinc-300">
          查看实际提交的含 @ 引用提示词
        </summary>
        <pre className="max-h-80 overflow-auto whitespace-pre-wrap border-t border-white/10 p-3 font-sans text-xs leading-5 text-zinc-400">
          {providerPrompt}
        </pre>
      </details>
      {hasDirectorTech ? (
        <div className="mt-3 grid grid-cols-3 gap-2 text-xs">
          <div className="border border-cyan-400/25 bg-cyan-400/8 p-3">
            <p className="text-cyan-200">导演技法</p>
            <p className="mt-1 text-zinc-300">
              {block.director_technique || "未标记"}
            </p>
          </div>
          <div className="border border-cyan-400/25 bg-cyan-400/8 p-3">
            <p className="text-cyan-200">细节镜头</p>
            <p className="mt-1 text-zinc-300">
              {block.selected_detail_shot ||
                block.detail_shot_candidates?.join(" / ") ||
                "未选择"}
            </p>
            {block.detail_shot_meaning ? (
              <p className="mt-1 text-zinc-500">{block.detail_shot_meaning}</p>
            ) : null}
          </div>
          <div className="border border-cyan-400/25 bg-cyan-400/8 p-3">
            <p className="text-cyan-200">蒙太奇 / 隐喻</p>
            <p className="mt-1 text-zinc-300">
              {block.montage_type || block.symbolic_object || "未使用"}
            </p>
            {block.symbolic_meaning || block.montage_goal ? (
              <p className="mt-1 text-zinc-500">
                {block.symbolic_meaning || block.montage_goal}
              </p>
            ) : null}
          </div>
        </div>
      ) : null}
      <div className="mt-3 grid grid-cols-2 gap-2">
        {block.precision_items.map((item) => (
          <div
            className="border border-white/10 bg-black/10 p-3"
            key={item.number}
          >
            <p className="text-xs text-orange-200">
              {item.number}. {item.title}
            </p>
            <pre className="mt-2 whitespace-pre-wrap font-sans text-xs leading-5 text-zinc-400">
              {humanizeCopy(item.content)}
            </pre>
          </div>
        ))}
      </div>
    </div>
  );
}

export function VideoPackagePage() {
  const location = useLocation();
  const {
    activeProject,
    projects,
    loadProjects,
    creativeGoal,
    setCreativeGoal,
  } = useWorkbenchStore();
  const confirmAction = useConfirmAction();
  const [data, setData] = useState<VideoPackageWorkspace | null>(null);
  const [sceneId, setSceneId] = useState("");
  const [expanded, setExpanded] = useState("");
  const [textStatus, setTextStatus] = useState<TextProviderStatus | null>(null);
  const [busy, setBusy] = useState(false);
  const [busyMessage, setBusyMessage] = useState("");
  const [error, setError] = useState("");
  const [vpGenerationJob, setVpGenerationJob] =
    useState<VpGenerationJob | null>(null);
  useEffect(() => {
    if (!projects.length) void loadProjects();
  }, [loadProjects, projects.length]);
  useEffect(() => {
    if (location.pathname !== "/video-package") return;
    void fetchTextProviderStatus()
      .then(setTextStatus)
      .catch(() => setTextStatus(null));
  }, [location.pathname]);
  useEffect(() => {
    if (!activeProject || location.pathname !== "/video-package") return;
    setBusy(true);
    setBusyMessage("正在读取当前镜头和历史提示词…");
    void fetchVideoPackages(activeProject.id)
      .then((next) => {
        setData(next);
        setSceneId((current) => current || next.scenes[0]?.id || "");
      })
      .catch((cause: Error) => setError(cause.message))
      .finally(() => {
        setBusy(false);
        setBusyMessage("");
      });
  }, [activeProject, location.pathname]);
  const scene = useMemo(
    () => data?.scenes.find((item) => item.id === sceneId) ?? data?.scenes[0],
    [data, sceneId],
  );
  useEffect(() => {
    if (!scene?.id || location.pathname !== "/video-package") return;
    void fetchLatestVpGenerationJob(scene.id)
      .then(setVpGenerationJob)
      .catch(() => setVpGenerationJob(null));
  }, [scene?.id, location.pathname]);
  useEffect(() => {
    if (!activeProject || !scene?.id || location.pathname !== "/video-package")
      return;
    if (
      !vpGenerationJob ||
      !["queued", "running", "retrying"].includes(vpGenerationJob.status)
    )
      return;
    let stopped = false;
    const refreshBackgroundProgress = async () => {
      try {
        const [job, workspace] = await Promise.all([
          fetchLatestVpGenerationJob(scene.id),
          fetchVideoPackages(activeProject.id),
        ]);
        if (stopped) return;
        setVpGenerationJob(job);
        setData(workspace);
        setError(job?.status === "failed" ? job.error_message : "");
      } catch (cause) {
        if (!stopped)
          setError(
            cause instanceof Error
              ? cause.message
              : "暂时无法读取后台进度，任务仍会继续运行。",
          );
      }
    };
    const timer = window.setInterval(
      () => void refreshBackgroundProgress(),
      2000,
    );
    void refreshBackgroundProgress();
    return () => {
      stopped = true;
      window.clearInterval(timer);
    };
  }, [
    activeProject,
    scene?.id,
    location.pathname,
    vpGenerationJob?.id,
    vpGenerationJob?.status,
  ]);
  const sceneShots = scene?.shots ?? [];
  const getDraft = (shot: NonNullable<typeof scene>["shots"][number]) =>
    shot.versions.find(
      (item) =>
        item.schema_version === "vp_precision_18_v1" &&
        item.package_stage === "director_draft",
    );
  const getFinal = (shot: NonNullable<typeof scene>["shots"][number]) =>
    shot.versions.find(
      (item) =>
        item.schema_version === "vp_precision_18_v1" &&
        item.package_stage === "final_execution",
    );
  const getAlignedFinal = (
    shot: NonNullable<typeof scene>["shots"][number],
  ) => {
    const draft = getDraft(shot);
    return shot.versions.find(
      (item) =>
        item.schema_version === "vp_precision_18_v1" &&
        item.package_stage === "final_execution" &&
        (!draft ||
          !item.basis_vp_block_id ||
          item.basis_vp_block_id === draft.id),
    );
  };
  const recommendedDuration = (
    shot: NonNullable<typeof scene>["shots"][number],
  ) => shot.recommended_duration_seconds ?? 8;
  const missingDraftShots = sceneShots.filter((shot) => !getDraft(shot));
  const missingFinalShots = sceneShots.filter((shot) => !getAlignedFinal(shot));
  const unconfirmedFinals = sceneShots
    .map((shot) => getAlignedFinal(shot))
    .filter(
      (block): block is VpBlock =>
        block !== undefined &&
        !["confirmed_current", "locked"].includes(block.status),
    );
  const durationRebuildShots = sceneShots.filter(
    (shot) =>
      getDraft(shot)?.duration_seconds === 5 && recommendedDuration(shot) !== 5,
  );
  const needsDurationRebuild = durationRebuildShots.length > 0;
  const vpJobActive = Boolean(
    vpGenerationJob &&
    ["queued", "running", "retrying"].includes(vpGenerationJob.status),
  );
  const vpJobFailed = vpGenerationJob?.status === "failed";
  const vpJobCancelled = vpGenerationJob?.status === "cancelled";
  const staleStoryboardShots = sceneShots.filter((shot) => {
    const draft = getDraft(shot);
    const previousFinal = getFinal(shot);
    return Boolean(
      draft &&
      previousFinal &&
      previousFinal.basis_vp_block_id &&
      previousFinal.basis_vp_block_id !== draft.id &&
      shot.confirmed_storyboard_vp_basis_block_id !== draft.id,
    );
  });
  const draftReadyCount = sceneShots.length - missingDraftShots.length;
  const finalReadyCount = sceneShots.length - missingFinalShots.length;
  const finalConfirmedCount = sceneShots.filter((shot) => {
    const block = getAlignedFinal(shot);
    return Boolean(
      block && ["confirmed_current", "locked"].includes(block.status),
    );
  }).length;
  const allDraftsReady =
    sceneShots.length > 0 && missingDraftShots.length === 0;
  const allFinalsGenerated =
    sceneShots.length > 0 && missingFinalShots.length === 0;
  const allFinalsConfirmed =
    sceneShots.length > 0 && finalConfirmedCount === sceneShots.length;
  const textChannelReady = Boolean(
    textStatus?.ready &&
    ["huimeng_chat", "openai_responses"].includes(textStatus.mode),
  );
  const textWorkRequired =
    missingDraftShots.length > 0 ||
    needsDurationRebuild ||
    (allDraftsReady &&
      missingFinalShots.length > 0 &&
      staleStoryboardShots.length === 0);
  const textChannelUnavailable =
    !textChannelReady && sceneShots.length > 0 && textWorkRequired;
  const generateSceneDrafts = async () => {
    if (!scene || missingDraftShots.length === 0) return;
    if (!textChannelReady) {
      setError(
        "生成分镜提示词需要先开启 AI 分析服务。请到“成本与设置”配置慧梦或 OpenAI 文本通道；如果已经配置，请确认后端 FastAPI 已在 http://127.0.0.1:8000 启动。",
      );
      return;
    }
    const confirmed = await confirmAction({
      title: "确认生成本场全部分镜提示词",
      message: textProviderConfirmationNotice(
        textStatus,
        `V7｜分镜提示词｜${scene.scope_code}`,
        `将为当前场 ${missingDraftShots.length} 个缺失镜头逐个生成故事板参考提示词。只生成文字，不生成图片，不提交视频。`,
      ),
      details: [
        `当前场：${scene.scope_code}｜${scene.name}`,
        `本场镜头：${sceneShots.length} 个`,
        `本次生成：${missingDraftShots.length} 个缺失分镜提示词`,
        "完成后再去故事板页，按这些提示词生成黑白故事板草稿。",
      ],
      confirmLabel: "确认生成",
      tone: "cost",
    });
    if (!confirmed) return;
    setBusy(true);
    setError("");
    try {
      let nextData: VideoPackageWorkspace | null = data;
      for (let index = 0; index < missingDraftShots.length; index += 1) {
        const shot = missingDraftShots[index];
        setBusyMessage(
          `正在生成本场分镜提示词：${index + 1}/${missingDraftShots.length}（${shot.shot_code}）`,
        );
        nextData = await generateAiVpBlock(
          shot.id,
          true,
          "director_draft",
          recommendedDuration(shot),
        );
        setData(nextData);
      }
      setBusyMessage("本场分镜提示词已全部生成，正在刷新页面…");
      if (nextData) setData(nextData);
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : "生成分镜提示词失败，请稍后重试。",
      );
    } finally {
      setBusy(false);
      setBusyMessage("");
    }
  };
  const generateSceneFinals = async () => {
    if (!scene || missingFinalShots.length === 0) return;
    if (!textChannelReady) {
      setError(
        "生成成片提示词需要先开启 AI 分析服务。请到“成本与设置”配置慧梦或 OpenAI 文本通道。",
      );
      return;
    }
    const assetlessFinal = creativeGoal === "prompt_storyboard";
    const confirmed = await confirmAction({
      title: assetlessFinal
        ? "确认生成无参考图成片提示词"
        : "确认生成本场成片提示词",
      message: textProviderConfirmationNotice(
        textStatus,
        `V7｜成片提示词｜${scene.scope_code}`,
        assetlessFinal
          ? "系统会读取已确认故事板，为缺失镜头生成文生视频使用的无参考图成片提示词。不会假装人物、服装或场景一致性已经锁定。"
          : "系统会先检查故事板是否已确认、正式资产图是否齐全，再为缺失镜头生成可直接给视频模型使用的成片提示词。",
      ),
      details: [
        `当前场：${scene.scope_code}｜${scene.name}`,
        `本场镜头：${sceneShots.length} 个`,
        `本次生成：${missingFinalShots.length} 个缺失成片提示词`,
        assetlessFinal
          ? "这条路线不要求资产图，但跨镜人物、服装和场景外观可能不一致；补齐资产后可以重新生成正式版本。"
          : "如果提示缺故事板，请先回故事板页确认；如果提示缺资产，请到资产页上传或生成资产图。",
      ],
      confirmLabel: assetlessFinal
        ? "确认生成无参考图提示词"
        : "确认生成成片提示词",
      tone: "cost",
    });
    if (!confirmed) return;
    setBusy(true);
    setError("");
    try {
      let nextData: VideoPackageWorkspace | null = data;
      for (let index = 0; index < missingFinalShots.length; index += 1) {
        const shot = missingFinalShots[index];
        setBusyMessage(
          `正在生成本场成片提示词：${index + 1}/${missingFinalShots.length}（${shot.shot_code}）`,
        );
        nextData = await generateAiVpBlock(
          shot.id,
          !assetlessFinal,
          "final_execution",
          recommendedDuration(shot),
        );
        setData(nextData);
      }
      setBusyMessage("本场成片提示词已生成，正在刷新页面…");
      if (nextData) setData(nextData);
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : "生成成片提示词失败，请稍后重试。",
      );
    } finally {
      setBusy(false);
      setBusyMessage("");
    }
  };
  const confirmSceneFinals = async () => {
    if (!scene || unconfirmedFinals.length === 0) return;
    const confirmed = await confirmAction({
      title: "确认本场成片提示词",
      message: `将把当前场 ${unconfirmedFinals.length} 个已生成的成片提示词确认为正式执行版本。确认后，未提交的视频队列会同步刷新，并要求重新确认预算。`,
      details: [
        `当前场：${scene.scope_code}｜${scene.name}`,
        `本次确认：${unconfirmedFinals.length} 个成片提示词`,
        "旧版本会保留为历史版本，不会覆盖或删除。",
        "确认后才能进入批量视频提交。",
      ],
      confirmLabel: "确认全部提示词",
    });
    if (!confirmed) return;
    setBusy(true);
    setError("");
    try {
      let nextData: VideoPackageWorkspace | null = data;
      for (let index = 0; index < unconfirmedFinals.length; index += 1) {
        const block = unconfirmedFinals[index];
        setBusyMessage(
          `正在确认本场成片提示词：${index + 1}/${unconfirmedFinals.length}`,
        );
        nextData = await transitionVpBlock(block.id, "confirm");
        setData(nextData);
      }
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : "确认成片提示词失败，请稍后重试。",
      );
    } finally {
      setBusy(false);
      setBusyMessage("");
    }
  };
  const switchToAssetlessFinal = async () => {
    setBusy(true);
    setBusyMessage("正在切换为无参考图提示词路线…");
    setError("");
    try {
      await setCreativeGoal("prompt_storyboard");
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : "切换创作路线失败，请稍后重试。",
      );
    } finally {
      setBusy(false);
      setBusyMessage("");
    }
  };
  const rebuildSceneTimingDrafts = async () => {
    if (!scene || !textChannelReady || durationRebuildShots.length === 0)
      return;
    const confirmed = await confirmAction({
      title: "确认按镜头节奏重建分镜提示词",
      message: textProviderConfirmationNotice(
        textStatus,
        `V7｜时长重建｜${scene.scope_code}`,
        `检测到本场 ${durationRebuildShots.length} 个镜头仍沿用旧版 5 秒默认值。系统只重建这些镜头，已经符合主规则的镜头保持不变，旧版本也会保留。`,
      ),
      details: [
        `本次重建：${durationRebuildShots.map((shot) => shot.shot_code).join("、")}`,
        "单一动作通常 6 秒，标准镜头约 8 秒，多阶段动作或蒙太奇约 10–12 秒。",
        "单个 Video Unit 仍严格不超过 15 秒；超过上限的内容必须拆分。",
        "生成新分镜提示词后，需要到故事板页重建并确认对应时间轴，再回来生成成片提示词。",
      ],
      confirmLabel: "确认重建时长",
      tone: "cost",
    });
    if (!confirmed) return;
    setBusy(true);
    setError("");
    try {
      setBusyMessage("正在把本场重建任务交给后台…");
      const job = await startVpDurationRebuild(scene.id);
      setVpGenerationJob(job);
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : "后台重建任务启动失败，请稍后重试。",
      );
    } finally {
      setBusy(false);
      setBusyMessage("");
    }
  };
  const retryBackgroundJob = async () => {
    if (!vpGenerationJob) return;
    setBusy(true);
    setBusyMessage("正在重新加入后台队列…");
    setError("");
    try {
      setVpGenerationJob(await retryVpGenerationJob(vpGenerationJob.id));
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : "后台任务重新启动失败，请稍后重试。",
      );
    } finally {
      setBusy(false);
      setBusyMessage("");
    }
  };
  const cancelBackgroundJob = async () => {
    if (!vpGenerationJob || !vpJobActive) return;
    const confirmed = await confirmAction({
      title: "停止后台时长重建？",
      message: `停止后不会再开始下一个镜头。已经完成的 ${vpGenerationJob.completed_count}/${vpGenerationJob.total_count} 个新提示词、旧提示词版本和现有故事板图片都会保留。`,
      details: [
        `${vpGenerationJob.current_shot_code || "当前镜头"} 如果已经发给文本服务，可能仍会完成；已经发生的调用无法撤回。`,
        "停止后可以再次点击“继续重建剩余镜头”，系统只处理仍为旧版 5 秒的镜头。",
        "故事板图片不会在这里删除；提示词时长更新完成后，故事板页会判断哪些旧图可沿用。",
      ],
      confirmLabel: "停止后续重建",
      tone: "danger",
    });
    if (!confirmed) return;
    setBusy(true);
    setBusyMessage("正在停止后续重建…");
    setError("");
    try {
      setVpGenerationJob(await cancelVpGenerationJob(vpGenerationJob.id));
      if (activeProject) setData(await fetchVideoPackages(activeProject.id));
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : "停止后台重建失败，请稍后重试。",
      );
    } finally {
      setBusy(false);
      setBusyMessage("");
    }
  };
  const currentTitle = vpJobActive
    ? `后台重建中：${vpGenerationJob?.completed_count ?? 0}/${vpGenerationJob?.total_count ?? durationRebuildShots.length}`
    : vpJobFailed
      ? `后台重建暂停在 ${vpGenerationJob?.current_shot_code || "当前镜头"}`
      : vpJobCancelled && needsDurationRebuild
        ? `后台重建已停止：剩余 ${durationRebuildShots.length} 个镜头`
        : textChannelUnavailable
          ? "先开启 AI 分析服务"
          : needsDurationRebuild
            ? durationRebuildShots.length === sceneShots.length
              ? "修正全场统一 5 秒的旧版时间轴"
              : `修正剩余 ${durationRebuildShots.length} 个旧版 5 秒镜头`
            : staleStoryboardShots.length > 0
              ? `按新时长重建 ${staleStoryboardShots.length} 张故事板`
              : !allDraftsReady
                ? missingDraftShots.length === sceneShots.length
                  ? "一次生成本场全部分镜提示词"
                  : `补齐剩余 ${missingDraftShots.length} 个分镜提示词`
                : !allFinalsGenerated
                  ? creativeGoal === "prompt_storyboard"
                    ? `生成本场无参考图成片提示词（已完成 ${finalReadyCount}/${sceneShots.length}）`
                    : `生成本场资产绑定版成片提示词（已完成 ${finalReadyCount}/${sceneShots.length}）`
                  : !allFinalsConfirmed
                    ? `确认本场 ${unconfirmedFinals.length} 个成片提示词`
                    : "分镜提示词已经准备好";
  const currentDescription = vpJobActive
    ? `${vpGenerationJob?.message || "后台正在继续处理"}。可切换到任何菜单；如需停止，请使用右侧按钮。现有故事板图片不会被删除。`
    : vpJobFailed
      ? `${vpGenerationJob?.error_message || "后台任务连续失败。"} 已完成的镜头不会重复生成，修正服务后可从当前镜头继续。`
      : vpJobCancelled && needsDurationRebuild
        ? `${vpGenerationJob?.message || "任务已停止。"} 可以保留当前结果，也可以继续完成剩余镜头；只有继续正式视频流程时才需要补齐。`
        : textChannelUnavailable
          ? "分镜提示词必须由真实文本 AI 按 V7 主系统生成，不能用本地占位内容冒充。请先配置并启动服务。"
          : needsDurationRebuild
            ? `仍有 ${durationRebuildShots.length} 个镜头来自旧版 5 秒默认值。系统只重建这些镜头，已符合主规则的镜头不会重复生成。`
            : staleStoryboardShots.length > 0
              ? "分镜提示词已经使用新的镜头时长，但现有故事板仍绑定旧的 5 秒时间轴。请先重建并确认故事板，系统才允许生成新的成片提示词。"
              : !allDraftsReady
                ? `这一步会按当前场所有镜头一次性生成文字提示词。已完成 ${draftReadyCount}/${sceneShots.length}，还缺 ${missingDraftShots.length} 个。`
                : !allFinalsGenerated
                  ? creativeGoal === "prompt_storyboard"
                    ? "这一步只要求故事板已经确认，将生成可用于文生视频的无参考图成片提示词。它不会虚构资产绑定，也不能保证跨镜外观一致。"
                    : "这一步会先检查故事板确认状态和正式资产图。缺什么会告诉你去哪里处理；通过后生成可直接给视频模型使用的资产绑定版成片提示词。"
                  : !allFinalsConfirmed
                    ? `成片提示词已经全部生成，但还有 ${unconfirmedFinals.length} 个处于待确认状态。确认后才会更新视频队列并允许继续。`
                    : "你可以查看完整提示词，或继续去批量视频页创建队列。";
  const assetError = error.includes("资产");
  const storyboardError = error.includes("故事板");
  const stageItems: DirectorStageItem[] = [
    {
      title: "读取镜头",
      detail: scene
        ? `${scene.scope_code}｜${sceneShots.length} 个镜头`
        : "请选择一个场",
      status: sceneShots.length > 0 ? "done" : "current",
    },
    {
      title: "分镜提示词",
      detail: vpJobActive
        ? `后台处理 ${vpGenerationJob?.completed_count ?? 0}/${vpGenerationJob?.total_count ?? 0}${vpGenerationJob?.current_shot_code ? `｜${vpGenerationJob.current_shot_code}` : ""}`
        : `${draftReadyCount}/${sceneShots.length || 0} 已生成`,
      status: vpJobFailed
        ? "blocked"
        : textChannelUnavailable
          ? "blocked"
          : allDraftsReady
            ? "done"
            : "current",
    },
    {
      title: "黑白故事板",
      detail: needsDurationRebuild
        ? "新时长生成后需重新确认"
        : allFinalsGenerated
          ? "已确认"
          : allDraftsReady
            ? "确认后生成成片提示词"
            : "提示词完成后再画",
      status: needsDurationRebuild
        ? "pending"
        : allFinalsGenerated
          ? "done"
          : allDraftsReady
            ? "current"
            : "pending",
    },
    {
      title: "成片提示词",
      detail: needsDurationRebuild
        ? "旧版本已保留，待时长链路更新"
        : `${finalReadyCount}/${sceneShots.length || 0} 已生成｜${finalConfirmedCount}/${sceneShots.length || 0} 已确认`,
      status: needsDurationRebuild
        ? "pending"
        : allFinalsConfirmed
          ? "done"
          : allDraftsReady
            ? "current"
            : "pending",
    },
  ];

  return (
    <div className={workbenchPageClass}>
      {busy ? (
        <GuideProgressToast
          label={busyMessage || "正在生成分镜提示词，请稍等…"}
        />
      ) : null}
      <div className="mb-5 flex items-end justify-between gap-6">
        <div>
          <p className="text-xs tracking-[.18em] text-orange-400">
            V7｜分镜提示词
          </p>
          <h1 className="mt-2 text-4xl font-semibold tracking-[-0.04em]">
            分镜提示词
          </h1>
          <p className="mt-3 max-w-3xl text-sm leading-6 text-zinc-400">
            这一页只做文字提示词，不生成图片，也不提交视频。先给故事板用，故事板确认后再生成成片用。
          </p>
        </div>
        <select
          aria-label="选择场景"
          className="border border-white/15 bg-[#11171c] px-3 py-2 text-sm"
          value={scene?.id ?? ""}
          onChange={(event) => setSceneId(event.target.value)}
        >
          {data?.scenes.map((item) => (
            <option key={item.id} value={item.id}>
              {item.scope_code}｜{item.name}
            </option>
          ))}
        </select>
      </div>
      <DirectorWorkbenchFrame
        main={
          <GuideActionCard
            eyebrow={scene ? `当前场：${scene.scope_code}` : "当前任务"}
            title={currentTitle}
            description={
              sceneShots.length
                ? currentDescription
                : "请先选择一个有镜头的场。"
            }
            tone={
              !needsDurationRebuild &&
              staleStoryboardShots.length === 0 &&
              allFinalsConfirmed
                ? "done"
                : "current"
            }
            progressLabel={
              busy ? busyMessage || "正在处理，请稍等…" : undefined
            }
          >
            {vpJobActive ? (
              <div className="flex flex-wrap items-center justify-end gap-3">
                <span className="text-sm text-zinc-400">
                  {vpGenerationJob?.message || "后台重建中…"}
                </span>
                <button
                  className={button}
                  disabled={busy}
                  onClick={() => void cancelBackgroundJob()}
                  type="button"
                >
                  <Square size={13} />
                  停止后续重建
                </button>
              </div>
            ) : vpJobFailed ? (
              <GuidePrimaryButton
                loading={busy}
                loadingLabel="正在重新加入后台队列…"
                onClick={() => void retryBackgroundJob()}
              >
                从失败镜头继续
              </GuidePrimaryButton>
            ) : textChannelUnavailable ? (
              <GuidePrimaryButton href="/settings">
                去设置 AI 分析服务
              </GuidePrimaryButton>
            ) : needsDurationRebuild ? (
              <GuidePrimaryButton
                loading={busy}
                loadingLabel={busyMessage || "正在按镜头节奏重建…"}
                onClick={() => void rebuildSceneTimingDrafts()}
              >
                按主规则重建本场时长
              </GuidePrimaryButton>
            ) : staleStoryboardShots.length > 0 ? (
              <GuidePrimaryButton href="/storyboards">
                去重建故事板时间轴
              </GuidePrimaryButton>
            ) : !allDraftsReady && sceneShots.length > 0 ? (
              <GuidePrimaryButton
                loading={busy}
                loadingLabel={busyMessage || "正在生成本场分镜提示词…"}
                onClick={() => void generateSceneDrafts()}
              >
                一次生成本场全部分镜提示词
              </GuidePrimaryButton>
            ) : allDraftsReady && !allFinalsGenerated ? (
              <GuidePrimaryButton
                loading={busy}
                loadingLabel={busyMessage || "正在生成本场成片提示词…"}
                onClick={() => void generateSceneFinals()}
              >
                {creativeGoal === "prompt_storyboard"
                  ? "生成无参考图成片提示词"
                  : "生成资产绑定版成片提示词"}
              </GuidePrimaryButton>
            ) : allFinalsGenerated && !allFinalsConfirmed ? (
              <GuidePrimaryButton
                loading={busy}
                loadingLabel={busyMessage || "正在确认本场成片提示词…"}
                onClick={() => void confirmSceneFinals()}
              >
                确认本场全部成片提示词
              </GuidePrimaryButton>
            ) : allFinalsConfirmed ? (
              <GuidePrimaryButton
                href={
                  creativeGoal === "prompt_storyboard"
                    ? "/storyboards"
                    : "/batch-video"
                }
              >
                {creativeGoal === "prompt_storyboard"
                  ? "查看已确认故事板"
                  : "去批量视频"}
              </GuidePrimaryButton>
            ) : null}
          </GuideActionCard>
        }
        aside={
          <div className="space-y-4">
            <DirectorStatusPanel
              title="本场提示词进度"
              description="这页只负责文字提示词。完成后去故事板页生成黑白草稿。"
              items={stageItems}
            />
          </div>
        }
      />
      {creativeGoal === "prompt_storyboard" ? (
        <section className="mt-4 border border-sky-400/30 bg-sky-400/6 px-4 py-3 text-sm leading-6 text-sky-100">
          当前是“提示词 +
          故事板”路线：故事板确认后可直接生成无参考图成片提示词，不要求人物或场景资产图。提示词按文生视频使用，不能保证跨镜外观一致。
        </section>
      ) : allDraftsReady && !allFinalsGenerated ? (
        <section className="mt-4 flex items-center justify-between gap-5 border border-sky-400/30 bg-sky-400/6 px-4 py-3 text-sm leading-6 text-sky-100">
          <span>
            当前是完整生产路线，资产绑定版成片提示词需要正式资产图。只想要提示词和故事板，可以改用无参考图路线。
          </span>
          <button
            className={button}
            disabled={busy}
            onClick={() => void switchToAssetlessFinal()}
            type="button"
          >
            不做资产，改用无参考图提示词
          </button>
        </section>
      ) : null}
      {error && !assetError ? (
        <p className="mt-4 border-l-2 border-red-400 bg-red-400/8 px-4 py-3 text-sm text-red-200">
          {humanizeCopy(error)}{" "}
          {storyboardError ? (
            <Link
              className="ml-3 text-orange-200 underline decoration-orange-400/60 underline-offset-4"
              to="/storyboards"
            >
              去故事板页确认故事板
            </Link>
          ) : null}
        </p>
      ) : null}
      {assetError && allDraftsReady ? (
        <section className="mt-4 border border-red-400/30 bg-red-400/8 px-4 py-3 text-sm leading-6 text-red-100">
          {humanizeCopy(error)}
          <Link
            className="ml-3 text-orange-200 underline decoration-orange-400/60 underline-offset-4"
            to="/assets"
          >
            去资产页上传或生成资产图
          </Link>
        </section>
      ) : null}
      <TechDetails title="可选：查看单镜提示词全文">
        <section className="space-y-4">
          {scene?.shots.map((shot) => {
            const versions = shot.versions.filter(
              (item) => item.schema_version === "vp_precision_18_v1",
            );
            const latest = versions[0];
            const final = versions.find(
              (item) => item.package_stage === "final_execution",
            );
            const draft = versions.find(
              (item) => item.package_stage === "director_draft",
            );
            return (
              <article
                className="border border-white/15 bg-[#151b21] p-4"
                key={shot.id}
              >
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <b className="text-orange-300">
                      {shot.shot_code}｜{shot.name}
                    </b>
                    <p className="mt-2 text-xs text-zinc-500">
                      故事板参考提示词：
                      {draft ? `第 ${draft.version_number} 版` : "未生成"}
                      ｜成片提示词：
                      {final ? `第 ${final.version_number} 版` : "未生成"}
                    </p>
                  </div>
                  <div className="flex flex-wrap justify-end gap-2">
                    {latest && (
                      <button
                        className={button}
                        onClick={() =>
                          setExpanded(expanded === latest.id ? "" : latest.id)
                        }
                        type="button"
                      >
                        <ShieldCheck size={14} />
                        {expanded === latest.id
                          ? "收起提示词"
                          : "查看完整提示词"}
                      </button>
                    )}
                  </div>
                </div>
                <p className="mt-3 text-xs leading-5 text-cyan-200">
                  主规则建议：{recommendedDuration(shot)} 秒
                  {shot.duration_reason ? `｜${shot.duration_reason}` : ""}
                  {latest ? `｜当前版本：${latest.duration_seconds} 秒` : ""}
                </p>
                {!draft ? (
                  <p className="mt-3 text-xs text-zinc-500">
                    请先生成故事板参考提示词。没有它，故事板页不知道该按哪些时间点来画。
                  </p>
                ) : null}
                {latest && (
                  <>
                    <div className="mt-4 flex flex-wrap gap-3 text-xs text-emerald-300">
                      <span>阶段：{stageName(latest.package_stage)}</span>
                      <span>状态：{versionStateName(latest.status)}</span>
                      {latest.validation_items.map((item) => (
                        <span key={item}>通过：{humanizeCopy(item)}</span>
                      ))}
                    </div>
                    {expanded === latest.id && (
                      <PrecisionDetails block={latest} />
                    )}
                  </>
                )}
              </article>
            );
          })}
        </section>
      </TechDetails>
    </div>
  );
}
