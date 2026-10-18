import {
  CheckCircle2,
  CircleAlert,
  CircleDashed,
  FolderOpen,
  Link2,
  MapPinned,
  Plus,
  RefreshCw,
  ShieldCheck,
  Upload,
  UserRound,
} from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

import { useConfirmAction } from "../components/ConfirmDialog";
import { ErrorBanner } from "../components/ErrorBanner";
import {
  GuideActionCard,
  GuidePrimaryButton,
  GuideProgress,
  GuideProgressToast,
  TechDetails,
} from "../components/Guide";
import { VersionRail } from "../components/assets/VersionRail";
import {
  analyzeAssetInventory,
  autoBindAssets,
  createCharacter,
  createCostume,
  downloadAssetImage,
  fetchAssetImageJobs,
  fetchAssetWorkspace,
  revealInFolder,
  fetchAssetImageReadiness,
  pollAssetImage,
  saveSceneAsset,
  saveSceneBinding,
  submitAssetImage,
  transitionAssetVersion,
  updateAssetRequirement,
  uploadAssetImage,
} from "../services/api";
import { useWorkbenchStore } from "../stores/useWorkbenchStore";
import { workbenchPageClass } from "../styles/layout";
import type {
  AssetVersion,
  AssetImageJob,
  AssetImageReadiness,
  AssetImageTargetKind,
  AssetRequirement,
  AssetWorkspace,
  CharacterDraft,
  SceneAssetDraft,
} from "../types/assets";
import { humanizeCopy } from "../utils/humanCopy";

type Tab = "characters" | "scenes" | "bindings";

function waitForVisibleUpdate() {
  return new Promise<void>((resolve) => {
    if (typeof window.requestAnimationFrame === "function") {
      window.requestAnimationFrame(() => resolve());
      return;
    }
    window.setTimeout(resolve, 0);
  });
}

const emptyCharacter: CharacterDraft = {
  name: "",
  face_shape: "",
  facial_features: "",
  age_description: "",
  height_description: "",
  body_type: "",
  hair_style: "",
  identity_temperament: "",
};

const emptySceneAsset: SceneAssetDraft = {
  name: "",
  description: "",
  spatial_layout: "",
  time_weather_light: "",
  key_props: "",
  palette_mood: "",
};

function activeVersion(versions: AssetVersion[]) {
  return versions.find((version) =>
    ["confirmed_current", "locked"].includes(version.status),
  );
}

function imageKey(kind: AssetImageTargetKind | string, targetId: string) {
  return `${kind}:${targetId}`;
}

function normalizedImageJobStatus(job: AssetImageJob) {
  const status = job.status.toLowerCase().trim();
  if (["downloaded", "imported"].includes(status)) return "downloaded";
  if (
    [
      "completed",
      "complete",
      "success",
      "succeeded",
      "done",
      "finished",
    ].includes(status)
  ) {
    return job.image_url ? "downloaded" : "completed";
  }
  if (["failed", "failure", "error", "cancelled", "canceled"].includes(status))
    return "failed";
  if (["processing", "running", "generating", "in_progress"].includes(status))
    return "processing";
  return "submitted";
}

function imageJobPresentation(job: AssetImageJob) {
  const status = normalizedImageJobStatus(job);
  if (status === "downloaded") {
    return {
      label: "图片已保存",
      detail: "新图片已出现在下方版本列表中。",
      progress: 100,
    };
  }
  if (status === "completed") {
    return {
      label: "图片已生成，正在保存",
      detail: "正在把服务返回的图片保存到当前项目。",
      progress: 90,
    };
  }
  if (status === "processing") {
    return {
      label: "正在生成图片",
      detail: "图片服务正在绘制，页面会自动更新，不用重复点击。",
      progress: 60,
    };
  }
  if (status === "failed") {
    return {
      label: "生成失败",
      detail: job.error_message || "图片服务未能完成本次任务，可以重新生成。",
      progress: 100,
    };
  }
  return {
    label: "任务已提交",
    detail: "已交给图片服务，正在等待开始生成。",
    progress: 25,
  };
}

type RequirementDraft = {
  name: string;
  description: string;
  visual_prompt: string;
  reference_mode: "visual" | "text_only";
  importance_reason: string;
  text_prompt: string;
  scene_ids: string[];
};

function requirementTarget(
  workspace: AssetWorkspace,
  requirement: AssetRequirement,
) {
  if (requirement.asset_type === "character") {
    const target = workspace.characters.find(
      (item) => item.id === requirement.target_id,
    );
    return target
      ? {
          kind: "character-master" as const,
          id: target.id,
          versions: target.master_versions,
        }
      : null;
  }
  if (requirement.asset_type === "costume") {
    const target = workspace.characters
      .flatMap((character) => character.costumes)
      .find((item) => item.id === requirement.target_id);
    return target
      ? { kind: "costume" as const, id: target.id, versions: target.versions }
      : null;
  }
  if (requirement.asset_type === "scene") {
    const target = workspace.scene_assets.find(
      (item) => item.id === requirement.target_id,
    );
    return target
      ? { kind: "scene" as const, id: target.id, versions: target.versions }
      : null;
  }
  const target = workspace.props?.find(
    (item) => item.id === requirement.target_id,
  );
  return target
    ? { kind: "prop" as const, id: target.id, versions: target.versions }
    : null;
}

const requirementLabels: Record<AssetRequirement["asset_type"], string> = {
  character: "人物",
  costume: "服装",
  scene: "场景",
  prop: "道具",
};

type BindingIssue = {
  id: string;
  label: string;
  reason: string;
  action: string;
};

function bindingIssue(
  workspace: AssetWorkspace,
  requirement: AssetRequirement,
): BindingIssue | null {
  if (
    requirement.reference_mode === "text_only" ||
    requirement.status === "bound"
  )
    return null;
  const target = requirementTarget(workspace, requirement);
  const label = `${requirementLabels[requirement.asset_type]}｜${requirement.name}`;
  if (!target) {
    return {
      id: requirement.id,
      label,
      reason: "未找到对应的资产记录",
      action: "点击页面上方“重新识别清单”，重新建立该资产条目。",
    };
  }
  if (!activeVersion(target.versions)) {
    return {
      id: requirement.id,
      label,
      reason: "没有已确认或锁定的图片版本",
      action: "在上方对应资产卡片上传或生成图片，再确认或锁定该版本。",
    };
  }
  return {
    id: requirement.id,
    label,
    reason: "锁定版本已存在，但绑定状态未同步",
    action: "再次执行自检修复；若仍未恢复，请检查该资产的出现场次。",
  };
}

function Input({
  label,
  value,
  onChange,
  placeholder,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
}) {
  return (
    <label className="text-xs text-zinc-400">
      {label}
      <input
        value={value}
        placeholder={placeholder}
        onChange={(event) => onChange(event.target.value)}
        className="mt-2 w-full border border-white/15 bg-black/15 px-3 py-2.5 text-sm text-zinc-100 outline-none focus:border-orange-400/70"
      />
    </label>
  );
}

function Textarea({
  label,
  value,
  onChange,
  placeholder,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
}) {
  return (
    <label className="text-xs text-zinc-400">
      {label}
      <textarea
        value={value}
        placeholder={placeholder}
        onChange={(event) => onChange(event.target.value)}
        className="mt-2 min-h-20 w-full resize-y border border-white/15 bg-black/15 px-3 py-2.5 text-sm text-zinc-100 outline-none focus:border-orange-400/70"
      />
    </label>
  );
}

export function AssetsPage() {
  const navigate = useNavigate();
  const confirmAction = useConfirmAction();
  const { activeProject, projects, loadProjects } = useWorkbenchStore();
  const [workspace, setWorkspace] = useState<AssetWorkspace | null>(null);
  const [tab, setTab] = useState<Tab>("characters");
  const [busy, setBusy] = useState(false);
  const [busyMessage, setBusyMessage] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [bindingFeedback, setBindingFeedback] = useState<{
    tone: "progress" | "success" | "error";
    message: string;
    issues?: BindingIssue[];
  } | null>(null);
  const [characterDraft, setCharacterDraft] = useState(emptyCharacter);
  const [selectedCharacterId, setSelectedCharacterId] = useState("");
  const [costumeUsage, setCostumeUsage] = useState("");
  const [costumeDescription, setCostumeDescription] = useState("");
  const [selectedSceneId, setSelectedSceneId] = useState("");
  const [sceneDraft, setSceneDraft] = useState(emptySceneAsset);
  const [selectedSceneAssetId, setSelectedSceneAssetId] = useState("");
  const [bindingSceneId, setBindingSceneId] = useState("");
  const [bindingCharacterId, setBindingCharacterId] = useState("");
  const [bindingMasterId, setBindingMasterId] = useState("");
  const [bindingCostumeVersionId, setBindingCostumeVersionId] = useState("");
  const [sceneState, setSceneState] = useState("");
  const [hairChangeReason, setHairChangeReason] = useState("");
  const [imageJobs, setImageJobs] = useState<Record<string, AssetImageJob>>({});
  const [imageJobErrors, setImageJobErrors] = useState<Record<string, string>>(
    {},
  );
  const [imageReadiness, setImageReadiness] = useState<
    Record<string, AssetImageReadiness>
  >({});
  const [requirementDrafts, setRequirementDrafts] = useState<
    Record<string, RequirementDraft>
  >({});
  const [showManualArea, setShowManualArea] = useState(false);
  const [folderHint, setFolderHint] = useState("");
  const pollingJobsRef = useRef(new Set<string>());
  const downloadingJobsRef = useRef(new Set<string>());
  const downloadAttemptsRef = useRef(new Map<string, number>());

  useEffect(() => {
    if (projects.length === 0) void loadProjects();
  }, [loadProjects, projects.length]);

  useEffect(() => {
    if (!activeProject) return;
    setBusy(true);
    setBusyMessage("正在读取资产记录…");
    setBindingFeedback(null);
    setImageJobs({});
    setImageJobErrors({});
    pollingJobsRef.current.clear();
    downloadingJobsRef.current.clear();
    downloadAttemptsRef.current.clear();
    Promise.all([
      fetchAssetWorkspace(activeProject.id),
      fetchAssetImageJobs(activeProject.id),
    ])
      .then(([nextWorkspace, jobs]) => {
        setWorkspace(nextWorkspace);
        const latestJobs: Record<string, AssetImageJob> = {};
        for (const job of jobs) {
          const key = imageKey(job.target_type, job.target_id);
          if (!latestJobs[key]) latestJobs[key] = job;
        }
        setImageJobs(latestJobs);
        setError(null);
      })
      .catch((nextError: Error) => setError(nextError.message))
      .finally(() => {
        setBusy(false);
        setBusyMessage("");
      });
  }, [activeProject]);

  useEffect(() => {
    const timers: number[] = [];
    for (const [key, job] of Object.entries(imageJobs)) {
      const status = normalizedImageJobStatus(job);
      if (
        ["submitted", "processing"].includes(status) &&
        !pollingJobsRef.current.has(job.id)
      ) {
        const timer = window.setTimeout(async () => {
          if (pollingJobsRef.current.has(job.id)) return;
          pollingJobsRef.current.add(job.id);
          try {
            const nextJob = await pollAssetImage(job.id);
            setImageJobs((current) => ({ ...current, [key]: nextJob }));
            setImageJobErrors((current) => ({ ...current, [key]: "" }));
          } catch (nextError) {
            setImageJobErrors((current) => ({
              ...current,
              [key]: (nextError as Error).message,
            }));
          } finally {
            pollingJobsRef.current.delete(job.id);
          }
        }, 1600);
        timers.push(timer);
      }

      if (status === "completed" && !downloadingJobsRef.current.has(job.id)) {
        const attempts = downloadAttemptsRef.current.get(job.id) ?? 0;
        if (attempts < 3) {
          downloadAttemptsRef.current.set(job.id, attempts + 1);
          const timer = window.setTimeout(
            async () => {
              downloadingJobsRef.current.add(job.id);
              try {
                const nextWorkspace = await downloadAssetImage(job.id);
                setWorkspace(nextWorkspace);
                setImageJobs((current) => ({
                  ...current,
                  [key]: { ...current[key], status: "downloaded" },
                }));
                setImageJobErrors((current) => ({ ...current, [key]: "" }));
                downloadAttemptsRef.current.delete(job.id);
              } catch (nextError) {
                const message = (nextError as Error).message;
                setImageJobErrors((current) => ({
                  ...current,
                  [key]: message,
                }));
                if (message.includes("过期")) {
                  // 链接已被服务端清理，重试无意义，直接停止自动重试
                  downloadAttemptsRef.current.set(job.id, 3);
                }
                // 触发 effect 重跑，安排下一次自动重试
                setImageJobs((current) => ({ ...current }));
              } finally {
                downloadingJobsRef.current.delete(job.id);
              }
            },
            attempts === 0 ? 250 : attempts * 4000,
          );
          timers.push(timer);
        }
      }
    }
    return () => timers.forEach((timer) => window.clearTimeout(timer));
  }, [imageJobs]);

  useEffect(() => {
    if (!workspace) return;
    setSelectedCharacterId(
      (current) => current || workspace.characters[0]?.id || "",
    );
    setSelectedSceneId((current) => current || workspace.scenes[0]?.id || "");
    setBindingSceneId((current) => current || workspace.scenes[0]?.id || "");
    setBindingCharacterId(
      (current) => current || workspace.characters[0]?.id || "",
    );
  }, [workspace]);

  useEffect(() => {
    if (!workspace) return;
    setRequirementDrafts(
      Object.fromEntries(
        (workspace.requirements ?? []).map((requirement) => [
          requirement.id,
          {
            name: requirement.name,
            description: requirement.description,
            visual_prompt: requirement.visual_prompt,
            reference_mode: requirement.reference_mode,
            importance_reason: requirement.importance_reason,
            text_prompt: requirement.text_prompt,
            scene_ids: requirement.scene_ids,
          },
        ]),
      ),
    );
  }, [workspace]);

  const selectedCharacter = workspace?.characters.find(
    (character) => character.id === selectedCharacterId,
  );
  const sceneAssets =
    workspace?.scene_assets.filter(
      (asset) => asset.scene_id === selectedSceneId,
    ) ?? [];
  const selectedSceneAsset =
    sceneAssets.find((asset) => asset.id === selectedSceneAssetId) ??
    sceneAssets[0];
  const bindingCharacter = workspace?.characters.find(
    (character) => character.id === bindingCharacterId,
  );
  const confirmedMasters =
    bindingCharacter?.master_versions.filter((version) =>
      ["confirmed_current", "locked"].includes(version.status),
    ) ?? [];
  const confirmedCostumeVersions = useMemo(
    () =>
      bindingCharacter?.costumes.flatMap((costume) =>
        costume.versions
          .filter((version) =>
            ["confirmed_current", "locked"].includes(version.status),
          )
          .map((version) => ({ costume, version })),
      ) ?? [],
    [bindingCharacter],
  );

  useEffect(() => {
    setSceneDraft(
      selectedSceneAsset
        ? {
            name: selectedSceneAsset.name,
            description: selectedSceneAsset.description,
            spatial_layout: selectedSceneAsset.spatial_layout,
            time_weather_light: selectedSceneAsset.time_weather_light,
            key_props: selectedSceneAsset.key_props,
            palette_mood: selectedSceneAsset.palette_mood,
          }
        : emptySceneAsset,
    );
  }, [selectedSceneAsset]);

  useEffect(() => {
    setBindingMasterId(confirmedMasters[0]?.id ?? "");
    setBindingCostumeVersionId(confirmedCostumeVersions[0]?.version.id ?? "");
  }, [bindingCharacterId, workspace]);

  const perform = async (
    operation: () => Promise<AssetWorkspace>,
    message = "正在保存资产记录…",
  ) => {
    setBusy(true);
    setBusyMessage(message);
    setError(null);
    try {
      setWorkspace(await operation());
    } catch (nextError) {
      setError((nextError as Error).message);
    } finally {
      setBusy(false);
      setBusyMessage("");
    }
  };

  const analyzeInventory = async (forceRegenerate = false) => {
    if (!activeProject) return;
    const ok = await confirmAction({
      title: forceRegenerate ? "重新识别剧本资产" : "从剧本识别资产",
      message:
        "AI 会读取当前项目已解析的剧本文本，识别需要保持一致的关键参考，并把普通细节整理为文字描述。",
      details: [
        "这是一次真实文字请求，可能产生少量费用。",
        "这一步只建立清单，不会自动生成图片。",
        "只有关键参考需要生成或上传图片，普通细节会留给视频模型合理发挥。",
      ],
      confirmLabel: "确认识别资产",
      tone: "cost",
    });
    if (!ok) return;
    await perform(
      () => analyzeAssetInventory(activeProject.id, forceRegenerate),
      "AI 正在从剧本识别人名、场景和道具…",
    );
  };

  const saveRequirement = async (requirement: AssetRequirement) => {
    const draft = requirementDrafts[requirement.id];
    if (!draft) return;
    await perform(
      () => updateAssetRequirement(requirement.id, draft),
      `正在保存“${draft.name}”的资产要求…`,
    );
  };

  const bindAllReadyAssets = async () => {
    if (!activeProject) return;
    const ok = await confirmAction({
      title: "按剧情自动绑定关键参考",
      message:
        "系统只会把已确认的关键人物、产品、重复场景和关键道具图绑定到对应场次。",
      details: [
        "文字描述项不会成为 @图片，但会写入视频提示词。",
        "不会生成新图片，你仍可在下方手动修正。",
      ],
      confirmLabel: "确认自动绑定",
    });
    if (!ok) return;
    setBusy(true);
    setBusyMessage("正在按剧情场次绑定已确认资产…");
    setError(null);
    setBindingFeedback({
      tone: "progress",
      message: "正在读取锁定版本并写入对应场次，请稍等…",
    });
    // Let React paint the progress state before the local binding request starts.
    await waitForVisibleUpdate();
    try {
      const nextWorkspace = await autoBindAssets(activeProject.id);
      setWorkspace(nextWorkspace);
      const requirements = nextWorkspace.requirements ?? [];
      const visualRequirements = requirements.filter(
        (requirement) => requirement.reference_mode !== "text_only",
      );
      const boundVisualCount = visualRequirements.filter(
        (requirement) => requirement.status === "bound",
      ).length;
      const textOnlyCount = requirements.filter(
        (requirement) => requirement.reference_mode === "text_only",
      ).length;
      const issues = visualRequirements
        .map((requirement) => bindingIssue(nextWorkspace, requirement))
        .filter((issue): issue is BindingIssue => Boolean(issue));
      const remainingCount = issues.length;
      setBindingFeedback({
        tone: remainingCount === 0 ? "success" : "error",
        message:
          remainingCount === 0
            ? `自检修复完成：${boundVisualCount} 项关键参考已绑定，${textOnlyCount} 项普通细节已写入文字描述。`
            : `自检完成：已绑定 ${boundVisualCount}/${visualRequirements.length} 项关键参考。以下 ${remainingCount} 项仍需处理。`,
        issues,
      });
    } catch (nextError) {
      const rawMessage = (nextError as Error).message;
      const message = /failed to fetch|networkerror|load failed/i.test(
        rawMessage,
      )
        ? "自动绑定失败：本地 FastAPI 后端未连接。请启动工作台后端，再点击此按钮重试。"
        : `自动绑定失败：${rawMessage}`;
      setBindingFeedback({ tone: "error", message });
    } finally {
      setBusy(false);
      setBusyMessage("");
    }
  };

  async function openProjectFolder() {
    if (!activeProject) return;
    try {
      const result = await revealInFolder(activeProject.id);
      setFolderHint(`已打开项目文件夹：${result.path}`);
    } catch (nextError) {
      setFolderHint((nextError as Error).message);
    }
  }

  async function prepareRealAssetImage(
    kind: AssetImageTargetKind,
    targetId: string,
  ) {
    const key = imageKey(kind, targetId);
    setBusy(true);
    setBusyMessage("正在检查图片生成条件…");
    setError(null);
    try {
      const readiness = await fetchAssetImageReadiness(kind, targetId);
      setImageReadiness((current) => ({ ...current, [key]: readiness }));
      if (!readiness.ready) {
        const missing = readiness.gate_items
          .filter((item) => !item.passed)
          .map((item) => item.label)
          .join("、");
        setError(`还不能生成图片：${missing}`);
        return;
      }
      const ok = await confirmAction({
        title: `确认生成${readiness.asset_type}`,
        message: "这一步会向已配置的图片服务发送一次真实生图请求。",
        details: [
          `服务：${readiness.provider_name}`,
          `模型：${readiness.model_id}`,
          "范围：只生成当前资产一张图",
          "不会生成视频；可能产生图片费用，请先核对账户价格。",
        ],
        confirmLabel: "确认生成图片",
        tone: "cost",
      });
      if (!ok) return;
      setBusyMessage("正在提交图片生成任务…");
      const job = await submitAssetImage(kind, targetId);
      setImageJobs((current) => ({ ...current, [key]: job }));
      setImageJobErrors((current) => ({ ...current, [key]: "" }));
      downloadAttemptsRef.current.delete(job.id);
      if ((job.status || "").toLowerCase() === "downloaded" && activeProject) {
        // 即时生图模式：图片已在提交时存入项目，直接刷新版本列表。
        setWorkspace(await fetchAssetWorkspace(activeProject.id));
      }
    } catch (nextError) {
      setError((nextError as Error).message);
    } finally {
      setBusy(false);
      setBusyMessage("");
    }
  }

  async function retrySavingAssetImage(
    kind: AssetImageTargetKind,
    targetId: string,
  ) {
    const key = imageKey(kind, targetId);
    const job = imageJobs[key];
    if (!job) return;
    downloadAttemptsRef.current.delete(job.id);
    setBusy(true);
    setBusyMessage("正在下载图片并保存新版本…");
    setImageJobErrors((current) => ({ ...current, [key]: "" }));
    try {
      const nextWorkspace = await downloadAssetImage(job.id);
      setWorkspace(nextWorkspace);
      setImageJobs((current) => ({
        ...current,
        [key]: { ...current[key], status: "downloaded" },
      }));
    } catch (nextError) {
      setImageJobErrors((current) => ({
        ...current,
        [key]: (nextError as Error).message,
      }));
    } finally {
      setBusy(false);
      setBusyMessage("");
    }
  }

  async function uploadExistingAssetImage(
    kind: AssetImageTargetKind,
    targetId: string,
    file: File,
  ) {
    const ok = await confirmAction({
      title: "确认上传已有资产图",
      message: "这会把你选择的本地图片保存成新的资产版本，旧版本不会被覆盖。",
      details: [
        `文件：${file.name}`,
        "支持 PNG / JPG / JPEG / WEBP，单张最多 25 MB。",
        "上传后请在版本列表里点击“确认为当前”；如果旧版已锁定，请先解锁旧版。",
      ],
      confirmLabel: "确认上传",
    });
    if (!ok) return;
    setBusy(true);
    setBusyMessage("正在保存你上传的资产图…");
    setError(null);
    try {
      setWorkspace(await uploadAssetImage(kind, targetId, file));
    } catch (nextError) {
      setError((nextError as Error).message);
    } finally {
      setBusy(false);
      setBusyMessage("");
    }
  }

  function renderImageControls(kind: AssetImageTargetKind, targetId: string) {
    const key = imageKey(kind, targetId);
    const readiness = imageReadiness[key];
    const job = imageJobs[key];
    const jobStatus = job ? normalizedImageJobStatus(job) : null;
    const jobError = imageJobErrors[key];
    const jobIsExpired = Boolean(jobError?.includes("过期"));
    const basePresentation = job ? imageJobPresentation(job) : null;
    const jobPresentation =
      job && basePresentation && jobError
        ? {
            label: jobIsExpired ? "图片链接已过期" : "自动保存失败",
            detail: jobIsExpired
              ? "生成结果只在服务端保留约 24 小时，这张图的链接已失效。请点“生成新图”重新生成。"
              : humanizeCopy(jobError),
            progress: 100,
          }
        : basePresentation;
    const jobIsActive =
      jobStatus === "submitted" ||
      jobStatus === "processing" ||
      (jobStatus === "completed" && !jobError);
    return (
      <div className="mt-3 space-y-2">
        <div className="flex flex-wrap gap-2">
          <label className="inline-flex cursor-pointer items-center gap-2 border border-white/20 px-3 py-2 text-xs text-zinc-200 transition hover:border-orange-400/45 hover:text-orange-200">
            <Upload size={14} />
            上传已有图
            <input
              type="file"
              accept="image/png,image/jpeg,image/jpg,image/webp"
              className="hidden"
              disabled={busy}
              onChange={(event) => {
                const file = event.currentTarget.files?.[0];
                event.currentTarget.value = "";
                if (file) void uploadExistingAssetImage(kind, targetId, file);
              }}
            />
          </label>
          <button
            type="button"
            disabled={busy || jobIsActive}
            onClick={() => void prepareRealAssetImage(kind, targetId)}
            className="border border-emerald-400/45 px-3 py-2 text-xs text-emerald-200 transition hover:bg-emerald-400/10 disabled:opacity-45"
          >
            {jobIsActive
              ? "正在生成…"
              : jobStatus === "failed" ||
                  (jobStatus === "completed" && jobError)
                ? "重新生成"
                : "生成新图"}
          </button>
          {jobStatus === "completed" && jobError && !jobIsExpired ? (
            <button
              type="button"
              disabled={busy}
              onClick={() => void retrySavingAssetImage(kind, targetId)}
              className="border border-orange-400/50 px-3 py-2 text-xs text-orange-200 transition hover:bg-orange-400/10 disabled:opacity-45"
            >
              重新保存图片
            </button>
          ) : null}
        </div>
        {job && jobPresentation ? (
          <div
            role="status"
            aria-live="polite"
            className={`rounded-xl border px-3 py-3 text-xs ${
              jobStatus === "failed" || jobError
                ? "border-red-400/30 bg-red-400/5"
                : jobStatus === "downloaded"
                  ? "border-emerald-400/30 bg-emerald-400/5"
                  : "border-sky-400/30 bg-sky-400/5"
            }`}
          >
            <div className="flex items-center justify-between gap-3">
              <p className="font-medium text-zinc-100">
                {jobPresentation.label}
              </p>
              <p className="tabular-nums text-zinc-400">
                {jobPresentation.progress}%
              </p>
            </div>
            <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-white/10">
              <div
                className={`h-full rounded-full transition-all duration-500 ${
                  jobStatus === "failed" || jobError
                    ? "bg-red-400"
                    : "bg-emerald-400"
                }`}
                style={{ width: `${jobPresentation.progress}%` }}
              />
            </div>
            <p className="mt-2 leading-5 text-zinc-400">
              {jobPresentation.detail}
            </p>
          </div>
        ) : null}
        {readiness && !readiness.ready ? (
          <details className="border border-white/10 bg-black/10 p-2 text-xs leading-5 text-zinc-400">
            <summary className="cursor-pointer text-zinc-300">
              为什么还不能生成？
            </summary>
            <div className="mt-2">
              {readiness.gate_items.map((item) => (
                <p
                  key={item.label}
                  className={
                    item.passed ? "text-emerald-200/80" : "text-red-200/80"
                  }
                >
                  {item.passed ? "通过" : "缺少"}：{humanizeCopy(item.label)}
                </p>
              ))}
            </div>
          </details>
        ) : null}
      </div>
    );
  }

  if (!activeProject) {
    return (
      <div className={workbenchPageClass}>
        <h1 className="text-3xl font-semibold text-zinc-100">资产</h1>
        <p className="mt-3 text-sm text-zinc-400">
          请先创建或打开项目，再用真实 AI 生成或登记资产版本。
        </p>
        <button
          type="button"
          onClick={() => navigate("/start-plan")}
          className="mt-6 bg-orange-500 px-4 py-2.5 text-sm font-medium text-black"
        >
          前往开始 / 规划
        </button>
      </div>
    );
  }

  return (
    <div className={workbenchPageClass}>
      {busy ? (
        <GuideProgressToast label={busyMessage || "正在处理资产，请稍等…"} />
      ) : null}
      <div className="flex items-end justify-between gap-4">
        <div>
          <p className="text-xs tracking-[0.18em] text-orange-400">V7｜资产</p>
          <h1 className="mt-2 text-3xl font-semibold tracking-wide text-zinc-100">
            从剧本整理并绑定资产
          </h1>
          <p className="mt-3 max-w-3xl text-sm leading-6 text-zinc-400">
            AI
            会先判断哪些人物、场景和道具必须保持准确一致。只有关键参考需要图片并进入
            @图片绑定，普通细节保留为文字描述，让视频模型拥有合理发挥空间。
          </p>
        </div>
      </div>

      <section className="mt-7 space-y-5">
        {(workspace?.requirements ?? []).length === 0 ? (
          <GuideActionCard
            eyebrow="第一步"
            title="让 AI 识别关键参考与普通细节"
            description="AI 会根据剧情重要性、跨镜头一致性和 Seedance 参考规范分类。关键参考需要图片，普通细节只进入文字提示词。"
            tone="current"
          >
            <GuidePrimaryButton
              disabled={busy}
              onClick={() => void analyzeInventory(false)}
            >
              从剧本识别资产
            </GuidePrimaryButton>
          </GuideActionCard>
        ) : (
          <>
            <div className="rounded-[28px] border border-white/12 bg-[#141a20]/92 p-6">
              <div className="flex items-start justify-between gap-5">
                <div>
                  <p className="text-xs tracking-[0.18em] text-orange-400">
                    AI 已整理
                  </p>
                  <h2 className="mt-2 text-2xl font-semibold text-zinc-100">
                    逐项确认关键参考与文字描述
                  </h2>
                  <p className="mt-2 text-sm leading-6 text-zinc-400">
                    关键参考用于锁定身份、产品和连续性；文字描述项不要求图片，只把必要信息交给视频模型。你可以随时手动调整分类。
                  </p>
                </div>
                <div className="flex shrink-0 flex-col items-end gap-2">
                  <button
                    type="button"
                    disabled={busy}
                    onClick={() => void openProjectFolder()}
                    className="inline-flex items-center gap-2 border border-white/15 px-3 py-2 text-xs text-zinc-300 transition hover:border-orange-400/45 hover:text-orange-200 disabled:opacity-45"
                  >
                    <FolderOpen size={14} />
                    打开项目文件夹
                  </button>
                  <button
                    type="button"
                    disabled={busy}
                    onClick={() => void analyzeInventory(true)}
                    className="group inline-flex min-h-12 items-center gap-3 border border-orange-400/55 bg-orange-400/10 px-4 py-2.5 text-left text-orange-100 shadow-[0_10px_28px_rgba(0,0,0,0.22)] transition hover:-translate-y-0.5 hover:border-orange-300 hover:bg-orange-400/16 disabled:cursor-not-allowed disabled:opacity-45"
                  >
                    <RefreshCw
                      size={18}
                      className={
                        busy
                          ? "animate-spin"
                          : "transition-transform group-hover:rotate-45"
                      }
                    />
                    <span>
                      <span className="block text-sm font-semibold">
                        重新识别关键资产
                      </span>
                      <span className="mt-0.5 block text-[11px] font-normal text-orange-200/65">
                        按剧情重判图片参考与文字描述
                      </span>
                    </span>
                  </button>
                  {folderHint ? (
                    <p className="max-w-64 text-right text-xs text-emerald-200/80">
                      {folderHint}
                    </p>
                  ) : null}
                </div>
              </div>

              <div className="mt-6 grid grid-cols-2 gap-4">
                {(workspace?.requirements ?? []).map((requirement) => {
                  const target = workspace
                    ? requirementTarget(workspace, requirement)
                    : null;
                  const currentVersion = target
                    ? activeVersion(target.versions)
                    : undefined;
                  const draft = requirementDrafts[requirement.id];
                  const isTextOnly = requirement.reference_mode === "text_only";
                  return (
                    <article
                      key={requirement.id}
                      className={`rounded-2xl border p-5 ${
                        isTextOnly
                          ? "border-zinc-500/30 bg-zinc-400/[0.03]"
                          : requirement.status === "bound"
                            ? "border-emerald-400/30 bg-emerald-400/5"
                            : currentVersion
                              ? "border-sky-400/30 bg-sky-400/5"
                              : "border-orange-400/30 bg-orange-400/5"
                      }`}
                    >
                      <div className="flex items-start justify-between gap-4">
                        <div>
                          <p className="text-xs font-medium text-orange-300">
                            {requirementLabels[requirement.asset_type]}
                            {requirement.scene_scope_codes.length
                              ? `｜${requirement.scene_scope_codes.join("、")}`
                              : "｜全项目"}
                          </p>
                          <h3 className="mt-2 text-xl font-semibold text-zinc-100">
                            {requirement.name}
                          </h3>
                        </div>
                        <span
                          className={`rounded-full border px-3 py-1 text-xs ${
                            isTextOnly
                              ? "border-zinc-400/30 text-zinc-300"
                              : requirement.status === "bound"
                                ? "border-emerald-400/35 text-emerald-200"
                                : currentVersion
                                  ? "border-sky-400/35 text-sky-200"
                                  : "border-orange-400/35 text-orange-200"
                          }`}
                        >
                          {isTextOnly
                            ? "文字描述"
                            : requirement.status === "bound"
                              ? "关键参考已绑定"
                              : currentVersion
                                ? "关键图片已确认"
                                : "等待关键图片"}
                        </span>
                      </div>
                      <p className="mt-3 text-sm leading-6 text-zinc-300">
                        {requirement.description}
                      </p>
                      {requirement.evidence ? (
                        <p className="mt-2 text-xs leading-5 text-zinc-500">
                          剧本依据：{requirement.evidence}
                        </p>
                      ) : null}
                      {requirement.importance_reason ? (
                        <p className="mt-2 text-xs leading-5 text-zinc-400">
                          分类依据：{requirement.importance_reason}
                        </p>
                      ) : null}

                      {isTextOnly ? (
                        <div className="mt-4 border border-white/10 bg-black/10 p-4">
                          <p className="text-xs font-medium text-zinc-300">
                            后续视频中的文字描述
                          </p>
                          <p className="mt-2 text-sm leading-6 text-zinc-400">
                            {requirement.text_prompt ||
                              requirement.description ||
                              "保留剧情原文描述，由视频模型合理补全。"}
                          </p>
                          {target?.versions.length ? (
                            <p className="mt-2 text-xs text-zinc-500">
                              已有图片版本仍保留在历史中，但不会自动进入
                              @图片绑定。
                            </p>
                          ) : null}
                        </div>
                      ) : target ? (
                        renderImageControls(target.kind, target.id)
                      ) : (
                        <p className="mt-3 border border-red-400/25 bg-red-400/5 p-3 text-xs text-red-200">
                          这条清单还没有建立对应资产记录，请重新识别关键资产。
                        </p>
                      )}
                      {!isTextOnly && target ? (
                        <VersionRail
                          versions={target.versions}
                          kind={target.kind}
                          assetName={requirement.name}
                          projectId={activeProject.id}
                          onTransition={(kind, versionId, action) =>
                            void perform(
                              () =>
                                transitionAssetVersion(kind, versionId, action),
                              "正在更新图片版本…",
                            )
                          }
                        />
                      ) : null}

                      <details className="mt-4 border-t border-white/10 pt-3">
                        <summary className="cursor-pointer text-sm text-zinc-400 hover:text-zinc-200">
                          修改分类、描述或出现场次
                        </summary>
                        {draft ? (
                          <div className="mt-4 space-y-3">
                            <label className="block text-xs text-zinc-400">
                              后续使用方式
                              <select
                                value={draft.reference_mode}
                                onChange={(event) =>
                                  setRequirementDrafts((current) => ({
                                    ...current,
                                    [requirement.id]: {
                                      ...draft,
                                      reference_mode: event.target.value as
                                        | "visual"
                                        | "text_only",
                                    },
                                  }))
                                }
                                className="mt-2 w-full border border-white/15 bg-[#11171d] px-3 py-2.5 text-sm text-zinc-100 outline-none focus:border-orange-400/70"
                              >
                                <option value="visual">
                                  关键参考：需要图片并保持一致
                                </option>
                                <option value="text_only">
                                  文字描述：不绑定图片，允许合理发挥
                                </option>
                              </select>
                            </label>
                            <Input
                              label="名称"
                              value={draft.name}
                              onChange={(name) =>
                                setRequirementDrafts((current) => ({
                                  ...current,
                                  [requirement.id]: { ...draft, name },
                                }))
                              }
                            />
                            <Textarea
                              label="剧情设定"
                              value={draft.description}
                              onChange={(description) =>
                                setRequirementDrafts((current) => ({
                                  ...current,
                                  [requirement.id]: { ...draft, description },
                                }))
                              }
                            />
                            <Textarea
                              label="为什么这样分类"
                              value={draft.importance_reason}
                              onChange={(importance_reason) =>
                                setRequirementDrafts((current) => ({
                                  ...current,
                                  [requirement.id]: {
                                    ...draft,
                                    importance_reason,
                                  },
                                }))
                              }
                            />
                            {draft.reference_mode === "visual" ? (
                              <Textarea
                                label="生成关键参考图时必须遵守的画面要求"
                                value={draft.visual_prompt}
                                onChange={(visual_prompt) =>
                                  setRequirementDrafts((current) => ({
                                    ...current,
                                    [requirement.id]: {
                                      ...draft,
                                      visual_prompt,
                                    },
                                  }))
                                }
                              />
                            ) : (
                              <Textarea
                                label="写入视频提示词的文字描述"
                                value={draft.text_prompt}
                                onChange={(text_prompt) =>
                                  setRequirementDrafts((current) => ({
                                    ...current,
                                    [requirement.id]: { ...draft, text_prompt },
                                  }))
                                }
                              />
                            )}
                            <div>
                              <p className="text-xs text-zinc-400">
                                出现在哪些场次
                              </p>
                              <div className="mt-2 flex flex-wrap gap-2">
                                {(workspace?.scenes ?? []).map((scene) => {
                                  const checked = draft.scene_ids.includes(
                                    scene.id,
                                  );
                                  return (
                                    <label
                                      key={scene.id}
                                      className="flex items-center gap-2 border border-white/12 px-3 py-2 text-xs text-zinc-300"
                                    >
                                      <input
                                        type="checkbox"
                                        checked={checked}
                                        onChange={() =>
                                          setRequirementDrafts((current) => ({
                                            ...current,
                                            [requirement.id]: {
                                              ...draft,
                                              scene_ids: checked
                                                ? draft.scene_ids.filter(
                                                    (id) => id !== scene.id,
                                                  )
                                                : [
                                                    ...draft.scene_ids,
                                                    scene.id,
                                                  ],
                                            },
                                          }))
                                        }
                                      />
                                      {scene.scope_code}｜{scene.name}
                                    </label>
                                  );
                                })}
                              </div>
                            </div>
                            <button
                              type="button"
                              disabled={busy || !draft.name.trim()}
                              onClick={() => void saveRequirement(requirement)}
                              className="border border-orange-400/45 px-4 py-2 text-sm text-orange-200 disabled:opacity-45"
                            >
                              保存修改
                            </button>
                          </div>
                        ) : null}
                      </details>
                    </article>
                  );
                })}
              </div>
            </div>

            {(() => {
              const requirements = workspace?.requirements ?? [];
              const readyCount = requirements.filter((requirement) => {
                if (requirement.reference_mode === "text_only") return true;
                const target = workspace
                  ? requirementTarget(workspace, requirement)
                  : null;
                return Boolean(target && activeVersion(target.versions));
              }).length;
              const boundCount = requirements.filter(
                (requirement) =>
                  requirement.reference_mode === "text_only" ||
                  requirement.status === "bound",
              ).length;
              const allReady =
                requirements.length > 0 && readyCount === requirements.length;
              const allBound =
                requirements.length > 0 && boundCount === requirements.length;
              return (
                <GuideActionCard
                  progressLabel={
                    bindingFeedback?.tone === "progress"
                      ? bindingFeedback.message
                      : undefined
                  }
                  eyebrow={
                    allBound ? "资产已就位" : allReady ? "最后一步" : "当前进度"
                  }
                  title={
                    allBound
                      ? "人物、服装、场景和道具已按剧情绑定"
                      : allReady
                        ? "把确认好的资产自动放进对应场次"
                        : `已处理 ${readyCount}/${requirements.length} 项资产要求`
                  }
                  description={
                    allBound
                      ? "关键参考会进入 @图片绑定，普通细节会以文字描述进入视频提示词。"
                      : allReady
                        ? "系统会按出现场次绑定关键参考，并把文字描述交给视频模型；之后仍可手动修正。"
                        : "请继续处理上方标记为“等待关键图片”的项目。文字描述项无需生图，历史版本不会被覆盖。"
                  }
                  tone={allBound ? "done" : "current"}
                >
                  <div className="space-y-3">
                    {allBound ? (
                      <GuidePrimaryButton href="/video-package">
                        下一步：生成成片提示词
                      </GuidePrimaryButton>
                    ) : allReady ? (
                      <GuidePrimaryButton
                        disabled={busy}
                        onClick={() => void bindAllReadyAssets()}
                      >
                        {bindingFeedback?.tone === "progress"
                          ? "正在自动绑定…"
                          : bindingFeedback?.tone === "error"
                            ? "再次自检并修复"
                            : "自检并修复自动绑定"}
                      </GuidePrimaryButton>
                    ) : null}
                    {bindingFeedback ? (
                      <div
                        role="status"
                        aria-live="polite"
                        className={`border-l-2 px-3 py-2 text-sm leading-6 ${
                          bindingFeedback.tone === "success"
                            ? "border-emerald-400 bg-emerald-400/8 text-emerald-200"
                            : bindingFeedback.tone === "error"
                              ? "border-red-400 bg-red-400/8 text-red-200"
                              : "border-cyan-400 bg-cyan-400/8 text-cyan-100"
                        }`}
                      >
                        <p>{bindingFeedback.message}</p>
                        {bindingFeedback.issues?.length ? (
                          <ul className="mt-3 space-y-2 text-left">
                            {bindingFeedback.issues.map((issue) => (
                              <li
                                key={issue.id}
                                className="border border-red-300/20 bg-black/15 px-3 py-2"
                              >
                                <strong className="block text-red-100">
                                  {issue.label}
                                </strong>
                                <span className="block">
                                  原因：{issue.reason}
                                </span>
                                <span className="block text-zinc-300">
                                  处理：{issue.action}
                                </span>
                              </li>
                            ))}
                          </ul>
                        ) : null}
                      </div>
                    ) : null}
                  </div>
                </GuideActionCard>
              );
            })()}
          </>
        )}
      </section>

      <div className="mt-5">
        <ErrorBanner message={error} onClose={() => setError(null)} />
        {busy ? (
          <GuideProgress label={busyMessage || "正在处理资产，请稍等…"} />
        ) : null}
      </div>

      <TechDetails
        title="手动补录与绑定（识别不准时使用）"
        open={showManualArea}
        onToggle={(event) => setShowManualArea(event.currentTarget.open)}
      >
        <section className="mb-5 flex flex-wrap gap-2 border-y border-white/10 py-3">
          {[
            ["characters", "人物与服装", UserRound],
            ["scenes", "场景资产", MapPinned],
            ["bindings", "场次绑定", Link2],
          ].map(([key, label, Icon]) => (
            <button
              key={key as string}
              type="button"
              onClick={() => setTab(key as Tab)}
              className={`flex items-center gap-2 px-3 py-2 text-sm transition ${
                tab === key
                  ? "bg-orange-400/12 text-orange-300"
                  : "text-zinc-400 hover:bg-white/5 hover:text-zinc-100"
              }`}
            >
              <Icon size={16} />
              {label as string}
            </button>
          ))}
          <span className="ml-auto self-center text-xs text-zinc-500">
            {activeProject.project_code}｜每次生成都会先问你
          </span>
        </section>

        {tab === "characters" && (
          <div className="mt-5 grid grid-cols-[300px_minmax(0,1fr)] gap-5">
            <aside className="space-y-4">
              <section className="border border-white/15 bg-[#151b21]/90 p-4">
                <h2 className="font-semibold text-zinc-100">人物列表</h2>
                <div className="mt-3 space-y-2">
                  {workspace?.characters.length ? (
                    workspace.characters.map((character) => (
                      <button
                        key={character.id}
                        type="button"
                        onClick={() => setSelectedCharacterId(character.id)}
                        className={`w-full border px-3 py-2.5 text-left text-sm ${
                          selectedCharacterId === character.id
                            ? "border-orange-400/60 bg-orange-400/8 text-orange-200"
                            : "border-white/10 text-zinc-300"
                        }`}
                      >
                        {character.character_code}｜{character.name}
                      </button>
                    ))
                  ) : (
                    <p className="text-sm text-zinc-500">还没有人物。</p>
                  )}
                </div>
              </section>
              <form
                className="space-y-3 border border-white/15 bg-[#151b21]/90 p-4"
                onSubmit={(event) => {
                  event.preventDefault();
                  void perform(async () => {
                    const next = await createCharacter(
                      activeProject.id,
                      characterDraft,
                    );
                    setCharacterDraft(emptyCharacter);
                    setSelectedCharacterId(next.characters.at(-1)?.id ?? "");
                    return next;
                  });
                }}
              >
                <h2 className="font-semibold text-zinc-100">新增人物</h2>
                <Input
                  label="角色名"
                  value={characterDraft.name}
                  onChange={(name) =>
                    setCharacterDraft({ ...characterDraft, name })
                  }
                />
                <Input
                  label="脸型"
                  value={characterDraft.face_shape}
                  onChange={(face_shape) =>
                    setCharacterDraft({ ...characterDraft, face_shape })
                  }
                />
                <Input
                  label="五官"
                  value={characterDraft.facial_features}
                  onChange={(facial_features) =>
                    setCharacterDraft({ ...characterDraft, facial_features })
                  }
                />
                <Input
                  label="年龄"
                  value={characterDraft.age_description}
                  onChange={(age_description) =>
                    setCharacterDraft({ ...characterDraft, age_description })
                  }
                />
                <Input
                  label="身高"
                  value={characterDraft.height_description}
                  onChange={(height_description) =>
                    setCharacterDraft({ ...characterDraft, height_description })
                  }
                />
                <Input
                  label="体型"
                  value={characterDraft.body_type}
                  onChange={(body_type) =>
                    setCharacterDraft({ ...characterDraft, body_type })
                  }
                />
                <Input
                  label="发型"
                  value={characterDraft.hair_style}
                  onChange={(hair_style) =>
                    setCharacterDraft({ ...characterDraft, hair_style })
                  }
                />
                <Textarea
                  label="身份气质"
                  value={characterDraft.identity_temperament}
                  onChange={(identity_temperament) =>
                    setCharacterDraft({
                      ...characterDraft,
                      identity_temperament,
                    })
                  }
                />
                <button
                  disabled={busy || !characterDraft.name.trim()}
                  className="flex items-center gap-2 bg-orange-500 px-3 py-2 text-sm font-medium text-black disabled:opacity-45"
                >
                  <Plus size={15} /> 登记人物
                </button>
              </form>
            </aside>

            <div className="min-w-0 space-y-5">
              {selectedCharacter ? (
                <>
                  <section className="border border-white/15 bg-[#151b21]/90 p-5">
                    <div className="flex items-center justify-between gap-3">
                      <div>
                        <p className="text-xs tracking-[0.16em] text-orange-400">
                          {selectedCharacter.character_code}
                        </p>
                        <h2 className="mt-1 text-xl font-semibold text-zinc-100">
                          {selectedCharacter.name}｜人物母版
                        </h2>
                      </div>
                    </div>
                    {renderImageControls(
                      "character-master",
                      selectedCharacter.id,
                    )}
                    <div className="mt-4 grid grid-cols-4 gap-3 text-xs text-zinc-400">
                      <p>脸型：{selectedCharacter.face_shape || "未填写"}</p>
                      <p>
                        五官：{selectedCharacter.facial_features || "未填写"}
                      </p>
                      <p>
                        年龄：{selectedCharacter.age_description || "未填写"}
                      </p>
                      <p>
                        身高：{selectedCharacter.height_description || "未填写"}
                      </p>
                      <p>体型：{selectedCharacter.body_type || "未填写"}</p>
                      <p>发型：{selectedCharacter.hair_style || "未填写"}</p>
                      <p className="col-span-2">
                        身份气质：
                        {selectedCharacter.identity_temperament || "未填写"}
                      </p>
                    </div>
                    <VersionRail
                      versions={selectedCharacter.master_versions}
                      kind="character-master"
                      assetName={selectedCharacter.name}
                      projectId={activeProject.id}
                      onTransition={(kind, id, action) =>
                        void perform(() =>
                          transitionAssetVersion(kind, id, action),
                        )
                      }
                    />
                  </section>

                  <section className="border border-white/15 bg-[#151b21]/90 p-5">
                    <div className="flex items-center gap-2 text-orange-300">
                      <ShieldCheck size={18} />
                      <h2 className="font-semibold">换衣服，但不换人</h2>
                    </div>
                    <p className="mt-2 text-sm leading-6 text-zinc-400">
                      服装可以改变，但不得改变人物母版中的脸、年龄、骨相、体型、身高与身份气质。
                    </p>
                    <form
                      onSubmit={(event) => {
                        event.preventDefault();
                        void perform(async () => {
                          const next = await createCostume(
                            selectedCharacter.id,
                            costumeUsage,
                            costumeDescription,
                          );
                          setCostumeUsage("");
                          setCostumeDescription("");
                          return next;
                        });
                      }}
                      className="mt-4 grid grid-cols-[180px_minmax(0,1fr)_auto] gap-3"
                    >
                      <Input
                        label="使用场合"
                        value={costumeUsage}
                        onChange={setCostumeUsage}
                        placeholder="例如：登基大典"
                      />
                      <Input
                        label="服装说明"
                        value={costumeDescription}
                        onChange={setCostumeDescription}
                        placeholder="例如：玄色礼服，金线暗纹"
                      />
                      <button
                        disabled={busy || !costumeUsage.trim()}
                        className="mt-6 bg-orange-500 px-3 py-2 text-sm font-medium text-black disabled:opacity-45"
                      >
                        新增服装
                      </button>
                    </form>
                    <div className="mt-5 space-y-4">
                      {selectedCharacter.costumes.length ? (
                        selectedCharacter.costumes.map((costume) => (
                          <article
                            key={costume.id}
                            className="border border-white/10 p-4"
                          >
                            <div className="flex items-center justify-between gap-3">
                              <div>
                                <p className="text-sm font-medium text-zinc-100">
                                  {costume.costume_code}｜
                                  {costume.usage_context}
                                </p>
                                <p className="mt-1 text-xs text-zinc-500">
                                  {costume.description || "未填写服装说明"}
                                </p>
                              </div>
                            </div>
                            {renderImageControls("costume", costume.id)}
                            <VersionRail
                              versions={costume.versions}
                              kind="costume"
                              assetName={costume.usage_context}
                              projectId={activeProject.id}
                              onTransition={(kind, id, action) =>
                                void perform(() =>
                                  transitionAssetVersion(kind, id, action),
                                )
                              }
                            />
                          </article>
                        ))
                      ) : (
                        <p className="text-sm text-zinc-500">
                          还没有服装派生记录。
                        </p>
                      )}
                    </div>
                  </section>
                </>
              ) : (
                <section className="border border-dashed border-white/15 p-8 text-sm text-zinc-500">
                  请先登记人物。
                </section>
              )}
            </div>
          </div>
        )}

        {tab === "scenes" && (
          <section className="mt-5 border border-white/15 bg-[#151b21]/90 p-5">
            <div className="flex items-center justify-between gap-3">
              <div>
                <h2 className="font-semibold text-zinc-100">场景资产</h2>
                <p className="mt-1 text-xs text-zinc-500">
                  先写清楚空间、光线、道具和色彩氛围，再用 AI 生成正式场景版本。
                </p>
              </div>
              <div className="flex gap-2">
                <select
                  value={selectedSceneId}
                  onChange={(event) => {
                    setSelectedSceneId(event.target.value);
                    setSelectedSceneAssetId("");
                  }}
                  className="border border-white/15 bg-[#11171c] px-3 py-2 text-sm text-zinc-100"
                >
                  {workspace?.scenes.map((scene) => (
                    <option key={scene.id} value={scene.id}>
                      {scene.scope_code}｜{scene.name}
                    </option>
                  ))}
                </select>
                {sceneAssets.length > 1 ? (
                  <select
                    aria-label="选择场景资产"
                    value={selectedSceneAsset?.id ?? ""}
                    onChange={(event) =>
                      setSelectedSceneAssetId(event.target.value)
                    }
                    className="border border-white/15 bg-[#11171c] px-3 py-2 text-sm text-zinc-100"
                  >
                    {sceneAssets.map((asset) => (
                      <option key={asset.id} value={asset.id}>
                        {asset.name || "未命名场景"}
                      </option>
                    ))}
                  </select>
                ) : null}
              </div>
            </div>
            <form
              onSubmit={(event) => {
                event.preventDefault();
                if (selectedSceneId)
                  void perform(() =>
                    saveSceneAsset(selectedSceneId, sceneDraft),
                  );
              }}
              className="mt-5 grid grid-cols-2 gap-3"
            >
              <Input
                label="场景名称（同一场次有多个地点时用于区分）"
                value={sceneDraft.name}
                onChange={(name) => setSceneDraft({ ...sceneDraft, name })}
                placeholder="例如：红泥坡训练场；留空为默认场景"
              />
              <Textarea
                label="场景说明"
                value={sceneDraft.description}
                onChange={(description) =>
                  setSceneDraft({ ...sceneDraft, description })
                }
                placeholder="例如：坤宁宫寝殿"
              />
              <Textarea
                label="空间布局"
                value={sceneDraft.spatial_layout}
                onChange={(spatial_layout) =>
                  setSceneDraft({ ...sceneDraft, spatial_layout })
                }
              />
              <Textarea
                label="时间 / 天气 / 光线"
                value={sceneDraft.time_weather_light}
                onChange={(time_weather_light) =>
                  setSceneDraft({ ...sceneDraft, time_weather_light })
                }
              />
              <Textarea
                label="关键道具"
                value={sceneDraft.key_props}
                onChange={(key_props) =>
                  setSceneDraft({ ...sceneDraft, key_props })
                }
              />
              <Textarea
                label="主色 / 辅色 / 氛围"
                value={sceneDraft.palette_mood}
                onChange={(palette_mood) =>
                  setSceneDraft({ ...sceneDraft, palette_mood })
                }
              />
              <div className="flex items-end gap-3">
                <button
                  disabled={busy || !selectedSceneId}
                  className="bg-orange-500 px-4 py-2.5 text-sm font-medium text-black disabled:opacity-45"
                >
                  保存场景结构
                </button>
              </div>
            </form>
            {selectedSceneAsset && (
              <>
                {renderImageControls("scene", selectedSceneAsset.id)}
                <VersionRail
                  versions={selectedSceneAsset.versions}
                  kind="scene"
                  assetName="场景资产"
                  projectId={activeProject.id}
                  onTransition={(kind, id, action) =>
                    void perform(() => transitionAssetVersion(kind, id, action))
                  }
                />
              </>
            )}
          </section>
        )}

        {tab === "bindings" && (
          <div className="mt-5 grid grid-cols-[420px_minmax(0,1fr)] gap-5">
            <form
              onSubmit={(event) => {
                event.preventDefault();
                if (
                  bindingSceneId &&
                  bindingCharacterId &&
                  bindingMasterId &&
                  bindingCostumeVersionId
                )
                  void perform(() =>
                    saveSceneBinding(
                      bindingSceneId,
                      bindingCharacterId,
                      bindingMasterId,
                      bindingCostumeVersionId,
                      sceneState,
                      hairChangeReason,
                    ),
                  );
              }}
              className="space-y-3 border border-white/15 bg-[#151b21]/90 p-5"
            >
              <h2 className="font-semibold text-zinc-100">登记场次人物绑定</h2>
              <label className="block text-xs text-zinc-400">
                场次
                <select
                  value={bindingSceneId}
                  onChange={(event) => setBindingSceneId(event.target.value)}
                  className="mt-2 w-full border border-white/15 bg-[#11171c] px-3 py-2.5 text-sm text-zinc-100"
                >
                  {workspace?.scenes.map((scene) => (
                    <option key={scene.id} value={scene.id}>
                      {scene.scope_code}｜{scene.name}
                    </option>
                  ))}
                </select>
              </label>
              <label className="block text-xs text-zinc-400">
                人物
                <select
                  value={bindingCharacterId}
                  onChange={(event) =>
                    setBindingCharacterId(event.target.value)
                  }
                  className="mt-2 w-full border border-white/15 bg-[#11171c] px-3 py-2.5 text-sm text-zinc-100"
                >
                  <option value="">请选择人物</option>
                  {workspace?.characters.map((character) => (
                    <option key={character.id} value={character.id}>
                      {character.character_code}｜{character.name}
                    </option>
                  ))}
                </select>
              </label>
              <label className="block text-xs text-zinc-400">
                已确认人物母版
                <select
                  value={bindingMasterId}
                  onChange={(event) => setBindingMasterId(event.target.value)}
                  className="mt-2 w-full border border-white/15 bg-[#11171c] px-3 py-2.5 text-sm text-zinc-100"
                >
                  <option value="">请选择母版</option>
                  {confirmedMasters.map((version) => (
                    <option key={version.id} value={version.id}>
                      V{String(version.version_number).padStart(3, "0")}｜
                      {version.status}
                    </option>
                  ))}
                </select>
              </label>
              <label className="block text-xs text-zinc-400">
                已确认服装版本
                <select
                  value={bindingCostumeVersionId}
                  onChange={(event) =>
                    setBindingCostumeVersionId(event.target.value)
                  }
                  className="mt-2 w-full border border-white/15 bg-[#11171c] px-3 py-2.5 text-sm text-zinc-100"
                >
                  <option value="">请选择服装</option>
                  {confirmedCostumeVersions.map(({ costume, version }) => (
                    <option key={version.id} value={version.id}>
                      {costume.costume_code}｜V
                      {String(version.version_number).padStart(3, "0")}
                    </option>
                  ))}
                </select>
              </label>
              <Textarea
                label="场次状态"
                value={sceneState}
                onChange={setSceneState}
                placeholder="例如：病态、战损、湿发、污渍"
              />
              <Textarea
                label="发型变化原因（如有）"
                value={hairChangeReason}
                onChange={setHairChangeReason}
                placeholder="例如：雨夜赶路后湿发"
              />
              <button
                disabled={
                  busy ||
                  !bindingSceneId ||
                  !bindingCharacterId ||
                  !bindingMasterId ||
                  !bindingCostumeVersionId
                }
                className="bg-orange-500 px-4 py-2.5 text-sm font-medium text-black disabled:opacity-45"
              >
                保存绑定与一致性记录
              </button>
            </form>
            <section className="space-y-3">
              <div>
                <h2 className="font-semibold text-zinc-100">人物一致性检查</h2>
                <p className="mt-1 text-xs text-zinc-500">
                  故事板可以先用分镜提示词做黑白草稿；成片提示词会继续检查资产引用。
                </p>
              </div>
              {workspace?.bindings.length ? (
                workspace.bindings.map((binding) => (
                  <article
                    key={binding.id}
                    className="border border-white/15 bg-[#151b21]/90 p-4"
                  >
                    <div className="flex items-center justify-between gap-3">
                      <p className="text-sm font-medium text-zinc-100">
                        {binding.scope_code}｜{binding.character_name}｜
                        {binding.costume_code}
                      </p>
                      <span
                        className={
                          binding.consistency_status === "passed"
                            ? "text-xs text-emerald-300"
                            : "text-xs text-red-300"
                        }
                      >
                        {binding.consistency_status === "passed"
                          ? "检查通过"
                          : "需要修正"}
                      </span>
                    </div>
                    <div className="mt-3 space-y-2">
                      {binding.checks.map((check) => (
                        <div
                          key={check.key}
                          className="flex items-start gap-2 text-xs"
                        >
                          {check.status === "passed" ? (
                            <CheckCircle2
                              size={15}
                              className="shrink-0 text-emerald-300"
                            />
                          ) : check.status === "failed" ? (
                            <CircleAlert
                              size={15}
                              className="shrink-0 text-red-300"
                            />
                          ) : (
                            <CircleDashed
                              size={15}
                              className="shrink-0 text-zinc-500"
                            />
                          )}
                          <p className="text-zinc-300">
                            {humanizeCopy(check.label)}
                            <span className="ml-2 text-zinc-500">
                              {humanizeCopy(check.detail)}
                            </span>
                          </p>
                        </div>
                      ))}
                    </div>
                  </article>
                ))
              ) : (
                <p className="border border-dashed border-white/15 p-6 text-sm text-zinc-500">
                  还没有场次人物绑定。
                </p>
              )}
            </section>
          </div>
        )}
      </TechDetails>
    </div>
  );
}
