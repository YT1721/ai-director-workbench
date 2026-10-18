import type { SeedanceSkillStatus, SystemPromptStatus } from "../types/system";
import type {
  AssetImageJob,
  AssetImageReadiness,
  AssetImageTargetKind,
  AssetWorkspace,
  CharacterDraft,
  SceneAssetDraft,
} from "../types/assets";
import type {
  IntakeDraft,
  ProjectDetail,
  ProjectOverview,
  ProjectSummary,
  SourceInputCategory,
  SourceFile,
  UcodeRun,
} from "../types/workbench";
import type {
  AxisPlan,
  PromptStoryboardExport,
  StoryboardImageJob,
  StoryboardImageReadiness,
  StoryboardVersionDraft,
  StoryboardWorkspace,
} from "../types/storyboards";
import type {
  BatchWorkspace,
  JimengCliReadiness,
  JimengCliStatus,
  JimengVideoModel,
  LiveProviderStatus,
  LiveReadiness,
  ProviderPreflight,
  ProviderProfile,
  ProviderRequestPreview,
  ProviderResponsePreview,
  ProviderTemplate,
  VideoGenerationSettings,
  VideoPackageWorkspace,
  VideoProviderModel,
  VideoReferenceItemUpdate,
  VideoTaskSupervisorStatus,
} from "../types/videos";
import type {
  AiProviderStatus,
  AiTextRun,
  AiTextRunCreate,
  LocalEnvStatus,
  LocalEnvUpdate,
  RealTextAcceptance,
  TextProviderStatus,
  WorkflowReview,
} from "../types/workflows";
import type { FlowNav } from "../types/flowNav";
import type { PlanningDraft, SourceTextExtraction } from "../types/planning";
import type { CreativeGoal } from "../utils/creativeGoal";
import type {
  SeedanceOsWorkspace,
  SeedancePromptCompileResult,
  SeedanceTakeReview,
} from "../types/seedanceOs";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "";

function apiUrl(path: string): string {
  return `${API_BASE_URL}${path}`;
}

export async function fetchSystemPromptStatus(): Promise<SystemPromptStatus> {
  return request<SystemPromptStatus>("/api/system-prompt/status");
}

export async function fetchSeedanceSkillStatus(): Promise<SeedanceSkillStatus> {
  return request<SeedanceSkillStatus>("/api/seedance-skill-os/status");
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(apiUrl(path), options);
  } catch {
    throw new Error(
      "无法连接后端服务。请确认 FastAPI 已在 127.0.0.1:8000 启动，并且前端 6001 已开启代理，然后刷新页面再试。",
    );
  }
  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as {
      detail?: string;
    } | null;
    throw new Error(
      body?.detail ??
        `接口 ${path} 请求失败（HTTP ${response.status}），请刷新后重试。`,
    );
  }
  if (response.status === 204) {
    return undefined as T;
  }
  const result = response.json() as Promise<T>;
  if (options?.method && options.method !== "GET") {
    window.dispatchEvent(new CustomEvent("flow-nav-refresh"));
  }
  return result;
}

const jsonHeaders = { "Content-Type": "application/json" };

export function fetchProjects(
  includeArchived = false,
): Promise<ProjectSummary[]> {
  return request(`/api/projects?include_archived=${includeArchived}`);
}

export function fetchProjectOverview(
  includeArchived = true,
): Promise<ProjectOverview[]> {
  return request(`/api/projects/overview?include_archived=${includeArchived}`);
}

export function fetchProject(projectId: string): Promise<ProjectDetail> {
  return request(`/api/projects/${projectId}`);
}

export function createProject(
  name: string,
  description: string,
): Promise<ProjectDetail> {
  return request("/api/projects", {
    method: "POST",
    headers: jsonHeaders,
    body: JSON.stringify({ name, description }),
  });
}

export function createRealAcceptanceProject(): Promise<ProjectDetail> {
  return request("/api/projects/real-acceptance", {
    method: "POST",
    headers: jsonHeaders,
    body: JSON.stringify({}),
  });
}

export function updateProject(
  projectId: string,
  name: string,
  description: string,
): Promise<ProjectDetail> {
  return request(`/api/projects/${projectId}`, {
    method: "PATCH",
    headers: jsonHeaders,
    body: JSON.stringify({ name, description }),
  });
}

export function updateProjectCreativeGoal(
  projectId: string,
  creativeGoal: CreativeGoal,
): Promise<ProjectDetail> {
  return request(`/api/projects/${projectId}/creative-goal`, {
    method: "PATCH",
    headers: jsonHeaders,
    body: JSON.stringify({ creative_goal: creativeGoal }),
  });
}

export function setProjectArchived(
  projectId: string,
  archived: boolean,
): Promise<ProjectDetail> {
  return request(`/api/projects/${projectId}${archived ? "" : "/restore"}`, {
    method: archived ? "DELETE" : "POST",
  });
}

export function hardDeleteProject(
  projectId: string,
  confirmProjectName: string,
): Promise<void> {
  return request(`/api/projects/${projectId}/hard-delete`, {
    method: "POST",
    headers: jsonHeaders,
    body: JSON.stringify({
      confirm_delete: true,
      confirm_project_name: confirmProjectName,
    }),
  });
}

export function projectExportUrl(projectId: string): string {
  return apiUrl(`/api/projects/${projectId}/export`);
}

export function createEpisode(projectId: string): Promise<ProjectDetail> {
  return request(`/api/projects/${projectId}/episodes`, { method: "POST" });
}

export function createScene(episodeId: string): Promise<ProjectDetail> {
  return request(`/api/episodes/${episodeId}/scenes`, { method: "POST" });
}

export function createShot(sceneId: string): Promise<ProjectDetail> {
  return request(`/api/scenes/${sceneId}/shots`, { method: "POST" });
}

export function renameHierarchy(
  kind: "episodes" | "scenes" | "shots",
  id: string,
  name: string,
): Promise<ProjectDetail> {
  return request(`/api/${kind}/${id}`, {
    method: "PATCH",
    headers: jsonHeaders,
    body: JSON.stringify({ name }),
  });
}

export function setHierarchyArchived(
  kind: "episodes" | "scenes" | "shots",
  id: string,
  archived: boolean,
): Promise<ProjectDetail> {
  return request(`/api/${kind}/${id}${archived ? "" : "/restore"}`, {
    method: archived ? "DELETE" : "POST",
  });
}

export function fetchSourceFiles(projectId: string): Promise<SourceFile[]> {
  return request(`/api/projects/${projectId}/source-files`);
}

export function uploadSourceFile(
  projectId: string,
  category: SourceInputCategory,
  file: File,
): Promise<SourceFile> {
  const body = new FormData();
  body.append("category", category);
  body.append("file", file);
  return request(`/api/projects/${projectId}/source-files`, {
    method: "POST",
    body,
  });
}

export function saveSourceText(
  projectId: string,
  category: "script_text" | "storyboard_table",
  title: string,
  content: string,
): Promise<SourceFile> {
  return request(`/api/projects/${projectId}/source-files/text`, {
    method: "POST",
    headers: jsonHeaders,
    body: JSON.stringify({ category, title, content }),
  });
}

export async function saveIntakeSource(
  projectId: string,
  intake: IntakeDraft,
): Promise<SourceFile> {
  if (intake.kind === "text") {
    return saveSourceText(
      projectId,
      intake.category,
      intake.title,
      intake.content,
    );
  }
  return uploadSourceFile(projectId, intake.category, intake.file);
}

export function fetchUcodeRuns(projectId: string): Promise<UcodeRun[]> {
  return request(`/api/projects/${projectId}/ucode-runs`);
}

export function extractSourceText(
  sourceFileId: string,
): Promise<SourceTextExtraction> {
  return request(`/api/source-files/${sourceFileId}/extract-text`, {
    method: "POST",
  });
}

export function fetchSourceTextExtractions(
  projectId: string,
): Promise<SourceTextExtraction[]> {
  return request(`/api/projects/${projectId}/source-text-extractions`);
}

export function fetchPlanningDrafts(
  projectId: string,
): Promise<PlanningDraft[]> {
  return request(`/api/projects/${projectId}/planning-drafts`);
}

export function applyPlanningDraft(draftId: string): Promise<PlanningDraft> {
  return request(`/api/planning-drafts/${draftId}/apply`, { method: "POST" });
}

export function fetchTextProviderStatus(): Promise<TextProviderStatus> {
  return request("/api/text-provider/status");
}

export function runTextProviderSmokeTest(
  payload: AiTextRunCreate,
): Promise<AiTextRun> {
  return request("/api/text-provider/smoke-test", {
    method: "POST",
    headers: jsonHeaders,
    body: JSON.stringify(payload),
  });
}

export function fetchAiTextRuns(projectId: string): Promise<AiTextRun[]> {
  return request(`/api/projects/${projectId}/ai-text-runs`);
}

export function fetchRealTextAcceptance(
  projectId: string,
): Promise<RealTextAcceptance> {
  return request(`/api/projects/${projectId}/real-text-acceptance`);
}

export function createAiTextRun(
  projectId: string,
  payload: AiTextRunCreate,
): Promise<AiTextRun> {
  return request(`/api/projects/${projectId}/ai-text-runs`, {
    method: "POST",
    headers: jsonHeaders,
    body: JSON.stringify(payload),
  });
}

export function createDirectorAnalysis(
  projectId: string,
  payload: AiTextRunCreate,
): Promise<AiTextRun> {
  return request(`/api/projects/${projectId}/director-analyses/ai`, {
    method: "POST",
    headers: jsonHeaders,
    body: JSON.stringify(payload),
  });
}

export function createAiPlanningDraft(
  projectId: string,
  payload: AiTextRunCreate,
): Promise<PlanningDraft> {
  return request(`/api/projects/${projectId}/planning-drafts/ai`, {
    method: "POST",
    headers: jsonHeaders,
    body: JSON.stringify(payload),
  });
}

export function createAssetBrief(
  projectId: string,
  payload: AiTextRunCreate,
): Promise<AiTextRun> {
  return request(`/api/projects/${projectId}/asset-briefs/ai`, {
    method: "POST",
    headers: jsonHeaders,
    body: JSON.stringify(payload),
  });
}

export function createStoryboardBrief(
  shotId: string,
  payload: AiTextRunCreate,
): Promise<AiTextRun> {
  return request(`/api/shots/${shotId}/storyboard-briefs/ai`, {
    method: "POST",
    headers: jsonHeaders,
    body: JSON.stringify(payload),
  });
}

export function executeUcodeRun(
  projectId: string,
  ucodeAction: string,
  scopeCode: string,
  additionalRequest: string,
): Promise<UcodeRun> {
  return request(`/api/projects/${projectId}/ucode-runs`, {
    method: "POST",
    headers: jsonHeaders,
    body: JSON.stringify({
      ucode_action: ucodeAction,
      scope_code: scopeCode,
      additional_request: additionalRequest,
    }),
  });
}

export function fetchFlowNav(projectId: string): Promise<FlowNav> {
  return request(`/api/projects/${projectId}/flow-nav`);
}

export function confirmDirectorOption(
  episodeId: string,
  optionName: string,
  notes: string,
): Promise<FlowNav> {
  return request(`/api/episodes/${episodeId}/director-option-confirmations`, {
    method: "POST",
    headers: jsonHeaders,
    body: JSON.stringify({ option_name: optionName, notes }),
  });
}

export function assetImageUrl(assetUrl: string): string {
  return apiUrl(assetUrl);
}

type SaveFilePickerHandle = {
  name?: string;
  createWritable: () => Promise<{
    write: (data: Blob) => Promise<void>;
    close: () => Promise<void>;
  }>;
};

declare global {
  interface Window {
    showSaveFilePicker?: (options?: {
      suggestedName?: string;
      types?: Array<{
        description: string;
        accept: Record<string, string[]>;
      }>;
    }) => Promise<SaveFilePickerHandle>;
  }
}

export type LocalAssetDownloadResult = {
  method: "save_picker" | "browser_download";
  filename: string;
};

function filenameFromAssetUrl(assetUrl: string, fallbackName: string): string {
  const cleanPath = assetUrl.split("?")[0] ?? "";
  const name = cleanPath.split("/").filter(Boolean).pop();
  return name ? decodeURIComponent(name) : fallbackName;
}

function pickerTypesFor(
  filename: string,
  mimeType: string,
):
  | Array<{ description: string; accept: Record<string, string[]> }>
  | undefined {
  const ext = filename.includes(".")
    ? `.${filename.split(".").pop()?.toLowerCase()}`
    : "";
  if (!ext) return undefined;
  if (ext === ".zip")
    return [
      { description: "ZIP 压缩包", accept: { "application/zip": [".zip"] } },
    ];
  if (ext === ".png")
    return [{ description: "PNG 图片", accept: { "image/png": [".png"] } }];
  if (ext === ".jpg" || ext === ".jpeg")
    return [
      { description: "图片文件", accept: { "image/jpeg": [".jpg", ".jpeg"] } },
    ];
  return [
    {
      description: "下载文件",
      accept: { [mimeType || "application/octet-stream"]: [ext] },
    },
  ];
}

export async function downloadLocalAsset(
  assetUrl: string,
  fallbackName = "download",
): Promise<LocalAssetDownloadResult> {
  const url = assetImageUrl(assetUrl);
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error("文件已经生成，但下载失败。请刷新页面后再试。");
  }
  const blob = await response.blob();
  const filename = filenameFromAssetUrl(assetUrl, fallbackName);

  if (window.showSaveFilePicker) {
    try {
      const handle = await window.showSaveFilePicker({
        suggestedName: filename,
        types: pickerTypesFor(filename, blob.type),
      });
      const writable = await handle.createWritable();
      await writable.write(blob);
      await writable.close();
      return { method: "save_picker", filename: handle.name || filename };
    } catch (error) {
      if (error instanceof DOMException && error.name === "AbortError") {
        throw new Error(
          "已取消保存。文件仍保存在项目本地目录，之后可以重新点击下载。",
        );
      }
      throw error;
    }
  }

  const objectUrl = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = objectUrl;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(objectUrl);
  return { method: "browser_download", filename };
}

export function revealInFolder(
  projectId: string,
  relativePath = "",
): Promise<{ opened: boolean; path: string }> {
  return request(`/api/projects/${projectId}/reveal`, {
    method: "POST",
    headers: jsonHeaders,
    body: JSON.stringify({ relative_path: relativePath }),
  });
}

export function fetchAssetWorkspace(
  projectId: string,
): Promise<AssetWorkspace> {
  return request(`/api/projects/${projectId}/assets`);
}

export function fetchAssetImageJobs(
  projectId: string,
): Promise<AssetImageJob[]> {
  return request(`/api/projects/${projectId}/asset-image-jobs`);
}

export function createCharacter(
  projectId: string,
  draft: CharacterDraft,
): Promise<AssetWorkspace> {
  return request(`/api/projects/${projectId}/characters`, {
    method: "POST",
    headers: jsonHeaders,
    body: JSON.stringify(draft),
  });
}

export function createCostume(
  characterId: string,
  usageContext: string,
  description: string,
): Promise<AssetWorkspace> {
  return request(`/api/characters/${characterId}/costumes`, {
    method: "POST",
    headers: jsonHeaders,
    body: JSON.stringify({
      usage_context: usageContext,
      description,
    }),
  });
}

export function saveSceneAsset(
  sceneId: string,
  draft: SceneAssetDraft,
): Promise<AssetWorkspace> {
  return request(`/api/scenes/${sceneId}/assets`, {
    method: "POST",
    headers: jsonHeaders,
    body: JSON.stringify(draft),
  });
}

export function saveSceneBinding(
  sceneId: string,
  characterId: string,
  characterMasterVersionId: string,
  costumeVersionId: string,
  sceneState: string,
  hairChangeReason: string,
): Promise<AssetWorkspace> {
  return request(`/api/scenes/${sceneId}/bindings`, {
    method: "POST",
    headers: jsonHeaders,
    body: JSON.stringify({
      character_id: characterId,
      character_master_version_id: characterMasterVersionId,
      costume_version_id: costumeVersionId,
      scene_state: sceneState,
      hair_change_reason: hairChangeReason,
    }),
  });
}

export function transitionAssetVersion(
  kind: AssetImageTargetKind,
  versionId: string,
  action: "confirm" | "lock" | "unlock" | "rollback",
): Promise<AssetWorkspace> {
  return request(`/api/asset-versions/${kind}/${versionId}/${action}`, {
    method: "POST",
  });
}

export function analyzeAssetInventory(
  projectId: string,
  forceRegenerate = false,
): Promise<AssetWorkspace> {
  return request(`/api/projects/${projectId}/asset-inventory/analyze`, {
    method: "POST",
    headers: jsonHeaders,
    body: JSON.stringify({
      confirm_live_request: true,
      force_regenerate: forceRegenerate,
    }),
  });
}

export function updateAssetRequirement(
  requirementId: string,
  payload: {
    name?: string;
    description?: string;
    visual_prompt?: string;
    reference_mode?: "visual" | "text_only";
    importance_reason?: string;
    text_prompt?: string;
    scene_ids?: string[];
  },
): Promise<AssetWorkspace> {
  return request(`/api/asset-requirements/${requirementId}`, {
    method: "PATCH",
    headers: jsonHeaders,
    body: JSON.stringify(payload),
  });
}

export function autoBindAssets(projectId: string): Promise<AssetWorkspace> {
  return request(`/api/projects/${projectId}/assets/auto-bind`, {
    method: "POST",
  });
}

export function fetchAssetImageReadiness(
  kind: AssetImageTargetKind,
  targetId: string,
): Promise<AssetImageReadiness> {
  return request(`/api/asset-images/${kind}/${targetId}/readiness`);
}

export function submitAssetImage(
  kind: AssetImageTargetKind,
  targetId: string,
): Promise<AssetImageJob> {
  return request(`/api/asset-images/${kind}/${targetId}/submit`, {
    method: "POST",
    headers: jsonHeaders,
    body: JSON.stringify({ confirm_live_request: true }),
  });
}

export function uploadAssetImage(
  kind: AssetImageTargetKind,
  targetId: string,
  file: File,
): Promise<AssetWorkspace> {
  const body = new FormData();
  body.append("file", file);
  return request(`/api/asset-images/${kind}/${targetId}/upload`, {
    method: "POST",
    body,
  });
}

export function pollAssetImage(jobId: string): Promise<AssetImageJob> {
  return request(`/api/asset-image-jobs/${jobId}/poll`, {
    method: "POST",
    headers: jsonHeaders,
    body: JSON.stringify({ confirm_live_request: true }),
  });
}

export function downloadAssetImage(jobId: string): Promise<AssetWorkspace> {
  return request(`/api/asset-image-jobs/${jobId}/download`, {
    method: "POST",
    headers: jsonHeaders,
    body: JSON.stringify({ confirm_live_request: true }),
  });
}

export function fetchStoryboardWorkspace(
  projectId: string,
): Promise<StoryboardWorkspace> {
  return request(`/api/projects/${projectId}/storyboards`);
}

export function saveAxisPlan(
  sceneId: string,
  draft: Omit<AxisPlan, "id" | "axis_code">,
): Promise<StoryboardWorkspace> {
  return request(`/api/scenes/${sceneId}/axis-plan`, {
    method: "PATCH",
    headers: jsonHeaders,
    body: JSON.stringify(draft),
  });
}

export function generateStoryboardVersion(
  shotId: string,
  draft: Partial<StoryboardVersionDraft> = {},
): Promise<StoryboardWorkspace> {
  return request(`/api/shots/${shotId}/storyboard-versions`, {
    method: "POST",
    headers: jsonHeaders,
    body: JSON.stringify(draft),
  });
}

export function transitionStoryboardVersion(
  versionId: string,
  action: "confirm" | "lock" | "rollback",
): Promise<StoryboardWorkspace> {
  return request(`/api/storyboard-versions/${versionId}/${action}`, {
    method: "POST",
  });
}

export function reuseStoryboardImage(
  versionId: string,
  sourceVersionId: string,
  forceReuse = false,
): Promise<StoryboardWorkspace> {
  return request(`/api/storyboard-versions/${versionId}/reuse-image`, {
    method: "POST",
    headers: jsonHeaders,
    body: JSON.stringify({
      source_version_id: sourceVersionId,
      confirm_reuse: true,
      force_reuse: forceReuse,
    }),
  });
}

export function generateStoryboardPage(
  sceneId: string,
): Promise<StoryboardWorkspace> {
  return request(`/api/scenes/${sceneId}/storyboard-pages`, {
    method: "POST",
  });
}

export function exportPromptStoryboardPack(
  sceneId: string,
): Promise<PromptStoryboardExport> {
  return request(`/api/scenes/${sceneId}/prompt-storyboard-export`, {
    method: "POST",
  });
}

export function fetchStoryboardImageReadiness(
  versionId: string,
): Promise<StoryboardImageReadiness> {
  return request(`/api/storyboard-versions/${versionId}/image-readiness`);
}

export function fetchStoryboardImagePrompt(
  versionId: string,
): Promise<{ prompt: string }> {
  return request(`/api/storyboard-versions/${versionId}/image-prompt`);
}

export function submitStoryboardImage(
  versionId: string,
  correctionNote = "",
  promptOverride = "",
): Promise<StoryboardImageJob> {
  return request(`/api/storyboard-versions/${versionId}/image-submit`, {
    method: "POST",
    headers: jsonHeaders,
    body: JSON.stringify({
      confirm_live_request: true,
      correction_note: correctionNote,
      prompt_override: promptOverride,
    }),
  });
}

export function pollStoryboardImage(
  jobId: string,
): Promise<StoryboardImageJob> {
  return request(`/api/image-generation-jobs/${jobId}/poll`, {
    method: "POST",
    headers: jsonHeaders,
    body: JSON.stringify({ confirm_live_request: true }),
  });
}

export function downloadStoryboardImage(
  jobId: string,
): Promise<StoryboardWorkspace> {
  return request(`/api/image-generation-jobs/${jobId}/download`, {
    method: "POST",
    headers: jsonHeaders,
    body: JSON.stringify({ confirm_live_request: true }),
  });
}

export function fetchVideoPackages(
  projectId: string,
): Promise<VideoPackageWorkspace> {
  return request(`/api/projects/${projectId}/video-packages`);
}
export function fetchLatestVpGenerationJob(
  sceneId: string,
): Promise<import("../types/videos").VpGenerationJob | null> {
  return request(`/api/scenes/${sceneId}/vp-generation-jobs/latest`);
}
export function startVpDurationRebuild(
  sceneId: string,
): Promise<import("../types/videos").VpGenerationJob> {
  return request(`/api/scenes/${sceneId}/vp-generation-jobs`, {
    method: "POST",
    headers: jsonHeaders,
    body: JSON.stringify({
      operation: "duration_rebuild",
      confirm_live_request: true,
    }),
  });
}
export function retryVpGenerationJob(
  jobId: string,
): Promise<import("../types/videos").VpGenerationJob> {
  return request(`/api/vp-generation-jobs/${jobId}/retry`, { method: "POST" });
}
export function cancelVpGenerationJob(
  jobId: string,
): Promise<import("../types/videos").VpGenerationJob> {
  return request(`/api/vp-generation-jobs/${jobId}/cancel`, { method: "POST" });
}
export function generateAiVpBlock(
  shotId: string,
  hasCharacter: boolean,
  packageStage: "director_draft" | "final_execution" = "director_draft",
  durationSeconds?: number,
): Promise<VideoPackageWorkspace> {
  return request(`/api/shots/${shotId}/vp-blocks/ai-version`, {
    method: "POST",
    headers: jsonHeaders,
    body: JSON.stringify({
      vp_block: {
        has_character: hasCharacter,
        package_stage: packageStage,
        ...(durationSeconds ? { duration_seconds: durationSeconds } : {}),
      },
      ai_text: { module_type: "vp_precision_18", confirm_live_request: true },
    }),
  });
}
export function transitionVpBlock(
  id: string,
  action: "confirm" | "lock" | "rollback",
): Promise<VideoPackageWorkspace> {
  return request(`/api/vp-blocks/${id}/${action}`, { method: "POST" });
}
export function fetchBatchVideo(projectId: string): Promise<BatchWorkspace> {
  return request(`/api/projects/${projectId}/batch-video`);
}
export function fetchSeedanceOsWorkspace(
  projectId: string,
): Promise<SeedanceOsWorkspace> {
  return request(`/api/projects/${projectId}/video-units/workspace`);
}
export function createSeedanceVideoUnit(
  projectId: string,
  payload: Record<string, unknown>,
): Promise<Record<string, unknown>> {
  return request(`/api/projects/${projectId}/video-units`, {
    method: "POST",
    headers: jsonHeaders,
    body: JSON.stringify(payload),
  });
}
export function compileSeedanceVideoUnit(
  videoUnitId: string,
  vpBlockId: string,
): Promise<SeedancePromptCompileResult> {
  return request(`/api/video-units/${videoUnitId}/compile/${vpBlockId}`, {
    method: "POST",
    headers: jsonHeaders,
    body: JSON.stringify({ vp_precision_18: [], additional_constraints: [] }),
  });
}
export function reviewSeedanceTake(
  videoUnitId: string,
  payload: Record<string, unknown>,
): Promise<SeedanceTakeReview> {
  return request(`/api/video-units/${videoUnitId}/take-reviews`, {
    method: "POST",
    headers: jsonHeaders,
    body: JSON.stringify(payload),
  });
}
export function createBatchVideo(
  sceneId: string,
  providerProfileId: string,
  submissionChannel: "huimeng" | "jimeng" | "volcengine_seedance25" = "jimeng",
): Promise<BatchWorkspace> {
  return request(`/api/scenes/${sceneId}/batch-video-jobs`, {
    method: "POST",
    headers: jsonHeaders,
    body: JSON.stringify({
      provider_profile_id: providerProfileId,
      submission_channel: submissionChannel,
    }),
  });
}
export function remapBatchVideoProvider(
  jobId: string,
  providerProfileId: string,
): Promise<BatchWorkspace> {
  return request(`/api/batch-video-jobs/${jobId}/remap-provider`, {
    method: "POST",
    headers: jsonHeaders,
    body: JSON.stringify({ provider_profile_id: providerProfileId }),
  });
}
export function updateBatchVideoSubmissionChannel(
  jobId: string,
  submissionChannel: "huimeng" | "jimeng" | "volcengine_seedance25",
  huimengProviderProfileId = "",
): Promise<BatchWorkspace> {
  return request(`/api/batch-video-jobs/${jobId}/submission-channel`, {
    method: "PATCH",
    headers: jsonHeaders,
    body: JSON.stringify({
      submission_channel: submissionChannel,
      huimeng_provider_profile_id: huimengProviderProfileId,
    }),
  });
}
export function confirmBatchCostRisk(jobId: string): Promise<BatchWorkspace> {
  return request(`/api/batch-video-jobs/${jobId}/confirm-cost-risk`, {
    method: "POST",
  });
}
export function confirmAllVideoReferenceBindings(
  jobId: string,
): Promise<BatchWorkspace> {
  return request(`/api/batch-video-jobs/${jobId}/reference-bindings/confirm`, {
    method: "POST",
  });
}
export function confirmVideoReferenceBindings(
  taskId: string,
): Promise<BatchWorkspace> {
  return request(
    `/api/batch-video-tasks/${taskId}/reference-bindings/confirm`,
    { method: "POST" },
  );
}
export function resetVideoReferenceBindings(
  taskId: string,
): Promise<BatchWorkspace> {
  return request(`/api/batch-video-tasks/${taskId}/reference-bindings/reset`, {
    method: "POST",
  });
}
export function launchBatchVideoJob(jobId: string): Promise<BatchWorkspace> {
  return request(`/api/batch-video-jobs/${jobId}/launch`, {
    method: "POST",
    headers: jsonHeaders,
    body: JSON.stringify({ confirm_live_request: true }),
  });
}
export function confirmAllCompletedVideos(
  jobId: string,
): Promise<BatchWorkspace> {
  return request(`/api/batch-video-jobs/${jobId}/review-completed`, {
    method: "POST",
  });
}
export function exportJimeng(jobId: string): Promise<BatchWorkspace> {
  return request(`/api/batch-video-jobs/${jobId}/jimeng-export`, {
    method: "POST",
  });
}
export function importTaskVideo(
  taskId: string,
  file: File,
): Promise<BatchWorkspace> {
  const body = new FormData();
  body.append("file", file);
  return request(`/api/batch-video-tasks/${taskId}/import-video`, {
    method: "POST",
    body,
  });
}
export function reviewVideoResult(
  resultId: string,
  decision: "confirm" | "redo",
): Promise<BatchWorkspace> {
  return request(`/api/video-result-versions/${resultId}/review`, {
    method: "POST",
    headers: jsonHeaders,
    body: JSON.stringify({ decision }),
  });
}
export function fetchProviderProfiles(): Promise<ProviderProfile[]> {
  return request("/api/video-provider-profiles");
}
export function fetchAtlasCloudTemplate(): Promise<ProviderTemplate> {
  return request("/api/video-provider-templates/atlas-cloud");
}
export function fetchHuimengTemplate(): Promise<ProviderTemplate> {
  return request("/api/video-provider-templates/huimeng");
}
export function fetchLiveProviderStatus(): Promise<LiveProviderStatus> {
  return request("/api/video-provider-live-status");
}
export function fetchJimengCliStatus(): Promise<JimengCliStatus> {
  return request("/api/jimeng-cli/status");
}
export function fetchVideoTaskSupervisorStatus(): Promise<VideoTaskSupervisorStatus> {
  return request("/api/video-task-supervisor/status");
}
export function fetchJimengVideoModels(): Promise<JimengVideoModel[]> {
  return request("/api/jimeng-cli/video-models");
}
export function fetchVideoProviderModels(
  providerType: string,
): Promise<VideoProviderModel[]> {
  return request(
    `/api/video-provider-models?provider_type=${encodeURIComponent(providerType)}`,
  );
}
export function createProviderProfile(
  payload: Record<string, unknown>,
): Promise<ProviderProfile> {
  return request("/api/video-provider-profiles", {
    method: "POST",
    headers: jsonHeaders,
    body: JSON.stringify(payload),
  });
}
export function updateProviderProfile(
  id: string,
  payload: Record<string, unknown>,
): Promise<ProviderProfile> {
  return request(`/api/video-provider-profiles/${id}`, {
    method: "PATCH",
    headers: jsonHeaders,
    body: JSON.stringify(payload),
  });
}
export function validateProviderProfile(id: string): Promise<ProviderProfile> {
  return request(`/api/video-provider-profiles/${id}/validate`, {
    method: "POST",
  });
}
export function setDefaultProvider(id: string): Promise<ProviderProfile> {
  return request(`/api/video-provider-profiles/${id}/set-default`, {
    method: "POST",
  });
}
export function preflightProvider(id: string): Promise<ProviderPreflight> {
  return request(`/api/video-provider-profiles/${id}/preflight`, {
    method: "POST",
  });
}
export function previewProviderResponse(
  id: string,
  sampleResponse: Record<string, unknown>,
): Promise<ProviderResponsePreview> {
  return request(`/api/video-provider-profiles/${id}/response-preview`, {
    method: "POST",
    headers: jsonHeaders,
    body: JSON.stringify({ sample_response: sampleResponse }),
  });
}
export function previewProviderRequest(
  taskId: string,
): Promise<ProviderRequestPreview> {
  return request(`/api/batch-video-tasks/${taskId}/provider-request-preview`, {
    method: "POST",
  });
}
export function fetchLiveReadiness(taskId: string): Promise<LiveReadiness> {
  return request(`/api/batch-video-tasks/${taskId}/live-readiness`);
}
export function submitLiveVideoTask(taskId: string): Promise<BatchWorkspace> {
  return request(`/api/batch-video-tasks/${taskId}/live-submit`, {
    method: "POST",
    headers: jsonHeaders,
    body: JSON.stringify({ confirm_live_request: true }),
  });
}
export function pollLiveVideoTask(taskId: string): Promise<BatchWorkspace> {
  return request(`/api/batch-video-tasks/${taskId}/live-poll`, {
    method: "POST",
    headers: jsonHeaders,
    body: JSON.stringify({ confirm_live_request: true }),
  });
}
export function downloadLiveVideoTask(taskId: string): Promise<BatchWorkspace> {
  return request(`/api/batch-video-tasks/${taskId}/live-download`, {
    method: "POST",
    headers: jsonHeaders,
    body: JSON.stringify({ confirm_live_request: true }),
  });
}
export function fetchJimengCliReadiness(
  taskId: string,
): Promise<JimengCliReadiness> {
  return request(`/api/batch-video-tasks/${taskId}/jimeng-cli-readiness`, {
    method: "POST",
  });
}
export function updateJimengCliModel(
  taskId: string,
  modelId: string,
): Promise<BatchWorkspace> {
  return request(`/api/batch-video-tasks/${taskId}/jimeng-cli-model`, {
    method: "PATCH",
    headers: jsonHeaders,
    body: JSON.stringify({ model_id: modelId }),
  });
}
export function updateBatchJimengCliModel(
  jobId: string,
  modelId: string,
): Promise<BatchWorkspace> {
  return request(`/api/batch-video-jobs/${jobId}/jimeng-cli-model`, {
    method: "PATCH",
    headers: jsonHeaders,
    body: JSON.stringify({ model_id: modelId }),
  });
}
export function updateVideoReferenceBindings(
  taskId: string,
  assetIds: string[],
): Promise<BatchWorkspace> {
  return request(`/api/batch-video-tasks/${taskId}/reference-bindings`, {
    method: "PATCH",
    headers: jsonHeaders,
    body: JSON.stringify({ asset_ids: assetIds }),
  });
}
export function updateStructuredVideoReferenceBindings(
  taskId: string,
  referenceItems: VideoReferenceItemUpdate[],
): Promise<BatchWorkspace> {
  return request(`/api/batch-video-tasks/${taskId}/reference-bindings`, {
    method: "PATCH",
    headers: jsonHeaders,
    body: JSON.stringify({ reference_items: referenceItems }),
  });
}
export function updateBatchVideoGenerationSettings(
  jobId: string,
  settings: VideoGenerationSettings,
): Promise<BatchWorkspace> {
  return request(`/api/batch-video-jobs/${jobId}/generation-settings`, {
    method: "PATCH",
    headers: jsonHeaders,
    body: JSON.stringify(settings),
  });
}
export function updateVideoTaskGenerationSettings(
  taskId: string,
  settings: VideoGenerationSettings,
): Promise<BatchWorkspace> {
  return request(`/api/batch-video-tasks/${taskId}/generation-settings`, {
    method: "PATCH",
    headers: jsonHeaders,
    body: JSON.stringify(settings),
  });
}
export function refreshBatchTaskPreflight(
  taskId: string,
): Promise<BatchWorkspace> {
  return request(`/api/batch-video-tasks/${taskId}/refresh-preflight`, {
    method: "POST",
  });
}
export function prepareJimengCliRetry(taskId: string): Promise<BatchWorkspace> {
  return request(`/api/batch-video-tasks/${taskId}/jimeng-cli-prepare-retry`, {
    method: "POST",
  });
}
export function prepareVideoTaskRetry(taskId: string): Promise<BatchWorkspace> {
  return request(`/api/batch-video-tasks/${taskId}/prepare-retry`, {
    method: "POST",
  });
}
export function submitJimengCliTask(taskId: string): Promise<BatchWorkspace> {
  return request(`/api/batch-video-tasks/${taskId}/jimeng-cli-submit`, {
    method: "POST",
    headers: jsonHeaders,
    body: JSON.stringify({ confirm_live_request: true }),
  });
}
export function pollJimengCliTask(taskId: string): Promise<BatchWorkspace> {
  return request(`/api/batch-video-tasks/${taskId}/jimeng-cli-poll`, {
    method: "POST",
    headers: jsonHeaders,
    body: JSON.stringify({ confirm_live_request: true }),
  });
}
export function downloadJimengCliTask(taskId: string): Promise<BatchWorkspace> {
  return request(`/api/batch-video-tasks/${taskId}/jimeng-cli-download`, {
    method: "POST",
    headers: jsonHeaders,
    body: JSON.stringify({ confirm_live_request: true }),
  });
}
export function fetchWorkflowReview(
  projectId: string,
): Promise<WorkflowReview> {
  return request(`/api/projects/${projectId}/workflow-review`);
}
export function generateWorkflowReport(
  sceneId: string,
): Promise<WorkflowReview> {
  return request(`/api/scenes/${sceneId}/workflow-check-reports`, {
    method: "POST",
  });
}
export function fetchAiProviderStatus(): Promise<AiProviderStatus> {
  return request("/api/ai-provider/status");
}
export function fetchLocalEnvStatus(): Promise<LocalEnvStatus> {
  return request("/api/local-env/status");
}
export function updateLocalEnv(
  payload: LocalEnvUpdate,
): Promise<LocalEnvStatus> {
  return request("/api/local-env", {
    method: "PATCH",
    headers: jsonHeaders,
    body: JSON.stringify(payload),
  });
}
