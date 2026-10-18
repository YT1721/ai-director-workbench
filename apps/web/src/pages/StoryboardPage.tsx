import { useEffect, useMemo, useState } from "react";
import { Axis3D, Download, RefreshCw, Save, X } from "lucide-react";

import {
  DirectorStatusPanel,
  DirectorWorkbenchFrame,
  GuideActionCard,
  GuidePrimaryButton,
  GuideProgressToast,
  type DirectorStageItem,
} from "../components/Guide";
import { useConfirmAction } from "../components/ConfirmDialog";
import {
  assetImageUrl,
  downloadLocalAsset,
  downloadStoryboardImage,
  exportPromptStoryboardPack,
  fetchStoryboardImagePrompt,
  fetchStoryboardWorkspace,
  fetchStoryboardImageReadiness,
  generateStoryboardPage,
  generateStoryboardVersion,
  pollStoryboardImage,
  reuseStoryboardImage,
  saveAxisPlan,
  submitStoryboardImage,
  transitionStoryboardVersion,
} from "../services/api";
import { useWorkbenchStore } from "../stores/useWorkbenchStore";
import { workbenchPageClass } from "../styles/layout";
import type {
  AxisPlan,
  StoryboardScene,
  StoryboardImageJob,
  StoryboardImageReadiness,
  StoryboardVersion,
  StoryboardWorkspace,
  PromptStoryboardExport,
} from "../types/storyboards";
import { humanizeCopy } from "../utils/humanCopy";

const inputClass =
  "w-full border border-white/15 bg-[#0f151a] px-3 py-2 text-sm text-zinc-200 outline-none transition focus:border-orange-400/70";
const buttonClass =
  "inline-flex items-center gap-2 border border-white/12 bg-white/[0.03] px-3 py-2 text-xs text-zinc-400 transition hover:border-orange-400/35 hover:bg-orange-400/7 hover:text-orange-200 disabled:cursor-not-allowed disabled:opacity-35";

type PreviewImage = {
  shotCode: string;
  shotName: string;
  version: StoryboardVersion;
  assetUrl: string;
  url: string;
  isRealImage?: boolean;
};

const storyboardSchemas = new Set(["unified_sb_v1", "vp_precision_18_v1"]);
const activeImageJobStatuses = new Set(["submitted", "processing"]);

function imageJobStage(status: string) {
  if (status === "submitted") return 1;
  if (status === "processing") return 2;
  if (status === "completed") return 3;
  if (status === "downloaded") return 4;
  return 0;
}

function workspaceWithImageJob(
  workspace: StoryboardWorkspace,
  versionId: string,
  job: StoryboardImageJob,
): StoryboardWorkspace {
  return {
    ...workspace,
    scenes: workspace.scenes.map((scene) => ({
      ...scene,
      shots: scene.shots.map((shot) => ({
        ...shot,
        versions: shot.versions.map((version) =>
          version.id === versionId
            ? { ...version, latest_image_job: job }
            : version,
        ),
      })),
    })),
  };
}

function imageJobStatusText(status: string) {
  if (status === "submitted") return "已提交，后台正在排队";
  if (status === "processing") return "生成中，后台会持续查询";
  if (status === "completed") return "图片已完成，等待保存到项目";
  if (status === "downloaded") return "图片已保存到项目";
  if (status === "failed" || status === "cancelled") return "本次生成失败";
  return humanizeCopy(status);
}

function isStoryboardSchema(schema: string) {
  return storyboardSchemas.has(schema);
}

function latestStoryboardVersion(shot: StoryboardScene["shots"][number]) {
  return shot.versions.find(
    (version) =>
      isStoryboardSchema(version.schema_version) &&
      (!shot.latest_vp_draft_id ||
        version.vp_basis_block_id === shot.latest_vp_draft_id),
  );
}

function isStoryboardConfirmed(version?: StoryboardVersion) {
  return Boolean(version && version.status !== "draft");
}

function isRealStoryboardImage(version?: StoryboardVersion) {
  if (!version?.image_url) return false;
  const imageUrl = version.image_url.toLowerCase();
  return (
    version.grid_reason.includes("真实生图") ||
    imageUrl.includes("_sb_real_") ||
    imageUrl.includes("_sb_reused_")
  );
}

function latestConfirmedStoryboardVersion(
  shot: StoryboardScene["shots"][number],
) {
  return shot.versions.find(
    (version) =>
      isStoryboardSchema(version.schema_version) &&
      isStoryboardConfirmed(version) &&
      (!shot.latest_vp_draft_id ||
        version.vp_basis_block_id === shot.latest_vp_draft_id),
  );
}

function sceneStoryboardStats(scene?: StoryboardScene) {
  const shots = scene?.shots ?? [];
  const versions = shots.map((shot) => latestStoryboardVersion(shot));
  const missingShots = shots.filter((shot) => !latestStoryboardVersion(shot));
  const draftVersions = versions.filter(
    (version): version is StoryboardVersion =>
      Boolean(version && version.status === "draft"),
  );
  const confirmedVersions = versions.filter(isStoryboardConfirmed);
  const realImageVersions = versions.filter(isRealStoryboardImage);
  const confirmedWithoutRealImages = shots
    .map(latestConfirmedStoryboardVersion)
    .filter((version): version is StoryboardVersion =>
      Boolean(version && !isRealStoryboardImage(version)),
    );
  const previewVersions = versions.filter(
    (version): version is StoryboardVersion => Boolean(version?.image_url),
  );
  const reusableShots = shots.filter((shot) => {
    const version = latestConfirmedStoryboardVersion(shot);
    return Boolean(
      version &&
      !isRealStoryboardImage(version) &&
      shot.reuse_assessment?.can_reuse,
    );
  });

  return {
    total: shots.length,
    missing: missingShots.length,
    drafts: draftVersions.length,
    confirmed: confirmedVersions.length,
    realImages: realImageVersions.length,
    confirmedWithoutRealImages,
    reusableShots,
    previews: previewVersions.length,
    missingShots,
    draftVersions,
    complete: shots.length > 0 && confirmedVersions.length === shots.length,
  };
}

function storyboardNextStep(scene?: StoryboardScene) {
  if (!scene) {
    return {
      title: "请选择一场戏",
      detail: "选好场次后，系统会按镜头显示故事板进度。",
      tone: "pending",
    };
  }
  const stats = sceneStoryboardStats(scene);
  if (stats.missing > 0) {
    return {
      title: `补齐 ${stats.missing} 张故事板草稿`,
      detail:
        "一次按本场所有镜头生成黑白故事板草稿。它读取分镜提示词，不需要先补正式资产图。",
      tone: "current",
    };
  }
  if (stats.drafts > 0) {
    return {
      title: `确认 ${stats.drafts} 个镜头的拆分与时间段`,
      detail:
        "这里确认的是格数、动作节点和镜头方向，不是真实故事板图片。确认后，下一步会逐张生成 AI 故事板图。",
      tone: "current",
    };
  }
  if (stats.confirmedWithoutRealImages.length > 0) {
    if (stats.reusableShots.length > 0) {
      return {
        title: `确认是否沿用 ${stats.reusableShots.length} 张旧故事板图`,
        detail:
          "系统已比较格数、动作节点、机位和轴线。结构兼容的旧图可复制为新版本并绑定当前时间轴，不会调用生图服务。",
        tone: "current",
      };
    }
    return {
      title: `生成下一张真实故事板图`,
      detail: `本场 ${stats.confirmed}/${stats.total} 张草稿已确认，但还有 ${stats.confirmedWithoutRealImages.length} 张只是本地结构图。每次只发起 1 张真实 image-2 请求，避免误扣费。`,
      tone: "current",
    };
  }
  if (!stats.complete) {
    return {
      title: "检查故事板状态",
      detail: "有镜头状态不完整。请在更多资料里查看单镜记录。",
      tone: "current",
    };
  }
  return {
    title: "故事板已经准备好",
    detail:
      "可以导出故事板包；如果要继续做完整视频，再回到分镜提示词页生成最终视频提示词。",
    tone: "done",
  };
}

export function StoryboardPage() {
  const { activeProject, projects, loadProjects, creativeGoal } =
    useWorkbenchStore();
  const [workspace, setWorkspace] = useState<StoryboardWorkspace | null>(null);
  const [sceneId, setSceneId] = useState("");
  const [axisDraft, setAxisDraft] = useState<AxisPlan | null>(null);
  const [busy, setBusy] = useState(false);
  const [busyMessage, setBusyMessage] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [actionMessage, setActionMessage] = useState<string | null>(null);
  const [downloadHint, setDownloadHint] = useState<string | null>(null);
  const [exportResult, setExportResult] =
    useState<PromptStoryboardExport | null>(null);
  const [previewImage, setPreviewImage] = useState<PreviewImage | null>(null);
  const [imageConfirm, setImageConfirm] = useState<{
    version: StoryboardVersion;
    shotCode: string;
    readiness: StoryboardImageReadiness;
    correctionNote?: string;
    promptOverride?: string;
    mode?: "generate" | "regenerate";
  } | null>(null);
  const [imagePromptDrafts, setImagePromptDrafts] = useState<
    Record<string, string>
  >({});
  const [imagePromptLoading, setImagePromptLoading] = useState<
    Record<string, boolean>
  >({});
  const [activeImageVersionId, setActiveImageVersionId] = useState("");
  const [imageActionErrors, setImageActionErrors] = useState<
    Record<string, string>
  >({});
  const [imageLastSyncedAt, setImageLastSyncedAt] = useState("");
  const confirmAction = useConfirmAction();

  useEffect(() => {
    if (projects.length === 0) void loadProjects();
  }, [loadProjects, projects.length]);

  useEffect(() => {
    if (!activeProject) return;
    setBusy(true);
    setBusyMessage("正在读取故事板任务…");
    fetchStoryboardWorkspace(activeProject.id)
      .then((result) => {
        setWorkspace(result);
        setImageLastSyncedAt(
          new Date().toLocaleTimeString("zh-CN", { hour12: false }),
        );
        setSceneId((current) => current || result.scenes[0]?.id || "");
        setError(null);
      })
      .catch((nextError: Error) => setError(nextError.message))
      .finally(() => {
        setBusy(false);
        setBusyMessage("");
      });
  }, [activeProject]);

  const scene = useMemo(
    () =>
      workspace?.scenes.find((item) => item.id === sceneId) ??
      workspace?.scenes[0],
    [sceneId, workspace],
  );
  const firstShot = scene?.shots[0];

  useEffect(() => {
    if (scene) setAxisDraft(scene.axis_plan);
  }, [scene]);

  useEffect(() => {
    if (!activeProject || !workspace) return;
    const hasActiveImageTask = workspace.scenes.some((item) =>
      item.shots.some((shot) => {
        const job = latestStoryboardVersion(shot)?.latest_image_job;
        return Boolean(
          job && ["submitted", "processing", "completed"].includes(job.status),
        );
      }),
    );
    if (!hasActiveImageTask) return;
    const timer = window.setInterval(() => {
      fetchStoryboardWorkspace(activeProject.id)
        .then((result) => {
          setWorkspace(result);
          setImageLastSyncedAt(
            new Date().toLocaleTimeString("zh-CN", { hour12: false }),
          );
        })
        .catch(() => undefined);
    }, 3000);
    return () => window.clearInterval(timer);
  }, [activeProject, workspace]);

  useEffect(() => {
    if (!scene) return;
    scene.shots.forEach((shot) => {
      const version = latestStoryboardVersion(shot);
      if (!version) return;
      if (version.latest_image_job?.prompt) {
        setImagePromptDrafts((current) =>
          current[version.id]
            ? current
            : {
                ...current,
                [version.id]: version.latest_image_job?.prompt ?? "",
              },
        );
        return;
      }
      if (imagePromptDrafts[version.id] || imagePromptLoading[version.id])
        return;
      setImagePromptLoading((current) => ({ ...current, [version.id]: true }));
      fetchStoryboardImagePrompt(version.id)
        .then((result) => {
          setImagePromptDrafts((current) =>
            current[version.id]
              ? current
              : { ...current, [version.id]: result.prompt },
          );
        })
        .catch(() => {
          setImagePromptDrafts((current) =>
            current[version.id] ? current : { ...current, [version.id]: "" },
          );
        })
        .finally(() => {
          setImagePromptLoading((current) => ({
            ...current,
            [version.id]: false,
          }));
        });
    });
  }, [scene, imagePromptDrafts, imagePromptLoading]);

  useEffect(() => {
    if (!previewImage) return;
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") setPreviewImage(null);
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [previewImage]);

  function run(
    operation: () => Promise<StoryboardWorkspace>,
    message = "正在处理故事板，请稍等…",
  ) {
    setBusy(true);
    setBusyMessage(message);
    setError(null);
    setActionMessage(null);
    operation()
      .then((nextWorkspace) => {
        setWorkspace(nextWorkspace);
        setActionMessage("已完成。页面已刷新，请按当前主按钮继续下一步。");
      })
      .catch((nextError: Error) => setError(nextError.message))
      .finally(() => {
        setBusy(false);
        setBusyMessage("");
      });
  }

  async function generateMissingSceneStoryboards(targetScene: StoryboardScene) {
    let nextWorkspace = workspace;
    const missingShots = sceneStoryboardStats(targetScene).missingShots;
    for (const [index, shot] of missingShots.entries()) {
      setBusyMessage(
        `正在生成故事板草稿 ${index + 1}/${missingShots.length}：${shot.shot_code}`,
      );
      nextWorkspace = await generateStoryboardVersion(shot.id, {
        camera_point: `CAM0${targetScene.shots.findIndex((item) => item.id === shot.id) + 1}`,
        movement_direction: targetScene.axis_plan.movement_direction,
        camera_side: targetScene.axis_plan.camera_safe_side,
      });
    }
    return nextWorkspace ?? fetchStoryboardWorkspace(activeProject!.id);
  }

  async function confirmSceneStoryboards(targetScene: StoryboardScene) {
    let nextWorkspace = workspace;
    const draftVersions = sceneStoryboardStats(targetScene).draftVersions;
    for (const [index, version] of draftVersions.entries()) {
      setBusyMessage(`正在确认故事板草稿 ${index + 1}/${draftVersions.length}`);
      nextWorkspace = await transitionStoryboardVersion(version.id, "confirm");
    }
    return nextWorkspace ?? fetchStoryboardWorkspace(activeProject!.id);
  }

  async function confirmReuseStoryboard(
    shot: StoryboardScene["shots"][number],
    version: StoryboardVersion,
    forceReuse = false,
  ) {
    const assessment = shot.reuse_assessment;
    if (!assessment || (!assessment.can_reuse && !forceReuse)) return;
    const confirmed = await confirmAction({
      title: forceReuse
        ? `仍使用 ${shot.shot_code} 原故事板图？`
        : `确认沿用 ${shot.shot_code} 旧故事板图`,
      message: forceReuse
        ? "系统检测到新旧结构存在明显差异。你仍可人工决定使用原图，但原图中的格数、动作或机位可能与新时间轴不一致。"
        : assessment.recommendation === "reuse"
          ? "系统判断画面结构兼容。确认后会复制旧图为新版本，并绑定当前时间轴。"
          : "部分镜头参数有变化，请先查看旧图和差异。确认后系统会按你的决定沿用，不会调用生图服务。",
      details: [
        ...assessment.reasons,
        `旧时间段：${assessment.old_time_ranges.join(" / ") || "未记录"}`,
        `新时间段：${assessment.new_time_ranges.join(" / ") || "未记录"}`,
        "旧图和历史版本会保留，本操作不会产生图片生成费用。",
        ...(forceReuse
          ? ["系统会记录为“用户人工强制沿用”，不会标记成结构兼容。"]
          : []),
      ],
      confirmLabel: forceReuse ? "仍使用原图并绑定" : "确认沿用并绑定",
      tone: forceReuse ? "danger" : "normal",
    });
    if (!confirmed) return;
    run(
      () =>
        reuseStoryboardImage(
          version.id,
          assessment.source_version_id,
          forceReuse,
        ),
      `正在沿用并重新绑定 ${shot.shot_code}…`,
    );
  }

  async function createStoryboardOverview(targetScene: StoryboardScene) {
    setBusyMessage("正在生成故事板总览图…");
    return generateStoryboardPage(targetScene.id);
  }

  async function pollAndDownloadRealImage(jobId: string) {
    setBusyMessage("正在查询真实故事板图片…");
    const job = await pollStoryboardImage(jobId);
    if (job.status === "completed" && job.remote_result_url) {
      setBusyMessage("真实图片已完成，正在下载到项目…");
      return downloadStoryboardImage(job.id);
    }
    setActionMessage(
      `真实图片任务已提交，当前状态：${humanizeCopy(job.status)}。稍后再点主按钮查询并下载。`,
    );
    return fetchStoryboardWorkspace(activeProject!.id);
  }

  async function submitRealImageTask(
    version: StoryboardVersion,
    correctionNote = "",
    promptOverride = "",
  ) {
    setBusyMessage("正在提交真实故事板图片请求…");
    const correction = correctionNote.trim();
    const prompt = promptOverride.trim();
    const job = prompt
      ? await submitStoryboardImage(version.id, "", prompt)
      : correction
        ? await submitStoryboardImage(version.id, correction)
        : await submitStoryboardImage(version.id);
    setWorkspace((current) =>
      current ? workspaceWithImageJob(current, version.id, job) : current,
    );
    setImageLastSyncedAt(
      new Date().toLocaleTimeString("zh-CN", { hour12: false }),
    );
    if (job.status === "downloaded") {
      // 即时生图模式：图片已在提交时存入项目并生成新版本。
      setActionMessage(
        "真实故事板图片已生成并保存为新版本，可在下方版本列表查看。",
      );
      return fetchStoryboardWorkspace(activeProject!.id);
    }
    setActionMessage(
      `${imageJobStatusText(job.status)}。后台会继续处理，可以切换页面。`,
    );
    return fetchStoryboardWorkspace(activeProject!.id);
  }

  async function prepareRealImageGeneration(
    version: StoryboardVersion,
    shotCode: string,
    correctionNote = "",
    mode: "generate" | "regenerate" = "generate",
    promptOverride = "",
  ) {
    const existingJob = version.latest_image_job;
    if (existingJob && activeImageJobStatuses.has(existingJob.status)) {
      run(
        () => pollAndDownloadRealImage(existingJob.id),
        `正在查询 ${shotCode} 的真实故事板图片…`,
      );
      return;
    }
    if (existingJob?.status === "completed" && existingJob.remote_result_url) {
      run(
        () => downloadStoryboardImage(existingJob.id),
        `正在把 ${shotCode} 的真实故事板图片保存到项目…`,
      );
      return;
    }
    setBusy(true);
    setActiveImageVersionId(version.id);
    setBusyMessage("正在检查真实生图条件…");
    setError(null);
    setActionMessage(null);
    setImageActionErrors((current) => ({ ...current, [version.id]: "" }));
    try {
      const readiness = await fetchStoryboardImageReadiness(version.id);
      if (!readiness.ready) {
        const missing = readiness.gate_items
          .filter((item) => !item.passed)
          .map((item) => `${item.label}：${item.detail}`)
          .join("；");
        const message = `还不能生成真实故事板图片。${missing}`;
        setError(message);
        setImageActionErrors((current) => ({
          ...current,
          [version.id]: message,
        }));
        return;
      }
      setImageConfirm({
        version,
        shotCode,
        readiness,
        correctionNote,
        promptOverride,
        mode,
      });
    } catch (nextError) {
      const message =
        nextError instanceof Error
          ? nextError.message
          : "检查真实生图条件失败。";
      setError(message);
      setImageActionErrors((current) => ({
        ...current,
        [version.id]: message,
      }));
    } finally {
      setBusy(false);
      setActiveImageVersionId("");
      setBusyMessage("");
    }
  }

  function confirmRealImageGeneration() {
    if (!imageConfirm) return;
    const target = imageConfirm;
    setImageConfirm(null);
    const message =
      target.mode === "regenerate"
        ? `正在按修改后的提示词重新生成 ${target.shotCode}…`
        : `正在生成 ${target.shotCode} 的真实黑白故事板图…`;
    setBusy(true);
    setActiveImageVersionId(target.version.id);
    setBusyMessage(message);
    setError(null);
    setImageActionErrors((current) => ({
      ...current,
      [target.version.id]: "",
    }));
    submitRealImageTask(
      target.version,
      target.correctionNote ?? "",
      target.promptOverride ?? "",
    )
      .then((nextWorkspace) => {
        setWorkspace(nextWorkspace);
        setActionMessage(
          "任务已经提交。后台会持续查询，完成后自动保存到项目；可以放心切换页面。",
        );
      })
      .catch((nextError: Error) => {
        const errorMessage = nextError.message || "故事板图片生成失败。";
        setError(errorMessage);
        setImageActionErrors((current) => ({
          ...current,
          [target.version.id]: errorMessage,
        }));
      })
      .finally(() => {
        setBusy(false);
        setActiveImageVersionId("");
        setBusyMessage("");
      });
  }

  function localPathHint(assetUrl: string): string {
    const match = assetUrl.match(/\/api\/projects\/([^/]+)\/assets\/(.+)$/);
    if (!match) return assetUrl;
    return `data/projects/${match[1]}/${decodeURIComponent(match[2])}`;
  }

  async function downloadWithHint(assetUrl: string, fallbackName: string) {
    const hint = localPathHint(assetUrl);
    try {
      const result = await downloadLocalAsset(assetUrl, fallbackName);
      setDownloadHint(
        result.method === "save_picker"
          ? `已保存到你选择的位置：${result.filename}。项目本地也保留一份：${hint}`
          : `已交给浏览器下载。如果没有弹出下载窗口，文件也已保存在本机：${hint}`,
      );
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "下载失败，请稍后再试。";
      if (message.includes("已取消保存")) {
        setDownloadHint(`${message} 本地备份位置：${hint}`);
        return;
      }
      throw error;
    }
  }

  function exportPromptPack() {
    if (!scene) return;
    setBusy(true);
    setBusyMessage("正在导出故事板资料包…");
    setError(null);
    exportPromptStoryboardPack(scene.id)
      .then(async (result) => {
        setExportResult(result);
        await downloadWithHint(
          result.zip_url,
          `${result.scope_code}_提示词_故事板.zip`,
        );
      })
      .catch((nextError: Error) => setError(nextError.message))
      .finally(() => {
        setBusy(false);
        setBusyMessage("");
      });
  }

  if (!activeProject) {
    return (
      <div className={workbenchPageClass}>
        <p className="text-xs tracking-[0.18em] text-orange-400">V7｜故事板</p>
        <h1 className="mt-2 text-4xl font-semibold text-zinc-100">
          把每个镜头画成故事板
        </h1>
        <section className="mt-7 border border-white/15 bg-[#151b21]/85 p-7 text-sm text-zinc-400">
          请先在“开始 / 规划”创建并打开一个项目。
        </section>
      </div>
    );
  }

  const latestPage = scene?.execution_pages[0];
  const nextStep = storyboardNextStep(scene);
  const stats = sceneStoryboardStats(scene);
  const firstMissingShot = scene?.shots.find(
    (shot) => !latestStoryboardVersion(shot),
  );
  const firstNeedsConfirmShot = scene?.shots.find(
    (shot) => latestStoryboardVersion(shot)?.status === "draft",
  );
  const firstReusableShot = stats.reusableShots[0];
  const reuseReviewShots =
    scene?.shots.filter((shot) => shot.reuse_assessment) ?? [];
  const firstNeedsRealImageShot = scene?.shots.find((shot) => {
    const version = latestConfirmedStoryboardVersion(shot);
    return Boolean(version && !isRealStoryboardImage(version));
  });
  const firstNeedsRealImageVersion = firstNeedsRealImageShot
    ? latestConfirmedStoryboardVersion(firstNeedsRealImageShot)
    : undefined;
  const firstPendingRealImageJob = scene?.shots
    .map(latestConfirmedStoryboardVersion)
    .map((version) => version?.latest_image_job)
    .find((job) => job && ["submitted", "processing"].includes(job.status));
  const firstCompletedRealImageJob = scene?.shots
    .map(latestConfirmedStoryboardVersion)
    .map((version) => version?.latest_image_job)
    .find((job) => job && job.status === "completed" && job.remote_result_url);
  const sceneImageJobs = (scene?.shots ?? []).flatMap((shot) => {
    const version = latestStoryboardVersion(shot);
    return version?.latest_image_job
      ? [{ shotCode: shot.shot_code, job: version.latest_image_job }]
      : [];
  });
  const activeSceneImageJobs = sceneImageJobs.filter(
    ({ job }) =>
      activeImageJobStatuses.has(job.status) || job.status === "completed",
  );
  const failedSceneImageJobs = sceneImageJobs.filter(
    ({ job }) => job.status === "failed" || job.status === "cancelled",
  );
  const primaryCard = {
    title: nextStep.title.replace("现在只做一件事：", ""),
    detail: nextStep.detail,
  };
  const stageItems: DirectorStageItem[] = [
    {
      title: "分镜提示词",
      detail: firstShot ? "已读取镜头提示词" : "先去分镜提示词页",
      status: firstShot ? "done" : "blocked",
    },
    {
      title: "黑白草稿",
      detail: `${stats.total - stats.missing}/${stats.total} 已生成`,
      status: stats.missing > 0 ? "current" : "done",
    },
    {
      title: "确认镜头拆分",
      detail:
        stats.drafts > 0
          ? `${stats.drafts} 个待确认`
          : `${stats.confirmed}/${stats.total} 已确认`,
      status:
        stats.drafts > 0 ? "current" : stats.complete ? "done" : "pending",
    },
    {
      title: "真实图片",
      detail: `${stats.realImages}/${stats.total} 已下载`,
      status:
        stats.confirmedWithoutRealImages.length > 0
          ? "current"
          : stats.total > 0 && stats.realImages === stats.total
            ? "done"
            : "pending",
    },
    {
      title: "导出故事板包",
      detail: latestPage ? "总览已生成，可下载" : "真实图完成后再导出",
      status:
        stats.total > 0 && stats.realImages === stats.total
          ? latestPage
            ? "done"
            : "current"
          : "pending",
    },
  ];

  return (
    <div className={workbenchPageClass}>
      {busy ? (
        <GuideProgressToast label={busyMessage || "正在处理故事板，请稍等…"} />
      ) : null}
      {previewImage ? (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/85 px-8 py-8 backdrop-blur-sm"
          role="dialog"
          aria-modal="true"
          aria-label={`${previewImage.shotCode} 故事板大图预览`}
          onClick={() => setPreviewImage(null)}
        >
          <div
            className="flex max-h-[92vh] w-full max-w-6xl flex-col border border-orange-400/40 bg-[#11171c] shadow-2xl shadow-black/60"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="flex items-center justify-between border-b border-white/10 px-5 py-4">
              <div>
                <p className="text-xs tracking-[0.18em] text-orange-300">
                  {previewImage.isRealImage ||
                  isRealStoryboardImage(previewImage.version)
                    ? "AI 故事板预览"
                    : "镜头结构图预览 · 非 AI 图片"}
                </p>
                <h2 className="mt-1 text-xl font-semibold text-zinc-100">
                  {previewImage.shotCode}｜{previewImage.shotName}
                </h2>
                {!previewImage.isRealImage &&
                !isRealStoryboardImage(previewImage.version) ? (
                  <p className="mt-1 text-xs text-zinc-400">
                    仅用于检查镜头拆分、时间段和方向，不作为最终故事板。
                  </p>
                ) : null}
              </div>
              <div className="flex items-center gap-2">
                <button
                  className={buttonClass}
                  type="button"
                  onClick={() =>
                    void downloadWithHint(
                      previewImage.assetUrl,
                      `${previewImage.shotCode}_故事板.png`,
                    )
                  }
                >
                  <Download size={15} />
                  {previewImage.isRealImage ||
                  isRealStoryboardImage(previewImage.version)
                    ? "下载图片"
                    : "下载结构图"}
                </button>
                <button
                  className={buttonClass}
                  type="button"
                  onClick={() => setPreviewImage(null)}
                >
                  <X size={15} />
                  关闭
                </button>
              </div>
            </div>
            <div className="overflow-auto bg-[#0b0f12] p-4">
              <img
                src={previewImage.url}
                alt={`${previewImage.shotCode} 故事板大图`}
                className="mx-auto max-h-[76vh] w-auto max-w-full object-contain"
              />
            </div>
          </div>
        </div>
      ) : null}
      {imageConfirm ? (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 px-8 py-8 backdrop-blur-sm"
          role="dialog"
          aria-modal="true"
          aria-label="确认生成真实故事板图片"
        >
          <div className="w-full max-w-2xl rounded-[28px] border border-orange-300/40 bg-[#17120d] p-7 shadow-2xl shadow-black/70">
            <p className="text-xs font-semibold tracking-[0.18em] text-orange-300">
              需要你确认
            </p>
            <h2 className="mt-3 text-3xl font-semibold text-zinc-100">
              {imageConfirm.mode === "regenerate"
                ? "按修改要求重新生成"
                : "生成"}{" "}
              {imageConfirm.shotCode} 真实黑白故事板图
            </h2>
            <p className="mt-4 text-sm leading-6 text-zinc-300">
              这一步会向已配置的图片服务发送 1
              次真实请求。不会生成视频，也不会批量提交；完成后会自动下载到当前项目。
            </p>
            {imageConfirm.promptOverride ? (
              <details
                className="mt-5 border border-cyan-300/25 bg-cyan-300/7 p-4 text-sm leading-6 text-cyan-50"
                open
              >
                <summary className="cursor-pointer font-semibold text-cyan-100">
                  本次会使用你修改后的完整提示词
                </summary>
                <pre className="mt-3 max-h-48 overflow-auto whitespace-pre-wrap text-xs leading-5 text-cyan-50/85">
                  {imageConfirm.promptOverride}
                </pre>
              </details>
            ) : imageConfirm.correctionNote ? (
              <div className="mt-5 border border-amber-300/35 bg-amber-300/8 p-4 text-sm leading-6 text-amber-50">
                <p className="font-semibold text-amber-200">本次修改要求</p>
                <p className="mt-2 whitespace-pre-wrap">
                  {imageConfirm.correctionNote}
                </p>
              </div>
            ) : null}
            <div className="mt-5 grid gap-3 border border-white/10 bg-black/15 p-4 text-sm text-zinc-300">
              <p>服务：{imageConfirm.readiness.provider_name}</p>
              <p>模型：{imageConfirm.readiness.model_id}</p>
              <p>范围：仅当前镜头 {imageConfirm.shotCode} 的一张黑白故事板图</p>
              <p>{imageConfirm.readiness.risk_notice}</p>
            </div>
            <div className="mt-6 flex justify-end gap-3">
              <button
                className={buttonClass}
                type="button"
                onClick={() => setImageConfirm(null)}
              >
                取消
              </button>
              <GuidePrimaryButton
                onClick={confirmRealImageGeneration}
                pulse={false}
              >
                {imageConfirm.mode === "regenerate"
                  ? "确认重新生成"
                  : "确认生成这一张"}
              </GuidePrimaryButton>
            </div>
          </div>
        </div>
      ) : null}
      <div className="mb-5 flex items-end justify-between gap-6">
        <div>
          <p className="text-xs tracking-[0.18em] text-orange-400">
            V7｜故事板
          </p>
          <h1 className="mt-2 max-w-4xl text-4xl font-semibold leading-tight tracking-[-0.04em] text-zinc-100">
            把分镜提示词变成黑白故事板
          </h1>
          <p className="mt-4 max-w-3xl text-base leading-7 text-zinc-400">
            {activeProject.project_code}｜{activeProject.name}
            。先确认镜头拆分和时间段，再逐张生成真实 AI
            故事板图；全部完成后才能导出正式故事板包。
          </p>
        </div>
        <select
          aria-label="选择故事板场景"
          value={scene?.id ?? ""}
          onChange={(event) => setSceneId(event.target.value)}
          className={`${inputClass} w-[280px]`}
        >
          {workspace?.scenes.map((item) => (
            <option key={item.id} value={item.id}>
              {item.scope_code}｜{item.name}
            </option>
          ))}
        </select>
      </div>

      <DirectorWorkbenchFrame
        main={
          <GuideActionCard
            eyebrow={
              stats.complete && stats.realImages === stats.total
                ? "本场已完成"
                : "当前主任务"
            }
            title={primaryCard.title}
            description={primaryCard.detail}
            tone={nextStep.tone === "done" ? "done" : "current"}
            progressLabel={
              busy ? busyMessage || "正在处理故事板，请稍等…" : undefined
            }
          >
            {firstMissingShot && scene ? (
              <GuidePrimaryButton
                loading={busy}
                loadingLabel={`正在生成 ${stats.missing} 张草稿…`}
                onClick={() =>
                  run(
                    () => generateMissingSceneStoryboards(scene),
                    `正在生成本场 ${stats.missing} 张故事板草稿…`,
                  )
                }
              >
                一次生成本场故事板草稿
              </GuidePrimaryButton>
            ) : firstNeedsConfirmShot && scene ? (
              <GuidePrimaryButton
                loading={busy}
                loadingLabel={`正在确认 ${stats.drafts} 张草稿…`}
                onClick={() =>
                  run(
                    () => confirmSceneStoryboards(scene),
                    `正在确认本场 ${stats.drafts} 张故事板草稿…`,
                  )
                }
              >
                确认本场镜头拆分
              </GuidePrimaryButton>
            ) : firstCompletedRealImageJob ? (
              <GuidePrimaryButton
                loading={busy}
                loadingLabel="正在下载真实图片…"
                onClick={() =>
                  run(
                    () =>
                      downloadStoryboardImage(firstCompletedRealImageJob.id),
                    "真实图片已完成，正在下载到项目…",
                  )
                }
              >
                下载已完成的真实图片
              </GuidePrimaryButton>
            ) : firstPendingRealImageJob ? (
              <GuidePrimaryButton
                loading={busy}
                loadingLabel="正在查询真实图片…"
                onClick={() =>
                  run(
                    () => pollAndDownloadRealImage(firstPendingRealImageJob.id),
                    "正在查询真实故事板图片…",
                  )
                }
              >
                查询并下载真实图片
              </GuidePrimaryButton>
            ) : firstReusableShot ? (
              <GuidePrimaryButton href="#storyboard-reuse-review">
                查看并处理可沿用旧图
              </GuidePrimaryButton>
            ) : firstNeedsRealImageShot && firstNeedsRealImageVersion ? (
              <GuidePrimaryButton
                loading={busy}
                loadingLabel="正在检查真实生图条件…"
                onClick={() =>
                  void prepareRealImageGeneration(
                    firstNeedsRealImageVersion,
                    firstNeedsRealImageShot.shot_code,
                  )
                }
              >
                生成下一张真实故事板图
              </GuidePrimaryButton>
            ) : scene && !latestPage ? (
              <GuidePrimaryButton
                loading={busy}
                loadingLabel="正在生成故事板总览…"
                onClick={() =>
                  run(
                    () => createStoryboardOverview(scene),
                    "正在生成故事板总览图…",
                  )
                }
              >
                生成故事板总览
              </GuidePrimaryButton>
            ) : scene ? (
              <GuidePrimaryButton
                loading={busy}
                loadingLabel="正在导出故事板包…"
                onClick={exportPromptPack}
              >
                下载故事板包
              </GuidePrimaryButton>
            ) : null}
            {scene ? (
              <p className="mt-4 text-sm text-zinc-400">
                本场进度：{stats.confirmed}/{stats.total} 个镜头拆分已确认
                {stats.missing > 0 ? `，还缺 ${stats.missing} 张草稿` : ""}
                {stats.drafts > 0 ? `，${stats.drafts} 张待确认` : ""}
                {stats.confirmedWithoutRealImages.length > 0
                  ? `，${stats.confirmedWithoutRealImages.length} 张还不是 AI 真实图片`
                  : ""}
              </p>
            ) : null}
          </GuideActionCard>
        }
        aside={
          <div className="space-y-4">
            <DirectorStatusPanel
              title="故事板生成状态"
              description="先确认镜头拆分与时间段，再逐张生成真实 AI 故事板图片。"
              items={stageItems}
            />
          </div>
        }
      />
      {actionMessage ? (
        <p className="mt-4 border border-emerald-400/25 bg-emerald-400/7 px-4 py-3 text-sm text-emerald-100">
          {actionMessage}
        </p>
      ) : null}

      {creativeGoal === "prompt_storyboard" ? (
        <section className="mt-4 border border-sky-400/30 bg-sky-400/6 px-4 py-3 text-sm leading-6 text-sky-100">
          <div className="flex items-center justify-between gap-4">
            <p>
              当前目标是“提示词 + 故事板”。所有镜头的真实 AI
              故事板图片生成完成后，你就已经拿到这轮需要的核心产出；后面的成片提示词、批量视频和视频提交都可以先不做。
            </p>
            <span className="shrink-0 border border-sky-300/35 px-3 py-2 text-xs text-sky-100/80">
              下载按钮在完成后会成为本页主按钮
            </span>
          </div>
          {exportResult ? (
            <p className="mt-3 text-xs text-sky-100/80">
              已导出 {exportResult.shot_count} 个镜头：
              <button
                className="ml-2 underline decoration-sky-300/60 underline-offset-4"
                type="button"
                onClick={() =>
                  void downloadWithHint(
                    exportResult.zip_url,
                    `${exportResult.scope_code}_提示词_故事板.zip`,
                  )
                }
              >
                下载提示词 + 故事板 ZIP
              </button>
            </p>
          ) : (
            <p className="mt-3 text-xs text-sky-100/70">
              包内包含每个镜头的可复制分镜提示词、导演结构
              JSON、故事板图片和复制卡片。
            </p>
          )}
        </section>
      ) : null}

      {error && (
        <p className="mt-4 border-l-2 border-red-400 bg-red-400/8 px-4 py-3 text-sm text-red-200">
          {humanizeCopy(error)}
          {error.includes("无法连接后端服务") ? (
            <span className="ml-3 text-red-100/80">
              这不是故事板内容问题，是本地后端没有连上。
            </span>
          ) : null}
          {error.includes("导演草案") ? (
            <a
              className="ml-3 text-orange-200 underline decoration-orange-400/60 underline-offset-4"
              href="/video-package"
            >
              去分镜提示词页生成参考提示词
            </a>
          ) : null}
        </p>
      )}

      <section
        aria-label="故事板图片生成状态"
        className="mt-5 border border-cyan-300/25 bg-[#0d1a20] p-5"
      >
        <div className="flex items-start justify-between gap-6">
          <div>
            <p className="text-xs font-semibold tracking-[.16em] text-cyan-300">
              后台任务监控
            </p>
            <h2 className="mt-2 text-xl font-semibold text-zinc-100">
              故事板图片生成状态
            </h2>
            <p className="mt-2 text-sm leading-6 text-zinc-400">
              页面每 3
              秒同步一次本地后台状态。切换菜单不会停止任务；服务商未返回真实百分比时，只展示可核验的处理阶段。
            </p>
          </div>
          <span className="inline-flex shrink-0 items-center gap-2 border border-white/12 px-3 py-2 text-xs text-zinc-400">
            <RefreshCw
              size={14}
              className={
                activeSceneImageJobs.length > 0
                  ? "animate-spin text-cyan-300"
                  : "text-emerald-300"
              }
            />
            {imageLastSyncedAt
              ? `最近同步 ${imageLastSyncedAt}`
              : "等待首次同步"}
          </span>
        </div>
        <div className="mt-4 grid grid-cols-3 gap-3">
          <div className="border border-white/10 bg-black/15 px-4 py-3">
            <p className="text-xs text-zinc-500">后台处理中</p>
            <p className="mt-1 text-lg font-semibold text-cyan-200">
              {activeSceneImageJobs.length} 张
            </p>
          </div>
          <div className="border border-white/10 bg-black/15 px-4 py-3">
            <p className="text-xs text-zinc-500">已保存真实图片</p>
            <p className="mt-1 text-lg font-semibold text-emerald-200">
              {stats.realImages}/{stats.total} 张
            </p>
          </div>
          <div className="border border-white/10 bg-black/15 px-4 py-3">
            <p className="text-xs text-zinc-500">需要处理</p>
            <p
              className={`mt-1 text-lg font-semibold ${failedSceneImageJobs.length > 0 ? "text-red-200" : "text-zinc-300"}`}
            >
              {failedSceneImageJobs.length} 张
            </p>
          </div>
        </div>
        {activeSceneImageJobs.length > 0 || failedSceneImageJobs.length > 0 ? (
          <div className="mt-4 space-y-3">
            {[...activeSceneImageJobs, ...failedSceneImageJobs].map(
              ({ shotCode, job }) => {
                const currentStage = imageJobStage(job.status);
                const failed =
                  job.status === "failed" || job.status === "cancelled";
                return (
                  <article
                    key={job.id}
                    className={`border px-4 py-3 ${failed ? "border-red-400/35 bg-red-400/7" : "border-cyan-300/25 bg-cyan-300/[0.04]"}`}
                  >
                    <div className="flex items-center justify-between gap-4">
                      <p className="text-sm font-semibold text-zinc-100">
                        {shotCode}｜{imageJobStatusText(job.status)}
                      </p>
                      <span className="text-xs text-zinc-500">
                        任务 {job.external_task_id || job.id}
                      </span>
                    </div>
                    {!failed ? (
                      <div
                        className="mt-3 grid grid-cols-4 gap-2"
                        aria-label={`${shotCode} 生成阶段`}
                      >
                        {["已提交", "生成中", "服务完成", "保存本地"].map(
                          (label, index) => (
                            <div
                              key={label}
                              className={`border px-2 py-2 text-center text-[11px] ${currentStage >= index + 1 ? "border-cyan-300/45 bg-cyan-300/12 text-cyan-100" : "border-white/10 text-zinc-600"}`}
                            >
                              {label}
                            </div>
                          ),
                        )}
                      </div>
                    ) : (
                      <p className="mt-2 text-xs leading-5 text-red-200">
                        {job.error_message ||
                          "服务商未返回具体原因，请修改提示词后重新生成。"}
                      </p>
                    )}
                  </article>
                );
              },
            )}
          </div>
        ) : (
          <p className="mt-4 border border-emerald-400/20 bg-emerald-400/[0.05] px-4 py-3 text-sm text-emerald-100">
            当前没有正在生成的故事板图片。新任务提交后会立即出现在这里。
          </p>
        )}
      </section>

      {reuseReviewShots.length > 0 ? (
        <section
          id="storyboard-reuse-review"
          className="mt-5 scroll-mt-24 border border-orange-400/35 bg-orange-400/[0.06] p-5"
        >
          <div className="flex items-start justify-between gap-6">
            <div>
              <p className="text-xs font-semibold text-orange-300">
                重建后的旧图处理
              </p>
              <h2 className="mt-2 text-xl font-semibold text-zinc-100">
                逐张确认旧故事板图是否沿用
              </h2>
              <p className="mt-2 max-w-3xl text-sm leading-6 text-zinc-400">
                系统只比较格数、动作节点、机位和轴线，不会假装识别图片内容。兼容图可直接沿用；结构变化明显时建议重新生成，也可由你人工核对后选择仍使用原图。
              </p>
            </div>
            <span className="border border-orange-300/30 px-3 py-2 text-xs text-orange-200">
              {reuseReviewShots.length} 张待处理
            </span>
          </div>
          <div className="mt-5 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {reuseReviewShots.map((shot) => {
              const current = latestStoryboardVersion(shot);
              const assessment = shot.reuse_assessment!;
              return (
                <article
                  key={shot.id}
                  className={`border p-4 ${assessment.can_reuse ? "border-orange-300/30 bg-[#11171c]" : "border-red-400/30 bg-red-400/[0.04]"}`}
                >
                  <div className="flex items-center justify-between gap-3">
                    <b className="text-sm text-zinc-100">
                      {shot.shot_code}｜{shot.name}
                    </b>
                    <span
                      className={`text-xs font-semibold ${assessment.can_reuse ? "text-orange-200" : "text-red-200"}`}
                    >
                      {assessment.recommendation === "reuse"
                        ? "建议沿用"
                        : assessment.recommendation === "review"
                          ? "人工判断"
                          : "必须重生成"}
                    </span>
                  </div>
                  <button
                    className="mt-3 block aspect-video w-full overflow-hidden border border-white/12 bg-black/20"
                    type="button"
                    onClick={() =>
                      current &&
                      setPreviewImage({
                        shotCode: shot.shot_code,
                        shotName: `${shot.name}（旧版真实故事板）`,
                        version: current,
                        assetUrl: assessment.source_image_url,
                        url: assetImageUrl(assessment.source_image_url),
                        isRealImage: true,
                      })
                    }
                  >
                    <img
                      className="h-full w-full object-cover grayscale"
                      src={assetImageUrl(assessment.source_image_url)}
                      alt={`${shot.shot_code} 待审核旧故事板`}
                    />
                  </button>
                  <div className="mt-3 space-y-1 text-xs leading-5 text-zinc-400">
                    {assessment.reasons.map((reason) => (
                      <p key={reason}>· {reason}</p>
                    ))}
                    <p>
                      旧时间段：
                      {assessment.old_time_ranges.join(" / ") || "未记录"}
                    </p>
                    <p>
                      新时间段：
                      {assessment.new_time_ranges.join(" / ") || "未记录"}
                    </p>
                  </div>
                  {assessment.can_reuse && current ? (
                    <button
                      className="mt-4 border border-orange-300/55 bg-orange-500 px-3 py-2 text-xs font-semibold text-black transition hover:bg-orange-400 disabled:opacity-40"
                      type="button"
                      disabled={busy || !isStoryboardConfirmed(current)}
                      onClick={() => void confirmReuseStoryboard(shot, current)}
                    >
                      {isStoryboardConfirmed(current)
                        ? "沿用旧图并绑定新时间轴"
                        : "先确认新镜头结构"}
                    </button>
                  ) : (
                    <div className="mt-4 space-y-3">
                      <p className="border-l-2 border-red-400 pl-3 text-xs leading-5 text-red-200">
                        新旧结构不兼容，系统建议重新生成。确认原图仍符合创作意图时，可以人工覆盖并绑定新时间轴。
                      </p>
                      <button
                        className="border border-red-300/55 bg-red-400/10 px-3 py-2 text-xs font-semibold text-red-100 transition hover:bg-red-400/18 disabled:opacity-40"
                        type="button"
                        disabled={
                          busy || !current || !isStoryboardConfirmed(current)
                        }
                        onClick={() =>
                          current &&
                          void confirmReuseStoryboard(shot, current, true)
                        }
                      >
                        {current && isStoryboardConfirmed(current)
                          ? "仍使用原图"
                          : "先确认新镜头结构"}
                      </button>
                    </div>
                  )}
                </article>
              );
            })}
          </div>
        </section>
      ) : null}

      <section aria-labelledby="storyboard-details-title" className="mt-5">
        <header className="mb-4 border-l-2 border-orange-400 bg-orange-400/[0.05] px-5 py-4">
          <div className="flex items-start justify-between gap-6">
            <div>
              <p className="text-xs font-semibold tracking-[.16em] text-orange-300">
                核心检查区
              </p>
              <h2
                id="storyboard-details-title"
                className="mt-2 text-2xl font-semibold text-zinc-100"
              >
                逐镜故事板详情
              </h2>
              <p className="mt-2 max-w-4xl text-sm leading-6 text-zinc-400">
                逐张检查画面、镜头格数、对应时间段、轴线连续性和生成提示词。对象或构图不正确时，可直接修改该镜头提示词并重新生成。
              </p>
            </div>
            <span className="shrink-0 border border-orange-300/30 px-3 py-2 text-xs text-orange-200">
              {scene?.shots.length ?? 0} 个镜头
            </span>
          </div>
        </header>
        <div className="space-y-5">
          <details className="border border-white/15 bg-[#151b21]/85 p-5">
            <summary className="flex cursor-pointer items-center gap-2 text-base font-semibold text-zinc-100">
              <Axis3D size={18} className="text-orange-400" />
              镜头方向规则（一般不用改）
            </summary>
            <div className="flex items-center gap-2">
              <h2 className="mt-4 text-base font-semibold text-zinc-100">
                镜头方向规则
              </h2>
            </div>
            <p className="mt-2 text-xs leading-5 text-zinc-500">
              同一场连续镜头要保持人物站位、视线和运动方向一致。需要换方向时，请写清楚怎么过渡。
            </p>
            {axisDraft && scene && (
              <div className="mt-4 space-y-3">
                <label className="block text-xs text-zinc-500">
                  规则编号
                  <input
                    className={`${inputClass} mt-1`}
                    disabled
                    value={axisDraft.axis_code}
                  />
                </label>
                <label className="block text-xs text-zinc-500">
                  主要空间关系
                  <input
                    className={`${inputClass} mt-1`}
                    value={axisDraft.axis_line_description}
                    onChange={(event) =>
                      setAxisDraft({
                        ...axisDraft,
                        axis_line_description: event.target.value,
                      })
                    }
                  />
                </label>
                <label className="block text-xs text-zinc-500">
                  摄影机主要站在哪一侧
                  <select
                    className={`${inputClass} mt-1`}
                    value={axisDraft.camera_safe_side}
                    onChange={(event) =>
                      setAxisDraft({
                        ...axisDraft,
                        camera_safe_side: event.target.value,
                      })
                    }
                  >
                    <option>A侧</option>
                    <option>B侧</option>
                  </select>
                </label>
                <label className="block text-xs text-zinc-500">
                  人物站位
                  <textarea
                    className={`${inputClass} mt-1 min-h-16`}
                    value={axisDraft.character_blocking}
                    onChange={(event) =>
                      setAxisDraft({
                        ...axisDraft,
                        character_blocking: event.target.value,
                      })
                    }
                  />
                </label>
                <label className="block text-xs text-zinc-500">
                  视线方向
                  <input
                    className={`${inputClass} mt-1`}
                    value={axisDraft.eyeline_direction}
                    onChange={(event) =>
                      setAxisDraft({
                        ...axisDraft,
                        eyeline_direction: event.target.value,
                      })
                    }
                  />
                </label>
                <label className="block text-xs text-zinc-500">
                  运动方向
                  <select
                    className={`${inputClass} mt-1`}
                    value={axisDraft.movement_direction}
                    onChange={(event) =>
                      setAxisDraft({
                        ...axisDraft,
                        movement_direction: event.target.value,
                      })
                    }
                  >
                    <option>从左向右</option>
                    <option>从右向左</option>
                    <option>静止</option>
                  </select>
                </label>
                <label className="flex items-center gap-2 text-xs text-zinc-400">
                  <input
                    type="checkbox"
                    checked={axisDraft.allow_cross_axis}
                    onChange={(event) =>
                      setAxisDraft({
                        ...axisDraft,
                        allow_cross_axis: event.target.checked,
                      })
                    }
                  />
                  允许镜头换方向
                </label>
                <label className="block text-xs text-zinc-500">
                  换方向的过渡说明
                  <textarea
                    className={`${inputClass} mt-1 min-h-16`}
                    value={axisDraft.cross_axis_transition}
                    onChange={(event) =>
                      setAxisDraft({
                        ...axisDraft,
                        cross_axis_transition: event.target.value,
                      })
                    }
                  />
                </label>
                <button
                  className={buttonClass}
                  disabled={busy}
                  onClick={() => run(() => saveAxisPlan(scene.id, axisDraft))}
                  type="button"
                >
                  <Save size={15} />
                  保存轴线计划
                </button>
              </div>
            )}
          </details>

          <section className="border border-white/15 bg-[#151b21]/85 p-5">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-base font-semibold text-zinc-100">
                  逐镜故事板
                </h2>
                <p className="mt-1 text-xs text-zinc-500">
                  这里保留每个镜头的草稿、格数和时间段。正常创作只用上方主按钮即可。
                </p>
              </div>
              <span className="text-xs text-zinc-500">
                {scene?.shots.length ?? 0} 个镜头
              </span>
            </div>
            <div className="mt-4 grid grid-cols-3 gap-4">
              {scene?.shots.map((shot) => {
                const current = latestStoryboardVersion(shot);
                const hasDisplayImage = Boolean(current?.image_url);
                const hasRealImage = isRealStoryboardImage(current);
                const promptText = current
                  ? (imagePromptDrafts[current.id] ??
                    current.latest_image_job?.prompt ??
                    "")
                  : "";
                const promptIsLoading = current
                  ? Boolean(imagePromptLoading[current.id])
                  : false;
                const imageJob = current?.latest_image_job;
                const imageJobActive = Boolean(
                  imageJob && activeImageJobStatuses.has(imageJob.status),
                );
                const imageJobCompleted = Boolean(
                  imageJob?.status === "completed" &&
                  imageJob.remote_result_url,
                );
                const imageActionError = current
                  ? imageActionErrors[current.id]
                  : "";
                const isThisImageBusy = Boolean(
                  current && activeImageVersionId === current.id,
                );
                return (
                  <article
                    key={shot.id}
                    className="border border-white/12 bg-[#10161b] p-3"
                  >
                    <div className="flex items-center justify-between text-xs">
                      <b className="text-orange-300">{shot.shot_code}</b>
                      <span className="text-zinc-500">
                        {current
                          ? `V${String(current.version_number).padStart(3, "0")}`
                          : "未生成"}
                      </span>
                    </div>
                    <div className="mt-3 aspect-video border border-white/12 bg-[#0d1216]">
                      {current && hasDisplayImage && hasRealImage ? (
                        <button
                          className="group relative block h-full w-full overflow-hidden text-left"
                          type="button"
                          onClick={() =>
                            setPreviewImage({
                              shotCode: shot.shot_code,
                              shotName: shot.name,
                              version: current,
                              assetUrl: current.image_url,
                              url: assetImageUrl(current.image_url),
                            })
                          }
                        >
                          <img
                            src={assetImageUrl(current.image_url)}
                            alt={`${shot.shot_code} 黑白故事板`}
                            className="h-full w-full object-cover grayscale transition duration-200 group-hover:scale-[1.02] group-hover:brightness-110"
                          />
                          <span className="absolute inset-x-0 bottom-0 bg-black/70 px-3 py-2 text-xs text-zinc-100 opacity-0 transition group-hover:opacity-100">
                            点击放大查看
                          </span>
                          <span className="absolute left-2 top-2 border border-emerald-300/50 bg-black/70 px-2 py-1 text-[10px] text-emerald-100">
                            AI 真实图片
                          </span>
                        </button>
                      ) : current && hasDisplayImage ? (
                        <button
                          className="flex h-full w-full flex-col items-center justify-center px-6 text-center transition hover:bg-white/[0.03]"
                          type="button"
                          onClick={() =>
                            setPreviewImage({
                              shotCode: shot.shot_code,
                              shotName: shot.name,
                              version: current,
                              assetUrl: current.image_url,
                              url: assetImageUrl(current.image_url),
                            })
                          }
                        >
                          <Axis3D size={28} className="text-orange-300" />
                          <span className="mt-3 text-sm font-semibold text-zinc-100">
                            镜头结构与时间轴草稿
                          </span>
                          <span className="mt-1 text-xs text-orange-200">
                            {current.storyboard_grid} 格 · 非 AI 图片
                          </span>
                          <span className="mt-2 text-[11px] leading-5 text-zinc-500">
                            只用于检查拆分和方向，不作为最终故事板
                          </span>
                          <span className="mt-2 text-[11px] text-zinc-400 underline underline-offset-4">
                            查看结构图
                          </span>
                        </button>
                      ) : current ? (
                        <div className="flex h-full flex-col items-center justify-center px-5 text-center text-xs leading-5 text-zinc-500">
                          <span className="text-orange-300">
                            故事板任务已经建立
                          </span>
                          <span className="mt-2">
                            这里已有黑白故事板草稿，可以先确认。更精细的 AI
                            图片可以后面再做。
                          </span>
                        </div>
                      ) : (
                        <div className="flex h-full items-center justify-center text-xs text-zinc-600">
                          等待故事板任务
                        </div>
                      )}
                    </div>
                    <p className="mt-3 truncate text-sm text-zinc-200">
                      {shot.name}
                    </p>
                    {current && (
                      <div className="mt-3 space-y-1 text-xs">
                        <p className="text-orange-300">
                          故事板格数：{current.storyboard_grid} 格
                        </p>
                        <p className="leading-5 text-zinc-500">
                          为什么这么分：{humanizeCopy(current.grid_reason)}
                        </p>
                        <p className="leading-5 text-zinc-500">
                          对应视频时间段：
                          {current.prompt_match
                            .map((item) => item.time_range)
                            .join(" / ")}
                        </p>
                        <p
                          className={
                            current.style_validation_status === "passed"
                              ? "text-emerald-300"
                              : "text-red-300"
                          }
                        >
                          画风检查{" "}
                          {current.style_validation_status === "passed"
                            ? "通过"
                            : "未通过"}
                        </p>
                        <p
                          className={
                            current.axis_validation_status === "passed"
                              ? "text-emerald-300"
                              : "text-red-300"
                          }
                        >
                          方向连续检查{" "}
                          {current.axis_validation_status === "passed"
                            ? "通过"
                            : "未通过"}
                        </p>
                      </div>
                    )}
                    {current ? (
                      <div className="mt-3">
                        {isStoryboardConfirmed(current) ? (
                          <span className="inline-flex border border-emerald-400/30 bg-emerald-400/8 px-3 py-2 text-xs font-semibold text-emerald-200">
                            {hasRealImage
                              ? "AI 故事板已确认"
                              : "镜头拆分已确认"}
                          </span>
                        ) : (
                          <button
                            className="border border-emerald-400/45 bg-emerald-400/8 px-3 py-2 text-xs font-semibold text-emerald-100 transition hover:bg-emerald-400/15 disabled:opacity-45"
                            type="button"
                            disabled={busy}
                            onClick={() =>
                              run(
                                () =>
                                  transitionStoryboardVersion(
                                    current.id,
                                    "confirm",
                                  ),
                                `正在确认 ${shot.shot_code} 故事板…`,
                              )
                            }
                          >
                            确认结构与时间段
                          </button>
                        )}
                      </div>
                    ) : null}
                    <p className="mt-3 border border-white/10 bg-black/10 px-3 py-2 text-xs leading-5 text-zinc-500">
                      {hasRealImage
                        ? "这张已经是真实 AI 图片；如果对象画错了，直接改下面的提示词重新生成，旧图会保留。"
                        : "这不是故事板图片，只是镜头拆分和方向示意。确认结构后，使用页面上方主按钮生成真实 AI 故事板图。"}
                    </p>
                    {current && (
                      <div className="mt-3 border border-cyan-300/18 bg-cyan-300/[0.04] p-3">
                        <label className="block text-xs font-semibold text-cyan-100">
                          本张生成提示词（可直接修改）
                          <textarea
                            className={`${inputClass} mt-2 min-h-40 resize-y text-xs leading-5`}
                            value={promptText}
                            onChange={(event) =>
                              setImagePromptDrafts((drafts) => ({
                                ...drafts,
                                [current.id]: event.target.value,
                              }))
                            }
                            placeholder={
                              promptIsLoading
                                ? "正在读取这张图的生成提示词…"
                                : "这里会显示生成这张故事板用的完整提示词。"
                            }
                          />
                        </label>
                        <p className="mt-2 text-[11px] leading-5 text-zinc-500">
                          例：把“汽车”改成“越野摩托车”，并补一句“不要汽车，轮胎和车把必须清楚”。
                        </p>
                        {imageJob && imageJob.status !== "downloaded" ? (
                          <div
                            className={`mt-3 border px-3 py-2 text-xs leading-5 ${
                              imageJob.status === "failed" ||
                              imageJob.status === "cancelled"
                                ? "border-red-400/35 bg-red-400/8 text-red-200"
                                : "border-cyan-300/30 bg-cyan-300/7 text-cyan-100"
                            }`}
                            role="status"
                          >
                            <p className="font-semibold">
                              {imageJobStatusText(imageJob.status)}
                            </p>
                            <p className="mt-1 text-[11px] opacity-75">
                              {imageJob.error_message ||
                                (imageJobActive
                                  ? "可以切换到其他页面，后台任务不会停止。"
                                  : "系统会自动保存完成结果。")}
                            </p>
                          </div>
                        ) : null}
                        {imageActionError ? (
                          <p
                            className="mt-3 border border-red-400/35 bg-red-400/8 px-3 py-2 text-xs leading-5 text-red-200"
                            role="alert"
                          >
                            {humanizeCopy(imageActionError)}
                          </p>
                        ) : null}
                        <div className="mt-3 flex flex-wrap gap-2">
                          {imageJobActive || imageJobCompleted ? (
                            <button
                              className={buttonClass}
                              type="button"
                              disabled={busy}
                              onClick={() =>
                                void prepareRealImageGeneration(
                                  current,
                                  shot.shot_code,
                                  "",
                                  hasRealImage ? "regenerate" : "generate",
                                  promptText,
                                )
                              }
                            >
                              {imageJobCompleted
                                ? "保存已完成图片"
                                : "立即查询生成进度"}
                            </button>
                          ) : (
                            <button
                              className={buttonClass}
                              type="button"
                              disabled={!promptText.trim() || busy}
                              onClick={() =>
                                void prepareRealImageGeneration(
                                  current,
                                  shot.shot_code,
                                  "",
                                  hasRealImage ? "regenerate" : "generate",
                                  promptText,
                                )
                              }
                            >
                              {isThisImageBusy
                                ? "正在检查生成条件…"
                                : hasRealImage
                                  ? "用这段提示词重新生成"
                                  : "用这段提示词生成真实故事板"}
                            </button>
                          )}
                          {hasDisplayImage ? (
                            <button
                              className={buttonClass}
                              type="button"
                              onClick={() =>
                                void downloadWithHint(
                                  current.image_url,
                                  `${shot.shot_code}_故事板.png`,
                                )
                              }
                            >
                              <Download size={14} />
                              下载这张图
                            </button>
                          ) : null}
                        </div>
                      </div>
                    )}
                  </article>
                );
              })}
            </div>
          </section>
        </div>

        {latestPage || exportResult || downloadHint ? (
          <section className="border border-white/12 bg-[#10161b] p-4">
            <div className="flex items-center justify-between gap-4">
              <div>
                <h2 className="text-sm font-semibold text-zinc-100">
                  下载结果
                </h2>
                <p className="mt-1 text-xs text-zinc-500">
                  这里仅保留已生成文件的下载记录，不再重复展示大面积总览预览。
                </p>
              </div>
              <div className="flex shrink-0 gap-2">
                {latestPage ? (
                  <button
                    className={buttonClass}
                    type="button"
                    onClick={() =>
                      void downloadWithHint(
                        latestPage.png_url,
                        "故事板总览图.png",
                      )
                    }
                  >
                    <Download size={15} />
                    下载总览 PNG
                  </button>
                ) : null}
                {exportResult ? (
                  <button
                    className={buttonClass}
                    type="button"
                    onClick={() =>
                      void downloadWithHint(
                        exportResult.zip_url,
                        `${exportResult.scope_code}_提示词_故事板.zip`,
                      )
                    }
                  >
                    <Download size={15} />
                    下载故事板 ZIP
                  </button>
                ) : null}
              </div>
            </div>
            {downloadHint ? (
              <p className="mt-3 border border-sky-400/25 bg-sky-400/6 px-3 py-2 text-xs leading-5 text-sky-100">
                {downloadHint}
              </p>
            ) : null}
          </section>
        ) : null}
      </section>
    </div>
  );
}
