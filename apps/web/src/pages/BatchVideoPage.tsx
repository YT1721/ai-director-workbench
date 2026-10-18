import { useEffect, useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Download,
  ExternalLink,
  Eye,
  FolderOpen,
  Play,
  RefreshCw,
  RotateCcw,
  Settings2,
  Upload,
} from "lucide-react";
import { useLocation } from "react-router-dom";

import {
  assetImageUrl,
  confirmAllCompletedVideos,
  confirmAllVideoReferenceBindings,
  confirmBatchCostRisk,
  confirmVideoReferenceBindings,
  createBatchVideo,
  downloadJimengCliTask,
  downloadLiveVideoTask,
  exportJimeng,
  fetchBatchVideo,
  fetchJimengCliReadiness,
  fetchJimengCliStatus,
  fetchVideoProviderModels,
  fetchLiveReadiness,
  fetchLocalEnvStatus,
  fetchVideoTaskSupervisorStatus,
  importTaskVideo,
  launchBatchVideoJob,
  pollJimengCliTask,
  pollLiveVideoTask,
  prepareJimengCliRetry,
  prepareVideoTaskRetry,
  refreshBatchTaskPreflight,
  previewProviderRequest,
  remapBatchVideoProvider,
  reviewVideoResult,
  submitJimengCliTask,
  submitLiveVideoTask,
  updateBatchVideoSubmissionChannel,
  updateBatchVideoGenerationSettings,
  updateVideoTaskGenerationSettings,
  updateBatchJimengCliModel,
  updateLocalEnv,
  updateJimengCliModel,
  updateStructuredVideoReferenceBindings,
  updateVideoReferenceBindings,
  resetVideoReferenceBindings,
} from "../services/api";
import { useConfirmAction } from "../components/ConfirmDialog";
import { SeedanceOsPanel } from "../components/SeedanceOsPanel";
import {
  DirectorStatusPanel,
  DirectorWorkbenchFrame,
  GuideActionCard,
  GuidePrimaryButton,
  GuideProgressToast,
  TechDetails,
  type DirectorStageItem,
} from "../components/Guide";
import { useWorkbenchStore } from "../stores/useWorkbenchStore";
import { workbenchPageClass } from "../styles/layout";
import type {
  BatchTask,
  BatchJob,
  BatchWorkspace,
  JimengCliReadiness,
  JimengCliStatus,
  JimengVideoModel,
  VideoProviderModel,
  VideoGenerationSettings,
  VideoReferenceCandidate,
  VideoReferenceItemUpdate,
  LiveReadiness,
  ProviderRequestPreview,
  VideoTaskSupervisorStatus,
} from "../types/videos";
import type { LocalEnvStatus } from "../types/workflows";
import { humanizeCopy, versionStateName } from "../utils/humanCopy";

const button =
  "inline-flex items-center gap-2 border border-white/12 bg-white/[0.03] px-3 py-2 text-xs text-zinc-400 transition hover:border-orange-400/35 hover:bg-orange-400/7 hover:text-orange-200 disabled:cursor-not-allowed disabled:opacity-35";

type SubmissionChannel = "huimeng" | "jimeng" | "volcengine_seedance25";

const channelNames: Record<SubmissionChannel, string> = {
  huimeng: "慧梦 API",
  jimeng: "即梦 CLI",
  volcengine_seedance25: "火山方舟 Seedance 2.5（Mock）",
};

function submissionChannelFromProviderMode(mode?: string): SubmissionChannel {
  if (mode === "jimeng_cli") return "jimeng";
  if (mode === "volcengine_seedance25") return "volcengine_seedance25";
  return "huimeng";
}

const derivedGateLabels = new Set([
  "预算确认",
  "费用风险确认",
  "提交状态",
  "任务状态",
]);

function gateGuidance(label: string, channel: SubmissionChannel) {
  const value = label.toLowerCase();
  if (value.includes("全能参考绑定") || value.includes("参考图绑定")) {
    return {
      impact:
        "参考图用途错位会直接造成主体、场景或产品结构不准确，提交前必须核对。",
      href: "#reference-bindings",
      action: "修改参考图绑定",
    };
  }
  if (value.includes("视频服务模式")) {
    return {
      impact:
        "仅阻止慧梦 API 提交，不影响提示词或成片内容。改用即梦 CLI 时可忽略。",
      href: "",
      action: "切换到慧梦 API 模式",
    };
  }
  if (
    value.includes("api key") ||
    value.includes("服务通道") ||
    value.includes("真实视频开关")
  ) {
    return {
      impact: "只影响能否向当前 API 发出请求，不改变分镜和成片内容。",
      href: "/settings#video-service",
      action: "配置视频服务",
    };
  }
  if (value.includes("即梦 cli") || value.includes("即梦账号")) {
    return {
      impact: "只影响即梦 CLI 通道能否提交；改用慧梦 API 时可忽略。",
      href: "/settings#jimeng-cli",
      action: "查看即梦通道",
    };
  }
  if (
    value.includes("分镜提示词") ||
    value.includes("提示词") ||
    value.includes("任务缺失")
  ) {
    return {
      impact: "会直接影响镜头动作、构图、连续性和资产约束，不能忽略。",
      href: "/video-package",
      action: "补齐成片提示词",
    };
  }
  if (value.includes("镜头时长规划")) {
    return {
      impact:
        "统一 5 秒会压缩复杂动作、情绪和蒙太奇节奏，直接影响最终成片，不能忽略。",
      href: "/video-package",
      action: "去重建镜头时长",
    };
  }
  if (value.includes("规格") || value.includes("时长")) {
    return {
      impact: "规格不兼容会导致服务拒绝请求或生成结果不可用，不能忽略。",
      href: "/video-package",
      action: "调整镜头规格",
    };
  }
  if (value.includes("单镜")) {
    return {
      impact: "当前真实测试只允许一次提交 1 个镜头，避免误批量扣费。",
      href: "",
      action: "重新建立单镜队列",
    };
  }
  return {
    impact:
      channel === "huimeng"
        ? "当前项会阻止慧梦 API 提交；它不一定影响内容质量，但提交前必须处理。"
        : "当前项会阻止即梦 CLI 提交；它不一定影响内容质量，但提交前必须处理。",
    href: "/video-package",
    action: "去处理",
  };
}

function videoFailureGuidance(message: string) {
  const value = message.toLowerCase();
  if (
    value.includes("applyimageupload") ||
    value.includes("upload resource") ||
    value.includes("context deadline exceeded")
  ) {
    return {
      reason: "参考图上传到即梦时超时，云端生成任务没有成功建立。",
      impact:
        "故事板、资产绑定和提示词不需要因此修改。当前没有可查询的云端生成任务；检查网络后重新上传即可，重新提交前仍会要求费用确认。",
      href: "",
      action: "重新上传参考图",
    };
  }
  if (value.includes("final generation failed")) {
    return {
      reason:
        "即梦已接收并计费，但最终生成阶段失败；服务商没有返回更具体的失败原因。",
      impact:
        "本次没有生成可保存的视频。不要直接重复提交，否则可能再次扣除积分；建议先检查参考图和提示词，再由你确认是否重试。",
      href: "/video-package",
      action: "检查成片提示词",
    };
  }
  if (
    value.includes("401") ||
    value.includes("unauthorized") ||
    value.includes("api key") ||
    value.includes("鉴权")
  ) {
    return {
      reason: "视频服务鉴权失败，当前 Key 可能无效、过期或没有视频权限。",
      impact: "请求无法进入生成服务，不会得到成片。",
      href: "/settings#video-service",
      action: "检查视频服务配置",
    };
  }
  if (
    value.includes("credit") ||
    value.includes("balance") ||
    value.includes("积分") ||
    value.includes("余额") ||
    value.includes("额度")
  ) {
    return {
      reason: "服务商账户余额或调用额度不足。",
      impact: "任务可能未开始生成；补充额度后需要重新提交。",
      href: "/settings#video-service",
      action: "检查账户与费用",
    };
  }
  if (
    value.includes("policy") ||
    value.includes("moderation") ||
    value.includes("审核") ||
    value.includes("违规") ||
    value.includes("敏感")
  ) {
    return {
      reason: "提示词或参考素材未通过服务商内容审核。",
      impact: "当前版本无法生成，需要调整敏感描述或替换参考素材。",
      href: "/video-package",
      action: "修改成片提示词",
    };
  }
  if (
    value.includes("duration") ||
    value.includes("resolution") ||
    value.includes("ratio") ||
    value.includes("时长") ||
    value.includes("分辨率") ||
    value.includes("画幅")
  ) {
    return {
      reason: "镜头规格不在当前视频服务支持范围内。",
      impact: "服务会拒绝任务或无法返回可用视频。",
      href: "/video-package",
      action: "调整镜头规格",
    };
  }
  if (
    value.includes("download") ||
    value.includes("下载") ||
    value.includes("video url") ||
    value.includes("视频 url") ||
    value.includes("文件")
  ) {
    return {
      reason: "线上生成可能已经完成，但结果文件暂时无法下载或定位。",
      impact: "成片可能仍在线上，尚未安全保存到本地。",
      href: "",
      action: "重新查询并保存",
    };
  }
  if (
    value.includes("timeout") ||
    value.includes("timed out") ||
    value.includes("network") ||
    value.includes("connection") ||
    value.includes("查询失败") ||
    value.includes("502")
  ) {
    return {
      reason: "状态查询暂时失败，通常是网络或服务商接口波动。",
      impact: "不代表视频生成失败，也不应重复提交；先重新查询同一个任务。",
      href: "",
      action: "重新查询状态",
    };
  }
  return {
    reason: message
      ? humanizeCopy(message)
      : "视频服务返回了失败状态，但没有提供更具体的原因。",
    impact:
      "当前任务没有得到可保存的成片，需要按原任务 ID 查询，确认失败后再修正并重新提交。",
    href: "/video-package",
    action: "检查成片提示词",
  };
}

export function BatchVideoPage() {
  const location = useLocation();
  const { activeProject, projects, loadProjects } = useWorkbenchStore();
  const confirmAction = useConfirmAction();
  const [data, setData] = useState<BatchWorkspace | null>(null);
  const [sceneId, setSceneId] = useState("");
  const [provider, setProvider] = useState("huimeng_live");
  const [preview, setPreview] = useState<ProviderRequestPreview | null>(null);
  const [readiness, setReadiness] = useState<Record<string, LiveReadiness>>({});
  const [jimengCliStatus, setJimengCliStatus] =
    useState<JimengCliStatus | null>(null);
  const [jimengModels, setJimengModels] = useState<JimengVideoModel[]>([]);
  const [seedance25Models, setSeedance25Models] = useState<
    VideoProviderModel[]
  >([]);
  const [huimengModels, setHuimengModels] = useState<VideoProviderModel[]>([]);
  const [jimengReadiness, setJimengReadiness] = useState<
    Record<string, JimengCliReadiness>
  >({});
  const [localEnv, setLocalEnv] = useState<LocalEnvStatus | null>(null);
  const [submissionChannel, setSubmissionChannel] =
    useState<SubmissionChannel>("jimeng");
  const [readinessRefresh, setReadinessRefresh] = useState(0);
  const [monitorError, setMonitorError] = useState("");
  const [supervisorStatus, setSupervisorStatus] =
    useState<VideoTaskSupervisorStatus | null>(null);
  const [lastMonitorAt, setLastMonitorAt] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [busyMessage, setBusyMessage] = useState("");
  const [preflightCheckedTaskId, setPreflightCheckedTaskId] = useState("");
  const [durationRebuildCount, setDurationRebuildCount] = useState<
    number | null
  >(null);
  useEffect(() => {
    if (!projects.length) void loadProjects();
  }, [projects.length, loadProjects]);

  useEffect(() => {
    if (!activeProject || location.pathname !== "/batch-video") return;
    setReadiness({});
    setJimengReadiness({});
    void Promise.all([
      fetchBatchVideo(activeProject.id),
      fetchJimengCliStatus(),
      fetchLocalEnvStatus(),
      Promise.allSettled([
        fetchVideoProviderModels("jimeng_cli"),
        fetchVideoProviderModels("volcengine_seedance25"),
        fetchVideoProviderModels("huimeng"),
      ]),
    ])
      .then(([next, cli, env, catalogs]) => {
        const [jimengCatalog, seedance25Catalog, huimengCatalog] = catalogs;
        setJimengCliStatus(cli);
        setJimengModels(
          jimengCatalog.status === "fulfilled" ? jimengCatalog.value : [],
        );
        setSeedance25Models(
          seedance25Catalog.status === "fulfilled"
            ? seedance25Catalog.value
            : [],
        );
        setHuimengModels(
          huimengCatalog.status === "fulfilled" ? huimengCatalog.value : [],
        );
        if (catalogs.some((item) => item.status === "rejected")) {
          setError(
            "部分视频模型目录暂时读取失败。可刷新重试；系统不会伪造模型或自动降级提交。",
          );
        }
        setLocalEnv(env);
        return { next, env };
      })
      .then(({ next, env }) => {
        setData(next);
        setSceneId(next.scenes[0]?.id ?? "");
        const currentJob = next.jobs[0];
        const defaultChannel = submissionChannelFromProviderMode(
          env.video_provider_mode,
        );
        setSubmissionChannel(currentJob?.submission_channel ?? defaultChannel);
        setProvider(
          currentJob?.provider_profile_id ??
            (defaultChannel === "huimeng"
              ? next.providers.find(
                  (item) => item.provider_type === "seedance_huimeng_live",
                )?.id
              : undefined) ??
            next.providers.find((item) => item.is_default)?.id ??
            next.providers.find(
              (item) => item.provider_type === "seedance_huimeng_live",
            )?.id ??
            "huimeng_live",
        );
      })
      .catch((cause: Error) =>
        setError(`批量视频工作台加载失败：${cause.message}`),
      );
  }, [activeProject, location.pathname]);

  const run = (
    op: () => Promise<BatchWorkspace>,
    message = "正在处理视频队列…",
  ) => {
    setBusy(true);
    setBusyMessage(message);
    setError("");
    void op()
      .then((next) => {
        setData(next);
        setPreview(null);
      })
      .catch(async (cause: Error) => {
        setError(cause.message);
        if (activeProject) {
          try {
            setData(await fetchBatchVideo(activeProject.id));
          } catch {
            // Keep the actionable provider error when the follow-up refresh also fails.
          }
        }
      })
      .finally(() => {
        setBusy(false);
        setBusyMessage("");
      });
  };

  const job = data?.jobs[0];
  const profile = data?.providers.find(
    (item) => item.id === job?.provider_profile_id,
  );
  const isHuimeng = profile?.provider_type === "seedance_huimeng_live";
  const selectableProviders =
    data?.providers.filter((item) => item.provider_type !== "seedance_mock") ??
    [];
  const huimengProvider = data?.providers.find(
    (item) => item.provider_type === "seedance_huimeng_live" && item.is_enabled,
  );
  const seedance25Provider = data?.providers.find(
    (item) => item.provider_type === "volcengine_seedance25" && item.is_enabled,
  );
  const jobProviderName = humanizeCopy(job?.provider_name ?? "");
  const isLegacyDebugJob = profile?.provider_type === "seedance_mock";
  const readinessKey =
    job?.tasks
      .map((task) =>
        [
          task.id,
          task.status,
          task.updated_at,
          task.canonical_request.duration_seconds,
          (
            task.canonical_request.provider_options as
              | Record<string, unknown>
              | undefined
          )?.jimeng_model_version ?? "",
          task.missing_items.join(","),
        ].join(":"),
      )
      .join("|") ?? "";
  const firstTask = job?.tasks[0];
  const latestResult = firstTask?.results.at(-1);
  const resultReviewStatus = latestResult?.status ?? "";
  const activeScene = data?.scenes.find(
    (item) => item.id === (job?.scene_id ?? sceneId),
  );
  const sceneShotCount = activeScene?.shot_count ?? 0;
  const confirmedVideoCount = activeScene?.confirmed_video_count ?? 0;
  const channelEditable =
    !job ||
    job.tasks.every(
      (task) =>
        !task.external_task_id &&
        ["blocked", "awaiting_budget_confirm", "ready"].includes(task.status),
    );
  const firstLiveReadiness = firstTask ? readiness[firstTask.id] : undefined;
  const firstJimengReadiness = firstTask
    ? jimengReadiness[firstTask.id]
    : undefined;
  const activeReadiness =
    submissionChannel === "huimeng"
      ? firstLiveReadiness
      : submissionChannel === "jimeng"
        ? firstJimengReadiness
        : undefined;
  const technicalBlockers =
    activeReadiness?.gate_items.filter(
      (item) =>
        !item.passed &&
        !derivedGateLabels.has(item.label) &&
        !(
          item.label.includes("镜头时长规划") &&
          Number(firstTask?.canonical_request.duration_seconds ?? 0) !== 5
        ),
    ) ?? [];
  const technicalChecksLoaded =
    submissionChannel === "volcengine_seedance25"
      ? Boolean(firstTask)
      : Boolean(firstTask && activeReadiness);
  const technicalChecksPassed =
    technicalChecksLoaded && technicalBlockers.length === 0;
  useEffect(() => {
    if (!job || !isHuimeng) {
      setReadiness({});
      return;
    }
    const pendingTasks = job.tasks.filter((task) =>
      ["blocked", "awaiting_budget_confirm", "ready"].includes(task.status),
    );
    if (!pendingTasks.length) {
      setReadiness({});
      return;
    }
    void Promise.all(
      pendingTasks.map((task) =>
        fetchLiveReadiness(task.id).then((item) => [task.id, item] as const),
      ),
    )
      .then((items) => setReadiness(Object.fromEntries(items)))
      .catch((cause: Error) => setError(cause.message));
  }, [job?.id, readinessKey, isHuimeng, readinessRefresh]);

  useEffect(() => {
    if (!job || submissionChannel !== "jimeng") {
      setJimengReadiness({});
      return;
    }
    const pendingTasks = job.tasks.filter((task) =>
      ["blocked", "awaiting_budget_confirm", "ready"].includes(task.status),
    );
    if (!pendingTasks.length) {
      setJimengReadiness({});
      return;
    }
    void Promise.all(
      pendingTasks.map((task) =>
        fetchJimengCliReadiness(task.id).then(
          (item) => [task.id, item] as const,
        ),
      ),
    )
      .then((items) => setJimengReadiness(Object.fromEntries(items)))
      .catch((cause: Error) => setError(cause.message));
  }, [job?.id, readinessKey, readinessRefresh, submissionChannel]);

  useEffect(() => {
    if (!activeProject || location.pathname !== "/batch-video") return;
    let stopped = false;
    const refreshLocalState = async () => {
      try {
        const [next, supervisor] = await Promise.all([
          fetchBatchVideo(activeProject.id),
          fetchVideoTaskSupervisorStatus(),
        ]);
        if (stopped) return;
        setData(next);
        setSupervisorStatus(supervisor);
        setMonitorError(supervisor.last_error);
        setLastMonitorAt(
          new Date().toLocaleTimeString("zh-CN", { hour12: false }),
        );
      } catch (cause) {
        if (stopped) return;
        setMonitorError((cause as Error).message);
        setLastMonitorAt(
          new Date().toLocaleTimeString("zh-CN", { hour12: false }),
        );
      }
    };
    const timer = window.setInterval(() => void refreshLocalState(), 2000);
    return () => {
      stopped = true;
      window.clearInterval(timer);
    };
  }, [activeProject?.id, location.pathname]);

  const refreshTaskStatus = (task: BatchTask) => {
    const action =
      task.external_provider === "jimeng_cli"
        ? pollJimengCliTask(task.id)
        : pollLiveVideoTask(task.id);
    run(() => action, `正在刷新 ${task.shot_code} 的视频状态…`);
  };

  const saveCompletedTask = (task: BatchTask) => {
    const action =
      task.external_provider === "jimeng_cli"
        ? downloadJimengCliTask(task.id)
        : downloadLiveVideoTask(task.id);
    run(() => action, `正在把 ${task.shot_code} 保存到本地项目目录…`);
  };

  const switchToHuimengMode = async () => {
    setBusy(true);
    setBusyMessage("正在启用慧梦 API 提交通道…");
    setError("");
    try {
      const next = await updateLocalEnv({
        confirm_local_env_write: true,
        video_provider_mode: "huimeng_live",
      });
      setLocalEnv(next);
      setSubmissionChannel("huimeng");
      setReadinessRefresh((current) => current + 1);
    } catch (cause) {
      setError((cause as Error).message);
    } finally {
      setBusy(false);
      setBusyMessage("");
    }
  };

  const changeSubmissionChannel = async (nextChannel: SubmissionChannel) => {
    if (nextChannel === submissionChannel) return;
    if (!channelEditable) {
      setError(
        "当前任务已经提交到服务商，不能中途切换生成服务。请等待任务结束后重新建立队列。",
      );
      return;
    }
    if (nextChannel === "huimeng" && !huimengProvider) {
      setError("尚未找到可用的慧梦 API 配置，请先到成本与设置页完成配置。");
      return;
    }
    if (nextChannel === "volcengine_seedance25" && !seedance25Provider) {
      setError(
        "Seedance 2.5 Mock Provider 尚未初始化，请重启 FastAPI 后刷新页面。",
      );
      return;
    }
    if (!job) {
      setSubmissionChannel(nextChannel);
      if (nextChannel === "huimeng" && huimengProvider)
        setProvider(huimengProvider.id);
      if (nextChannel === "volcengine_seedance25" && seedance25Provider)
        setProvider(seedance25Provider.id);
      return;
    }

    setBusy(true);
    setBusyMessage(`正在把本次队列切换为${channelNames[nextChannel]}…`);
    setError("");
    try {
      const next = await updateBatchVideoSubmissionChannel(
        job.id,
        nextChannel,
        huimengProvider?.id ?? "",
      );
      setData(next);
      setSubmissionChannel(nextChannel);
      setProvider(next.jobs[0]?.provider_profile_id ?? provider);
      setReadinessRefresh((current) => current + 1);
    } catch (cause) {
      setError((cause as Error).message);
    } finally {
      setBusy(false);
      setBusyMessage("");
    }
  };

  const confirmLiveSubmit = async (task: BatchTask, item?: LiveReadiness) => {
    const confirmed = await confirmAction({
      title: "确认提交真实视频",
      message:
        "这一步会发送 1 次真实视频请求。当前仍是受控逐镜提交，不会自动批量扣费。",
      details: item
        ? [
            `服务：${item.provider_name}`,
            `模型：${item.model_id}`,
            item.risk_notice,
          ]
        : ["可能消耗积分，请先核对账户价格。"],
      confirmLabel: "确认提交",
      tone: "cost",
    });
    if (confirmed) {
      run(
        () => submitLiveVideoTask(task.id),
        `正在提交 ${task.shot_code} 的真实视频任务…`,
      );
    }
  };

  const confirmLivePoll = async (task: BatchTask) => {
    const confirmed = await confirmAction({
      title: "查询真实视频任务",
      message: "只查询已提交任务的状态，不会创建新视频任务。",
      confirmLabel: "确认查询",
    });
    if (confirmed)
      run(
        () => pollLiveVideoTask(task.id),
        `正在查询 ${task.shot_code} 的视频状态…`,
      );
  };

  const confirmLiveDownload = async (task: BatchTask) => {
    const confirmed = await confirmAction({
      title: "下载视频并绑定镜头",
      message: "下载后会保存视频结果，并绑定到当前镜头 ID。旧结果不会覆盖。",
      confirmLabel: "确认下载",
    });
    if (confirmed)
      run(
        () => downloadLiveVideoTask(task.id),
        `正在下载 ${task.shot_code} 的视频并绑定镜头…`,
      );
  };

  const confirmJimengSubmit = async (
    task: BatchTask,
    item?: JimengCliReadiness,
  ) => {
    const confirmed = await confirmAction({
      title: "确认用即梦 CLI 提交",
      message:
        "这一步会调用你电脑上的 dreamina 命令，使用已登录的即梦账号，可能消耗积分。",
      details: item
        ? [
            `模型：${item.model_id}`,
            `参考素材：${item.asset_count} 个（没有素材也可提交纯提示词）`,
            item.risk_notice,
          ]
        : ["请先核对即梦账号积分和当前镜头提示词。"],
      confirmLabel: "确认提交",
      tone: "cost",
    });
    if (confirmed)
      run(
        () => submitJimengCliTask(task.id),
        `正在把 ${task.shot_code} 提交给即梦 CLI…`,
      );
  };

  const changeJimengModel = (task: BatchTask, modelId: string) => {
    run(
      () => updateJimengCliModel(task.id, modelId),
      "正在保存即梦模型并重新确认费用风险…",
    );
    setReadinessRefresh((current) => current + 1);
  };

  const changeProviderModel = (task: BatchTask, modelId: string) => {
    if (submissionChannel === "jimeng") {
      changeJimengModel(task, modelId);
      return;
    }
    run(
      () =>
        updateVideoTaskGenerationSettings(task.id, {
          provider_model_id: modelId,
        }),
      "正在保存 Seedance 2.5 模型并撤销受影响的绑定确认…",
    );
  };

  const refreshCurrentPreflight = (task: BatchTask) => {
    setPreflightCheckedTaskId(task.id);
    run(
      () => refreshBatchTaskPreflight(task.id),
      "正在同步最新提示词、故事板和资产条件…",
    );
    setReadinessRefresh((current) => current + 1);
  };

  const saveReferenceBindings = (task: BatchTask, assetIds: string[]) => {
    if (submissionChannel === "volcengine_seedance25") {
      const existing = new Map(
        (task.reference_bindings ?? []).map((item) => [item.asset_id, item]),
      );
      const candidates = new Map(
        (task.reference_candidates ?? []).map((item) => [item.asset_id, item]),
      );
      const referenceItems: VideoReferenceItemUpdate[] = assetIds.map(
        (assetId) => {
          const candidate = candidates.get(assetId);
          const previous = existing.get(assetId);
          const mediaType =
            candidate?.media_type ?? previous?.media_type ?? "image";
          return {
            asset_id: assetId,
            media_type: mediaType,
            purpose: seedance25ReferencePurpose(
              candidate?.role ?? previous?.role,
              mediaType,
            ),
            must_preserve: previous?.must_preserve ?? "",
            must_not_transfer: previous?.must_not_transfer ?? "",
          };
        },
      );
      run(
        () => updateStructuredVideoReferenceBindings(task.id, referenceItems),
        "正在保存图片、视频和音频参考，并重编对应 @ 标签…",
      );
      setReadinessRefresh((current) => current + 1);
      return;
    }
    run(
      () => updateVideoReferenceBindings(task.id, assetIds),
      "正在保存人工参考图绑定并重编 @图片N 提示词…",
    );
    setReadinessRefresh((current) => current + 1);
  };

  const confirmJimengPoll = async (task: BatchTask) => {
    const confirmed = await confirmAction({
      title: "查询即梦 CLI 结果",
      message: "只查询已提交任务的状态，不会创建新视频，也不会重复扣积分。",
      confirmLabel: "确认查询",
    });
    if (confirmed)
      run(
        () => pollJimengCliTask(task.id),
        `正在查询 ${task.shot_code} 的即梦结果…`,
      );
  };

  const confirmJimengDownload = async (task: BatchTask) => {
    const confirmed = await confirmAction({
      title: "下载即梦视频并绑定镜头",
      message:
        "下载后会保存到当前项目的视频结果目录，并绑定当前镜头 ID。旧结果不会被覆盖。",
      confirmLabel: "确认下载",
    });
    if (confirmed)
      run(
        () => downloadJimengCliTask(task.id),
        `正在下载 ${task.shot_code} 的即梦视频…`,
      );
  };

  const confirmCostAuthorization = async () => {
    if (!job) return;
    const hasEstimate =
      submissionChannel === "huimeng" &&
      job.cost_estimate_status === "estimated" &&
      job.estimated_cost !== null;
    const isMock = submissionChannel === "volcengine_seedance25";
    const channelName = isMock
      ? channelNames[submissionChannel]
      : submissionChannel === "huimeng"
        ? jobProviderName
        : "即梦 CLI（本机登录账号）";
    const confirmed = await confirmAction({
      title: isMock
        ? "确认启动模拟批次"
        : hasEstimate
          ? "确认本次预计费用"
          : "确认本次费用风险",
      message: isMock
        ? "首期 Seedance 2.5 仅运行本地 Mock，不会向火山方舟发送请求，也不会产生积分或视频。"
        : hasEstimate
          ? `当前服务配置估算为 ${job.estimated_cost} ${job.currency}。实际扣费仍以服务商账单为准。`
          : "当前服务配置无法可靠计算本次消耗。请先在服务商账户核对价格和余额；未知费用不代表免费。",
      details: [
        `提交方式：${channelName}`,
        isMock
          ? "模拟任务只验证参考绑定、请求编译、后台派发、恢复和幂等保存。"
          : submissionChannel === "huimeng"
            ? job.cost_estimate_note
            : "即梦 CLI 使用账号积分，系统无法读取当前任务的准确扣分。",
        submissionChannel === "huimeng" && job.cost_source_url
          ? `价格来源：${job.cost_source_url}`
          : "请以当前账号和服务商页面显示为准。",
        isMock
          ? "结果会保存为 .mock.json 验收记录，不会伪造 MP4。"
          : "确认后只会解锁当前队列，真正发送请求时仍会再次确认。",
      ].filter(Boolean),
      confirmLabel: isMock
        ? "启动 Mock 验收"
        : hasEstimate
          ? "确认预计费用"
          : "已核对，允许提交",
      tone: isMock ? "normal" : "cost",
    });
    if (confirmed) {
      run(
        () => confirmBatchCostRisk(job.id),
        hasEstimate ? "正在确认预计费用…" : "正在记录费用风险确认…",
      );
    }
  };

  const rebuildForSelectedProvider = () => {
    if (!job) {
      run(
        () =>
          createBatchVideo(
            sceneId,
            provider || "huimeng_live",
            submissionChannel,
          ),
        "正在创建单镜视频队列…",
      );
      return;
    }
    run(
      () => remapBatchVideoProvider(job.id, provider || "huimeng_live"),
      "正在切换视频服务并重建单镜队列…",
    );
  };

  const createNextSingleShotQueue = () => {
    run(
      () =>
        createBatchVideo(
          job?.scene_id ?? sceneId,
          provider || "huimeng_live",
          submissionChannel,
        ),
      resultReviewStatus === "rejected"
        ? "正在重新建立当前镜头任务…"
        : "正在建立下一镜头任务…",
    );
  };

  const reviewCurrentVideo = async (decision: "confirm" | "redo") => {
    if (!latestResult || !firstTask) return;
    const confirmed = await confirmAction({
      title:
        decision === "confirm"
          ? `确认 ${firstTask.shot_code} 视频通过`
          : `确认重做 ${firstTask.shot_code}`,
      message:
        decision === "confirm"
          ? "通过后，这个视频会成为当前镜头的正式结果；下一步将建立下一个尚未完成的镜头。"
          : "当前视频文件和历史记录会保留，但不会作为正式结果；下一步会重新建立当前镜头任务。",
      details:
        decision === "confirm"
          ? ["请先完整播放视频，核对主体、产品、动作、镜头连续性和尾帧。"]
          : ["重新生成可能再次消耗服务商积分，系统不会自动提交。"],
      confirmLabel: decision === "confirm" ? "通过这个视频" : "标记重做",
      tone: decision === "confirm" ? "normal" : "danger",
    });
    if (confirmed) {
      run(
        () => reviewVideoResult(latestResult.id, decision),
        decision === "confirm"
          ? "正在确认视频并更新本场进度…"
          : "正在记录重做决定…",
      );
    }
  };

  const blockedHref = (() => {
    const missing = (firstTask?.missing_items.join(" ") ?? "").toLowerCase();
    if (
      missing.includes("vp") ||
      missing.includes("视频") ||
      missing.includes("提示词")
    )
      return "/video-package";
    if (missing.includes("storyboard") || missing.includes("故事板"))
      return "/storyboards";
    if (
      missing.includes("asset") ||
      missing.includes("资产") ||
      missing.includes("人物") ||
      missing.includes("场景")
    )
      return "/assets";
    const firstGate = technicalBlockers[0];
    if (firstGate)
      return (
        gateGuidance(firstGate.label, submissionChannel).href ||
        "/video-package"
      );
    return "/video-package";
  })();

  const blockedReason = firstTask?.missing_items.length
    ? firstTask.missing_items.map(humanizeCopy).join("；")
    : technicalBlockers
        .map(
          (item) => `${humanizeCopy(item.label)}：${humanizeCopy(item.detail)}`,
        )
        .join("；") || "还没有满足提交条件。";
  const hasQueueValidationIssue = Boolean(
    firstTask?.missing_items.some((item) => {
      const value = item.toLowerCase();
      return (
        value.includes("服务配置") ||
        value.includes("服务通道") ||
        value.includes("seedance 单条") ||
        value.includes("分辨率") ||
        value.includes("参考图片数量")
      );
    }),
  );

  const primaryCard = (() => {
    const taskAlreadyRunning = [
      "verifying",
      "submitted",
      "processing",
      "completed",
      "imported",
    ].includes(firstTask?.status ?? "");
    if (durationRebuildCount && !taskAlreadyRunning) {
      return {
        title: `先修正剩余 ${durationRebuildCount} 个旧版 5 秒镜头`,
        description:
          "这些镜头时长与主规则不一致。请先按主规则生成新版分镜提示词，再复核对应故事板；旧提示词和旧故事板图片都会保留。",
        action: (
          <GuidePrimaryButton href="/video-package">
            去按主规则重建
          </GuidePrimaryButton>
        ),
      };
    }
    if (!job) {
      return {
        title: "创建一个单镜视频队列",
        description:
          "这里只先准备 1 个镜头，方便你低风险验收视频通道。不会自动提交，也不会扣费。",
        action: (
          <GuidePrimaryButton
            loading={busy}
            loadingLabel="正在创建单镜队列…"
            onClick={rebuildForSelectedProvider}
          >
            创建单镜队列
          </GuidePrimaryButton>
        ),
      };
    }
    if (isLegacyDebugJob || provider !== job.provider_profile_id) {
      return {
        title: "使用当前选择的视频服务",
        description: `当前队列与所选服务不一致。切换到 ${humanizeCopy(data?.providers.find((item) => item.id === provider)?.display_name ?? "所选视频服务")} 后，系统会重新检查规格和费用。`,
        action: (
          <GuidePrimaryButton
            loading={busy}
            loadingLabel="正在切换队列…"
            onClick={rebuildForSelectedProvider}
          >
            切换视频服务
          </GuidePrimaryButton>
        ),
      };
    }
    if (firstTask?.missing_items.length) {
      return {
        title: hasQueueValidationIssue
          ? "重新按当前视频服务校验"
          : preflightCheckedTaskId === firstTask.id
            ? "仍有真实缺项需要处理"
            : "先同步最新提交条件",
        description: hasQueueValidationIssue
          ? `${blockedReason} 系统会按当前选择的视频通道和模型原地重算，不需要返回已完成的提示词页。`
          : preflightCheckedTaskId === firstTask.id
            ? blockedReason
            : "系统会在当前页重新读取最新提示词、故事板和资产，不再先跳到另一个页面。只有复查后仍存在的真实缺项，才需要去对应页面修改。",
        action: hasQueueValidationIssue ? (
          <GuidePrimaryButton
            loading={busy}
            loadingLabel="正在修复队列校验…"
            onClick={() => refreshCurrentPreflight(firstTask)}
          >
            按当前服务重新校验
          </GuidePrimaryButton>
        ) : preflightCheckedTaskId === firstTask.id ? (
          <GuidePrimaryButton href={blockedHref}>
            去处理这个缺项
          </GuidePrimaryButton>
        ) : (
          <GuidePrimaryButton
            loading={busy}
            loadingLabel="正在重新检查条件…"
            onClick={() => refreshCurrentPreflight(firstTask)}
          >
            重新检查当前条件
          </GuidePrimaryButton>
        ),
      };
    }
    if (!firstTask) {
      return {
        title: "队列里还没有镜头",
        description: "请重新创建单镜队列，或回到分镜提示词页确认当前镜头。",
        action: (
          <GuidePrimaryButton href="/video-package">
            去分镜提示词页
          </GuidePrimaryButton>
        ),
      };
    }
    if (firstTask.status === "imported") {
      if (resultReviewStatus === "confirmed") {
        const sceneDone =
          sceneShotCount > 0 && confirmedVideoCount >= sceneShotCount;
        return {
          title: sceneDone
            ? "本场全部视频已通过验收"
            : `${firstTask.shot_code} 已通过验收`,
          description: sceneDone
            ? `本场 ${confirmedVideoCount}/${sceneShotCount} 个镜头已完成，可以回项目总控台查看整体进度。`
            : `本场已完成 ${confirmedVideoCount}/${sceneShotCount || "?"} 个镜头。下一步将自动选择尚未完成的镜头，不会重复提交 ${firstTask.shot_code}。`,
          action: sceneDone ? (
            <GuidePrimaryButton href="/">回项目总控台</GuidePrimaryButton>
          ) : (
            <GuidePrimaryButton
              loading={busy}
              loadingLabel="正在建立下一镜头任务…"
              onClick={createNextSingleShotQueue}
            >
              继续生成下一个镜头
            </GuidePrimaryButton>
          ),
        };
      }
      if (resultReviewStatus === "rejected") {
        return {
          title: `${firstTask.shot_code} 已标记重做`,
          description:
            "旧视频仍保留在项目目录中，但不会作为正式结果。重新建立任务后，可修改模型或提示词并再次人工确认提交。",
          action: (
            <GuidePrimaryButton
              loading={busy}
              loadingLabel="正在重新建立当前镜头任务…"
              onClick={createNextSingleShotQueue}
            >
              重新建立这个镜头
            </GuidePrimaryButton>
          ),
        };
      }
      return {
        title: `请先预览并验收 ${firstTask.shot_code}`,
        description:
          "视频已经保存到本地。下载只是另存文件，不会推进流程；请在下方完整播放后选择“通过并继续”或“需要重做”。",
        action: (
          <GuidePrimaryButton
            onClick={() =>
              document
                .getElementById("video-result-review")
                ?.scrollIntoView({ behavior: "smooth", block: "center" })
            }
          >
            去预览并验收
          </GuidePrimaryButton>
        ),
      };
    }
    if (firstTask.status === "completed") {
      return {
        title: "线上生成已完成，正在保存到本地",
        description:
          "系统正在自动下载成片并绑定当前 Shot ID。线上地址可能过期，本地保存完成前请不要重复提交。",
        action: (
          <GuidePrimaryButton
            loading={busy}
            loadingLabel="正在保存到本地…"
            onClick={() => saveCompletedTask(firstTask)}
          >
            立即保存到本地
          </GuidePrimaryButton>
        ),
      };
    }
    if (["verifying", "submitted", "processing"].includes(firstTask.status)) {
      return {
        title:
          firstTask.status === "verifying"
            ? "即梦已返回任务 ID，正在确认真实状态"
            : firstTask.status === "submitted"
              ? "视频服务已接收任务"
              : "视频正在生成",
        description:
          firstTask.status === "verifying"
            ? "当前只确认 CLI 已记录任务，还不能声称网页生成队列已经开始。系统会继续查询同一个任务，不会重复提交。"
            : "系统会持续查询同一个任务，不会重复提交或重复扣费。切换左侧页面后监控仍会继续。",
        action: (
          <GuidePrimaryButton
            loading={busy}
            loadingLabel="正在刷新视频状态…"
            onClick={() => refreshTaskStatus(firstTask)}
          >
            立即刷新状态
          </GuidePrimaryButton>
        ),
      };
    }
    if (firstTask.status === "failed") {
      const guidance = videoFailureGuidance(firstTask.error_message);
      if (firstTask.external_provider === "jimeng_cli") {
        return {
          title: "即梦没有创建这次视频任务",
          description: `${guidance.reason} ${guidance.impact} 先重新准备任务，再选择模型并重新确认费用；系统不会自动再次扣分。`,
          action: (
            <GuidePrimaryButton
              loading={busy}
              loadingLabel="正在重新准备任务…"
              onClick={() =>
                run(
                  () => prepareJimengCliRetry(firstTask.id),
                  "正在保留失败记录并重新准备任务…",
                )
              }
            >
              重新准备这条任务
            </GuidePrimaryButton>
          ),
        };
      }
      return {
        title: "视频生成失败",
        description: `${guidance.reason} ${guidance.impact}`,
        action: (
          <GuidePrimaryButton href={guidance.href || "/video-package"}>
            {guidance.action}
          </GuidePrimaryButton>
        ),
      };
    }
    if (
      (submissionChannel === "huimeng" && firstLiveReadiness === undefined) ||
      (submissionChannel === "jimeng" && firstJimengReadiness === undefined)
    ) {
      return {
        title: "正在检查提交条件",
        description: "正在核对视频服务、提示词和参考素材，请稍等。",
        action: (
          <GuidePrimaryButton loading loadingLabel="正在检查提交条件…">
            检查提交条件
          </GuidePrimaryButton>
        ),
      };
    }
    if (technicalBlockers.length) {
      const firstBlocker = technicalBlockers[0];
      const guidance = gateGuidance(firstBlocker.label, submissionChannel);
      return {
        title: `先处理：${humanizeCopy(firstBlocker.label)}`,
        description: `${humanizeCopy(firstBlocker.detail)} ${guidance.impact}`,
        action:
          guidance.action === "切换到慧梦 API 模式" ? (
            <GuidePrimaryButton
              loading={busy}
              loadingLabel="正在切换提交通道…"
              onClick={() => void switchToHuimengMode()}
            >
              切换到慧梦 API 模式
            </GuidePrimaryButton>
          ) : (
            <GuidePrimaryButton href={guidance.href || blockedHref}>
              {guidance.action}
            </GuidePrimaryButton>
          ),
      };
    }
    if (!job.budget_confirmed) {
      const hasEstimate =
        submissionChannel === "huimeng" &&
        job.cost_estimate_status === "estimated" &&
        job.estimated_cost !== null;
      return {
        title: hasEstimate
          ? "确认这 1 个镜头的预计费用"
          : "确认这 1 个镜头的费用风险",
        description: hasEstimate
          ? `当前服务配置估算为 ${job.estimated_cost} ${job.currency}，实际扣费仍以服务商账单为准。`
          : "当前系统无法可靠计算积分消耗。请先在服务商账户核对价格和余额；未知费用不代表 0 或免费。",
        action: (
          <GuidePrimaryButton
            loading={busy}
            loadingLabel={
              hasEstimate ? "正在确认预计费用…" : "正在确认费用风险…"
            }
            onClick={() => void confirmCostAuthorization()}
          >
            {hasEstimate ? "确认预计费用" : "确认费用风险"}
          </GuidePrimaryButton>
        ),
      };
    }
    if (
      submissionChannel === "huimeng" &&
      isHuimeng &&
      firstLiveReadiness?.ready
    ) {
      return {
        title: "提交这 1 个镜头",
        description:
          "提交前会再次弹窗确认。系统只提交当前 1 个镜头，不会无人值守批量扣费。",
        action: (
          <GuidePrimaryButton
            loading={busy}
            loadingLabel="正在提交视频任务…"
            onClick={() =>
              void confirmLiveSubmit(firstTask, firstLiveReadiness)
            }
          >
            提交这个镜头
          </GuidePrimaryButton>
        ),
      };
    }
    if (submissionChannel === "jimeng" && firstJimengReadiness?.ready) {
      return {
        title: "用即梦 CLI 提交这个镜头",
        description:
          "会调用你电脑上已登录的 dreamina 命令，提交前仍会弹窗确认。",
        action: (
          <GuidePrimaryButton
            loading={busy}
            loadingLabel="正在提交给即梦 CLI…"
            onClick={() =>
              void confirmJimengSubmit(firstTask, firstJimengReadiness)
            }
          >
            用即梦 CLI 提交
          </GuidePrimaryButton>
        ),
      };
    }
    return {
      title: "先补齐提交条件",
      description:
        blockedReason ||
        "当前镜头还不能提交。请先补齐分镜提示词、故事板或服务配置。",
      action: (
        <GuidePrimaryButton href={blockedHref}>去补齐条件</GuidePrimaryButton>
      ),
    };
  })();
  const videoStageItems: DirectorStageItem[] = [
    {
      title: "单镜队列",
      detail: job ? `${job.tasks.length} 个任务` : "还没创建",
      status: job ? "done" : "current",
    },
    {
      title: "提交条件",
      detail: durationRebuildCount
        ? `${durationRebuildCount} 个镜头时长待重建`
        : !technicalChecksLoaded
          ? "正在检查"
          : technicalChecksPassed
            ? "技术条件通过"
            : "还有条件没满足",
      status: !job
        ? "pending"
        : durationRebuildCount
          ? "blocked"
          : !technicalChecksLoaded
            ? "current"
            : technicalChecksPassed
              ? "done"
              : "blocked",
    },
    {
      title:
        submissionChannel === "huimeng" &&
        job?.cost_estimate_status === "estimated"
          ? "预计费用确认"
          : "费用风险确认",
      detail: job?.budget_confirmed
        ? "已确认"
        : submissionChannel === "huimeng" &&
            job?.cost_estimate_status === "estimated"
          ? "等待确认估算金额"
          : "费用未知，需人工核对",
      status:
        durationRebuildCount || !technicalChecksPassed
          ? "pending"
          : job?.budget_confirmed
            ? "done"
            : "current",
    },
    {
      title: "生成 / 下载",
      detail: durationRebuildCount
        ? "等待时长重建"
        : firstTask?.status
          ? versionStateName(firstTask.status)
          : "等待提交",
      status: durationRebuildCount
        ? "pending"
        : firstTask?.status === "imported"
          ? "done"
          : ["verifying", "submitted", "processing", "completed"].includes(
                firstTask?.status ?? "",
              )
            ? "current"
            : "pending",
    },
    {
      title: "验收 / 下一镜",
      detail:
        resultReviewStatus === "confirmed"
          ? "已通过，可继续下一镜"
          : resultReviewStatus === "rejected"
            ? "需要重做当前镜头"
            : firstTask?.status === "imported"
              ? "等待人工验收"
              : "视频保存后进行",
      status:
        resultReviewStatus === "confirmed"
          ? "done"
          : firstTask?.status === "imported"
            ? "current"
            : "pending",
    },
  ];

  const confirmBatchBindings = async () => {
    if (!job) return;
    const confirmed = await confirmAction({
      title: `确认 ${job.tasks.length} 个镜头的参考绑定`,
      message:
        "确认后，系统会锁定当前模型、时长、提示词和 @图片顺序。任何一项变化都会自动撤销对应镜头的确认。",
      details: ["请重点核对故事板、人物、场景和产品参考没有错位。"],
      confirmLabel: "确认全部有效绑定",
    });
    if (confirmed)
      run(
        () => confirmAllVideoReferenceBindings(job.id),
        "正在确认全部参考绑定…",
      );
  };

  const launchWholeBatch = async () => {
    if (!job) return;
    const isMock = submissionChannel === "volcengine_seedance25";
    const confirmed = await confirmAction({
      title: `${isMock ? "模拟" : "启动"} ${job.tasks.length} 个镜头的后台生产`,
      message: isMock
        ? "后台将完整演练派发、查询和持久化，但不会连接火山方舟，也不会生成视频。"
        : "授权后，后台会按顺序逐条提交。离开页面不会停止；明确失败的镜头不会阻塞其他镜头。",
      details: [
        `总时长：${job.total_seconds} 秒`,
        isMock
          ? "费用：不产生费用（Mock）"
          : job.estimated_cost === null
            ? "费用未知，请以服务商账户实际扣费为准。"
            : `预计费用：${job.estimated_cost} ${job.currency}`,
        `服务：${channelNames[submissionChannel]}`,
      ],
      confirmLabel: isMock ? "启动 Mock 批次" : "确认并启动整批生产",
      tone: isMock ? "normal" : "cost",
    });
    if (confirmed)
      run(() => launchBatchVideoJob(job.id), "正在授权后台批量生产…");
  };

  const reviewTaskVideo = async (
    task: BatchTask,
    decision: "confirm" | "redo",
  ) => {
    const result = task.results.at(-1);
    if (!result) return;
    const confirmed = await confirmAction({
      title:
        decision === "confirm"
          ? `确认 ${task.shot_code} 通过`
          : `标记 ${task.shot_code} 重做`,
      message:
        decision === "confirm"
          ? "通过后将作为当前正式视频结果。"
          : "旧视频和审核记录会保留，只重新准备这一条镜头。",
      confirmLabel: decision === "confirm" ? "确认通过" : "标记重做",
      tone: decision === "confirm" ? "normal" : "danger",
    });
    if (confirmed)
      run(
        () => reviewVideoResult(result.id, decision),
        decision === "confirm" ? "正在确认视频…" : "正在保留旧版并准备重做…",
      );
  };

  return (
    <div className={workbenchPageClass}>
      {busy ? (
        <GuideProgressToast
          label={busyMessage || "正在处理视频队列，请稍等…"}
        />
      ) : null}
      <p className="text-xs tracking-[.18em] text-orange-400">V7｜批量视频</p>
      <h1 className="mt-2 text-4xl font-semibold">生成视频</h1>
      <p className="mt-3 text-sm text-zinc-400">
        集中核对当前场次全部镜头的参考绑定，一次授权后由后台依次提交、查询和保存，最后统一预览验收。
      </p>
      {error && <p className="mt-4 text-sm text-red-300">{error}</p>}

      <SubmissionChannelPicker
        channel={submissionChannel}
        defaultChannel={submissionChannelFromProviderMode(
          localEnv?.video_provider_mode,
        )}
        editable={channelEditable && !busy}
        huimengAvailable={Boolean(huimengProvider)}
        jimengReady={Boolean(jimengCliStatus?.ready)}
        seedance25Available={Boolean(seedance25Provider)}
        onChange={(channel) => void changeSubmissionChannel(channel)}
      />
      {job &&
      channelEditable &&
      submissionChannel !== "jimeng" &&
      submissionChannelFromProviderMode(localEnv?.video_provider_mode) ===
        "jimeng" ? (
        <section className="border-b border-cyan-400/25 bg-cyan-400/5 px-5 py-4">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <p className="text-sm font-semibold text-cyan-100">
                这是尚未派发的旧渠道队列
              </p>
              <p className="mt-1 text-xs leading-5 text-zinc-400">
                系统不会擅自修改旧队列。你可以明确切换到当前默认的即梦
                CLI，并按该渠道能力重新建立任务快照。
              </p>
            </div>
            <button
              className={button}
              type="button"
              disabled={busy}
              onClick={() => void changeSubmissionChannel("jimeng")}
            >
              切换到默认即梦 CLI 并重建队列
            </button>
          </div>
        </section>
      ) : null}
      {submissionChannel === "jimeng" &&
      jimengModels.every((model) => !model.id.includes("2.5")) ? (
        <p className="border-b border-amber-400/25 bg-amber-400/5 px-5 py-3 text-xs leading-5 text-amber-100">
          即梦网页已经出现 Seedance 2.5，但当前本机 dreamina CLI
          的帮助输出尚未开放 2.5 模型值，因此这里不会显示或伪提交 2.5。需要 2.5
          时请选择独立的火山方舟 API Mock 通道。
        </p>
      ) : null}
      {job ? (
        <BatchProductionWorkbench
          job={job}
          models={
            submissionChannel === "volcengine_seedance25"
              ? seedance25Models
              : submissionChannel === "jimeng"
                ? jimengModels
                : huimengModels
          }
          submissionChannel={submissionChannel}
          supervisorStatus={supervisorStatus}
          monitorError={monitorError}
          busy={busy}
          expectedTaskCount={Math.max(0, sceneShotCount - confirmedVideoCount)}
          onRebuildBatch={() =>
            run(
              () =>
                createBatchVideo(
                  job.scene_id,
                  provider || "huimeng_live",
                  submissionChannel,
                ),
              "正在升级为当前场次批量队列…",
            )
          }
          onConfirmAllBindings={() => void confirmBatchBindings()}
          onConfirmTask={(task) =>
            run(
              () => confirmVideoReferenceBindings(task.id),
              `正在确认 ${task.shot_code} 的参考绑定…`,
            )
          }
          onSaveBindings={(task, assetIds) =>
            saveReferenceBindings(task, assetIds)
          }
          onResetBindings={(task) =>
            run(
              () => resetVideoReferenceBindings(task.id),
              `正在恢复 ${task.shot_code} 的自动推荐…`,
            )
          }
          onModelChange={(task, modelId) => changeProviderModel(task, modelId)}
          onBatchModelChange={(modelId) =>
            run(
              () =>
                submissionChannel === "jimeng"
                  ? updateBatchJimengCliModel(job.id, modelId)
                  : updateBatchVideoGenerationSettings(job.id, {
                      provider_model_id: modelId,
                    }),
              "正在统一更新本批次模型…",
            )
          }
          onGenerationSettingsChange={(settings) =>
            run(
              () => updateBatchVideoGenerationSettings(job.id, settings),
              "正在更新 2.5 时长与分辨率设置…",
            )
          }
          onConfirmCost={() => void confirmCostAuthorization()}
          onLaunch={() => void launchWholeBatch()}
          onRetry={(task) =>
            run(
              () => prepareVideoTaskRetry(task.id),
              `正在保留失败记录并重新准备 ${task.shot_code}…`,
            )
          }
          onReview={(task, decision) => void reviewTaskVideo(task, decision)}
          onApproveAll={() =>
            run(
              () => confirmAllCompletedVideos(job.id),
              "正在通过全部待验收视频…",
            )
          }
          onImport={(task, file) =>
            run(
              () => importTaskVideo(task.id, file),
              `正在导入 ${task.shot_code} 的视频结果…`,
            )
          }
        />
      ) : (
        <GuideActionCard
          eyebrow="当前主任务"
          title="建立当前场次批量队列"
          description="系统会载入当前场次全部未验收镜头，先集中检查参考绑定，不会立即提交或扣费。"
          tone="current"
        >
          <GuidePrimaryButton
            loading={busy}
            loadingLabel="正在建立批量队列…"
            onClick={rebuildForSelectedProvider}
          >
            建立批量队列
          </GuidePrimaryButton>
        </GuideActionCard>
      )}

      {job && firstTask && activeProject && preview ? (
        <>
          <section id="current-primary-task">
            <DirectorWorkbenchFrame
              main={
                <GuideActionCard
                  eyebrow="当前主任务"
                  title={primaryCard.title}
                  description={primaryCard.description}
                  progressLabel={
                    busy ? busyMessage || "正在处理视频队列…" : undefined
                  }
                  tone={resultReviewStatus === "confirmed" ? "done" : "current"}
                >
                  {primaryCard.action}
                </GuideActionCard>
              }
              aside={
                <div className="space-y-4">
                  <DirectorStatusPanel
                    title="视频提交闸门"
                    description="这里不会自动批量扣费。每次真实提交都会再次弹窗确认。"
                    items={videoStageItems}
                  />
                </div>
              }
            />
          </section>

          {(!firstTask ||
            ["blocked", "awaiting_budget_confirm", "ready"].includes(
              firstTask.status,
            )) &&
          !durationRebuildCount ? (
            <SubmissionGateGuide
              channel={submissionChannel}
              readiness={activeReadiness}
              hasTask={Boolean(firstTask)}
              onSwitchHuimeng={() => void switchToHuimengMode()}
              onRebuild={rebuildForSelectedProvider}
              onRefreshPreflight={() =>
                firstTask && refreshCurrentPreflight(firstTask)
              }
              onSaveBindings={(assetIds) =>
                firstTask && saveReferenceBindings(firstTask, assetIds)
              }
              busy={busy}
            />
          ) : null}

          {firstTask ? (
            <VideoGenerationMonitor
              task={firstTask}
              projectCode={data?.project_code ?? ""}
              monitorError={monitorError}
              supervisorStatus={supervisorStatus}
              lastMonitorAt={lastMonitorAt}
              onRefresh={() => refreshTaskStatus(firstTask)}
              onSave={() => saveCompletedTask(firstTask)}
              onAccept={() => void reviewCurrentVideo("confirm")}
              onRedo={() => void reviewCurrentVideo("redo")}
              busy={busy}
            />
          ) : null}

          {activeProject ? (
            <SeedanceOsPanel
              projectId={activeProject.id}
              onDurationRebuildCountChange={setDurationRebuildCount}
            />
          ) : null}

          <TechDetails className="mt-6" title="可选：选择视频服务和导出资料包">
            <section className="flex flex-wrap items-end gap-3">
              <label className="text-xs text-zinc-400">
                场次
                <select
                  className="mt-1 block border border-white/15 bg-[#11171c] px-3 py-2"
                  value={sceneId}
                  onChange={(event) => setSceneId(event.target.value)}
                >
                  {data?.scenes.map((scene) => (
                    <option key={scene.id} value={scene.id}>
                      {scene.scope_code}
                    </option>
                  ))}
                </select>
              </label>
              <label className="text-xs text-zinc-400">
                视频服务
                <select
                  className="mt-1 block border border-white/15 bg-[#11171c] px-3 py-2"
                  value={provider}
                  onChange={(event) => setProvider(event.target.value)}
                >
                  {selectableProviders.map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.display_name}
                    </option>
                  ))}
                </select>
              </label>
              {job && (
                <button
                  className={button}
                  disabled={busy}
                  onClick={() =>
                    run(() => exportJimeng(job.id), "正在导出即梦 ZIP…")
                  }
                >
                  <Download size={14} />
                  导出即梦 ZIP
                </button>
              )}
              {job?.jimeng_zip_url && (
                <a
                  className={button}
                  href={assetImageUrl(job.jimeng_zip_url)}
                  download
                >
                  下载 ZIP
                </a>
              )}
              <p className="basis-full text-xs leading-5 text-zinc-500">
                建队列、切换队列和费用确认统一使用上方主按钮；这里仅保留服务选择和导出资料包，避免重复操作入口。
              </p>
            </section>
          </TechDetails>

          {isLegacyDebugJob && (
            <section className="mt-5 border border-orange-400/35 bg-orange-400/8 p-5">
              <p className="text-sm font-semibold text-orange-100">
                当前是旧开发队列，不适合正式测试
              </p>
              <p className="mt-2 text-sm leading-6 text-zinc-400">
                这条队列来自早期状态演练，只能验证按钮状态，不能代表真实视频生成。请使用上方主按钮，把它切换成慧梦真实单镜队列。
              </p>
            </section>
          )}

          <TechDetails className="mt-6" title="可选：查看任务状态">
            {job && (
              <section className="border border-white/15 bg-[#151b21] p-4">
                <p className="text-sm">
                  费用信息：{job.tasks.length} 镜头｜{job.total_seconds} 秒｜
                  {jobProviderName}｜
                  {job.cost_estimate_status === "estimated" &&
                  job.estimated_cost !== null
                    ? `预计 ${job.estimated_cost} ${job.currency}`
                    : "无法可靠估价，请人工核对"}
                </p>
                {job.cost_estimate_note && (
                  <p className="mt-2 text-xs leading-5 text-zinc-500">
                    {job.cost_estimate_note}
                  </p>
                )}
                {job.cost_source_url && (
                  <a
                    className="mt-2 inline-block text-xs text-cyan-300 hover:text-cyan-200"
                    href={job.cost_source_url}
                    target="_blank"
                    rel="noreferrer"
                  >
                    查看价格来源
                  </a>
                )}
              </section>
            )}
            <p className="mt-5 border border-white/10 bg-black/10 px-4 py-3 text-xs leading-5 text-zinc-400">
              当前使用“{channelNames[submissionChannel]}
              ”路线。其他通道的问题不会阻止当前批次，也不需要同时处理。
              {submissionChannelFromProviderMode(
                localEnv?.video_provider_mode,
              ) !== submissionChannel
                ? ` 当前全局默认是${channelNames[submissionChannelFromProviderMode(localEnv?.video_provider_mode)]}，本批次仍保持独立选择。`
                : ""}
            </p>
            {preview && (
              <section className="mt-5 border border-white/10 bg-black/10 p-4">
                <p className="text-sm text-emerald-300">
                  已生成发送前预览，未发送网络请求
                </p>
                {preview.missing_items.map((item) => (
                  <p key={item} className="mt-1 text-xs text-red-300">
                    {item}
                  </p>
                ))}
                {Boolean(preview.canonical_request.prompt_optimization) && (
                  <div className="mt-4 grid gap-3 lg:grid-cols-2">
                    <div className="border border-white/10 bg-[#12181d] p-3">
                      <b className="text-xs text-zinc-300">
                        导演原始提示词（未覆盖）
                      </b>
                      <p className="mt-2 max-h-52 overflow-y-auto whitespace-pre-wrap text-xs leading-5 text-zinc-400">
                        {String(preview.canonical_request.source_prompt ?? "")}
                      </p>
                    </div>
                    <div className="border border-cyan-400/25 bg-cyan-400/5 p-3">
                      <b className="text-xs text-cyan-200">
                        Seedance 2.5 后台优化结果
                      </b>
                      <p className="mt-1 text-[11px] text-zinc-500">
                        内置确定性规则，不调用外部 AI，不发送网络请求
                      </p>
                      <p className="mt-2 max-h-52 overflow-y-auto whitespace-pre-wrap text-xs leading-5 text-zinc-300">
                        {String(preview.mapped_request_preview.prompt ?? "")}
                      </p>
                    </div>
                  </div>
                )}
                <pre className="mt-3 max-h-80 overflow-x-auto text-xs leading-5 text-zinc-400">
                  {JSON.stringify(preview.mapped_request_preview, null, 2)}
                </pre>
              </section>
            )}

            <section className="mt-5 space-y-3">
              {job?.tasks.map((task) => {
                const live = readiness[task.id];
                const cli = jimengReadiness[task.id];
                const canPoll =
                  isHuimeng &&
                  task.external_provider === "huimeng_live" &&
                  ["submitted", "processing"].includes(task.status);
                const canDownload =
                  isHuimeng &&
                  task.external_provider === "huimeng_live" &&
                  task.status === "completed";
                const canJimengPoll = Boolean(
                  task.external_provider === "jimeng_cli" &&
                  task.external_task_id &&
                  ["verifying", "submitted", "processing"].includes(
                    task.status,
                  ),
                );
                const canJimengDownload = Boolean(
                  task.external_provider === "jimeng_cli" &&
                  task.external_task_id &&
                  task.status === "completed",
                );
                return (
                  <article
                    key={task.id}
                    className="grid grid-cols-[150px_1fr_430px] gap-4 border border-white/15 bg-[#151b21] p-4"
                  >
                    <div className="space-y-3">
                      {task.storyboard_url ? (
                        <div>
                          <p
                            className={`mb-1 text-[11px] ${task.storyboard_reference_status === "history" ? "text-red-300" : "text-zinc-500"}`}
                          >
                            {task.storyboard_reference_status === "history"
                              ? "本次已提交参考（错误）"
                              : "本次任务参考"}
                          </p>
                          <img
                            className="aspect-video w-full border border-white/10 grayscale"
                            src={assetImageUrl(task.storyboard_url)}
                          />
                        </div>
                      ) : (
                        <div />
                      )}
                      {task.storyboard_reference_status === "history" &&
                      task.current_storyboard_url ? (
                        <div>
                          <p className="mb-1 text-[11px] text-emerald-300">
                            当前正式故事板
                          </p>
                          <img
                            className="aspect-video w-full border border-emerald-400/30 grayscale"
                            src={assetImageUrl(task.current_storyboard_url)}
                          />
                        </div>
                      ) : null}
                    </div>
                    <div>
                      <b className="text-orange-300">{task.shot_code}</b>
                      <p className="mt-2 text-sm">
                        状态：{versionStateName(task.status)}
                      </p>
                      {task.storyboard_reference_note ? (
                        <p
                          className={`mt-2 text-xs leading-5 ${task.storyboard_reference_status === "history" ? "text-red-200" : "text-zinc-500"}`}
                        >
                          {task.storyboard_reference_note}
                        </p>
                      ) : null}
                      {task.missing_items.map((item) => (
                        <p key={item} className="mt-1 text-xs text-red-300">
                          {humanizeCopy(item)}
                        </p>
                      ))}
                      {task.error_message && (
                        <p className="text-xs text-red-300">
                          {humanizeCopy(task.error_message)}
                        </p>
                      )}
                      {submissionChannel === "huimeng" && isHuimeng && (
                        <p className="mt-2 text-xs text-amber-200">
                          当前路线：慧梦 API｜单镜 / 1-15 秒 / 720p / 手动确认
                        </p>
                      )}
                      {submissionChannel === "huimeng" &&
                        isHuimeng &&
                        live &&
                        !live.ready && (
                          <p className="mt-2 text-xs text-red-200">
                            暂不可提交：
                            {live.gate_items
                              .filter(
                                (item) =>
                                  !item.passed &&
                                  !derivedGateLabels.has(item.label),
                              )
                              .map((item) => humanizeCopy(item.label))
                              .join(" / ")}
                          </p>
                        )}
                      {submissionChannel === "huimeng" &&
                        isHuimeng &&
                        live?.ready && (
                          <p className="mt-2 text-xs text-emerald-300">
                            慧梦 API 条件已通过，仍需弹窗确认。
                          </p>
                        )}
                      {submissionChannel === "jimeng" && cli && !cli.ready && (
                        <p className="mt-2 text-xs text-amber-200">
                          即梦 CLI 暂不可提交：
                          {cli.gate_items
                            .filter(
                              (item) =>
                                !item.passed &&
                                !derivedGateLabels.has(item.label),
                            )
                            .map((item) => humanizeCopy(item.label))
                            .join(" / ")}
                        </p>
                      )}
                      {submissionChannel === "jimeng" && cli?.ready && (
                        <p className="mt-2 text-xs text-emerald-300">
                          即梦 CLI 已就绪：可用当前提示词提交。
                        </p>
                      )}
                    </div>
                    <div className="flex flex-wrap content-start gap-2">
                      <button
                        className={button}
                        disabled={busy}
                        onClick={() => {
                          setBusy(true);
                          setBusyMessage("正在生成发送前预览…");
                          void previewProviderRequest(task.id)
                            .then(setPreview)
                            .catch((cause: Error) => setError(cause.message))
                            .finally(() => {
                              setBusy(false);
                              setBusyMessage("");
                            });
                        }}
                      >
                        <Eye size={13} />
                        查看发送前预览
                      </button>
                      {isLegacyDebugJob && (
                        <p className="w-full border border-amber-400/25 bg-amber-400/8 px-3 py-2 text-xs leading-5 text-amber-100">
                          这是旧开发队列，状态演练已停用。请重新创建真实服务队列。
                        </p>
                      )}
                      {submissionChannel === "huimeng" && isHuimeng && (
                        <>
                          <button
                            disabled={busy || !live?.ready}
                            className={button}
                            onClick={() => void confirmLiveSubmit(task, live)}
                          >
                            <Play size={13} />
                            慧梦真实提交
                          </button>
                          {canPoll && (
                            <button
                              className={button}
                              disabled={busy}
                              onClick={() => void confirmLivePoll(task)}
                            >
                              <SearchCheckIcon />
                              查询状态
                            </button>
                          )}
                          {canDownload && (
                            <button
                              className={button}
                              disabled={busy}
                              onClick={() => void confirmLiveDownload(task)}
                            >
                              <Download size={13} />
                              下载结果
                            </button>
                          )}
                        </>
                      )}
                      {submissionChannel === "jimeng" && (
                        <>
                          {task.storyboard_reference_status === "history" &&
                          !task.external_task_id ? (
                            <button
                              className={button}
                              disabled={busy}
                              onClick={() =>
                                run(
                                  () => prepareJimengCliRetry(task.id),
                                  `正在把 ${task.shot_code} 换绑到当前正式故事板…`,
                                )
                              }
                            >
                              <RefreshCw size={13} />
                              换绑当前正式故事板
                            </button>
                          ) : null}
                          <button
                            disabled={busy || !cli?.ready}
                            className={button}
                            onClick={() => void confirmJimengSubmit(task, cli)}
                          >
                            <Play size={13} />
                            即梦 CLI 提交
                          </button>
                          {canJimengPoll && (
                            <button
                              className={button}
                              disabled={busy}
                              onClick={() => void confirmJimengPoll(task)}
                            >
                              <SearchCheckIcon />
                              即梦查询
                            </button>
                          )}
                          {canJimengDownload && (
                            <button
                              className={button}
                              disabled={busy}
                              onClick={() => void confirmJimengDownload(task)}
                            >
                              <Download size={13} />
                              即梦下载
                            </button>
                          )}
                        </>
                      )}
                      <label
                        className={`${button} ${busy ? "pointer-events-none opacity-40" : ""}`}
                      >
                        <Upload size={13} />
                        导入 MP4/MOV
                        <input
                          hidden
                          type="file"
                          accept=".mp4,.mov"
                          onChange={(event) => {
                            const file = event.target.files?.[0];
                            if (file)
                              run(
                                () => importTaskVideo(task.id, file),
                                `正在导入 ${task.shot_code} 的视频结果…`,
                              );
                          }}
                        />
                      </label>
                    </div>
                  </article>
                );
              })}
            </section>
          </TechDetails>
        </>
      ) : null}
    </div>
  );
}

function seedance25ReferencePurpose(
  role: string | undefined,
  mediaType: "image" | "video" | "audio",
): VideoReferenceItemUpdate["purpose"] {
  if (mediaType === "audio") return "sound";
  if (mediaType === "video") return "action";
  if (role === "character") return "subject";
  if (role === "product" || role === "prop_detail") return "product";
  if (role === "storyboard") return "camera";
  return "environment";
}

export function BatchProductionWorkbench({
  job,
  models,
  submissionChannel,
  supervisorStatus,
  monitorError,
  busy,
  expectedTaskCount,
  onRebuildBatch,
  onConfirmAllBindings,
  onConfirmTask,
  onSaveBindings,
  onResetBindings,
  onModelChange,
  onBatchModelChange,
  onGenerationSettingsChange,
  onConfirmCost,
  onLaunch,
  onRetry,
  onReview,
  onApproveAll,
  onImport,
}: {
  job: BatchJob;
  models: VideoProviderModel[];
  submissionChannel: SubmissionChannel;
  supervisorStatus: VideoTaskSupervisorStatus | null;
  monitorError: string;
  busy: boolean;
  expectedTaskCount: number;
  onRebuildBatch: () => void;
  onConfirmAllBindings: () => void;
  onConfirmTask: (task: BatchTask) => void;
  onSaveBindings: (task: BatchTask, assetIds: string[]) => void;
  onResetBindings: (task: BatchTask) => void;
  onModelChange: (task: BatchTask, modelId: string) => void;
  onBatchModelChange: (modelId: string) => void;
  onGenerationSettingsChange: (settings: VideoGenerationSettings) => void;
  onConfirmCost: () => void;
  onLaunch: () => void;
  onRetry: (task: BatchTask) => void;
  onReview: (task: BatchTask, decision: "confirm" | "redo") => void;
  onApproveAll: () => void;
  onImport: (task: BatchTask, file: File) => void;
}) {
  const [view, setView] = useState<"references" | "monitor" | "review">(
    job.batch_authorized ? "monitor" : "references",
  );
  useEffect(() => {
    if (job.status === "awaiting_review" || job.status === "completed")
      setView("review");
    else if (job.batch_authorized) setView("monitor");
    else if (
      [
        "blocked",
        "awaiting_budget_confirm",
        "ready",
        "partial_failed",
      ].includes(job.status)
    )
      setView("references");
  }, [job.status, job.batch_authorized]);

  const editable =
    !job.batch_authorized && job.tasks.every((task) => !task.external_task_id);
  const taskIsPreserved = (task: BatchTask) =>
    Boolean(task.external_task_id) ||
    ["imported", "mock_completed"].includes(task.status);
  const taskBindingSatisfied = (task: BatchTask) =>
    Boolean(task.reference_bindings_confirmed) || taskIsPreserved(task);
  const taskIsEditable = (task: BatchTask) =>
    !job.batch_authorized &&
    !task.external_task_id &&
    ["blocked", "awaiting_budget_confirm", "ready"].includes(task.status);
  const confirmedBindings = job.tasks.filter(taskBindingSatisfied).length;
  const blocked = job.tasks.filter(
    (task) => task.missing_items.length > 0 || task.status === "blocked",
  );
  const running = job.tasks.filter((task) =>
    ["verifying", "submitted", "processing", "completed"].includes(task.status),
  ).length;
  const failed = job.tasks.filter((task) => task.status === "failed").length;
  const saved = job.tasks.filter((task) => task.status === "imported").length;
  const mocked = job.tasks.filter(
    (task) => task.status === "mock_completed",
  ).length;
  const approved = job.tasks.filter(
    (task) => task.results.at(-1)?.status === "confirmed",
  ).length;
  const waitingReview = job.tasks.filter(
    (task) =>
      task.status === "imported" && task.results.at(-1)?.status !== "confirmed",
  );
  const allBindingsConfirmed =
    confirmedBindings === job.tasks.length && !blocked.length;
  const pendingBindingCount = job.tasks.filter(
    (task) => !taskBindingSatisfied(task),
  ).length;
  const awaitingAuthorization =
    !job.batch_authorized &&
    job.tasks.some((task) =>
      ["awaiting_budget_confirm", "ready"].includes(task.status),
    );
  const awaitingAuthorizationCount = job.tasks.filter((task) =>
    ["awaiting_budget_confirm", "ready"].includes(task.status),
  ).length;
  const preservedResultCount = job.tasks.filter((task) =>
    ["imported", "mock_completed"].includes(task.status),
  ).length;
  const firstCanonical = job.tasks[0]?.canonical_request ?? {};
  const batchModel = String(
    firstCanonical.provider_model_id ??
      (firstCanonical.provider_options as Record<string, unknown> | undefined)
        ?.jimeng_model_version ??
      "",
  );
  const durationMode = String(firstCanonical.duration_mode ?? "smart") as
    | "smart"
    | "specified";
  const durationSeconds = Number(firstCanonical.duration_seconds ?? 8);
  const resolution = String(firstCanonical.resolution ?? "720p") as
    | "480p"
    | "720p";
  const promptOptimization = firstCanonical.prompt_optimization as
    | Record<string, unknown>
    | undefined;
  const promptOptimizationEnabled = promptOptimization?.enabled !== false;
  const hasRunningTask = job.tasks.some(
    (task) =>
      Boolean(task.external_task_id) ||
      ["verifying", "submitted", "processing", "completed"].includes(
        task.status,
      ),
  );
  const needsBatchUpgrade =
    expectedTaskCount > job.tasks.length && !hasRunningTask;
  const selectedModel = models.find((model) => model.id === batchModel);
  const missingSelectedModel = Boolean(batchModel) && !selectedModel;
  const goToReferenceReview = () => {
    setView("references");
    window.requestAnimationFrame(() => {
      document
        .getElementById("batch-reference-review-start")
        ?.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  };

  return (
    <section className="mt-6 space-y-5">
      <section
        className="border border-cyan-400/30 bg-cyan-400/5 p-4"
        aria-label="本次生成配置"
      >
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-xs font-semibold tracking-[.14em] text-cyan-300">
              本次生成配置
            </p>
            <h2 className="mt-1 text-lg font-semibold text-zinc-100">
              视频模型
            </h2>
            <p className="mt-1 text-sm text-zinc-400">
              模型在付费提交前可自主选择；任务派发后继续展示，但会锁定以保护历史任务。
            </p>
          </div>

          {models.length ? (
            <label className="min-w-[18rem] text-xs text-zinc-400">
              本批次视频模型
              <select
                aria-label="本批次视频模型"
                className="mt-1 block w-full border border-white/15 bg-[#11171c] px-3 py-2 text-sm text-zinc-100"
                value={batchModel}
                disabled={!editable || busy}
                onChange={(event) => onBatchModelChange(event.target.value)}
              >
                {missingSelectedModel ? (
                  <option value={batchModel}>
                    {batchModel}（当前任务模型，目录中不可用）
                  </option>
                ) : null}
                {models.map((model) => (
                  <option
                    key={model.id}
                    value={model.id}
                    disabled={model.available === false}
                  >
                    {model.label}
                    {model.mock_only || model.is_mock_only ? "（模拟）" : ""}
                  </option>
                ))}
              </select>
              {selectedModel?.capability_source ||
              models[0]?.capability_source ? (
                <span className="mt-1 block text-zinc-500">
                  能力来源：
                  {selectedModel?.capability_source ??
                    models[0].capability_source}
                  {selectedModel?.cli_version || models[0]?.cli_version
                    ? `｜CLI ${selectedModel?.cli_version ?? models[0].cli_version}`
                    : ""}
                </span>
              ) : null}
              {!editable ? (
                <span className="mt-2 block text-amber-300">
                  {hasRunningTask
                    ? "任务已提交，模型已锁定，不能修改正在查询或生成的任务。"
                    : "本批次已授权，模型已锁定；结束后重建队列即可重新选择。"}
                </span>
              ) : null}
            </label>
          ) : (
            <div
              className="min-w-[18rem] border border-red-400/35 bg-red-400/8 px-4 py-3 text-sm text-red-100"
              role="alert"
            >
              <b className="block">模型目录未加载</b>
              <span className="mt-1 block text-xs text-red-200">
                当前无法可靠选择模型，请检查后端服务并刷新页面后重试；系统不会隐藏问题或自动降级模型。
              </span>
            </div>
          )}
        </div>

        {submissionChannel === "volcengine_seedance25" ? (
          <div className="mt-4 flex flex-wrap items-end gap-3 border-t border-white/10 pt-4">
            <label className="text-xs text-zinc-400">
              时长方式
              <select
                className="mt-1 block border border-white/15 bg-[#11171c] px-3 py-2 text-sm"
                value={durationMode}
                disabled={!editable || busy}
                onChange={(event) =>
                  onGenerationSettingsChange({
                    duration_mode: event.target.value as "smart" | "specified",
                    duration_seconds:
                      event.target.value === "smart" ? null : durationSeconds,
                  })
                }
              >
                <option value="smart">智能时长（官方智能值）</option>
                <option value="specified">指定时长</option>
              </select>
            </label>
            {durationMode === "specified" ? (
              <label className="text-xs text-zinc-400">
                秒数
                <input
                  className="mt-1 block w-24 border border-white/15 bg-[#11171c] px-3 py-2 text-sm"
                  type="number"
                  min={4}
                  max={30}
                  value={durationSeconds}
                  disabled={!editable || busy}
                  onChange={(event) =>
                    onGenerationSettingsChange({
                      duration_mode: "specified",
                      duration_seconds: Number(event.target.value),
                    })
                  }
                />
              </label>
            ) : null}
            <label className="text-xs text-zinc-400">
              分辨率
              <select
                className="mt-1 block border border-white/15 bg-[#11171c] px-3 py-2 text-sm"
                value={resolution}
                disabled={!editable || busy}
                onChange={(event) =>
                  onGenerationSettingsChange({
                    resolution: event.target.value as "480p" | "720p",
                  })
                }
              >
                <option value="720p">720p（默认）</option>
                <option value="480p">480p</option>
              </select>
            </label>
            <label className="flex min-h-10 items-center gap-2 border border-cyan-400/25 bg-cyan-400/5 px-3 text-xs text-cyan-100">
              <input
                type="checkbox"
                checked={promptOptimizationEnabled}
                disabled={!editable || busy}
                onChange={(event) =>
                  onGenerationSettingsChange({
                    prompt_optimization_enabled: event.target.checked,
                  })
                }
              />
              自动优化 2.5 提示词
            </label>
          </div>
        ) : null}
      </section>

      <div className="grid grid-cols-3 border border-white/12 bg-[#12181d] p-1">
        {(
          [
            [
              "references",
              "1 参考检查",
              `${confirmedBindings}/${job.tasks.length} 已确认`,
            ],
            [
              "monitor",
              "2 生产监控",
              submissionChannel === "volcengine_seedance25"
                ? `${running} 运行 / ${mocked} 模拟完成`
                : `${running} 运行 / ${saved} 已保存`,
            ],
            ["review", "3 结果验收", `${approved}/${job.tasks.length} 已通过`],
          ] as const
        ).map(([key, label, detail]) => (
          <button
            key={key}
            type="button"
            onClick={() => setView(key)}
            className={`min-h-16 px-4 py-2 text-left transition ${view === key ? "bg-orange-500 text-black" : "text-zinc-300 hover:bg-white/5"}`}
          >
            <b className="block text-sm">{label}</b>
            <span
              className={`mt-1 block text-xs ${view === key ? "text-black/65" : "text-zinc-500"}`}
            >
              {detail}
            </span>
          </button>
        ))}
      </div>

      <div className="grid gap-3 md:grid-cols-6">
        <BatchMetric label="批次状态" value={batchStatusLabel(job.status)} />
        <BatchMetric label="镜头" value={`${job.tasks.length} 个`} />
        <BatchMetric label="总时长" value={`${job.total_seconds} 秒`} />
        <BatchMetric
          label="后台运行"
          value={supervisorStatus?.running ? "正常" : "未运行"}
          tone={supervisorStatus?.running ? "good" : "bad"}
        />
        <BatchMetric
          label="失败"
          value={`${failed} 个`}
          tone={failed ? "bad" : undefined}
        />
        <BatchMetric
          label="已通过"
          value={`${approved} 个`}
          tone={approved === job.tasks.length ? "good" : undefined}
        />
      </div>

      {monitorError ? (
        <p className="border border-red-400/35 bg-red-400/8 px-4 py-3 text-sm text-red-200">
          后台监控暂时异常：{humanizeCopy(monitorError)}
        </p>
      ) : null}

      {awaitingAuthorization ? (
        <section
          className="border border-orange-400/55 bg-orange-400/8 p-5"
          aria-label="批次恢复后的下一步"
        >
          <div className="flex flex-wrap items-center justify-between gap-5">
            <div className="max-w-4xl">
              <p className="text-xs font-semibold tracking-[.14em] text-orange-300">
                恢复已完成，等待重新授权
              </p>
              <h2 className="mt-2 text-xl font-semibold text-zinc-100">
                生产尚未重新启动，当前没有向服务商提交新任务
              </h2>
              <p className="mt-2 text-sm leading-6 text-zinc-300">
                {awaitingAuthorizationCount}{" "}
                个镜头已保留提示词和参考绑定，正在等待本批费用确认。
                {preservedResultCount
                  ? ` 已保存的 ${preservedResultCount} 个镜头会继续保留，不会重复生成或重复扣费。`
                  : ""}
              </p>
              <p className="mt-2 text-xs text-zinc-500">
                费用确认只解除本地队列门禁；点击随后出现的“一键继续后台生产”后，后台才会按顺序真实提交。
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              {!allBindingsConfirmed || blocked.length ? (
                <button
                  className="inline-flex items-center gap-2 bg-orange-500 px-5 py-3 text-sm font-semibold text-black disabled:opacity-35"
                  disabled={busy}
                  onClick={goToReferenceReview}
                >
                  <SearchCheckIcon />
                  去检查并确认参考绑定
                </button>
              ) : !job.budget_confirmed ? (
                <button
                  className="inline-flex items-center gap-2 bg-orange-500 px-5 py-3 text-sm font-semibold text-black disabled:opacity-35"
                  disabled={busy}
                  onClick={onConfirmCost}
                >
                  <CheckCircle2 size={16} />
                  确认费用风险并继续
                </button>
              ) : (
                <button
                  className="inline-flex items-center gap-2 bg-orange-500 px-5 py-3 text-sm font-semibold text-black disabled:opacity-35"
                  disabled={busy}
                  onClick={onLaunch}
                >
                  <Play size={16} />
                  一键继续后台生产
                </button>
              )}
              {view !== "references" ? (
                <button
                  className={button}
                  disabled={busy}
                  onClick={() => setView("references")}
                >
                  查看本批参考绑定
                </button>
              ) : null}
            </div>
          </div>
        </section>
      ) : null}

      {needsBatchUpgrade ? (
        <div className="flex flex-wrap items-center justify-between gap-4 border border-orange-400/45 bg-orange-400/8 p-5">
          <div>
            <b className="text-orange-200">当前仍是旧单镜头队列</b>
            <p className="mt-2 text-sm text-zinc-300">
              本场还有 {expectedTaskCount} 个未验收镜头，当前队列只有{" "}
              {job.tasks.length}{" "}
              个。升级操作只重建本地队列，不会提交服务商或产生费用。
            </p>
          </div>
          <button
            className="bg-orange-500 px-5 py-3 text-sm font-semibold text-black disabled:opacity-35"
            disabled={busy}
            onClick={onRebuildBatch}
          >
            升级为本场批量队列
          </button>
        </div>
      ) : null}

      {view === "references" ? (
        <div
          id="batch-reference-review-start"
          className="scroll-mt-24 space-y-4"
        >
          <div className="flex flex-wrap items-end justify-between gap-4 border border-cyan-400/25 bg-cyan-400/5 p-4">
            <div>
              <h2 className="text-xl font-semibold">全镜头全能参考纵览</h2>
              <p className="mt-2 text-sm text-zinc-400">
                统一核对故事板、人物、场景和产品的
                @图片顺序。修改模型、提示词、时长或资产后，对应确认会自动失效。
              </p>
            </div>
          </div>

          {blocked.length ? (
            <div className="border border-red-400/40 bg-red-400/8 p-4 text-sm text-red-100">
              <b>
                有 {blocked.length}{" "}
                个镜头存在阻塞，整批启动不会发出任何付费请求。
              </b>
              <p className="mt-2 text-xs text-red-200">
                请在下方对应镜头处理红色问题后，再统一确认绑定。
              </p>
            </div>
          ) : null}

          <div className="space-y-3">
            {job.tasks.map((task) => (
              <BatchReferenceTask
                key={task.id}
                task={task}
                models={models}
                editable={taskIsEditable(task)}
                busy={busy}
                submissionChannel={submissionChannel}
                onConfirm={() => onConfirmTask(task)}
                onSave={(ids) => onSaveBindings(task, ids)}
                onReset={() => onResetBindings(task)}
                onModelChange={(modelId) => onModelChange(task, modelId)}
              />
            ))}
          </div>

          <div
            id="batch-launch-actions"
            className="sticky bottom-3 z-10 flex scroll-mt-24 flex-wrap items-center justify-between gap-4 border border-orange-400/40 bg-[#171714] p-4 shadow-2xl"
          >
            <div>
              <b className="text-orange-200">启动前检查</b>
              <p className="mt-1 text-xs text-zinc-400">
                绑定 {confirmedBindings}/{job.tasks.length}｜费用风险{" "}
                {job.budget_confirmed ? "已确认" : "待确认"}｜阻塞{" "}
                {blocked.length}
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              {blocked.length ? (
                <button
                  className="inline-flex items-center gap-2 bg-orange-500 px-5 py-3 text-sm font-semibold text-black disabled:opacity-35"
                  disabled={busy}
                  onClick={() =>
                    document
                      .getElementById(`batch-task-${blocked[0].id}`)
                      ?.scrollIntoView({ behavior: "smooth", block: "center" })
                  }
                >
                  <SearchCheckIcon />
                  定位并处理 {blocked.length} 个阻塞
                </button>
              ) : !allBindingsConfirmed ? (
                <button
                  className="inline-flex items-center gap-2 bg-orange-500 px-5 py-3 text-sm font-semibold text-black disabled:opacity-35"
                  disabled={busy || pendingBindingCount === 0}
                  onClick={onConfirmAllBindings}
                >
                  <CheckCircle2 size={15} />
                  确认剩余 {pendingBindingCount} 个镜头绑定
                </button>
              ) : !job.budget_confirmed ? (
                <button
                  className="inline-flex items-center gap-2 bg-orange-500 px-5 py-3 text-sm font-semibold text-black disabled:opacity-35"
                  disabled={busy}
                  onClick={onConfirmCost}
                >
                  <CheckCircle2 size={15} />
                  {job.estimated_cost === null
                    ? "确认整批费用风险"
                    : "确认整批预计费用"}
                </button>
              ) : (
                <button
                  className="inline-flex items-center gap-2 bg-orange-500 px-5 py-3 text-sm font-semibold text-black disabled:opacity-35"
                  disabled={busy || Boolean(job.batch_authorized)}
                  onClick={onLaunch}
                >
                  <Play size={16} />
                  一键启动全部镜头
                </button>
              )}
            </div>
          </div>
        </div>
      ) : null}

      {view === "monitor" ? (
        <div className="space-y-4">
          <div
            className={`border p-5 ${awaitingAuthorization ? "border-orange-400/35 bg-orange-400/5" : "border-cyan-400/25 bg-cyan-400/5"}`}
          >
            <h2 className="text-xl font-semibold">后台生产监控</h2>
            <p className="mt-2 text-sm text-zinc-400">
              {awaitingAuthorization
                ? "当前批次处于安全暂停状态，后台监督器仍在运行，但不会绕过费用授权提交新任务。请使用上方橙色主操作继续。"
                : "后台按受控顺序派发并自动查询、下载。切换页面或关闭当前页面不会中断；这里只展示服务商实际状态，不伪造百分比。"}
            </p>
            <p
              className={`mt-3 text-sm ${awaitingAuthorization ? "text-orange-200" : "text-cyan-200"}`}
            >
              运行中 {running}｜已保存 {saved}｜失败 {failed}｜等待授权{" "}
              {awaitingAuthorizationCount}｜等待派发{" "}
              {
                job.tasks.filter(
                  (task) => task.status === "ready" && !task.external_task_id,
                ).length
              }
            </p>
          </div>
          <div className="space-y-3">
            {job.tasks.map((task) => (
              <BatchMonitorTask
                key={task.id}
                task={task}
                busy={busy}
                onRetry={() => onRetry(task)}
                onImport={(file) => onImport(task, file)}
              />
            ))}
          </div>
        </div>
      ) : null}

      {view === "review" ? (
        <div className="space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-4 border border-emerald-400/25 bg-emerald-400/5 p-5">
            <div>
              <h2 className="text-xl font-semibold">集中预览与验收</h2>
              <p className="mt-2 text-sm text-zinc-400">
                完整播放后逐条通过或标记重做。重做只影响当前镜头，旧视频和审核记录都会保留。
              </p>
            </div>
            <button
              className={button}
              disabled={busy || !waitingReview.length}
              onClick={onApproveAll}
            >
              <CheckCircle2 size={15} />
              批量通过全部待验收视频
            </button>
          </div>
          <div className="grid gap-4 xl:grid-cols-2">
            {job.tasks.map((task) => (
              <BatchReviewTask
                key={task.id}
                task={task}
                busy={busy}
                onReview={(decision) => onReview(task, decision)}
                onRetry={() => onRetry(task)}
              />
            ))}
          </div>
        </div>
      ) : null}
    </section>
  );
}

function BatchMetric({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone?: "good" | "bad";
}) {
  return (
    <div className="border border-white/12 bg-[#12181d] p-3">
      <span className="text-xs text-zinc-500">{label}</span>
      <b
        className={`mt-1 block text-sm ${tone === "good" ? "text-emerald-300" : tone === "bad" ? "text-red-300" : "text-zinc-100"}`}
      >
        {value}
      </b>
    </div>
  );
}

function batchStatusLabel(status: string) {
  return (
    (
      {
        draft: "待检查",
        blocked: "待检查",
        awaiting_budget_confirm: "待授权",
        ready: "待授权",
        dispatching: "后台生产中",
        processing: "后台生产中",
        partial_failed: "部分失败",
        awaiting_review: "待验收",
        completed: "已完成",
        mock_completed: "Mock 链路验收完成",
      } as Record<string, string>
    )[status] ?? versionStateName(status)
  );
}

function BatchReferenceTask({
  task,
  models,
  editable,
  busy,
  submissionChannel,
  onConfirm,
  onSave,
  onReset,
  onModelChange,
}: {
  task: BatchTask;
  models: VideoProviderModel[];
  editable: boolean;
  busy: boolean;
  submissionChannel: SubmissionChannel;
  onConfirm: () => void;
  onSave: (ids: string[]) => void;
  onReset: () => void;
  onModelChange: (modelId: string) => void;
}) {
  const preservedResult =
    Boolean(task.external_task_id) ||
    ["imported", "mock_completed"].includes(task.status);
  const bindingSatisfied =
    Boolean(task.reference_bindings_confirmed) || preservedResult;
  const bindingLabel = task.reference_bindings_confirmed
    ? "绑定已确认"
    : preservedResult
      ? "已有结果，保留原绑定"
      : "绑定待确认";
  const [editing, setEditing] = useState(false);
  const [ids, setIds] = useState<string[]>(
    task.reference_bindings?.map((item) => item.asset_id) ?? [],
  );
  useEffect(
    () => setIds(task.reference_bindings?.map((item) => item.asset_id) ?? []),
    [task.id, task.reference_bindings],
  );
  const modelId = String(
    task.canonical_request.provider_model_id ??
      (
        task.canonical_request.provider_options as
          | Record<string, unknown>
          | undefined
      )?.jimeng_model_version ??
      "",
  );
  const promptOptimization = task.canonical_request.prompt_optimization as
    | Record<string, unknown>
    | undefined;
  const maxImages = submissionChannel === "volcengine_seedance25" ? 30 : 9;
  const move = (index: number, offset: number) =>
    setIds((current) => {
      const next = [...current];
      const target = index + offset;
      if (target < 0 || target >= next.length) return current;
      [next[index], next[target]] = [next[target], next[index]];
      return next;
    });
  const candidates = task.reference_candidates ?? [];
  const mediaTypeFor = (id: string) =>
    candidates.find((candidate) => candidate.asset_id === id)?.media_type ??
    task.reference_bindings?.find((binding) => binding.asset_id === id)
      ?.media_type ??
    "image";
  const tokenFor = (id: string, position: number) => {
    const mediaType = mediaTypeFor(id);
    const index = ids
      .slice(0, position + 1)
      .filter((item) => mediaTypeFor(item) === mediaType).length;
    return `@${mediaType === "video" ? "视频" : mediaType === "audio" ? "音频" : "图片"}${index}`;
  };
  const canAdd = (candidate: VideoReferenceCandidate) => {
    const mediaType = candidate.media_type ?? "image";
    const count = ids.filter((id) => mediaTypeFor(id) === mediaType).length;
    const limit = mediaType === "image" ? maxImages : 10;
    return (
      ids.length <
        (submissionChannel === "volcengine_seedance25" ? 50 : maxImages) &&
      count < limit
    );
  };
  return (
    <article
      id={`batch-task-${task.id}`}
      className={`scroll-mt-24 border p-4 ${task.missing_items.length ? "border-red-400/35 bg-red-400/5" : bindingSatisfied ? "border-emerald-400/30 bg-emerald-400/5" : "border-white/15 bg-[#141a20]"}`}
    >
      <div className="grid gap-4 lg:grid-cols-[180px_1fr_auto]">
        <div>
          {task.storyboard_url ? (
            <img
              className="aspect-video w-full border border-white/10 object-cover grayscale"
              src={assetImageUrl(task.storyboard_url)}
              alt={`${task.shot_code} 故事板`}
            />
          ) : (
            <div className="flex aspect-video items-center justify-center border border-red-400/30 text-xs text-red-200">
              缺少故事板
            </div>
          )}
        </div>
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <b className="text-orange-300">{task.shot_code}</b>
            <span
              className={`text-xs ${bindingSatisfied ? "text-emerald-300" : "text-amber-200"}`}
            >
              {bindingLabel}
            </span>
          </div>
          <p className="mt-2 line-clamp-2 text-sm leading-6 text-zinc-300">
            {String(
              task.canonical_request.prompt ??
                task.provider_prompt_preview ??
                "暂无提示词",
            )}
          </p>
          {submissionChannel === "volcengine_seedance25" ? (
            <div
              className={`mt-2 border px-3 py-2 text-xs ${promptOptimization?.enabled === false ? "border-amber-400/30 text-amber-200" : "border-cyan-400/25 text-cyan-200"}`}
            >
              <b>
                {promptOptimization?.enabled === false
                  ? "自动优化已关闭"
                  : "自动优化已启用"}
              </b>
              <span className="ml-2 text-zinc-500">
                {String(promptOptimization?.rule_id ?? "sd25-pe-compatible")}｜
                {String(promptOptimization?.rule_version ?? "builtin-v1")}
              </span>
              {Array.isArray(promptOptimization?.warnings) &&
                promptOptimization.warnings.map((warning) => (
                  <p key={String(warning)} className="mt-1 text-amber-200">
                    {String(warning)}
                  </p>
                ))}
            </div>
          ) : null}
          <p className="mt-2 text-xs text-zinc-500">
            {task.canonical_request.duration_mode === "smart"
              ? "智能时长"
              : `${String(task.canonical_request.duration_seconds ?? "?")} 秒`}
            ｜{String(task.canonical_request.resolution ?? "720p")}｜
            {task.reference_bindings?.length ?? 0} 个参考
          </p>
          {task.reference_binding_note ? (
            <p
              className={`mt-2 border px-3 py-2 text-xs leading-5 ${task.reference_binding_status === "historical_snapshot" ? "border-amber-400/30 bg-amber-400/5 text-amber-100" : "border-emerald-400/25 bg-emerald-400/5 text-emerald-200"}`}
            >
              {task.reference_binding_note}
            </p>
          ) : null}
          {task.missing_items.map((item) => (
            <p key={item} className="mt-2 text-xs text-red-200">
              必须处理：{humanizeCopy(item)}
            </p>
          ))}
          <div className="mt-3 flex flex-wrap gap-2">
            {task.reference_bindings?.map((binding) => (
              <div
                key={`${binding.token}-${binding.asset_id}`}
                className={`flex items-center gap-2 border bg-black/20 p-2 ${binding.version_status === "history" ? "border-amber-400/35" : "border-white/10"}`}
              >
                {binding.asset_url &&
                (binding.media_type ?? "image") === "image" ? (
                  <img
                    className="h-10 w-14 object-cover"
                    src={assetImageUrl(binding.asset_url)}
                    alt={binding.label}
                  />
                ) : (
                  <span className="flex h-10 w-14 items-center justify-center border border-white/10 text-[10px] text-zinc-400">
                    {(binding.media_type ?? "image") === "image"
                      ? "图片"
                      : binding.media_type === "audio"
                        ? "音频"
                        : "视频"}
                  </span>
                )}
                <span className="max-w-36 text-[11px]">
                  <b className="block text-cyan-300">{binding.token}</b>
                  <span className="line-clamp-1 text-zinc-400">
                    {binding.label}
                  </span>
                  <span
                    className={
                      binding.version_status === "history"
                        ? "text-amber-300"
                        : "text-emerald-400"
                    }
                  >
                    {binding.version_status === "history"
                      ? "历史提交版"
                      : "当前锁定版"}
                  </span>
                </span>
              </div>
            ))}
          </div>
        </div>
        <div className="flex min-w-48 flex-col gap-2">
          {submissionChannel === "jimeng" ||
          submissionChannel === "volcengine_seedance25" ? (
            <select
              className="border border-white/15 bg-[#11171c] px-3 py-2 text-xs"
              value={modelId}
              disabled={!editable || busy}
              onChange={(event) => onModelChange(event.target.value)}
            >
              {models.map((model) => (
                <option key={model.id} value={model.id}>
                  {model.label}
                </option>
              ))}
            </select>
          ) : null}
          <button
            className={button}
            disabled={!editable || busy}
            onClick={() => setEditing((value) => !value)}
          >
            <Settings2 size={14} />
            {editing ? "收起绑定编辑" : "修改参考绑定"}
          </button>
          <button
            className={button}
            disabled={
              !editable ||
              busy ||
              task.reference_bindings_confirmed ||
              task.missing_items.length > 0
            }
            onClick={onConfirm}
          >
            <CheckCircle2 size={14} />
            确认本镜头绑定
          </button>
        </div>
      </div>
      {editing ? (
        <div className="mt-4 border-t border-white/10 pt-4">
          <p className="text-xs text-zinc-400">
            顺序决定同类素材的 @ 编号。当前模型上限：图片 {maxImages}、视频
            10、音频 10，Seedance 2.5 合计不超过 50 个。
          </p>
          <div className="mt-3 space-y-2">
            {ids.map((id, index) => {
              const item = candidates.find(
                (candidate) => candidate.asset_id === id,
              );
              return (
                <div
                  key={`${id}-${index}`}
                  className="flex items-center gap-2 border border-white/10 p-2"
                >
                  <b className="w-16 text-xs text-cyan-300">
                    {tokenFor(id, index)}
                  </b>
                  <span className="min-w-0 flex-1 truncate text-xs">
                    {item?.label ?? id}
                  </span>
                  <span className="text-[10px] text-zinc-500">
                    {mediaTypeFor(id)}
                  </span>
                  <button
                    title="上移"
                    className={button}
                    disabled={index === 0}
                    onClick={() => move(index, -1)}
                  >
                    <ChevronUp size={13} />
                  </button>
                  <button
                    title="下移"
                    className={button}
                    disabled={index === ids.length - 1}
                    onClick={() => move(index, 1)}
                  >
                    <ChevronDown size={13} />
                  </button>
                  <button
                    className={button}
                    onClick={() =>
                      setIds((current) =>
                        current.filter((_, itemIndex) => itemIndex !== index),
                      )
                    }
                  >
                    移除
                  </button>
                </div>
              );
            })}
          </div>
          <div className="mt-3 flex flex-wrap gap-2">
            {candidates
              .filter(
                (candidate) =>
                  !ids.includes(candidate.asset_id) &&
                  (submissionChannel === "volcengine_seedance25" ||
                    (candidate.media_type ?? "image") === "image"),
              )
              .map((candidate) => (
                <button
                  key={candidate.asset_id}
                  className={button}
                  disabled={!canAdd(candidate)}
                  onClick={() =>
                    setIds((current) => [...current, candidate.asset_id])
                  }
                >
                  +{" "}
                  {candidate.media_type === "video"
                    ? "视频"
                    : candidate.media_type === "audio"
                      ? "音频"
                      : "图片"}
                  ｜{candidate.label}
                </button>
              ))}
          </div>
          <div className="mt-4 flex gap-2">
            <button
              className={button}
              disabled={!ids.length || busy}
              onClick={() => {
                onSave(ids);
                setEditing(false);
              }}
            >
              <CheckCircle2 size={14} />
              保存绑定与顺序
            </button>
            <button
              className={button}
              disabled={busy}
              onClick={() => {
                onReset();
                setEditing(false);
              }}
            >
              <RotateCcw size={14} />
              恢复自动推荐
            </button>
          </div>
        </div>
      ) : null}
    </article>
  );
}

function BatchMonitorTask({
  task,
  busy,
  onRetry,
  onImport,
}: {
  task: BatchTask;
  busy: boolean;
  onRetry: () => void;
  onImport: (file: File) => void;
}) {
  const isMock =
    task.status === "mock_completed" ||
    task.storage_status === "mock" ||
    String(task.provider_status ?? "").startsWith("mock_");
  const failure = task.error_message
    ? videoFailureGuidance(task.error_message)
    : null;
  const isUploadFailure = Boolean(
    task.error_message &&
    (task.error_message.toLowerCase().includes("applyimageupload") ||
      task.error_message.toLowerCase().includes("upload resource") ||
      task.error_message.toLowerCase().includes("context deadline exceeded")),
  );
  return (
    <article className="grid gap-4 border border-white/15 bg-[#141a20] p-4 lg:grid-cols-[120px_1fr_auto]">
      {task.storyboard_url ? (
        <img
          className="aspect-video w-full object-cover grayscale"
          src={assetImageUrl(task.storyboard_url)}
          alt={`${task.shot_code} 故事板`}
        />
      ) : (
        <div />
      )}
      <div>
        <div className="flex items-center gap-2">
          <b className="text-orange-300">{task.shot_code}</b>
          {isMock ? (
            <span className="border border-cyan-400/40 px-2 py-0.5 text-[10px] text-cyan-200">
              模拟任务｜未发送外部请求
            </span>
          ) : null}
        </div>
        <p className="mt-1 text-sm">
          {task.progress_label || versionStateName(task.status)}
        </p>
        <p className="mt-2 text-xs text-zinc-500">
          任务 ID：
          {isUploadFailure
            ? "未建立云端任务"
            : task.external_task_id || "尚未派发"}
          ｜服务商状态：{task.provider_status || task.status}｜最近同步：
          {task.updated_at
            ? new Date(task.updated_at).toLocaleString("zh-CN", {
                hour12: false,
              })
            : "尚未同步"}
        </p>
        {task.local_file_path ? (
          <p className="mt-2 break-all text-xs text-emerald-300">
            {isMock ? "Mock 验收记录" : "本地视频"}：{task.local_file_path}
          </p>
        ) : null}
        {isMock ? (
          <p className="mt-2 text-xs text-cyan-200">
            首期仅验收编译、派发、轮询和恢复链路，不生成可播放视频，也不消耗火山方舟额度。
          </p>
        ) : null}
        {task.error_message ? (
          <div className="mt-3 border border-red-400/35 bg-red-400/8 p-3 text-xs text-red-100">
            <b>
              {failure?.reason ??
                `失败原因：${humanizeCopy(task.error_message)}`}
            </b>
            <p className="mt-1 text-red-200">
              {failure?.impact ?? "本镜头没有可验收成片；其他镜头继续生产。"}
            </p>
          </div>
        ) : null}
      </div>
      <div className="flex flex-wrap content-start gap-2">
        {task.status === "failed" ? (
          <button className={button} disabled={busy} onClick={onRetry}>
            <RefreshCw size={14} />
            {isUploadFailure ? "重新上传参考图" : "修正后重试本镜头"}
          </button>
        ) : null}
        <label className={button}>
          <Upload size={14} />
          导入本地视频
          <input
            hidden
            type="file"
            accept=".mp4,.mov"
            onChange={(event) => {
              const file = event.target.files?.[0];
              if (file) onImport(file);
            }}
          />
        </label>
      </div>
    </article>
  );
}

function BatchReviewTask({
  task,
  busy,
  onReview,
  onRetry,
}: {
  task: BatchTask;
  busy: boolean;
  onReview: (decision: "confirm" | "redo") => void;
  onRetry: () => void;
}) {
  const result = task.results.at(-1);
  return (
    <article className="border border-white/15 bg-[#141a20] p-4">
      <div className="flex items-center justify-between gap-3">
        <b className="text-orange-300">{task.shot_code}</b>
        <span
          className={`text-xs ${result?.status === "confirmed" ? "text-emerald-300" : task.status === "failed" ? "text-red-300" : task.status === "mock_completed" ? "text-cyan-200" : "text-zinc-400"}`}
        >
          {result?.status === "confirmed"
            ? "已通过"
            : task.status === "failed"
              ? "生成失败"
              : task.status === "imported"
                ? "待验收"
                : task.status === "mock_completed"
                  ? "Mock 链路完成（无视频）"
                  : "尚未完成"}
        </span>
      </div>
      {result?.video_url ? (
        <video
          className="mt-3 aspect-video w-full bg-black"
          controls
          preload="metadata"
          src={assetImageUrl(result.video_url)}
        />
      ) : (
        <div className="mt-3 flex aspect-video w-full items-center justify-center border border-white/10 px-5 text-center text-sm text-zinc-500">
          {task.status === "mock_completed"
            ? "模拟任务未调用火山方舟，因此没有可预览视频。"
            : "暂无可预览视频"}
        </div>
      )}
      <div className="mt-3 flex flex-wrap gap-2">
        {task.status === "imported" && result?.status !== "confirmed" ? (
          <>
            <button
              className={button}
              disabled={busy}
              onClick={() => onReview("confirm")}
            >
              <CheckCircle2 size={14} />
              通过
            </button>
            <button
              className={button}
              disabled={busy}
              onClick={() => onReview("redo")}
            >
              <RotateCcw size={14} />
              需要重做
            </button>
          </>
        ) : null}
        {task.status === "failed" ? (
          <button className={button} disabled={busy} onClick={onRetry}>
            <RefreshCw size={14} />
            修正后重新提交
          </button>
        ) : null}
        {result?.video_url ? (
          <a className={button} href={assetImageUrl(result.video_url)} download>
            <Download size={14} />
            下载
          </a>
        ) : null}
      </div>
    </article>
  );
}

function SubmissionChannelPicker({
  channel,
  defaultChannel,
  editable,
  huimengAvailable,
  jimengReady,
  seedance25Available,
  onChange,
}: {
  channel: SubmissionChannel;
  defaultChannel: SubmissionChannel;
  editable: boolean;
  huimengAvailable: boolean;
  jimengReady: boolean;
  seedance25Available: boolean;
  onChange: (channel: SubmissionChannel) => void;
}) {
  return (
    <section className="mt-6 border-y border-white/10 bg-[#12181d] px-5 py-4">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <p className="text-sm font-semibold text-zinc-100">
            选择本次视频生成方式
          </p>
          <p className="mt-1 text-xs leading-5 text-zinc-500">
            本次队列可独立选择；设置页只决定新队列默认值（当前默认：
            {channelNames[defaultChannel]}）。
          </p>
          {!editable ? (
            <p className="mt-1 text-xs leading-5 text-amber-200">
              当前任务已经派发，服务与模型已按任务锁定；结束后重新建立队列即可重新选择。
            </p>
          ) : null}
        </div>
        <div className="inline-grid grid-cols-1 border border-white/15 bg-black/20 p-1 sm:grid-cols-3">
          <button
            type="button"
            aria-label="即梦 CLI"
            disabled={!editable}
            onClick={() => onChange("jimeng")}
            className={`min-w-40 px-4 py-2 text-sm transition disabled:cursor-not-allowed disabled:opacity-35 ${
              channel === "jimeng"
                ? "bg-cyan-400 text-black"
                : "text-zinc-400 hover:text-zinc-100"
            }`}
          >
            即梦账号 CLI{jimengReady ? "（已就绪）" : ""}
          </button>
          <button
            type="button"
            aria-label="火山方舟 Seedance 2.5"
            disabled={!editable || !seedance25Available}
            onClick={() => onChange("volcengine_seedance25")}
            className={`min-w-48 px-4 py-2 text-sm transition disabled:cursor-not-allowed disabled:opacity-35 ${
              channel === "volcengine_seedance25"
                ? "bg-emerald-400 text-black"
                : "text-zinc-400 hover:text-zinc-100"
            }`}
          >
            火山方舟 API（2.5 Mock）
          </button>
          <button
            type="button"
            aria-label="慧梦 API"
            disabled={!editable || !huimengAvailable}
            onClick={() => onChange("huimeng")}
            className={`min-w-40 px-4 py-2 text-sm transition disabled:cursor-not-allowed disabled:opacity-35 ${
              channel === "huimeng"
                ? "bg-orange-500 text-black"
                : "text-zinc-400 hover:text-zinc-100"
            }`}
          >
            慧梦聚合 API
          </button>
        </div>
      </div>
    </section>
  );
}

function JimengModelPicker({
  models,
  selectedModelId,
  duration,
  resolution,
  editable,
  busy,
  onChange,
}: {
  models: JimengVideoModel[];
  selectedModelId: string;
  duration: number;
  resolution: string;
  editable: boolean;
  busy: boolean;
  onChange: (modelId: string) => void;
}) {
  const selected = models.find((item) => item.id === selectedModelId);
  return (
    <section className="border-b border-white/10 bg-[#10171c] px-5 py-4">
      <div className="grid gap-4 md:grid-cols-[minmax(260px,420px)_1fr] md:items-end">
        <label className="text-xs text-zinc-400">
          本次即梦视频模型
          <select
            aria-label="本次即梦视频模型"
            className="mt-1 block w-full border border-white/15 bg-[#11171c] px-3 py-2 text-sm text-zinc-100"
            value={selectedModelId}
            disabled={!editable || busy || models.length === 0}
            onChange={(event) => onChange(event.target.value)}
          >
            {models.map((model) => (
              <option key={model.id} value={model.id}>
                {model.label}
                {model.id === "seedance2.0_vip" ? "（默认）" : ""}
              </option>
            ))}
          </select>
        </label>
        <div className="text-xs leading-5 text-zinc-400">
          <p>
            {selected
              ? `${selected.speed_label}｜积分级别：${selected.cost_label}｜支持 ${selected.min_duration}-${selected.max_duration} 秒｜${selected.supported_resolutions.join(" / ")}`
              : "正在读取 CLI 支持的模型…"}
          </p>
          {selected ? (
            <p className="mt-1 text-zinc-500">{selected.description}</p>
          ) : null}
          <p className="mt-1 text-zinc-500">
            当前镜头：{duration} 秒 / {resolution}
            。准确积分由即梦按模型、时长、分辨率和参考素材实时计算。
          </p>
          {editable ? (
            <p className="mt-1 text-cyan-200">
              提交前可手动选择模型；切换后需要重新确认费用风险。
            </p>
          ) : null}
          {!editable ? (
            <p className="mt-1 text-amber-200">
              任务已经提交，模型已锁定；不能用切换模型修改正在查询的任务。
            </p>
          ) : null}
        </div>
      </div>
    </section>
  );
}

function SubmissionGateGuide({
  channel,
  readiness,
  hasTask,
  onSwitchHuimeng,
  onRebuild,
  onRefreshPreflight,
  onSaveBindings,
  busy,
}: {
  channel: SubmissionChannel;
  readiness?: LiveReadiness | JimengCliReadiness;
  hasTask: boolean;
  onSwitchHuimeng: () => void;
  onRebuild: () => void;
  onRefreshPreflight: () => void;
  onSaveBindings: (assetIds: string[]) => void;
  busy: boolean;
}) {
  const blockers =
    readiness?.gate_items.filter(
      (item) => !item.passed && !derivedGateLabels.has(item.label),
    ) ?? [];
  const automatic =
    readiness?.gate_items.filter(
      (item) => !item.passed && derivedGateLabels.has(item.label),
    ) ?? [];
  const bindings =
    readiness && "reference_bindings" in readiness
      ? (readiness.reference_bindings ?? [])
      : [];
  const candidates =
    readiness && "reference_candidates" in readiness
      ? (readiness.reference_candidates ?? [])
      : [];
  const bindingRows = bindings.length
    ? bindings
    : candidates.slice(0, 1).map((item) => ({
        ...item,
        token: "@图片1",
        purpose: item.purpose ?? "请为这张参考图确认用途。",
      }));
  const [editingBindings, setEditingBindings] = useState(false);
  const [selectedAssetIds, setSelectedAssetIds] = useState<string[]>([]);

  useEffect(() => {
    setSelectedAssetIds(bindingRows.map((item) => item.asset_id));
  }, [bindingRows.map((item) => item.asset_id).join("|")]);

  return (
    <section className="mt-5 border border-white/12 bg-[#12181d] p-5">
      <div className="flex items-center gap-2">
        <Settings2
          size={16}
          className={blockers.length ? "text-orange-300" : "text-emerald-300"}
        />
        <h2 className="text-base font-semibold text-zinc-100">
          {channel === "huimeng" ? "慧梦 API" : "即梦 CLI"}提交条件
        </h2>
      </div>
      {!hasTask ? (
        <p className="mt-3 text-sm text-zinc-400">
          先创建 1 个单镜队列，系统随后会逐项检查提交条件。
        </p>
      ) : !readiness ? (
        <p className="mt-3 text-sm text-zinc-400">
          正在读取当前路线的提交条件…
        </p>
      ) : blockers.length === 0 ? (
        <div className="mt-3 flex items-start gap-3 border border-emerald-400/25 bg-emerald-400/7 px-4 py-3">
          <CheckCircle2
            size={18}
            className="mt-0.5 shrink-0 text-emerald-300"
          />
          <div>
            <p className="text-sm font-semibold text-emerald-200">
              技术条件已通过
            </p>
            <p className="mt-1 text-xs leading-5 text-zinc-400">
              接下来只需按上方主任务完成费用风险确认，然后即可提交当前镜头。
            </p>
          </div>
        </div>
      ) : (
        <div className="mt-4 space-y-3">
          {blockers.map((item, index) => {
            const guidance = gateGuidance(item.label, channel);
            return (
              <article
                key={`${item.label}-${index}`}
                className="grid gap-4 border border-red-400/25 bg-red-400/5 p-4 md:grid-cols-[1fr_1.2fr_auto] md:items-center"
              >
                <div>
                  <p className="text-sm font-semibold text-red-200">
                    必须处理｜{humanizeCopy(item.label)}
                  </p>
                  <p className="mt-1 text-xs leading-5 text-zinc-400">
                    {humanizeCopy(item.detail)}
                  </p>
                </div>
                <div>
                  <p className="text-xs font-semibold text-zinc-300">
                    对最终成片的影响
                  </p>
                  <p className="mt-1 text-xs leading-5 text-zinc-500">
                    {guidance.impact}
                  </p>
                </div>
                {index === 0 && guidance.action === "修改参考图绑定" ? (
                  <a className={button} href="#reference-bindings">
                    修改参考图绑定
                  </a>
                ) : index === 0 ? (
                  <button
                    className={button}
                    disabled={busy}
                    onClick={onRefreshPreflight}
                  >
                    重新检查当前条件
                  </button>
                ) : guidance.action === "切换到慧梦 API 模式" ? (
                  <button
                    className={button}
                    disabled={busy}
                    onClick={onSwitchHuimeng}
                  >
                    切换到慧梦 API 模式
                  </button>
                ) : guidance.action === "重新建立单镜队列" ? (
                  <button
                    className={button}
                    disabled={busy}
                    onClick={onRebuild}
                  >
                    重新建立单镜队列
                  </button>
                ) : (
                  <a className={button} href={guidance.href}>
                    {guidance.action}
                  </a>
                )}
              </article>
            );
          })}
        </div>
      )}
      {automatic.length > 0 ? (
        <p className="mt-3 text-xs leading-5 text-zinc-500">
          “{automatic.map((item) => humanizeCopy(item.label)).join("、")}
          ”会在完成上方条件和费用确认后自动解除，不需要单独处理，也不会影响成片质量。
        </p>
      ) : null}
      {channel === "jimeng" && (bindings.length || candidates.length) ? (
        <details
          id="reference-bindings"
          className="mt-4 scroll-mt-24 border border-cyan-400/25 bg-cyan-400/[0.04]"
        >
          <summary className="cursor-pointer px-4 py-3 text-sm font-medium text-cyan-100">
            核对或替换全能参考绑定（{bindingRows.length}/9 张）
          </summary>
          <div className="border-t border-white/10 p-3">
            <div className="mb-3 flex items-center justify-between gap-3">
              <p className="text-xs leading-5 text-zinc-400">
                顺序就是即梦中的
                @图片1、@图片2。保存后会重新编译实际提交提示词，并重新要求费用确认。
              </p>
              <button
                className={button}
                disabled={busy || !candidates.length}
                onClick={() => setEditingBindings((value) => !value)}
              >
                {editingBindings ? "取消修改" : "修改绑定"}
              </button>
            </div>
            <div className="grid grid-cols-2 gap-2">
              {bindingRows.map((binding, index) => {
                const selected =
                  candidates.find(
                    (item) => item.asset_id === selectedAssetIds[index],
                  ) ?? binding;
                return (
                  <div
                    className="flex min-h-24 gap-3 border border-white/10 bg-black/15 p-2"
                    key={binding.token}
                  >
                    {selected.asset_url ? (
                      <img
                        alt={`${binding.token} ${selected.label}`}
                        className="h-16 w-24 shrink-0 object-cover"
                        src={selected.asset_url}
                      />
                    ) : null}
                    <div className="min-w-0 flex-1">
                      <p className="text-xs font-semibold text-cyan-200">
                        {binding.token}
                      </p>
                      {editingBindings ? (
                        <select
                          aria-label={`${binding.token} 参考图`}
                          className="mt-1 w-full border border-white/15 bg-[#11171c] px-2 py-2 text-xs text-zinc-200"
                          value={selectedAssetIds[index] ?? binding.asset_id}
                          onChange={(event) =>
                            setSelectedAssetIds((items) =>
                              items.map((item, itemIndex) =>
                                itemIndex === index ? event.target.value : item,
                              ),
                            )
                          }
                        >
                          {candidates.map((item) => (
                            <option key={item.asset_id} value={item.asset_id}>
                              {item.label}｜{item.role}
                            </option>
                          ))}
                        </select>
                      ) : (
                        <p className="mt-1 text-xs text-zinc-200">
                          {binding.label}
                        </p>
                      )}
                      <p className="mt-1 text-xs leading-5 text-zinc-400">
                        {selected.purpose ?? binding.purpose}
                      </p>
                    </div>
                  </div>
                );
              })}
            </div>
            {editingBindings ? (
              <div className="mt-3 flex justify-end">
                <button
                  className={button}
                  disabled={
                    busy ||
                    selectedAssetIds.length === 0 ||
                    new Set(selectedAssetIds).size !== selectedAssetIds.length
                  }
                  onClick={() => {
                    onSaveBindings(selectedAssetIds);
                    setEditingBindings(false);
                  }}
                >
                  保存参考图绑定
                </button>
              </div>
            ) : null}
          </div>
        </details>
      ) : null}
    </section>
  );
}

function VideoGenerationMonitor({
  task,
  projectCode,
  monitorError,
  supervisorStatus,
  lastMonitorAt,
  onRefresh,
  onSave,
  onAccept,
  onRedo,
  busy,
}: {
  task: BatchTask;
  projectCode: string;
  monitorError: string;
  supervisorStatus: VideoTaskSupervisorStatus | null;
  lastMonitorAt: string;
  onRefresh: () => void;
  onSave: () => void;
  onAccept: () => void;
  onRedo: () => void;
  busy: boolean;
}) {
  if (
    ![
      "verifying",
      "submitted",
      "processing",
      "completed",
      "failed",
      "imported",
    ].includes(task.status)
  )
    return null;

  const statusLabel = task.progress_label || versionStateName(task.status);
  const failureMessage = task.error_message;
  const failure = failureMessage ? videoFailureGuidance(failureMessage) : null;
  const localResult = task.results.at(-1);
  const reviewStatus = localResult?.status ?? "";
  const previewUrl = localResult
    ? assetImageUrl(localResult.video_url)
    : task.remote_video_url || "";
  const localPath =
    task.local_file_path ||
    (task.result_video_path
      ? `data/projects/${projectCode}/${task.result_video_path}`
      : "");
  const isRunning = ["verifying", "submitted", "processing"].includes(
    task.status,
  );
  const isOnline = task.status === "completed";
  const isLocal = task.status === "imported" || task.storage_status === "local";
  const supervisorRunning = Boolean(
    supervisorStatus?.enabled && supervisorStatus.running,
  );

  return (
    <section
      className="mt-5 border-y border-white/12 bg-[#10171c] px-5 py-5"
      aria-label="视频生成监控"
    >
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-xs tracking-[.16em] text-cyan-300">视频生成监控</p>
          <p className="mt-1 text-xs text-zinc-500">{task.shot_code}</p>
          <h2 className="mt-2 text-xl font-semibold text-zinc-100">
            {statusLabel}
          </h2>
          <p className="mt-2 text-sm leading-6 text-zinc-400">
            {task.status === "verifying"
              ? "CLI 已返回任务 ID，系统正在向服务商核验该任务是否已进入云端队列。"
              : task.status === "submitted" &&
                  task.external_provider === "jimeng_cli"
                ? "即梦 CLI 已确认云端任务。CLI 通道任务不保证显示在普通即梦网页项目记录中，系统会按同一任务 ID 持续查询，切勿重复提交扣费。"
                : isRunning
                  ? "后台正在查询同一个服务商任务；切换页面或关闭当前页面后仍会继续。"
                  : isOnline
                    ? "服务商已生成视频，当前结果在线上，系统正在自动保存到本地。"
                    : isLocal
                      ? "视频已经保存到当前项目目录，并绑定到这个镜头；可在下方直接预览。"
                      : "当前任务需要处理后才能继续。"}
          </p>
          {isRunning ? (
            <p
              className={`mt-2 inline-flex items-center gap-2 text-xs ${supervisorRunning ? "text-cyan-200" : "text-red-300"}`}
            >
              <RefreshCw size={13} className="animate-spin" />
              {supervisorRunning
                ? `后台监控中：每 ${supervisorStatus?.poll_interval_seconds ?? 5} 秒同步服务状态，无需停留在本页`
                : "后台监督器未运行，请使用立即查询并检查后端服务"}
            </p>
          ) : null}
        </div>
        <div className="flex flex-wrap gap-2">
          {isRunning ? (
            <button className={button} disabled={busy} onClick={onRefresh}>
              <RefreshCw size={14} />
              立即查询
            </button>
          ) : null}
          {isOnline ? (
            <button className={button} disabled={busy} onClick={onSave}>
              <Download size={14} />
              立即保存到本地
            </button>
          ) : null}
          {task.remote_video_url ? (
            <a
              className={button}
              href={task.remote_video_url}
              target="_blank"
              rel="noreferrer"
            >
              <ExternalLink size={14} />
              查看线上结果
            </a>
          ) : null}
          {localResult ? (
            <a
              className={button}
              href={assetImageUrl(localResult.video_url)}
              download
            >
              <Download size={14} />
              下载本地视频
            </a>
          ) : null}
        </div>
      </div>

      {previewUrl && (isOnline || isLocal) ? (
        <div className="mt-5 border border-white/12 bg-black/30 p-3">
          <video
            aria-label={`${task.shot_code} 视频预览`}
            className="aspect-video max-h-[560px] w-full bg-black object-contain"
            controls
            playsInline
            preload="metadata"
            src={previewUrl}
          >
            当前浏览器无法播放该视频，请使用下载按钮查看。
          </video>
          <p className="mt-2 text-xs text-zinc-500">
            {isLocal
              ? "正在播放项目本地副本。"
              : "正在预览服务商线上结果；系统仍会自动保存本地副本。"}
          </p>
        </div>
      ) : null}

      {isLocal && localResult ? (
        <section
          className={`mt-5 border p-4 ${
            reviewStatus === "confirmed"
              ? "border-emerald-400/30 bg-emerald-400/7"
              : reviewStatus === "rejected"
                ? "border-amber-400/30 bg-amber-400/7"
                : "border-orange-400/35 bg-orange-400/7"
          }`}
          id="video-result-review"
        >
          <p className="text-sm font-semibold text-zinc-100">
            {reviewStatus === "confirmed"
              ? `${task.shot_code} 已通过验收`
              : reviewStatus === "rejected"
                ? `${task.shot_code} 已标记重做`
                : `下一步：验收 ${task.shot_code}`}
          </p>
          <p className="mt-2 text-xs leading-5 text-zinc-400">
            {reviewStatus === "confirmed"
              ? "这个视频已经成为当前镜头的正式结果。请回到上方主任务继续建立下一个镜头。"
              : reviewStatus === "rejected"
                ? "旧视频仍会保留。请回到上方主任务重新建立当前镜头，真正再次提交前仍会要求确认。"
                : "请先完整播放上方视频，检查主体和产品是否一致、动作是否准确、镜头是否连续。下载视频不会自动表示通过。"}
          </p>
          {!["confirmed", "rejected"].includes(reviewStatus) ? (
            <div className="mt-4 flex flex-wrap gap-3">
              <button
                className="guide-primary-button guide-primary-button--pulse"
                disabled={busy}
                onClick={onAccept}
                type="button"
              >
                <CheckCircle2 size={16} />
                通过并继续下一镜
              </button>
              <button
                className={button}
                disabled={busy}
                onClick={onRedo}
                type="button"
              >
                <RefreshCw size={14} />
                这个视频需要重做
              </button>
            </div>
          ) : null}
        </section>
      ) : null}

      <div className="mt-5">
        {isRunning ? (
          <div className="border border-cyan-400/20 bg-cyan-400/5 px-4 py-3 text-xs leading-5 text-cyan-100">
            <p className="font-semibold">
              {task.provider_queue_status
                ? `服务商状态：${task.provider_queue_status}`
                : "服务商未提供可验证的生成百分比"}
            </p>
            {task.provider_queue_position != null ? (
              <p className="mt-1 text-zinc-400">
                当前队列位置：
                {task.provider_queue_position.toLocaleString("zh-CN")}
                {task.provider_queue_length != null
                  ? `，服务商返回队列总量：${task.provider_queue_length.toLocaleString("zh-CN")}`
                  : ""}
              </p>
            ) : (
              <p className="mt-1 text-zinc-400">
                系统只展示服务商真实阶段，不用固定百分比模拟进度。
              </p>
            )}
          </div>
        ) : (
          <p className="text-xs text-zinc-500">
            {task.status === "failed"
              ? "任务已终止"
              : isLocal
                ? "结果已保存到本地"
                : "等待可验证状态"}
          </p>
        )}
        <div className="mt-3 flex flex-wrap gap-x-6 gap-y-2 text-xs text-zinc-500">
          <span>服务任务 ID：{task.external_task_id || "等待服务商返回"}</span>
          {task.provider_status ? (
            <span>即梦原始状态：{task.provider_status}</span>
          ) : null}
          <span>
            存储位置：
            {isLocal
              ? "本地项目目录"
              : isOnline
                ? "服务商线上结果"
                : "尚未生成"}
          </span>
          {lastMonitorAt ? <span>页面同步：{lastMonitorAt}</span> : null}
          {supervisorStatus?.last_cycle_at ? (
            <span>
              后台同步：
              {new Date(supervisorStatus.last_cycle_at).toLocaleTimeString(
                "zh-CN",
                { hour12: false },
              )}
            </span>
          ) : null}
        </div>
      </div>

      {monitorError && !failure ? (
        <div className="mt-5 border border-amber-400/25 bg-amber-400/6 p-4">
          <p className="text-sm font-semibold text-amber-200">
            最近一次后台同步暂时异常，系统会自动重试
          </p>
          <p className="mt-2 text-xs leading-5 text-zinc-500">
            {humanizeCopy(monitorError)}
          </p>
        </div>
      ) : null}

      {failure ? (
        <div className="mt-5 grid gap-4 border border-red-400/30 bg-red-400/6 p-4 md:grid-cols-[1fr_1fr_auto] md:items-center">
          <div>
            <p className="flex items-center gap-2 text-sm font-semibold text-red-200">
              <AlertTriangle size={16} />
              {failure.reason}
            </p>
            <p className="mt-2 text-xs leading-5 text-zinc-500">
              原始信息：{humanizeCopy(failureMessage)}
            </p>
          </div>
          <div>
            <p className="text-xs font-semibold text-zinc-300">对成片的影响</p>
            <p className="mt-1 text-xs leading-5 text-zinc-500">
              {failure.impact}
            </p>
          </div>
          {task.status === "failed" ? (
            <a className={button} href="#current-primary-task">
              返回顶部处理：{failure.action}
            </a>
          ) : failure.href ? (
            <a className={button} href={failure.href}>
              {failure.action}
            </a>
          ) : task.status === "completed" ? (
            <button className={button} disabled={busy} onClick={onSave}>
              {failure.action}
            </button>
          ) : (
            <button className={button} disabled={busy} onClick={onRefresh}>
              {failure.action}
            </button>
          )}
        </div>
      ) : null}

      {isLocal && localPath ? (
        <div className="mt-5 flex items-start gap-3 border border-emerald-400/25 bg-emerald-400/7 px-4 py-3">
          <FolderOpen size={18} className="mt-0.5 shrink-0 text-emerald-300" />
          <div className="min-w-0">
            <p className="text-sm font-semibold text-emerald-200">
              本地保存完成
            </p>
            <p className="mt-1 break-all text-xs leading-5 text-zinc-400">
              {localPath}
            </p>
          </div>
        </div>
      ) : null}
    </section>
  );
}

function SearchCheckIcon() {
  return <Eye size={13} />;
}
