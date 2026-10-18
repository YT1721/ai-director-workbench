import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const api = vi.hoisted(() => ({
  fetchSystemPromptStatus: vi.fn(),
  fetchSeedanceSkillStatus: vi.fn(),
  fetchProjectOverview: vi.fn(),
  fetchProjects: vi.fn(),
  fetchProject: vi.fn(),
  createProject: vi.fn(),
  createRealAcceptanceProject: vi.fn(),
  updateProject: vi.fn(),
  updateProjectCreativeGoal: vi.fn(),
  setProjectArchived: vi.fn(),
  hardDeleteProject: vi.fn(),
  projectExportUrl: vi.fn(
    (projectId: string) =>
      `http://localhost:8000/api/projects/${projectId}/export`,
  ),
  createEpisode: vi.fn(),
  createScene: vi.fn(),
  createShot: vi.fn(),
  renameHierarchy: vi.fn(),
  setHierarchyArchived: vi.fn(),
  fetchSourceFiles: vi.fn(),
  uploadSourceFile: vi.fn(),
  saveSourceText: vi.fn(),
  saveIntakeSource: vi.fn(),
  extractSourceText: vi.fn(),
  fetchSourceTextExtractions: vi.fn(),
  fetchPlanningDrafts: vi.fn(),
  createAiPlanningDraft: vi.fn(),
  applyPlanningDraft: vi.fn(),
  fetchTextProviderStatus: vi.fn(),
  runTextProviderSmokeTest: vi.fn(),
  fetchAiTextRuns: vi.fn(),
  fetchRealTextAcceptance: vi.fn(),
  createAiTextRun: vi.fn(),
  createDirectorAnalysis: vi.fn(),
  createAssetBrief: vi.fn(),
  createStoryboardBrief: vi.fn(),
  fetchUcodeRuns: vi.fn(),
  executeUcodeRun: vi.fn(),
  fetchFlowNav: vi.fn(),
  confirmDirectorOption: vi.fn(),
  fetchAssetWorkspace: vi.fn(),
  fetchAssetImageJobs: vi.fn(),
  analyzeAssetInventory: vi.fn(),
  updateAssetRequirement: vi.fn(),
  autoBindAssets: vi.fn(),
  fetchAssetImageReadiness: vi.fn(),
  submitAssetImage: vi.fn(),
  pollAssetImage: vi.fn(),
  downloadAssetImage: vi.fn(),
  uploadAssetImage: vi.fn(),
  createCharacter: vi.fn(),
  createCostume: vi.fn(),
  saveSceneAsset: vi.fn(),
  saveSceneBinding: vi.fn(),
  transitionAssetVersion: vi.fn(),
  fetchStoryboardWorkspace: vi.fn(),
  saveAxisPlan: vi.fn(),
  generateStoryboardVersion: vi.fn(),
  transitionStoryboardVersion: vi.fn(),
  reuseStoryboardImage: vi.fn(),
  generateStoryboardPage: vi.fn(),
  exportPromptStoryboardPack: vi.fn(),
  fetchStoryboardImageReadiness: vi.fn(),
  fetchStoryboardImagePrompt: vi.fn(),
  submitStoryboardImage: vi.fn(),
  pollStoryboardImage: vi.fn(),
  downloadStoryboardImage: vi.fn(),
  fetchVideoPackages: vi.fn(),
  fetchLatestVpGenerationJob: vi.fn(),
  startVpDurationRebuild: vi.fn(),
  retryVpGenerationJob: vi.fn(),
  cancelVpGenerationJob: vi.fn(),
  generateAiVpBlock: vi.fn(),
  transitionVpBlock: vi.fn(),
  fetchBatchVideo: vi.fn(),
  createBatchVideo: vi.fn(),
  remapBatchVideoProvider: vi.fn(),
  updateBatchVideoSubmissionChannel: vi.fn(),
  confirmBatchCostRisk: vi.fn(),
  exportJimeng: vi.fn(),
  importTaskVideo: vi.fn(),
  reviewVideoResult: vi.fn(),
  fetchProviderProfiles: vi.fn(),
  fetchAtlasCloudTemplate: vi.fn(),
  fetchHuimengTemplate: vi.fn(),
  fetchLiveProviderStatus: vi.fn(),
  fetchJimengCliStatus: vi.fn(),
  fetchVideoTaskSupervisorStatus: vi.fn(),
  fetchJimengVideoModels: vi.fn(),
  fetchVideoProviderModels: vi.fn(),
  createProviderProfile: vi.fn(),
  updateProviderProfile: vi.fn(),
  validateProviderProfile: vi.fn(),
  setDefaultProvider: vi.fn(),
  preflightProvider: vi.fn(),
  previewProviderResponse: vi.fn(),
  previewProviderRequest: vi.fn(),
  fetchLiveReadiness: vi.fn(),
  fetchJimengCliReadiness: vi.fn(),
  updateJimengCliModel: vi.fn(),
  updateBatchVideoGenerationSettings: vi.fn(),
  updateVideoTaskGenerationSettings: vi.fn(),
  updateVideoReferenceBindings: vi.fn(),
  refreshBatchTaskPreflight: vi.fn(),
  prepareJimengCliRetry: vi.fn(),
  submitLiveVideoTask: vi.fn(),
  pollLiveVideoTask: vi.fn(),
  downloadLiveVideoTask: vi.fn(),
  submitJimengCliTask: vi.fn(),
  pollJimengCliTask: vi.fn(),
  downloadJimengCliTask: vi.fn(),
  fetchWorkflowReview: vi.fn(),
  generateWorkflowReport: vi.fn(),
  fetchAiProviderStatus: vi.fn(),
  fetchLocalEnvStatus: vi.fn(),
  updateLocalEnv: vi.fn(),
  assetImageUrl: vi.fn((path: string) => `http://localhost:8000${path}`),
  downloadLocalAsset: vi.fn(async () => ({
    method: "browser_download",
    filename: "EP01SC01_提示词_故事板.zip",
  })),
}));

vi.mock("../services/api", () => api);

import { App } from "../App";
import { realRunPrimaryAction } from "../components/RealRunChecklist";
import { useWorkbenchStore } from "../stores/useWorkbenchStore";

const loadedStatus = {
  loaded: true,
  filename: "剧本视觉化创作系统_V7.0_Plus_R1_当前主版本.txt",
  version:
    "V7.0 Plus R1｜UCODE-9 + FLOW-NAV + VP-PRECISION-18 + DIRECTOR-TECH PLUS + UNIFIED-SB",
  provider_mode: "huimeng_live",
  error: null,
};

const project = {
  id: "project-1",
  project_code: "PRJ001",
  name: "测试短剧",
  description: "本地项目",
  creative_goal: "full_pipeline" as const,
  is_archived: false,
  created_at: "2026-05-31T00:00:00Z",
  updated_at: "2026-05-31T00:00:00Z",
  episodes: [
    {
      id: "episode-1",
      episode_code: "EP01",
      name: "第 1 集",
      is_archived: false,
      scenes: [
        {
          id: "scene-1",
          scene_code: "SC01",
          name: "第 1 场",
          is_archived: false,
          shots: [
            {
              id: "shot-1",
              shot_code: "SH001",
              name: "镜头 1",
              is_archived: false,
            },
          ],
        },
      ],
    },
  ],
};

const acceptanceProject = {
  ...project,
  id: "project-acceptance",
  project_code: "PRJ002",
  name: "真实验收短片",
};

const projectOverview = {
  id: project.id,
  project_code: project.project_code,
  name: project.name,
  description: project.description,
  creative_goal: project.creative_goal,
  is_archived: false,
  created_at: project.created_at,
  updated_at: project.updated_at,
  episode_count: 1,
  scene_count: 1,
  shot_count: 1,
  source_file_count: 1,
  current_stage: "导演方案选择",
  short_status: "等待导演方案",
  primary_action_label: "处理下一步",
  primary_action_href: "/start-plan#director-option-panel",
};

const archivedProjectOverview = {
  ...projectOverview,
  id: "project-archived",
  project_code: "PRJ099",
  name: "已归档测试片",
  is_archived: true,
  short_status: "已归档",
};

const run = {
  id: "run-1",
  project_id: project.id,
  ucode_action: "start",
  scope_code: "EP01",
  additional_request: "先分析剧情",
  command_text: "V7｜开始｜EP01",
  status: "completed",
  result_summary:
    "手动记录已保存：开始。范围为 EP01。这不是 AI 分析结果；真正的导演级产出请使用页面上的 AI 分析入口。",
  checkpoint_required: true,
  created_at: "2026-05-31T00:00:00Z",
  checkpoints: [
    {
      id: "checkpoint-1",
      title: "请确认“开始”手动记录后再进入下一步。",
      status: "pending_confirmation",
      created_at: "2026-05-31T00:00:00Z",
    },
  ],
};

const flowNav = {
  project_id: project.id,
  project_code: project.project_code,
  project_name: project.name,
  scope_code: "EP01SC01",
  current_stage: "导演方案选择",
  completed_labels: ["开始"],
  pending_labels: [
    "导演方案选择",
    "规划",
    "分镜提示词",
    "故事板",
    "资产图",
    "成片提示词",
    "批量视频",
  ],
  director_option: null,
  directory: [
    {
      key: "start",
      label: "开始",
      command: "V7｜开始｜EP01",
      marker: "已完成",
      status_level: "done",
      short_status: "已完成启动分析",
      detail: "记录项目启动。",
      href: "/start-plan#source-intake",
    },
    {
      key: "director_option",
      label: "导演方案选择",
      command: "确认导演方案",
      marker: "当前建议",
      status_level: "current",
      short_status: "等待导演方案",
      detail: "人工确认方案。",
      href: "/start-plan#director-option-panel",
    },
    {
      key: "plan",
      label: "导演分析 / 规划",
      command: "V7｜规划｜EP01",
      marker: "待进行",
      status_level: "pending",
      short_status: "待规划",
      detail: "规划。",
      href: "/start-plan#planning-draft-panel",
    },
    {
      key: "video_package_draft",
      label: "故事板提示词",
      command: "V7｜分镜提示词｜EP01SC01｜SH001-SH001｜故事板参考",
      marker: "待进行",
      status_level: "pending",
      short_status: "先生成故事板提示词",
      detail: "故事板提示词。",
      href: "/video-package",
    },
    {
      key: "storyboard",
      label: "故事板",
      command: "V7｜故事板｜EP01SC01｜SH001",
      marker: "待进行",
      status_level: "pending",
      short_status: "缺少故事板",
      detail: "故事板。",
      href: "/storyboards",
    },
    {
      key: "assets",
      label: "资产图",
      command: "V7｜资产｜EP01SC01",
      marker: "待进行",
      status_level: "pending",
      short_status: "缺少资产图",
      detail: "资产图。",
      href: "/assets",
    },
    {
      key: "video_package",
      label: "成片提示词",
      command: "V7｜分镜提示词｜EP01SC01｜SH001｜成片",
      marker: "待进行",
      status_level: "pending",
      short_status: "缺少成片提示词",
      detail: "成片提示词。",
      href: "/video-package",
    },
    {
      key: "batch_video",
      label: "批量视频",
      command: "V7｜批量视频｜EP01SC01",
      marker: "待进行",
      status_level: "pending",
      short_status: "待创建队列",
      detail: "批量视频。",
      href: "/batch-video",
    },
    {
      key: "check",
      label: "流程体检",
      command: "V7｜检查｜EP01SC01",
      marker: "可选辅助",
      status_level: "optional",
      short_status: "提交前检查",
      detail: "检查当前最早的阻塞阶段。",
      href: "/check-fix",
    },
  ],
  next_command: "确认导演方案",
  next_reason: "人工确认当前集采用的导演方案。",
  blocking_reason: "",
  primary_action_label: "处理下一步",
  primary_action_href: "/start-plan#director-option-panel",
};
const confirmedFlowNav = {
  ...flowNav,
  current_stage: "规划",
  completed_labels: ["开始", "导演方案选择"],
  pending_labels: [
    "规划",
    "分镜提示词",
    "故事板",
    "资产图",
    "成片提示词",
    "批量视频",
  ],
  director_option: {
    id: "option-1",
    episode_id: "episode-1",
    version_number: 1,
    option_name: "克制压迫版",
    notes: "",
    status: "confirmed_current",
    created_at: "2026-06-02T00:00:00Z",
  },
  directory: flowNav.directory.map((item) =>
    item.key === "director_option"
      ? {
          ...item,
          marker: "已完成",
          status_level: "done",
          short_status: "已确认方案",
        }
      : item.key === "plan"
        ? { ...item, marker: "当前建议", status_level: "current" }
        : item,
  ),
  next_command: "V7｜规划｜EP01",
  next_reason: "确认场次、镜头拆分、资产需求和提示词基础。",
  primary_action_href: "/start-plan#ucode-command-panel",
};
const awaitingAiFlowNav = {
  ...flowNav,
  current_stage: "真实 AI 导演分析",
  completed_labels: [],
  pending_labels: [
    "开始",
    "导演方案选择",
    "规划",
    "分镜提示词",
    "故事板",
    "资产图",
    "成片提示词",
    "批量视频",
  ],
  directory: flowNav.directory.map((item) =>
    item.key === "start"
      ? {
          ...item,
          marker: "当前建议",
          status_level: "current",
          short_status: "已解析资料，等待AI分析",
        }
      : item.key === "director_option"
        ? { ...item, marker: "待进行", status_level: "pending" }
        : item,
  ),
  next_command: "V7｜开始｜EP01",
  next_reason: "资料已保存，请用 AI 分析生成导演分析。",
  blocking_reason: "资料已上传，但还没有完成真实 AI 导演分析。",
  primary_action_label: "用真实 AI 分析",
  primary_action_href: "/start-plan#ai-director-analysis",
};
const confirmedNoDraftFlowNav = {
  ...confirmedFlowNav,
  current_stage: "生成分镜规划",
  directory: confirmedFlowNav.directory.map((item) =>
    item.key === "plan"
      ? {
          ...item,
          marker: "当前建议",
          status_level: "current",
          short_status: "待生成草案",
        }
      : item,
  ),
  next_reason: "已确认导演方案，请先用 AI 分析生成 EP / SC / SH 分镜规划。",
  blocking_reason: "资料已解析，但尚未生成分镜规划。",
  primary_action_label: "用 AI 生成分镜规划",
  primary_action_href: "/start-plan#ai-planning-draft",
};

const sourceFile = {
  id: "source-1",
  project_id: project.id,
  category: "script_text" as const,
  original_filename: "第一份剧本资料.txt",
  stored_filename: "abc_第一份剧本资料.txt",
  relative_path: "00_source/scripts/abc_第一份剧本资料.txt",
  content_type: "text/plain; charset=utf-8",
  size_bytes: 42,
  created_at: "2026-06-02T00:00:00Z",
};

const extraction = {
  id: "extraction-1",
  project_id: project.id,
  source_file_id: sourceFile.id,
  version_number: 1,
  status: "extracted" as const,
  text_relative_path: "01_analysis/source_extractions/source-1_001.txt",
  character_count: 42,
  line_count: 3,
  preview: "第一场 宫门外\n镜头一：雨夜对峙。\n镜头二：旧信落地。",
  error: "",
  created_at: "2026-06-02T00:00:00Z",
};

const unsupportedExtraction = {
  ...extraction,
  id: "extraction-unsupported",
  status: "unsupported" as const,
  character_count: 0,
  line_count: 0,
  preview: "",
  error: "已保存，暂未解析正文。本轮只解析粘贴文本、TXT、MD、DOCX 和 XLSX。",
};

const planningDraft = {
  id: "draft-1",
  project_id: project.id,
  source_extraction_id: extraction.id,
  version_number: 1,
  status: "draft" as const,
  summary:
    "文本模型已生成规划建议（huimeng_chat｜gpt-5.5）。为保护项目结构，本草案仍需人工审阅后点击应用。",
  draft_json: "{}",
  applied_at: null,
  created_at: "2026-06-02T00:00:00Z",
  items: [
    {
      id: "draft-item-1",
      draft_id: "draft-1",
      project_id: project.id,
      episode_code: "EP01",
      scene_code: "SC01",
      shot_code: "SH001",
      source_excerpt: "镜头一：雨夜对峙。",
      suggested_task: "根据原文设计镜头：雨夜对峙。",
      status: "draft",
      created_at: "2026-06-02T00:00:00Z",
    },
    {
      id: "draft-item-2",
      draft_id: "draft-1",
      project_id: project.id,
      episode_code: "EP01",
      scene_code: "SC01",
      shot_code: "SH002",
      source_excerpt: "镜头二：旧信落地。",
      suggested_task: "根据原文设计镜头：旧信落地。",
      status: "draft",
      created_at: "2026-06-02T00:00:00Z",
    },
  ],
};

const appliedPlanningDraft = {
  ...planningDraft,
  status: "applied" as const,
  applied_at: "2026-06-02T00:01:00Z",
  items: planningDraft.items.map((item) => ({ ...item, status: "applied" })),
};

const appliedProject = {
  ...project,
  episodes: [
    {
      ...project.episodes[0],
      scenes: [
        {
          ...project.episodes[0].scenes[0],
          shots: [
            project.episodes[0].scenes[0].shots[0],
            {
              id: "shot-2",
              shot_code: "SH002",
              name: "根据原文设计镜头：旧信落地。",
              is_archived: false,
            },
          ],
        },
      ],
    },
  ],
};

const assetWorkspace = {
  project_id: project.id,
  project_code: project.project_code,
  characters: [
    {
      id: "character-1",
      character_code: "CH01",
      name: "朱元璋",
      face_shape: "清瘦长脸",
      facial_features: "眉骨清晰",
      age_description: "五十岁上下",
      height_description: "中等偏高",
      body_type: "清瘦",
      hair_style: "束发",
      identity_temperament: "帝王威严",
      is_archived: false,
      master_versions: [],
      costumes: [],
    },
  ],
  scenes: [
    {
      id: "scene-1",
      scope_code: "EP01SC01",
      scene_code: "SC01",
      name: "第 1 场",
    },
  ],
  scene_assets: [],
  bindings: [],
  requirements: [],
  props: [],
  prop_bindings: [],
};

const assetRequirement = {
  id: "requirement-1",
  inventory_version: 1,
  asset_type: "prop" as const,
  name: "旧信",
  description: "剧情转折所需的泛黄旧信",
  visual_prompt: "泛黄旧信，封口磨损，真人影视道具资产板",
  reference_mode: "visual" as const,
  importance_reason: "推动剧情转折的关键道具，需要跨镜头一致。",
  text_prompt: "泛黄旧信，封口磨损。",
  evidence: "她把旧信藏进抽屉。",
  scene_ids: ["scene-1"],
  scene_scope_codes: ["EP01SC01"],
  target_id: "prop-1",
  status: "identified",
};

const assetWorkspaceWithRequirements = {
  ...assetWorkspace,
  requirements: [assetRequirement],
  props: [
    {
      id: "prop-1",
      prop_code: "PROP01",
      name: "旧信",
      category: "关键道具",
      description: "剧情转折所需的泛黄旧信",
      visual_details: "封口磨损，纸张泛黄",
      is_archived: false,
      versions: [],
    },
  ],
};

const confirmedAssetVersion = {
  id: "prop-version-1",
  version_number: 1,
  asset_path: "04_assets/props/PROP01_v001.png",
  asset_url: "/api/projects/PRJ001/assets/04_assets/props/PROP01_v001.png",
  status: "confirmed_current" as const,
  created_at: "2026-07-14T00:00:00Z",
};

const assetWorkspaceReadyToBind = {
  ...assetWorkspaceWithRequirements,
  props: [
    {
      ...assetWorkspaceWithRequirements.props[0],
      versions: [confirmedAssetVersion],
    },
  ],
};

const storyboardWorkspace = {
  project_id: project.id,
  project_code: project.project_code,
  style_lock: {
    enabled: true,
    locked: true,
    style_name: "统一白底高信息密度导演故事板说明板风格",
  },
  scenes: [
    {
      id: "scene-1",
      scope_code: "EP01SC01",
      name: "第 1 场",
      axis_plan: {
        id: "axis-1",
        axis_code: "AXIS-01",
        axis_line_description: "人物连线作为主轴线",
        camera_safe_side: "A侧",
        character_blocking: "主角位于画面左侧，对手位于画面右侧",
        eyeline_direction: "主角向右，对手向左",
        movement_direction: "从左向右",
        allow_cross_axis: false,
        cross_axis_transition: "",
      },
      shots: [
        {
          id: "shot-1",
          shot_code: "SH001",
          name: "镜头 1",
          versions: [],
        },
      ],
      execution_pages: [],
    },
  ],
};

const storyboardTaskWorkspace = {
  ...storyboardWorkspace,
  scenes: [
    {
      ...storyboardWorkspace.scenes[0],
      shots: [
        {
          ...storyboardWorkspace.scenes[0].shots[0],
          versions: [
            {
              id: "storyboard-version-1",
              version_number: 1,
              image_url:
                "/api/projects/PRJ001/assets/04_storyboards/frames/SH001_v001.svg",
              schema_version: "unified_sb_v1",
              vp_basis_block_id: "vp-1",
              storyboard_grid: 6,
              grid_reason: "按镜头动作阶段分成 6 格。",
              prompt_match: [{ grid_index: 1, time_range: "0-1s" }],
              timeline_nodes: [{ time_range: "0-1s", description: "人物抬头" }],
              style_validation_status: "passed",
              axis_validation_status: "passed",
              axis_validation_notes: "方向连续。",
              status: "draft",
              created_at: "2026-06-01T00:00:00Z",
              shot_size: "中景",
              camera_angle: "平视",
              camera_movement: "缓慢推进",
              action_start: "人物抬头",
              emotion_state: "紧张",
              sound_light: "低光",
              camera_point: "CAM01",
              screen_position: "左侧",
              eyeline_direction: "向右",
              movement_direction: "从左向右",
              camera_side: "A侧",
            },
          ],
        },
      ],
    },
  ],
};

const storyboardConfirmedWorkspace = {
  ...storyboardTaskWorkspace,
  scenes: [
    {
      ...storyboardTaskWorkspace.scenes[0],
      shots: [
        {
          ...storyboardTaskWorkspace.scenes[0].shots[0],
          versions: [
            {
              ...storyboardTaskWorkspace.scenes[0].shots[0].versions[0],
              status: "confirmed_current",
            },
          ],
        },
      ],
    },
  ],
};

const storyboardReusableWorkspace = {
  ...storyboardConfirmedWorkspace,
  scenes: [
    {
      ...storyboardConfirmedWorkspace.scenes[0],
      shots: [
        {
          ...storyboardConfirmedWorkspace.scenes[0].shots[0],
          latest_vp_draft_id: "vp-2",
          reuse_assessment: {
            source_version_id: "storyboard-version-old",
            source_version_number: 2,
            source_image_url:
              "/api/projects/PRJ001/assets/04_storyboards/frames/SH001_sb_real_v002.png",
            recommendation: "reuse",
            can_reuse: true,
            reasons: [
              "格数、动作节点、机位方向均一致，仅时间段发生调整，建议沿用旧图",
            ],
            old_grid: 6,
            new_grid: 6,
            old_time_ranges: ["0-1s"],
            new_time_ranges: ["0-2s"],
          },
          versions: [
            {
              ...storyboardConfirmedWorkspace.scenes[0].shots[0].versions[0],
              id: "storyboard-version-new",
              vp_basis_block_id: "vp-2",
              prompt_match: [{ grid_index: 1, time_range: "0-2s" }],
              timeline_nodes: [{ time_range: "0-2s", description: "人物抬头" }],
              status: "confirmed_current",
            },
          ],
        },
      ],
    },
  ],
};

const storyboardForcedReuseWorkspace = {
  ...storyboardReusableWorkspace,
  scenes: [
    {
      ...storyboardReusableWorkspace.scenes[0],
      shots: [
        {
          ...storyboardReusableWorkspace.scenes[0].shots[0],
          reuse_assessment: {
            ...storyboardReusableWorkspace.scenes[0].shots[0].reuse_assessment,
            recommendation: "regenerate",
            can_reuse: false,
            reasons: [
              "故事板格数由 6 格变为 4 格",
              "画面结构已明显变化，旧图不能安全沿用",
            ],
            old_grid: 6,
            new_grid: 4,
          },
        },
      ],
    },
  ],
};

const storyboardCompletedImageWorkspace = {
  ...storyboardConfirmedWorkspace,
  scenes: [
    {
      ...storyboardConfirmedWorkspace.scenes[0],
      shots: [
        {
          ...storyboardConfirmedWorkspace.scenes[0].shots[0],
          versions: [
            {
              ...storyboardConfirmedWorkspace.scenes[0].shots[0].versions[0],
              latest_image_job: {
                id: "image-job-completed",
                project_id: project.id,
                target_type: "storyboard_version",
                target_id: "storyboard-version-1",
                provider: "huimeng_image",
                model_name: "image-2",
                external_task_id: "hm-image-1",
                status: "completed",
                remote_result_url: "https://example.test/storyboard.png",
                image_url: null,
                prompt: "为电影导演生成单镜头故事板图片。必须是黑白铅笔草稿。",
                error_message: "",
                created_at: "2026-06-01T00:00:00Z",
              },
            },
          ],
        },
      ],
    },
  ],
};

const storyboardProcessingImageWorkspace = {
  ...storyboardConfirmedWorkspace,
  scenes: [
    {
      ...storyboardConfirmedWorkspace.scenes[0],
      shots: [
        {
          ...storyboardConfirmedWorkspace.scenes[0].shots[0],
          versions: [
            {
              ...storyboardConfirmedWorkspace.scenes[0].shots[0].versions[0],
              latest_image_job: {
                id: "image-job-processing",
                project_id: project.id,
                target_type: "storyboard_version",
                target_id: "storyboard-version-1",
                provider: "huimeng_image",
                model_name: "image-2",
                external_task_id: "hm-image-processing",
                status: "processing",
                remote_result_url: "",
                image_url: null,
                prompt: "为电影导演生成单镜头故事板图片。必须是黑白铅笔草稿。",
                error_message: "",
                created_at: "2026-06-01T00:00:00Z",
              },
            },
          ],
        },
      ],
    },
  ],
};

const storyboardDownloadedWorkspace = {
  ...storyboardTaskWorkspace,
  scenes: [
    {
      ...storyboardTaskWorkspace.scenes[0],
      shots: [
        {
          ...storyboardTaskWorkspace.scenes[0].shots[0],
          versions: [
            {
              ...storyboardTaskWorkspace.scenes[0].shots[0].versions[0],
              image_url:
                "/api/projects/PRJ001/assets/04_storyboards/frames/SH001_sb_real_v002.png",
              version_number: 2,
              status: "confirmed_current",
            },
          ],
        },
      ],
    },
  ],
};

const videoPackages = {
  project_id: project.id,
  project_code: project.project_code,
  scenes: [
    {
      id: "scene-1",
      scope_code: "EP01SC01",
      name: "第 1 场",
      shots: [
        { id: "shot-1", shot_code: "SH001", name: "镜头 1", versions: [] },
      ],
    },
  ],
};
const provider = {
  id: "huimeng_live",
  display_name: "慧梦 API｜Seedance 2.0 Fast 单镜实测",
  provider_type: "seedance_huimeng_live",
  is_enabled: true,
  is_default: true,
  base_url: "https://api.huimengi.com",
  create_task_path: "/api/v1/tasks",
  get_task_path_template: "/api/v1/tasks/{id}",
  auth_type: "bearer",
  auth_header_name: "Authorization",
  auth_prefix: "Bearer ",
  auth_env_key_name: "HUIMENGI_API_KEY",
  capabilities: {},
  price_configs: [],
  validation_message: "受控真实单镜配置有效；未发送网络请求。",
};
const genericProvider = {
  ...provider,
  id: "generic-1",
  display_name: "本地聚合平台配置",
  provider_type: "seedance_aggregator_generic",
  is_default: false,
};
const huimengProvider = {
  ...provider,
  id: "huimeng_live",
  display_name: "慧梦 API｜Seedance 2.0 Fast 单镜实测",
  provider_type: "seedance_huimeng_live",
  is_default: false,
  base_url: "https://api.huimengi.com",
  create_task_path: "/api/v1/tasks",
  get_task_path_template: "/api/v1/tasks/{id}",
  auth_env_key_name: "HUIMENGI_API_KEY",
};
const atlasTemplate = {
  template_id: "atlas-cloud-seedance-2-fast-reference",
  title: "Atlas Cloud｜Seedance 2.0 Fast Reference",
  description:
    "禁用状态专属模板：只做本地映射、预算和响应演练。真实提交与 uploadMedia 素材上传尚未开放。",
  outbound_requests_enabled: false,
  profile: {
    ...genericProvider,
    id: undefined,
    display_name: "Atlas Cloud｜Seedance 2.0 Fast Reference",
    provider_type: "seedance_atlas_cloud_disabled",
    base_url: "https://api.atlascloud.ai",
    create_task_path: "/api/v1/model/generateVideo",
    get_task_path_template: "/api/v1/model/prediction/{id}",
    auth_env_key_name: "ATLASCLOUD_API_KEY",
    config: {
      model_mapping: {
        "seedance-2.0": "bytedance/seedance-2.0-fast/reference-to-video",
      },
    },
    price_configs: [
      { price_value: 0.1935, billing_unit: "per_second", currency: "USD" },
    ],
  },
};
const huimengTemplate = {
  template_id: "huimeng-seedance-2-fast-live",
  title: "慧梦 API｜Seedance 2.0 Fast 单镜实测",
  description: "受控真实单镜模板：仅允许 1 个任务、1-15 秒、720p。",
  outbound_requests_enabled: false,
  profile: {
    ...huimengProvider,
    id: undefined,
    config: { model_mapping: { "seedance-2.0": "seedance-2.0-fast" } },
    capabilities: {
      generation_modes: ["multimodal_reference"],
      supported_durations: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15],
      supported_resolutions: ["720p"],
      supported_aspect_ratios: ["16:9"],
    },
    price_configs: [
      {
        price_status: "unknown",
        billing_unit: "provider_defined",
        currency: "CREDITS",
      },
    ],
  },
};
const batchWorkspace = {
  project_id: project.id,
  project_code: project.project_code,
  providers: [provider],
  scenes: [{ id: "scene-1", scope_code: "EP01SC01", name: "第 1 场" }],
  jobs: [
    {
      id: "job-1",
      scene_id: "scene-1",
      scope_code: "EP01SC01",
      provider_profile_id: "huimeng_live",
      provider_name: "慧梦 API｜Seedance 2.0 Fast 单镜实测",
      status: "draft",
      budget_confirmed: false,
      estimated_cost: null,
      cost_estimate_status: "unknown" as const,
      cost_estimate_note: "当前没有可可靠计算的固定单价。",
      cost_source_url: "https://api.huimengi.com/models/seedance-2.0-fast",
      currency: "CREDITS",
      total_seconds: 5,
      jimeng_zip_url: null,
      tasks: [
        {
          id: "task-1",
          shot_id: "shot-1",
          status: "awaiting_budget_confirm",
          missing_items: [],
          canonical_request: {},
          retry_count: 0,
          error_message: "",
          storyboard_url: null,
          results: [],
          shot_code: "SH001",
        },
      ],
    },
  ],
};
const huimengBatchWorkspace = {
  ...batchWorkspace,
  providers: [huimengProvider],
  jobs: [
    {
      ...batchWorkspace.jobs[0],
      provider_profile_id: "huimeng_live",
      provider_name: "慧梦 API｜Seedance 2.0 Fast 单镜实测",
      budget_confirmed: true,
      status: "ready",
      tasks: [
        {
          ...batchWorkspace.jobs[0].tasks[0],
          status: "ready",
          canonical_request: { duration_seconds: 5, resolution: "720p" },
        },
      ],
    },
  ],
};
const providerPreview = {
  task_id: "task-1",
  provider_profile_id: "huimeng_live",
  canonical_request: {},
  mapped_request_preview: { mode: "preview_only" },
  missing_items: [],
  outbound_request_sent: false,
};
const aiStatus = {
  mode: "huimeng_chat",
  real_openai_enabled: true,
  api_key_configured: false,
  text_model_configured: true,
  text_model: "gpt-5.5",
  routine_model_configured: false,
  routine_model: "",
  image_model_configured: true,
  image_model: "image-2",
  image_provider_mode: "huimeng_image_controlled",
  live_task:
    "允许受控文本分析、规划、提示词和检查摘要；图像与视频仍按页面逐次确认，不会后台自动提交。",
  network_policy: "禁止自动真实调用；每次真实文本请求都需要页面确认。",
};
const liveProviderStatus = {
  provider_mode: "huimeng_live",
  real_seedance_enabled: false,
  huimengi_api_key_configured: false,
  huimengi_video_base_url: "https://api.huimengi.com",
  huimengi_video_model: "seedance-2.0-fast",
  huimengi_base_url: "https://api.huimengi.com",
  huimengi_model_id: "seedance-2.0-fast",
  live_video_task: "慧梦 Seedance 单镜真实测试",
  single_task_limit: "只允许 1 个任务，1-15 秒，720p；建议先用 5 秒小样",
  network_policy:
    "未配置 SEEDANCE_REAL_SUBMIT_ENABLED=true、HUIMENGI_API_KEY 和页面确认时，后端拒绝发送网络请求。",
};
const jimengCliStatus = {
  installed: false,
  logged_in: false,
  ready: false,
  command: "dreamina",
  account_summary: "",
  credit_summary: "",
  output_dir: "/tmp/projects/_jimeng_cli_downloads",
  blocking_reason: "本机没有检测到 dreamina 命令。",
  install_hint:
    "请按即梦官方 CLI 文档安装 dreamina；安装后在终端执行 dreamina login。",
};
const localEnvStatus = {
  openai_api_key_configured: false,
  openai_text_model: "",
  openai_model_routine: "",
  openai_image_model: "",
  openai_max_output_tokens: 4000,
  text_provider_mode: "huimeng_chat",
  enable_real_text_analysis: true,
  enable_real_openai: false,
  enable_real_image_generation: false,
  huimengi_api_key_configured: false,
  huimengi_text_base_url: "https://api.huimengi.com/v1",
  huimengi_text_model: "gpt-5.5",
  text_api_key_configured: false,
  text_base_url: "https://api.huimengi.com/v1",
  text_model: "gpt-5.5",
  text_service_label: "慧梦",
  image_provider_mode: "huimeng_tasks",
  image_api_key_configured: false,
  image_base_url: "",
  image_model: "",
  huimengi_image_base_url: "https://api.huimengi.com",
  huimengi_image_model: "image-2",
  huimengi_video_base_url: "https://api.huimengi.com",
  huimengi_video_model: "seedance-2.0-fast",
  huimengi_base_url: "https://api.huimengi.com",
  huimengi_model_id: "seedance-2.0-fast",
  enable_real_seedance: false,
  video_provider_mode: "huimeng_live",
  env_file_exists: false,
  env_file_path: "/tmp/.env",
  secret_policy: "密钥只写入本机 .env；接口只返回是否已配置，不返回密钥正文。",
};
const textProviderStatus = {
  mode: "huimeng_chat",
  mode_label: "慧梦 GPT-5.5 文本通道",
  real_text_enabled: true,
  requires_user_confirmation: true,
  uses_full_system_prompt: true,
  system_prompt_loaded: true,
  system_prompt_filename: "剧本视觉化创作系统_V7.0_Plus_R1_当前主版本.txt",
  system_prompt_version:
    "V7.0 Plus R1｜UCODE-9 + FLOW-NAV + VP-PRECISION-18 + DIRECTOR-TECH PLUS + UNIFIED-SB",
  system_prompt_sha256_short: "abc123def456",
  openai_api_key_configured: false,
  openai_model: "",
  huimengi_api_key_configured: true,
  huimengi_text_base_url: "https://api.huimengi.com/v1",
  huimengi_text_model: "gpt-5.5",
  text_api_key_configured: true,
  text_base_url: "https://api.huimengi.com/v1",
  text_model: "gpt-5.5",
  text_service_label: "慧梦",
  ready: true,
  blocking_reason: "",
  network_policy: "默认使用真实文本大脑；所有真实文本请求仍需页面逐次确认。",
};
const directorAnalysisText = [
  "## 可选导演方案",
  "方案一：原剧情版，适合不改人物关系和关键情节，视觉重点是优化镜头、节奏、光线和调度，主要风险是风格突破较少。",
  "方案二：唯美画意版，适合亲情和回忆段落，视觉重点是自然光、情绪留白和构图，主要风险是节奏偏慢。",
  "方案三：G版打斗特效版，不推荐用于本项目，视觉重点是动作五段式，主要风险是偏离剧情气质。",
  "方案四：H解说模式，适合信息量大的回忆和旁白，视觉重点是声画分离和反应镜头，主要风险是画面戏剧性不足。",
  "方案五：推荐导演方案，定制为悬疑压迫写实版，适合旧楼走廊压迫戏，视觉重点是低照度、纵深走廊和手部特写，主要风险是暗部细节丢失。",
  "## AI推荐结论",
  "推荐采用：方案五｜推荐导演方案",
  "推荐理由：它最能保留原剧情，同时强化旧楼走廊的悬疑压迫感。",
  "备用选择：方案一｜原剧情版，适合最大程度保留台词和情绪推进。",
  "风险提醒：暗部细节需要在资产和故事板阶段提前控制。",
].join("\n");
const aiTextRun = {
  id: "ai-text-1",
  project_id: project.id,
  report_id: null,
  source_extraction_id: extraction.id,
  target_type: "",
  target_id: "",
  module_type: "director_analysis",
  provider: "huimeng_chat",
  model_name: "gpt-5.5",
  response_text: directorAnalysisText,
  response_json: JSON.stringify({ system_prompt_sha256: "abc123def4567890" }),
  status: "completed",
  error_message: "",
  cache_hit: false,
  input_tokens: 20,
  cached_input_tokens: 0,
  output_tokens: 10,
  created_at: "2026-06-02T00:00:00Z",
};
const incompleteDirectorAnalysisRun = {
  ...aiTextRun,
  id: "ai-text-incomplete",
  response_text: [
    "## 可选导演方案",
    "方案一：原剧情版，适合最大保留原剧本台词和情绪推进，视觉重点是烛光审问与祖孙和解，主要风险是长对白需要精细拆组。",
    "方案二：帝王压迫悬疑版，适合强化朱元璋识破真相的压迫感，视觉重点是低角度近景和阴影切割，主要风险是温情感可能被压弱。",
    "方案三：亲情史诗温情版，适合强化祖孙羁绊和守江山使命感，视觉重点是月光、背影和手掌覆盖，主要风险是前半段审问张力会相对降低。",
  ].join("\n"),
};
const realTextAcceptance = {
  project_id: project.id,
  project_code: project.project_code,
  ready: false,
  current_label: "真实导演启动分析",
  primary_action_label: "去开始页生成导演分析",
  primary_action_href: "/start-plan#ai-director-analysis",
  summary: "下一步需要完成：真实导演启动分析。",
  items: [
    {
      key: "director_analysis",
      label: "真实导演启动分析",
      status: "current",
      evidence: "还没有真实 AI 完成记录；请在页面逐次确认后生成。",
      action_label: "去开始页生成导演分析",
      action_href: "/start-plan#ai-director-analysis",
      provider: "",
      model_name: "",
      output_tokens: 0,
      created_at: null,
    },
    {
      key: "planning_draft",
      label: "分镜规划",
      status: "pending",
      evidence: "等待前面的真实文本步骤完成后再做。",
      action_label: "去开始页生成分镜规划",
      action_href: "/start-plan#ai-planning-draft",
      provider: "",
      model_name: "",
      output_tokens: 0,
      created_at: null,
    },
  ],
};
const liveReadiness = {
  ready: true,
  provider_name: "慧梦 API｜Seedance 2.0 Fast 单镜实测",
  model_id: "seedance-2.0-fast",
  requires_user_confirmation: true,
  risk_notice:
    "点击真实提交会向慧梦发送一次单镜视频请求，可能消耗账户积分；提交、查询和下载都需要页面逐次确认。",
  gate_items: [
    {
      label: "Provider",
      passed: true,
      detail: "慧梦 API｜Seedance 2.0 Fast 单镜实测",
    },
    { label: "预算确认", passed: true, detail: "已确认预算" },
  ],
};
const jimengCliReadiness = {
  ready: false,
  provider_name: "即梦 CLI",
  model_id: "seedance2.0_vip",
  requires_user_confirmation: true,
  risk_notice: "点击提交会调用本机 dreamina CLI，可能消耗积分。",
  prompt_preview: "测试提示词",
  asset_count: 0,
  gate_items: [
    {
      label: "即梦 CLI",
      passed: false,
      detail: "本机没有检测到 dreamina 命令。",
    },
  ],
};
const workflowReview = {
  project_id: project.id,
  project_code: project.project_code,
  scenes: [{ id: "scene-1", scope_code: "EP01SC01", name: "第 1 场" }],
  reports: [
    {
      id: "report-1",
      project_id: project.id,
      scene_id: "scene-1",
      scope_code: "EP01SC01",
      version_number: 1,
      status: "blocked",
      ready_for_next: false,
      created_at: "2026-06-01T00:00:00Z",
      issues: [
        {
          id: "issue-1",
          category: "storyboard",
          severity: "blocking",
          target_type: "storyboard",
          target_id: "shot-1",
          title: "SH001 缺少已确认故事板",
          detail: "请生成并确认故事板。",
          fixable: true,
          status: "open",
        },
      ],
    },
  ],
  fix_runs: [],
  one_click_runs: [],
  summaries: [],
};

function resetStore() {
  useWorkbenchStore.setState({
    systemPromptStatus: null,
    isLoadingStatus: true,
    isBusy: false,
    error: null,
    selectedAction: null,
    projects: [],
    activeProject: null,
    selection: {},
    sourceFiles: [],
    sourceTextExtractions: [],
    planningDrafts: [],
    ucodeRuns: [],
    latestRun: null,
    commandDraft: {
      action: "start",
      scopeCode: "EP01",
      additionalRequest: "",
    },
  });
}

function seedProject() {
  useWorkbenchStore.setState({
    projects: [project],
    activeProject: project,
    sourceFiles: [sourceFile],
    sourceTextExtractions: [extraction],
    planningDrafts: [planningDraft],
    ucodeRuns: [run],
    latestRun: run,
    creativeGoal: project.creative_goal,
    selection: {
      episodeId: "episode-1",
      sceneId: "scene-1",
      shotId: "shot-1",
    },
  });
}

async function acceptWorkbenchConfirm(
  title?: string | RegExp,
  confirmName: string | RegExp = /确认/,
) {
  expect(
    await screen.findByText(
      /继续前，请确认|可能产生费用，需要你确认|危险操作，需要你确认/,
    ),
  ).toBeInTheDocument();
  const dialog = screen.getByRole("dialog");
  if (title) expect(within(dialog).getByText(title)).toBeInTheDocument();
  fireEvent.click(within(dialog).getByRole("button", { name: confirmName }));
}

describe("AI导演工作台", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    resetStore();
    api.fetchSystemPromptStatus.mockResolvedValue(loadedStatus);
    api.fetchSeedanceSkillStatus.mockResolvedValue({
      installed: true,
      pinned_commit: "57d01dc66f93ecb03c2475be5f22dc416d9b701d",
      vendor_path: "/workspace/vendor/seedance-20",
      module_count: 31,
      license_present: true,
    });
    api.fetchProjectOverview.mockResolvedValue([projectOverview]);
    api.fetchProjects.mockResolvedValue([]);
    api.createProject.mockResolvedValue(project);
    api.createRealAcceptanceProject.mockResolvedValue(acceptanceProject);
    api.fetchProject.mockResolvedValue(project);
    api.updateProjectCreativeGoal.mockResolvedValue({
      ...project,
      creative_goal: "prompt_storyboard",
    });
    api.updateProject.mockResolvedValue(project);
    api.setProjectArchived.mockResolvedValue({ ...project, is_archived: true });
    api.hardDeleteProject.mockResolvedValue(undefined);
    api.fetchSourceFiles.mockResolvedValue([]);
    api.saveSourceText.mockResolvedValue(sourceFile);
    api.saveIntakeSource.mockResolvedValue(sourceFile);
    api.extractSourceText.mockResolvedValue(extraction);
    api.fetchSourceTextExtractions.mockResolvedValue([]);
    api.fetchPlanningDrafts.mockResolvedValue([]);
    api.createAiPlanningDraft.mockResolvedValue(planningDraft);
    api.applyPlanningDraft.mockResolvedValue(appliedPlanningDraft);
    api.fetchTextProviderStatus.mockResolvedValue(textProviderStatus);
    api.runTextProviderSmokeTest.mockResolvedValue({
      ...aiTextRun,
      id: "smoke-run-1",
      project_id: null,
      module_type: "provider_smoke_test",
      response_text: "真实文本大脑已接入完整 V7 主系统，正式创作仍需逐次确认。",
    });
    api.fetchAiTextRuns.mockResolvedValue([]);
    api.fetchRealTextAcceptance.mockResolvedValue(realTextAcceptance);
    api.createAiTextRun.mockResolvedValue(aiTextRun);
    api.createDirectorAnalysis.mockResolvedValue(aiTextRun);
    api.createAssetBrief.mockResolvedValue({
      ...aiTextRun,
      module_type: "asset_brief",
    });
    api.createStoryboardBrief.mockResolvedValue({
      ...aiTextRun,
      module_type: "storyboard_brief",
      target_type: "shot",
      target_id: "shot-1",
    });
    api.fetchUcodeRuns.mockResolvedValue([]);
    api.executeUcodeRun.mockResolvedValue({ ...run, id: "run-new" });
    api.fetchFlowNav.mockResolvedValue(flowNav);
    api.confirmDirectorOption.mockResolvedValue(confirmedFlowNav);
    api.fetchAssetWorkspace.mockResolvedValue(assetWorkspace);
    api.fetchAssetImageJobs.mockResolvedValue([]);
    api.analyzeAssetInventory.mockResolvedValue(assetWorkspaceWithRequirements);
    api.updateAssetRequirement.mockResolvedValue(
      assetWorkspaceWithRequirements,
    );
    api.autoBindAssets.mockResolvedValue({
      ...assetWorkspaceReadyToBind,
      requirements: [{ ...assetRequirement, status: "bound" }],
      prop_bindings: [
        {
          id: "prop-binding-1",
          scene_id: "scene-1",
          prop_id: "prop-1",
          prop_name: "旧信",
          prop_version_id: confirmedAssetVersion.id,
          prop_version_number: 1,
          placement_note: "由剧本识别结果自动绑定",
        },
      ],
    });
    api.fetchAssetImageReadiness.mockResolvedValue({
      ready: true,
      asset_type: "道具资产图",
      provider_name: "慧梦图片服务",
      model_id: "image-2",
      gate_items: [{ label: "图片服务", passed: true, detail: "已配置" }],
      risk_notice: "可能产生图片费用。",
      requires_user_confirmation: true,
    });
    api.submitAssetImage.mockResolvedValue({
      id: "asset-image-job-1",
      project_id: project.id,
      target_type: "prop",
      target_id: "prop-1",
      provider: "huimeng_image",
      model_name: "image-2",
      external_task_id: "external-1",
      status: "submitted",
      remote_result_url: "",
      image_url: null,
      error_message: "",
      created_at: "2026-07-14T00:00:00Z",
    });
    api.pollAssetImage.mockResolvedValue({
      id: "asset-image-job-1",
      project_id: project.id,
      target_type: "prop",
      target_id: "prop-1",
      provider: "huimeng_image",
      model_name: "image-2",
      external_task_id: "external-1",
      status: "completed",
      remote_result_url: "https://example.com/prop.png",
      image_url: null,
      error_message: "",
      created_at: "2026-07-14T00:00:00Z",
    });
    api.downloadAssetImage.mockResolvedValue(assetWorkspaceReadyToBind);
    api.uploadAssetImage.mockResolvedValue(assetWorkspaceReadyToBind);
    api.fetchStoryboardWorkspace.mockResolvedValue(storyboardWorkspace);
    api.saveAxisPlan.mockResolvedValue(storyboardWorkspace);
    api.generateStoryboardVersion.mockResolvedValue(storyboardWorkspace);
    api.transitionStoryboardVersion.mockResolvedValue(storyboardWorkspace);
    api.reuseStoryboardImage.mockResolvedValue(storyboardDownloadedWorkspace);
    api.generateStoryboardPage.mockResolvedValue(storyboardWorkspace);
    api.exportPromptStoryboardPack.mockResolvedValue({
      scene_id: "scene-1",
      scope_code: "EP01SC01",
      zip_url:
        "/api/projects/PRJ001/assets/05_video_prompts/prompt_storyboard_exports/EP01SC01_v001.zip",
      relative_path:
        "05_video_prompts/prompt_storyboard_exports/EP01SC01_v001.zip",
      shot_count: 1,
      files: ["SH001/storyboard_frame.png", "SH001/video_prompt_copy.txt"],
    });
    api.fetchStoryboardImageReadiness.mockResolvedValue({
      ready: true,
      provider_name: "慧梦 image-2",
      model_id: "image-2",
      gate_items: [
        { label: "真实生图开关", passed: true, detail: "已开启" },
        { label: "图片模型", passed: true, detail: "image-2" },
      ],
      risk_notice: "可能产生图片费用。",
      requires_user_confirmation: true,
    });
    api.fetchStoryboardImagePrompt.mockResolvedValue({
      prompt: "为电影导演生成单镜头故事板图片。必须是黑白铅笔草稿。",
    });
    api.submitStoryboardImage.mockResolvedValue({
      id: "image-job-1",
      project_id: project.id,
      target_type: "storyboard",
      target_id: "storyboard-version-1",
      provider: "huimeng_image",
      model_name: "image-2",
      external_task_id: "hm-image-1",
      status: "processing",
      remote_result_url: "",
      image_url: null,
      prompt: "为电影导演生成单镜头故事板图片。必须是黑白铅笔草稿。",
      error_message: "",
      created_at: "2026-06-01T00:00:00Z",
    });
    api.pollStoryboardImage.mockResolvedValue({
      id: "image-job-1",
      project_id: project.id,
      target_type: "storyboard",
      target_id: "storyboard-version-1",
      provider: "huimeng_image",
      model_name: "image-2",
      external_task_id: "hm-image-1",
      status: "completed",
      remote_result_url: "https://example.test/storyboard.png",
      image_url: null,
      prompt: "为电影导演生成单镜头故事板图片。必须是黑白铅笔草稿。",
      error_message: "",
      created_at: "2026-06-01T00:00:00Z",
    });
    api.downloadStoryboardImage.mockResolvedValue(storyboardTaskWorkspace);
    api.fetchVideoPackages.mockResolvedValue(videoPackages);
    api.fetchLatestVpGenerationJob.mockResolvedValue(null);
    api.startVpDurationRebuild.mockResolvedValue({
      id: "vp-job-1",
      project_id: project.id,
      scene_id: "scene-1",
      operation: "duration_rebuild",
      status: "queued",
      total_count: 13,
      completed_count: 0,
      failed_count: 0,
      current_shot_code: "",
      message: "等待后台重建 13 个镜头",
      error_message: "",
      created_at: "2026-08-05T00:00:00Z",
      updated_at: "2026-08-05T00:00:00Z",
    });
    api.retryVpGenerationJob.mockResolvedValue(null);
    api.cancelVpGenerationJob.mockResolvedValue(null);
    api.generateAiVpBlock.mockResolvedValue(videoPackages);
    api.transitionVpBlock.mockResolvedValue(videoPackages);
    api.fetchBatchVideo.mockResolvedValue(batchWorkspace);
    api.createBatchVideo.mockResolvedValue(batchWorkspace);
    api.remapBatchVideoProvider.mockResolvedValue(batchWorkspace);
    api.updateBatchVideoSubmissionChannel.mockResolvedValue(batchWorkspace);
    api.confirmBatchCostRisk.mockResolvedValue(batchWorkspace);
    api.exportJimeng.mockResolvedValue(batchWorkspace);
    api.fetchProviderProfiles.mockResolvedValue([provider]);
    api.fetchAtlasCloudTemplate.mockResolvedValue(atlasTemplate);
    api.fetchHuimengTemplate.mockResolvedValue(huimengTemplate);
    api.fetchLiveProviderStatus.mockResolvedValue(liveProviderStatus);
    api.fetchJimengCliStatus.mockResolvedValue(jimengCliStatus);
    api.fetchVideoTaskSupervisorStatus.mockResolvedValue({
      enabled: true,
      running: true,
      poll_interval_seconds: 5,
      active_task_count: 1,
      last_cycle_at: "2026-07-30T18:00:00Z",
      last_success_at: "2026-07-30T18:00:00Z",
      last_error: "",
    });
    api.fetchJimengVideoModels.mockResolvedValue([
      {
        id: "seedance2.0_vip",
        label: "即梦 Seedance 2.0 VIP",
        speed_label: "会员通道",
        cost_label: "VIP",
        description: "默认成片模型",
        supported_resolutions: ["720p", "1080p", "4k"],
        min_duration: 4,
        max_duration: 15,
      },
      {
        id: "seedance2.0fast",
        label: "即梦 Seedance 2.0 Fast",
        speed_label: "较快",
        cost_label: "中等",
        description: "兼顾速度与质量",
        supported_resolutions: ["720p"],
        min_duration: 4,
        max_duration: 15,
      },
      {
        id: "seedance2.0mini",
        label: "即梦 Seedance 2.0 mini",
        speed_label: "快速",
        cost_label: "较低",
        description: "适合低成本试稿",
        supported_resolutions: ["720p"],
        min_duration: 4,
        max_duration: 15,
      },
    ]);
    api.fetchVideoProviderModels.mockResolvedValue([
      {
        id: "doubao-seedance-2-5-260628",
        label: "火山方舟 Seedance 2.5（Mock）",
        provider_type: "volcengine_seedance25",
        description: "首期只验证本地批量工作流，不发送真实请求。",
        supported_resolutions: ["480p", "720p"],
        min_duration: 4,
        max_duration: 30,
        duration_modes: ["smart", "specified"],
        generation_modes: ["text_to_video", "multimodal_reference"],
        max_image_references: 30,
        max_video_references: 10,
        max_audio_references: 10,
        max_reference_items: 50,
        live_enabled: false,
        mock_only: true,
      },
    ]);
    api.validateProviderProfile.mockResolvedValue(provider);
    api.setDefaultProvider.mockResolvedValue(provider);
    api.preflightProvider.mockResolvedValue({
      profile_id: "huimeng_live",
      provider_type: "seedance_huimeng_live",
      config_valid: true,
      secret_configured: false,
      documentation_url: "",
      price_source_url: "",
      price_configured: true,
      request_mapping_complete: false,
      response_mapping_complete: false,
      outbound_requests_enabled: false,
      ready_for_live_test: false,
      checklist: ["网络提交：必须逐次确认"],
    });
    api.previewProviderResponse.mockResolvedValue({
      profile_id: "generic-1",
      normalized_response: { task_id: "external-001", status: "completed" },
      missing_items: [],
      sample_saved: false,
      outbound_requests_sent: false,
      result_downloaded: false,
    });
    api.previewProviderRequest.mockResolvedValue(providerPreview);
    api.fetchLiveReadiness.mockResolvedValue(liveReadiness);
    api.fetchJimengCliReadiness.mockResolvedValue(jimengCliReadiness);
    api.updateJimengCliModel.mockResolvedValue(huimengBatchWorkspace);
    api.updateVideoReferenceBindings.mockResolvedValue(huimengBatchWorkspace);
    api.refreshBatchTaskPreflight.mockResolvedValue(huimengBatchWorkspace);
    api.prepareJimengCliRetry.mockResolvedValue(huimengBatchWorkspace);
    api.submitLiveVideoTask.mockResolvedValue(huimengBatchWorkspace);
    api.pollLiveVideoTask.mockResolvedValue({
      ...huimengBatchWorkspace,
      jobs: [
        {
          ...huimengBatchWorkspace.jobs[0],
          tasks: [
            { ...huimengBatchWorkspace.jobs[0].tasks[0], status: "completed" },
          ],
        },
      ],
    });
    api.downloadLiveVideoTask.mockResolvedValue({
      ...huimengBatchWorkspace,
      jobs: [
        {
          ...huimengBatchWorkspace.jobs[0],
          tasks: [
            {
              ...huimengBatchWorkspace.jobs[0].tasks[0],
              status: "imported",
              progress_percent: 100,
              progress_label: "已保存到本地",
              storage_status: "local",
              result_video_path: "07_results/generated_videos/demo.mp4",
              local_file_path:
                "/tmp/projects/PRJ001/07_results/generated_videos/demo.mp4",
              results: [
                {
                  id: "result-1",
                  version_number: 1,
                  source: "huimeng_live",
                  status: "imported",
                  video_url:
                    "/api/projects/PRJ001/assets/07_results/generated_videos/demo.mp4",
                },
              ],
            },
          ],
        },
      ],
    });
    api.submitJimengCliTask.mockResolvedValue({
      ...huimengBatchWorkspace,
      jobs: [
        {
          ...huimengBatchWorkspace.jobs[0],
          tasks: [
            {
              ...huimengBatchWorkspace.jobs[0].tasks[0],
              status: "submitted",
              external_task_id: "jm-submit-001",
              external_provider: "jimeng_cli",
            },
          ],
        },
      ],
    });
    api.pollJimengCliTask.mockResolvedValue({
      ...huimengBatchWorkspace,
      jobs: [
        {
          ...huimengBatchWorkspace.jobs[0],
          tasks: [
            {
              ...huimengBatchWorkspace.jobs[0].tasks[0],
              status: "completed",
              external_task_id: "jm-submit-001",
              external_provider: "jimeng_cli",
            },
          ],
        },
      ],
    });
    api.downloadJimengCliTask.mockResolvedValue({
      ...huimengBatchWorkspace,
      jobs: [
        {
          ...huimengBatchWorkspace.jobs[0],
          tasks: [
            {
              ...huimengBatchWorkspace.jobs[0].tasks[0],
              status: "imported",
              external_provider: "jimeng_cli",
              progress_percent: 100,
              progress_label: "已保存到本地",
              storage_status: "local",
              result_video_path: "07_results/generated_videos/jimeng.mp4",
              local_file_path:
                "/tmp/projects/PRJ001/07_results/generated_videos/jimeng.mp4",
              results: [
                {
                  id: "result-cli",
                  version_number: 1,
                  source: "jimeng_cli",
                  status: "imported",
                  video_url:
                    "/api/projects/PRJ001/assets/07_results/generated_videos/jimeng.mp4",
                },
              ],
            },
          ],
        },
      ],
    });
    api.reviewVideoResult.mockResolvedValue(huimengBatchWorkspace);
    api.fetchAiProviderStatus.mockResolvedValue(aiStatus);
    api.fetchLocalEnvStatus.mockResolvedValue(localEnvStatus);
    api.updateLocalEnv.mockResolvedValue({
      ...localEnvStatus,
      huimengi_api_key_configured: true,
      enable_real_seedance: true,
      video_provider_mode: "huimeng_live",
    });
    api.fetchWorkflowReview.mockResolvedValue(workflowReview);
    api.generateWorkflowReport.mockResolvedValue(workflowReview);
  });

  afterEach(() => {
    cleanup();
  });

  it("首页展示项目总控台、项目列表和当前项目详情", async () => {
    render(
      <MemoryRouter>
        <App />
      </MemoryRouter>,
    );

    await waitFor(() =>
      expect(screen.getAllByText("项目总控台").length).toBeGreaterThan(0),
    );
    expect(screen.getByText("选择项目，或上传新剧本开始")).toBeInTheDocument();
    expect(screen.getByText("项目列表")).toBeInTheDocument();
    expect(screen.getAllByText("PRJ001")).not.toHaveLength(0);
    expect(screen.getAllByText("等待导演方案")).not.toHaveLength(0);
    expect(
      screen.queryByRole("button", { name: "进入项目" }),
    ).not.toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "管理 PRJ001" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("navigation", { name: "主导航" }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "打开菜单" }),
    ).not.toBeInTheDocument();
    expect(document.querySelector(".workbench-page")).toBeInTheDocument();
  });

  it("侧边栏通过项目总控台返回总控台，也可以收起和展开菜单", async () => {
    seedProject();
    render(
      <MemoryRouter initialEntries={["/settings"]}>
        <App />
      </MemoryRouter>,
    );

    await waitFor(() =>
      expect(screen.getAllByText("项目总控台").length).toBeGreaterThan(0),
    );
    fireEvent.click(screen.getAllByText("项目总控台")[0]);
    await waitFor(() =>
      expect(screen.getAllByText("项目总控台").length).toBeGreaterThan(0),
    );
    expect(screen.queryByText("返回项目总控台")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "收起菜单" }));
    expect(
      screen.getByRole("button", { name: "展开菜单" }),
    ).toBeInTheDocument();
    expect(screen.queryByText("返回项目总控台")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "展开菜单" }));
    expect(
      screen.getByRole("button", { name: "收起菜单" }),
    ).toBeInTheDocument();
  });

  it("无项目时在工作区展示上传资料开始第一个项目", async () => {
    render(
      <MemoryRouter initialEntries={["/start-plan"]}>
        <App />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByText("上传资料开始第一个项目")).toBeInTheDocument();
    });
    expect(screen.getByText(/第一件事只有一个/)).toBeInTheDocument();
  });

  it("首页新建项目面板能粘贴剧本并进入开始分析", async () => {
    api.fetchProjects.mockResolvedValue([]);
    api.fetchSourceFiles.mockResolvedValue([sourceFile]);
    api.fetchUcodeRuns.mockResolvedValue([]);
    render(
      <MemoryRouter>
        <App />
      </MemoryRouter>,
    );

    await waitFor(() =>
      expect(screen.getAllByText("项目总控台").length).toBeGreaterThan(0),
    );
    fireEvent.click(screen.getByRole("button", { name: "新建项目" }));
    fireEvent.change(screen.getByPlaceholderText("例如：测试短片"), {
      target: { value: "资料优先测试" },
    });
    fireEvent.change(screen.getByPlaceholderText(/把剧本、小说片段/), {
      target: { value: "第一场：夜雨中的对峙。" },
    });
    fireEvent.click(screen.getByRole("button", { name: "创建项目并保存资料" }));

    await waitFor(() =>
      expect(api.createProject).toHaveBeenCalledWith("资料优先测试", ""),
    );
    expect(api.saveIntakeSource).toHaveBeenCalled();
    expect(api.extractSourceText).toHaveBeenCalledWith(sourceFile.id);
    expect(api.executeUcodeRun).not.toHaveBeenCalled();
  });

  it("首页支持编辑、归档恢复和两步删除项目", async () => {
    api.fetchProjectOverview
      .mockResolvedValueOnce([projectOverview, archivedProjectOverview])
      .mockResolvedValue([projectOverview]);
    api.fetchProject.mockImplementation((projectId: string) =>
      Promise.resolve(
        projectId === archivedProjectOverview.id
          ? {
              ...project,
              id: archivedProjectOverview.id,
              project_code: archivedProjectOverview.project_code,
              name: archivedProjectOverview.name,
              is_archived: true,
            }
          : project,
      ),
    );
    render(
      <MemoryRouter>
        <App />
      </MemoryRouter>,
    );

    await waitFor(() =>
      expect(screen.getByText("测试短剧")).toBeInTheDocument(),
    );
    fireEvent.click(screen.getByRole("button", { name: "管理 PRJ001" }));
    await waitFor(() =>
      expect(screen.getByText("项目管理")).toBeInTheDocument(),
    );
    fireEvent.change(screen.getByDisplayValue("测试短剧"), {
      target: { value: "修改后的项目名" },
    });
    fireEvent.click(screen.getByRole("button", { name: "保存项目信息" }));
    await waitFor(() =>
      expect(api.updateProject).toHaveBeenCalledWith(
        project.id,
        "修改后的项目名",
        "本地项目",
      ),
    );

    fireEvent.click(screen.getByRole("button", { name: "归档隐藏" }));
    await waitFor(() =>
      expect(api.setProjectArchived).toHaveBeenCalledWith(project.id, true),
    );

    fireEvent.click(screen.getByRole("button", { name: "删除这个项目" }));
    expect(screen.getByText("确认删除这个项目？")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "确认删除" }));
    await waitFor(() =>
      expect(api.hardDeleteProject).toHaveBeenCalledWith(
        project.id,
        "测试短剧",
      ),
    );
  });

  it("真实跑通主按钮按当前阶段推进，不会因为生图或视频未配置就拦住上传资料", () => {
    const action = realRunPrimaryAction({
      activeProject: null,
      flowNav: null,
      textStatus: textProviderStatus,
      localEnv: localEnvStatus,
      liveStatus: liveProviderStatus,
    });

    expect(action).toEqual({
      label: "上传资料开始",
      href: "/start-plan#source-intake",
      reason: "还没有当前项目。",
    });
  });

  it("开始页不再展示工程项目树和重复素材入口", () => {
    seedProject();
    render(
      <MemoryRouter initialEntries={["/start-plan"]}>
        <App />
      </MemoryRouter>,
    );

    expect(screen.getByText("当前主任务")).toBeInTheDocument();
    expect(screen.queryByText("EP01｜第 1 集")).not.toBeInTheDocument();
    expect(screen.queryByText("SC01｜第 1 场")).not.toBeInTheDocument();
    expect(screen.queryByText("SH001｜镜头 1")).not.toBeInTheDocument();
    expect(screen.queryByText("上传本地素材")).not.toBeInTheDocument();
    expect(
      screen.queryByText("旧操作记录（一般不用看）"),
    ).not.toBeInTheDocument();
  });

  it("开始页展示已解析资料、启动分析卡和分镜规划确认区", async () => {
    seedProject();
    api.fetchFlowNav.mockResolvedValue(confirmedFlowNav);
    render(
      <MemoryRouter initialEntries={["/start-plan"]}>
        <App />
      </MemoryRouter>,
    );

    await waitFor(() =>
      expect(screen.getAllByText("确认分镜规划").length).toBeGreaterThan(0),
    );
    expect(screen.getByText("可选：查看 AI 原文")).toBeInTheDocument();
    expect(screen.getByText("SH002")).toBeInTheDocument();
    expect(
      screen.getByText("根据原文设计镜头：旧信落地。"),
    ).toBeInTheDocument();
  });

  it("开始页主控卡可以逐次确认后调用真实 AI 导演分析", async () => {
    seedProject();
    api.fetchFlowNav.mockResolvedValue(awaitingAiFlowNav);
    render(
      <MemoryRouter initialEntries={["/start-plan"]}>
        <App />
      </MemoryRouter>,
    );

    await waitFor(() =>
      expect(screen.getByText("当前主任务")).toBeInTheDocument(),
    );
    fireEvent.click(screen.getByRole("button", { name: "用 AI 分析剧本" }));
    await acceptWorkbenchConfirm("确认使用 AI 分析文字", "确认，开始分析");

    await waitFor(() =>
      expect(api.createDirectorAnalysis).toHaveBeenCalledWith(
        project.id,
        expect.objectContaining({
          module_type: "director_analysis",
          source_extraction_id: extraction.id,
          confirm_live_request: true,
        }),
      ),
    );
  });

  it("开始页刷新后仍展示已保存的真实 AI 文本结果", async () => {
    seedProject();
    api.fetchAiTextRuns.mockResolvedValue([aiTextRun]);
    render(
      <MemoryRouter initialEntries={["/start-plan"]}>
        <App />
      </MemoryRouter>,
    );

    await waitFor(() =>
      expect(screen.getByText("AI 产出记录")).toBeInTheDocument(),
    );
    expect(screen.getByText("AI 导演运行台")).toBeInTheDocument();
    expect(
      screen.getByText("像对话一样，看见 AI 做了什么"),
    ).toBeInTheDocument();
    expect(screen.getByText("V7｜开始｜导演分析结果")).toBeInTheDocument();
    expect(screen.queryByText("查看完整 AI 分析原文")).not.toBeInTheDocument();
    expect(screen.getByText("可选：查看 AI 原文")).toBeInTheDocument();
    expect(screen.getAllByText(/真实 AI 新生成/).length).toBeGreaterThan(0);
    expect(screen.getByText("最新 AI 分析结果")).toBeInTheDocument();
    expect(screen.getAllByText(/方案一：原剧情版/).length).toBeGreaterThan(0);
    expect(screen.getAllByText("使用的系统规则").length).toBeGreaterThan(0);
    expect(
      screen.getAllByText(/本次新生成，已保存记录/).length,
    ).toBeGreaterThan(0);
  });

  it("确认导演方案时展示真实 AI 给出的所有方案卡，并可点击选择", async () => {
    seedProject();
    api.fetchFlowNav.mockResolvedValue(flowNav);
    api.fetchAiTextRuns.mockResolvedValue([aiTextRun]);
    render(
      <MemoryRouter initialEntries={["/start-plan#director-option-panel"]}>
        <App />
      </MemoryRouter>,
    );

    await waitFor(() =>
      expect(
        screen.getByText("真实 AI 给出的全部可选导演方案"),
      ).toBeInTheDocument(),
    );
    expect(screen.getByText("AI 推荐结论")).toBeInTheDocument();
    expect(screen.getByText("原剧情版")).toBeInTheDocument();
    expect(screen.getByText("唯美画意版")).toBeInTheDocument();
    expect(screen.getByText("G版打斗特效版")).toBeInTheDocument();
    expect(screen.getByText("H解说模式")).toBeInTheDocument();
    expect(screen.getByText("推荐导演方案")).toBeInTheDocument();
    expect(
      screen.getAllByText(/推荐理由：它最能保留原剧情/).length,
    ).toBeGreaterThan(0);

    fireEvent.click(
      screen.getByRole("button", { name: "选择导演方案：原剧情版" }),
    );

    expect(screen.getByLabelText("导演方案名称")).toHaveValue("原剧情版");
    expect(
      (screen.getByLabelText("导演方案备注") as HTMLInputElement).value,
    ).toContain("不改人物关系");
  });

  it("旧导演分析不完整时提供重新生成完整五方案入口", async () => {
    seedProject();
    api.fetchFlowNav.mockResolvedValue(flowNav);
    api.fetchAiTextRuns.mockResolvedValue([incompleteDirectorAnalysisRun]);
    render(
      <MemoryRouter initialEntries={["/start-plan#director-option-panel"]}>
        <App />
      </MemoryRouter>,
    );

    await waitFor(() =>
      expect(screen.getByText("这条导演分析还不完整")).toBeInTheDocument(),
    );
    expect(screen.getByText(/本次记录识别到 3 个方案/)).toBeInTheDocument();
    expect(screen.getByText("方案四")).toBeInTheDocument();
    expect(screen.getAllByText("原系统槽位").length).toBeGreaterThan(0);

    fireEvent.click(screen.getByRole("button", { name: "重新生成完整五方案" }));
    await acceptWorkbenchConfirm("确认使用 AI 分析文字", "确认，开始分析");

    await waitFor(() =>
      expect(api.createDirectorAnalysis).toHaveBeenCalledWith(
        project.id,
        expect.objectContaining({
          module_type: "director_analysis",
          source_extraction_id: extraction.id,
          confirm_live_request: true,
          force_regenerate: true,
        }),
      ),
    );
  });

  it("确认导演方案后主控卡先生成分镜规划，再提示应用", async () => {
    seedProject();
    useWorkbenchStore.setState({ planningDrafts: [] });
    api.fetchFlowNav.mockResolvedValue(confirmedNoDraftFlowNav);
    render(
      <MemoryRouter initialEntries={["/start-plan"]}>
        <App />
      </MemoryRouter>,
    );

    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: "生成分镜规划" }),
      ).toBeInTheDocument(),
    );
    expect(
      screen.queryByRole("button", { name: "用真实 AI 生成规划草案" }),
    ).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "生成分镜规划" }));
    await acceptWorkbenchConfirm("确认使用 AI 分析文字", "确认，开始分析");

    await waitFor(() =>
      expect(api.createAiPlanningDraft).toHaveBeenCalledWith(
        project.id,
        expect.objectContaining({
          module_type: "planning_draft",
          source_extraction_id: extraction.id,
          confirm_live_request: true,
        }),
      ),
    );
  });

  it("开始页可以确认分镜规划并保留复查内容", async () => {
    seedProject();
    api.fetchFlowNav.mockResolvedValue(confirmedFlowNav);
    api.fetchProject.mockResolvedValue(appliedProject);
    api.fetchPlanningDrafts.mockResolvedValue([appliedPlanningDraft]);
    render(
      <MemoryRouter initialEntries={["/start-plan"]}>
        <App />
      </MemoryRouter>,
    );

    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: "确认并使用这份规划" }),
      ).toBeInTheDocument(),
    );
    fireEvent.click(screen.getByRole("button", { name: "确认并使用这份规划" }));

    await waitFor(() =>
      expect(api.applyPlanningDraft).toHaveBeenCalledWith("draft-1"),
    );
    await waitFor(() =>
      expect(screen.getAllByText("已用于当前项目").length).toBeGreaterThan(0),
    );
    expect(screen.getByText("已确认分镜规划")).toBeInTheDocument();
  });

  it("导演方案和已应用分镜规划在进入资产前仍可复查", async () => {
    seedProject();
    api.fetchFlowNav.mockResolvedValue(confirmedFlowNav);
    api.fetchAiTextRuns.mockResolvedValue([aiTextRun]);
    api.fetchPlanningDrafts.mockResolvedValue([appliedPlanningDraft]);
    useWorkbenchStore.setState({ planningDrafts: [appliedPlanningDraft] });
    render(
      <MemoryRouter initialEntries={["/start-plan#director-option-panel"]}>
        <App />
      </MemoryRouter>,
    );

    await waitFor(() =>
      expect(screen.getByText("已确认导演方案")).toBeInTheDocument(),
    );
    expect(
      screen.getByText("真实 AI 给出的全部可选导演方案"),
    ).toBeInTheDocument();
    expect(screen.getAllByText("当前采用").length).toBeGreaterThan(0);
    expect(screen.getByText("原剧情版")).toBeInTheDocument();
    expect(screen.getByText("唯美画意版")).toBeInTheDocument();
    expect(screen.getByText("G版打斗特效版")).toBeInTheDocument();
    expect(screen.getByText("H解说模式")).toBeInTheDocument();
    expect(screen.getByText("推荐导演方案")).toBeInTheDocument();
    expect(screen.getByText("已确认分镜规划")).toBeInTheDocument();
    expect(
      screen.getByText("AI 拆分出 2 个镜头，请确认是否按这个顺序继续。"),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "已确认使用" })).toBeDisabled();
  });

  it("PDF 或图片资料显示已保存但暂未解析正文", async () => {
    seedProject();
    api.fetchSourceTextExtractions.mockResolvedValue([unsupportedExtraction]);
    useWorkbenchStore.setState({
      sourceTextExtractions: [unsupportedExtraction],
      planningDrafts: [],
    });
    render(
      <MemoryRouter initialEntries={["/start-plan"]}>
        <App />
      </MemoryRouter>,
    );

    await waitFor(() =>
      expect(screen.getByText("已保存，暂未解析正文")).toBeInTheDocument(),
    );
    expect(
      screen.getByText(/本轮只解析粘贴文本、TXT、MD、DOCX 和 XLSX/),
    ).toBeInTheDocument();
  });

  it("FLOW-NAV 支持人工确认导演方案并切换下一步建议", async () => {
    seedProject();
    render(
      <MemoryRouter initialEntries={["/start-plan"]}>
        <App />
      </MemoryRouter>,
    );
    await waitFor(() => expect(screen.getByText("下一步")).toBeInTheDocument());
    fireEvent.change(screen.getByLabelText("导演方案名称"), {
      target: { value: "克制压迫版" },
    });
    fireEvent.click(screen.getByRole("button", { name: "确认方案" }));
    await waitFor(() =>
      expect(api.confirmDirectorOption).toHaveBeenCalledWith(
        "episode-1",
        "克制压迫版",
        "",
      ),
    );
    expect(api.confirmDirectorOption).toHaveBeenCalledWith(
      "episode-1",
      "克制压迫版",
      "",
    );
  });

  it("本次创作目标按项目保存", async () => {
    seedProject();
    render(
      <MemoryRouter initialEntries={["/start-plan"]}>
        <App />
      </MemoryRouter>,
    );

    await waitFor(() =>
      expect(screen.getByText("本次创作目标")).toBeInTheDocument(),
    );
    fireEvent.click(screen.getByRole("button", { name: /提示词 \+ 故事板/ }));

    await waitFor(() => {
      expect(api.updateProjectCreativeGoal).toHaveBeenCalledWith(
        project.id,
        "prompt_storyboard",
      );
    });
  });

  it("故事板页展示故事板工作区", async () => {
    seedProject();
    render(
      <MemoryRouter initialEntries={["/storyboards"]}>
        <App />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(
        screen.getByText("把分镜提示词变成黑白故事板"),
      ).toBeInTheDocument();
    });
    expect(screen.queryByText("可选：查看画风规则")).not.toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "逐镜故事板详情" }),
    ).toBeInTheDocument();
    expect(
      screen.queryByText("可选：查看单镜故事板详情"),
    ).not.toBeInTheDocument();
    expect(screen.getByText("镜头方向规则（一般不用改）")).toBeInTheDocument();
    expect(screen.getByText("SH001")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "一次生成本场故事板草稿" }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        "这不是故事板图片，只是镜头拆分和方向示意。确认结构后，使用页面上方主按钮生成真实 AI 故事板图。",
      ),
    ).toBeInTheDocument();
  });

  it("本地结构草稿不会伪装成正式故事板图片", async () => {
    seedProject();
    api.fetchStoryboardWorkspace.mockResolvedValue(storyboardTaskWorkspace);
    render(
      <MemoryRouter initialEntries={["/storyboards"]}>
        <App />
      </MemoryRouter>,
    );

    await waitFor(() =>
      expect(screen.getByText("镜头结构与时间轴草稿")).toBeInTheDocument(),
    );
    expect(screen.getByText("6 格 · 非 AI 图片")).toBeInTheDocument();
    expect(
      screen.getByText("只用于检查拆分和方向，不作为最终故事板"),
    ).toBeInTheDocument();
    expect(screen.queryByAltText("SH001 黑白故事板")).not.toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "确认本场镜头拆分" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "确认结构与时间段" }),
    ).toBeInTheDocument();
  });

  it("故事板缩略图点击后可以放大预览", async () => {
    seedProject();
    api.fetchStoryboardWorkspace.mockResolvedValue(
      storyboardDownloadedWorkspace,
    );
    render(
      <MemoryRouter initialEntries={["/storyboards"]}>
        <App />
      </MemoryRouter>,
    );

    await waitFor(() =>
      expect(screen.getByAltText("SH001 黑白故事板")).toBeInTheDocument(),
    );
    fireEvent.click(screen.getByAltText("SH001 黑白故事板"));

    expect(
      screen.getByRole("dialog", { name: "SH001 故事板大图预览" }),
    ).toBeInTheDocument();
    expect(screen.getByAltText("SH001 故事板大图")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "关闭" }));
    await waitFor(() =>
      expect(
        screen.queryByRole("dialog", { name: "SH001 故事板大图预览" }),
      ).not.toBeInTheDocument(),
    );
  });

  it("主规则重建后常显旧图审核并允许绑定到新时间轴", async () => {
    seedProject();
    api.fetchStoryboardWorkspace.mockResolvedValue(storyboardReusableWorkspace);
    render(
      <MemoryRouter initialEntries={["/storyboards"]}>
        <App />
      </MemoryRouter>,
    );

    await waitFor(() =>
      expect(
        screen.getByText("逐张确认旧故事板图是否沿用"),
      ).toBeInTheDocument(),
    );
    expect(screen.getByAltText("SH001 待审核旧故事板")).toBeInTheDocument();
    expect(screen.getByText("建议沿用")).toBeInTheDocument();
    expect(screen.getByText("旧时间段：0-1s")).toBeInTheDocument();
    expect(screen.getByText("新时间段：0-2s")).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "查看并处理可沿用旧图" }),
    ).toHaveAttribute("href", "/storyboards#storyboard-reuse-review");

    fireEvent.click(
      screen.getByRole("button", { name: "沿用旧图并绑定新时间轴" }),
    );
    expect(await screen.findByRole("dialog")).toBeInTheDocument();
    fireEvent.click(
      within(screen.getByRole("dialog")).getByRole("button", {
        name: "确认沿用并绑定",
      }),
    );

    await waitFor(() =>
      expect(api.reuseStoryboardImage).toHaveBeenCalledWith(
        "storyboard-version-new",
        "storyboard-version-old",
        false,
      ),
    );
  });

  it("结构不兼容时允许用户明确选择仍使用原图", async () => {
    seedProject();
    api.fetchStoryboardWorkspace.mockResolvedValue(
      storyboardForcedReuseWorkspace,
    );
    render(
      <MemoryRouter initialEntries={["/storyboards"]}>
        <App />
      </MemoryRouter>,
    );

    await waitFor(() =>
      expect(screen.getByText("必须重生成")).toBeInTheDocument(),
    );
    fireEvent.click(screen.getByRole("button", { name: "仍使用原图" }));
    expect(
      await screen.findByText("仍使用 SH001 原故事板图？"),
    ).toBeInTheDocument();
    fireEvent.click(
      within(screen.getByRole("dialog")).getByRole("button", {
        name: "仍使用原图并绑定",
      }),
    );

    await waitFor(() =>
      expect(api.reuseStoryboardImage).toHaveBeenCalledWith(
        "storyboard-version-new",
        "storyboard-version-old",
        true,
      ),
    );
  });

  it("故事板页不在详情区重复显示导出按钮", async () => {
    seedProject();
    render(
      <MemoryRouter initialEntries={["/storyboards"]}>
        <App />
      </MemoryRouter>,
    );

    await waitFor(() =>
      expect(
        screen.getByText("把分镜提示词变成黑白故事板"),
      ).toBeInTheDocument(),
    );
    expect(
      screen.getByRole("button", { name: "一次生成本场故事板草稿" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "逐镜故事板详情" }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "下载故事板包" }),
    ).not.toBeInTheDocument();
    expect(api.exportPromptStoryboardPack).not.toHaveBeenCalled();
  });

  it("故事板页把真实图片生成作为确认后的主动作，并要求用户确认", async () => {
    seedProject();
    api.fetchStoryboardWorkspace
      .mockResolvedValueOnce(storyboardConfirmedWorkspace)
      .mockResolvedValue(storyboardProcessingImageWorkspace);
    api.downloadStoryboardImage.mockResolvedValue(
      storyboardDownloadedWorkspace,
    );
    render(
      <MemoryRouter initialEntries={["/storyboards"]}>
        <App />
      </MemoryRouter>,
    );

    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: "生成下一张真实故事板图" }),
      ).toBeInTheDocument(),
    );
    fireEvent.click(
      screen.getByRole("button", { name: "生成下一张真实故事板图" }),
    );

    await waitFor(() =>
      expect(api.fetchStoryboardImageReadiness).toHaveBeenCalledWith(
        "storyboard-version-1",
      ),
    );
    expect(
      screen.getByRole("dialog", { name: "确认生成真实故事板图片" }),
    ).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "确认生成这一张" }));

    await waitFor(() =>
      expect(api.submitStoryboardImage).toHaveBeenCalledWith(
        "storyboard-version-1",
      ),
    );
    await waitFor(() =>
      expect(
        screen.getByRole("region", { name: "故事板图片生成状态" }),
      ).toHaveTextContent("后台处理中"),
    );
    expect(api.pollStoryboardImage).not.toHaveBeenCalled();
    expect(api.downloadStoryboardImage).not.toHaveBeenCalled();
    expect(
      screen.queryByRole("button", { name: "保存图片版本" }),
    ).not.toBeInTheDocument();
  });

  it("刷新后已完成真实图片任务只从主按钮下载，不重复显示保存按钮", async () => {
    seedProject();
    api.fetchStoryboardWorkspace.mockResolvedValue(
      storyboardCompletedImageWorkspace,
    );
    api.downloadStoryboardImage.mockResolvedValue(
      storyboardDownloadedWorkspace,
    );
    render(
      <MemoryRouter initialEntries={["/storyboards"]}>
        <App />
      </MemoryRouter>,
    );

    await waitFor(() =>
      expect(screen.getByText("下载已完成的真实图片")).toBeInTheDocument(),
    );
    fireEvent.click(
      screen.getByRole("button", { name: "下载已完成的真实图片" }),
    );
    await waitFor(() =>
      expect(api.downloadStoryboardImage).toHaveBeenCalledWith(
        "image-job-completed",
      ),
    );
    await waitFor(() =>
      expect(screen.getByAltText("SH001 黑白故事板")).toBeInTheDocument(),
    );
    expect(
      screen.queryByRole("button", { name: "保存图片版本" }),
    ).not.toBeInTheDocument();
  });

  it("卡片内显示后台生图状态，重复点击只查询现有任务", async () => {
    seedProject();
    api.fetchStoryboardWorkspace.mockResolvedValue(
      storyboardProcessingImageWorkspace,
    );
    render(
      <MemoryRouter initialEntries={["/storyboards"]}>
        <App />
      </MemoryRouter>,
    );

    const monitor = await screen.findByRole("region", {
      name: "故事板图片生成状态",
    });
    expect(
      within(monitor).getByText(
        "页面每 3 秒同步一次本地后台状态。切换菜单不会停止任务；服务商未返回真实百分比时，只展示可核验的处理阶段。",
      ),
    ).toBeInTheDocument();
    expect(
      within(monitor).getByText("1 张", { selector: "p" }),
    ).toBeInTheDocument();
    expect(
      screen.getAllByText("生成中，后台会持续查询").length,
    ).toBeGreaterThanOrEqual(1);
    expect(
      screen.getByText("可以切换到其他页面，后台任务不会停止。"),
    ).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "立即查询生成进度" }));

    await waitFor(() =>
      expect(api.pollStoryboardImage).toHaveBeenCalledWith(
        "image-job-processing",
      ),
    );
    expect(api.submitStoryboardImage).not.toHaveBeenCalled();
  });

  it("开始页不再展示手动 UCODE 记录区", async () => {
    seedProject();
    render(
      <MemoryRouter initialEntries={["/start-plan"]}>
        <App />
      </MemoryRouter>,
    );

    await waitFor(() =>
      expect(screen.getByText("当前主任务")).toBeInTheDocument(),
    );
    expect(screen.queryByLabelText("UCODE 补充要求")).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "保存手动记录" }),
    ).not.toBeInTheDocument();
  });

  it("资产页从剧本识别人名、场景和道具", async () => {
    seedProject();
    render(
      <MemoryRouter initialEntries={["/assets"]}>
        <App />
      </MemoryRouter>,
    );

    await waitFor(() =>
      expect(screen.getByText("从剧本整理并绑定资产")).toBeInTheDocument(),
    );
    fireEvent.click(screen.getByRole("button", { name: "从剧本识别资产" }));
    await acceptWorkbenchConfirm("从剧本识别资产", "确认识别资产");
    await waitFor(() =>
      expect(api.analyzeAssetInventory).toHaveBeenCalledWith(project.id, false),
    );
  });

  it("资产清单支持真实生成或上传已有图片", async () => {
    seedProject();
    api.fetchAssetWorkspace.mockResolvedValue(assetWorkspaceWithRequirements);
    render(
      <MemoryRouter initialEntries={["/assets"]}>
        <App />
      </MemoryRouter>,
    );

    await waitFor(() =>
      expect(
        screen.getByText("逐项确认关键参考与文字描述"),
      ).toBeInTheDocument(),
    );
    expect(
      screen.getByRole("button", { name: /重新识别关键资产/ }),
    ).toBeInTheDocument();
    expect(
      screen.getByText("按剧情重判图片参考与文字描述"),
    ).toBeInTheDocument();
    const requirementCard = screen
      .getByRole("heading", { name: "旧信" })
      .closest("article");
    expect(requirementCard).not.toBeNull();
    const requirement = within(requirementCard as HTMLElement);
    expect(requirement.getByText(/她把旧信藏进抽屉/)).toBeInTheDocument();
    expect(requirement.getByText("上传已有图")).toBeInTheDocument();
    fireEvent.click(requirement.getByRole("button", { name: "生成新图" }));
    await acceptWorkbenchConfirm("确认生成道具资产图", "确认生成图片");
    await waitFor(() =>
      expect(api.fetchAssetImageReadiness).toHaveBeenCalledWith(
        "prop",
        "prop-1",
      ),
    );
    expect(api.submitAssetImage).toHaveBeenCalledWith("prop", "prop-1");

    const uploadLabel = requirement.getByText("上传已有图").closest("label");
    const fileInput = uploadLabel?.querySelector(
      "input[type='file']",
    ) as HTMLInputElement;
    const existingImage = new File(["existing-image"], "old-letter.png", {
      type: "image/png",
    });
    fireEvent.change(fileInput, { target: { files: [existingImage] } });
    await acceptWorkbenchConfirm("确认上传已有资产图", "确认上传");
    await waitFor(() =>
      expect(api.uploadAssetImage).toHaveBeenCalledWith(
        "prop",
        "prop-1",
        existingImage,
      ),
    );
  });

  it("切换左侧菜单后仍继续轮询并保存已提交的图片任务", async () => {
    seedProject();
    api.fetchAssetWorkspace.mockResolvedValue(assetWorkspaceWithRequirements);
    render(
      <MemoryRouter initialEntries={["/assets"]}>
        <App />
      </MemoryRouter>,
    );

    await waitFor(() =>
      expect(
        screen.getByText("逐项确认关键参考与文字描述"),
      ).toBeInTheDocument(),
    );
    const requirementCard = screen
      .getByRole("heading", { name: "旧信" })
      .closest("article");
    const requirement = within(requirementCard as HTMLElement);
    fireEvent.click(requirement.getByRole("button", { name: "生成新图" }));
    await acceptWorkbenchConfirm("确认生成道具资产图", "确认生成图片");
    await waitFor(() =>
      expect(screen.getByText("任务已提交")).toBeInTheDocument(),
    );

    fireEvent.click(screen.getByRole("link", { name: /^开始 / }));
    await waitFor(() =>
      expect(screen.getByText("当前主任务")).toBeInTheDocument(),
    );

    await waitFor(
      () =>
        expect(api.pollAssetImage).toHaveBeenCalledWith("asset-image-job-1"),
      { timeout: 3000 },
    );
    await waitFor(
      () =>
        expect(api.downloadAssetImage).toHaveBeenCalledWith(
          "asset-image-job-1",
        ),
      { timeout: 3000 },
    );
  });

  it("资产图全部确认后可按剧情自动绑定到场次", async () => {
    seedProject();
    api.fetchAssetWorkspace.mockResolvedValue(assetWorkspaceReadyToBind);
    render(
      <MemoryRouter initialEntries={["/assets"]}>
        <App />
      </MemoryRouter>,
    );

    await waitFor(() =>
      expect(
        screen.getByText("把确认好的资产自动放进对应场次"),
      ).toBeInTheDocument(),
    );
    fireEvent.click(screen.getByRole("button", { name: "自检并修复自动绑定" }));
    await acceptWorkbenchConfirm("按剧情自动绑定关键参考", "确认自动绑定");
    await waitFor(() =>
      expect(api.autoBindAssets).toHaveBeenCalledWith(project.id),
    );
    expect(
      await screen.findByText(/自检修复完成：1 项关键参考已绑定/),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "下一步：生成成片提示词" }),
    ).toBeInTheDocument();
  });

  it("确认自动绑定后立即显示执行状态，完成后给出明确下一步", async () => {
    seedProject();
    api.fetchAssetWorkspace.mockResolvedValue(assetWorkspaceReadyToBind);
    let finishBinding:
      | ((value: typeof assetWorkspaceReadyToBind) => void)
      | undefined;
    api.autoBindAssets.mockImplementation(
      () =>
        new Promise((resolve) => {
          finishBinding = resolve;
        }),
    );
    render(
      <MemoryRouter initialEntries={["/assets"]}>
        <App />
      </MemoryRouter>,
    );

    await waitFor(() =>
      expect(
        screen.getByText("把确认好的资产自动放进对应场次"),
      ).toBeInTheDocument(),
    );
    fireEvent.click(screen.getByRole("button", { name: "自检并修复自动绑定" }));
    await acceptWorkbenchConfirm("按剧情自动绑定关键参考", "确认自动绑定");

    expect(
      (await screen.findAllByText("正在按剧情场次绑定已确认资产…")).length,
    ).toBeGreaterThan(0);
    expect(
      screen.getByRole("button", { name: "正在自动绑定…" }),
    ).toBeDisabled();
    await waitFor(() =>
      expect(api.autoBindAssets).toHaveBeenCalledWith(project.id),
    );

    await act(async () => {
      finishBinding?.({
        ...assetWorkspaceReadyToBind,
        requirements: [{ ...assetRequirement, status: "bound" }],
      });
    });

    expect(
      await screen.findByRole("link", { name: "下一步：生成成片提示词" }),
    ).toBeInTheDocument();
  });

  it("资产自动绑定无法连接后端时在按钮区域直接说明原因", async () => {
    seedProject();
    api.fetchAssetWorkspace.mockResolvedValue(assetWorkspaceReadyToBind);
    api.autoBindAssets.mockRejectedValue(new TypeError("Failed to fetch"));
    render(
      <MemoryRouter initialEntries={["/assets"]}>
        <App />
      </MemoryRouter>,
    );

    await waitFor(() =>
      expect(
        screen.getByText("把确认好的资产自动放进对应场次"),
      ).toBeInTheDocument(),
    );
    fireEvent.click(screen.getByRole("button", { name: "自检并修复自动绑定" }));
    await acceptWorkbenchConfirm("按剧情自动绑定关键参考", "确认自动绑定");

    expect(
      await screen.findByText(/自动绑定失败：本地 FastAPI 后端未连接/),
    ).toBeInTheDocument();
  });

  it("资产全部绑定后引导生成成片提示词", async () => {
    seedProject();
    api.fetchAssetWorkspace.mockResolvedValue({
      ...assetWorkspaceReadyToBind,
      requirements: [{ ...assetRequirement, status: "bound" }],
    });
    render(
      <MemoryRouter initialEntries={["/assets"]}>
        <App />
      </MemoryRouter>,
    );

    await waitFor(() =>
      expect(
        screen.getByText("人物、服装、场景和道具已按剧情绑定"),
      ).toBeInTheDocument(),
    );
    expect(
      screen.getByRole("link", { name: "下一步：生成成片提示词" }),
    ).toHaveAttribute("href", "/video-package");
  });

  it("分镜提示词页可直接打开并一次生成本场全部分镜提示词", async () => {
    seedProject();
    render(
      <MemoryRouter initialEntries={["/video-package"]}>
        <App />
      </MemoryRouter>,
    );
    await waitFor(() =>
      expect(screen.getAllByText("分镜提示词").length).toBeGreaterThan(0),
    );
    expect(
      screen.getByRole("button", { name: "一次生成本场全部分镜提示词" }),
    ).toBeInTheDocument();
  });

  it("分镜提示词真实 AI 生成确认弹窗显示完整系统规则说明", async () => {
    seedProject();
    render(
      <MemoryRouter initialEntries={["/video-package"]}>
        <App />
      </MemoryRouter>,
    );
    await waitFor(() =>
      expect(screen.getAllByText("分镜提示词").length).toBeGreaterThan(0),
    );
    fireEvent.click(
      screen.getByRole("button", { name: "一次生成本场全部分镜提示词" }),
    );
    await acceptWorkbenchConfirm("确认生成本场全部分镜提示词", "确认生成");
    await waitFor(() => expect(api.generateAiVpBlock).toHaveBeenCalled());
  });

  it("成片提示词已生成但未确认时先确认本场再进入批量视频", async () => {
    seedProject();
    const generatedFinal = {
      id: "vp-final-1",
      shot_id: "shot-1",
      version_number: 2,
      schema_version: "vp_precision_18_v1",
      package_stage: "final_execution",
      status: "draft",
      precision_items: [],
      prompt_copy: "成片提示词",
      validation_items: ["VP-PRECISION-18 已完整生成"],
      meaning_chain: {},
    };
    const confirmedDraft = {
      ...generatedFinal,
      id: "vp-draft-1",
      version_number: 1,
      package_stage: "director_draft",
      status: "confirmed_current",
      prompt_copy: "故事板参考提示词",
    };
    const generatedWorkspace = {
      ...videoPackages,
      scenes: [
        {
          ...videoPackages.scenes[0],
          shots: [
            {
              ...videoPackages.scenes[0].shots[0],
              versions: [generatedFinal, confirmedDraft],
            },
          ],
        },
      ],
    };
    const confirmedWorkspace = {
      ...generatedWorkspace,
      scenes: [
        {
          ...generatedWorkspace.scenes[0],
          shots: [
            {
              ...generatedWorkspace.scenes[0].shots[0],
              versions: [
                { ...generatedFinal, status: "confirmed_current" },
                confirmedDraft,
              ],
            },
          ],
        },
      ],
    };
    api.fetchVideoPackages.mockResolvedValue(generatedWorkspace);
    api.transitionVpBlock.mockResolvedValue(confirmedWorkspace);

    render(
      <MemoryRouter initialEntries={["/video-package"]}>
        <App />
      </MemoryRouter>,
    );

    const confirmButton = await screen.findByRole("button", {
      name: "确认本场全部成片提示词",
    });
    expect(
      screen.queryByRole("link", { name: "去批量视频" }),
    ).not.toBeInTheDocument();
    fireEvent.click(confirmButton);
    await acceptWorkbenchConfirm("确认本场成片提示词", "确认全部提示词");
    await waitFor(() =>
      expect(api.transitionVpBlock).toHaveBeenCalledWith(
        "vp-final-1",
        "confirm",
      ),
    );
    expect(
      await screen.findByRole("link", { name: "去批量视频" }),
    ).toHaveAttribute("href", "/batch-video");
  });

  it("检测到全场统一 5 秒旧版本时先按主规则重建时长", async () => {
    seedProject();
    const durations = [8, 10, 12];
    api.fetchVideoPackages.mockResolvedValue({
      ...videoPackages,
      scenes: [
        {
          ...videoPackages.scenes[0],
          shots: durations.map((duration, index) => ({
            id: `shot-${index + 1}`,
            shot_code: `SH00${index + 1}`,
            name:
              index === 2
                ? "快速蒙太奇穿越泥坑并切换多个动作节点"
                : `镜头任务 ${index + 1}`,
            recommended_duration_seconds: duration,
            duration_reason: `按镜头密度建议 ${duration} 秒`,
            confirmed_storyboard_vp_basis_block_id: `vp-draft-${index + 1}`,
            versions: [
              {
                id: `vp-final-${index + 1}`,
                shot_id: `shot-${index + 1}`,
                version_number: 2,
                schema_version: "vp_precision_18_v1",
                package_stage: "final_execution",
                status: "confirmed_current",
                duration_seconds: 5,
                basis_vp_block_id: `vp-draft-${index + 1}`,
                precision_items: [],
                prompt_copy: "旧版成片提示词",
                validation_items: [],
                meaning_chain: {},
              },
              {
                id: `vp-draft-${index + 1}`,
                shot_id: `shot-${index + 1}`,
                version_number: 1,
                schema_version: "vp_precision_18_v1",
                package_stage: "director_draft",
                status: "confirmed_current",
                duration_seconds: 5,
                precision_items: [],
                prompt_copy: "旧版故事板提示词",
                validation_items: [],
                meaning_chain: {},
              },
            ],
          })),
        },
      ],
    });

    render(
      <MemoryRouter initialEntries={["/video-package"]}>
        <App />
      </MemoryRouter>,
    );

    expect(
      await screen.findByText("修正全场统一 5 秒的旧版时间轴"),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "按主规则重建本场时长" }),
    ).toBeInTheDocument();
    expect(screen.getByText(/主规则建议：8 秒/)).toBeInTheDocument();
    expect(screen.getByText(/主规则建议：10 秒/)).toBeInTheDocument();
    expect(screen.getByText(/主规则建议：12 秒/)).toBeInTheDocument();
    expect(
      screen.queryByRole("link", { name: "去批量视频" }),
    ).not.toBeInTheDocument();
  });

  it("部分镜头已修正时只重建剩余旧版 5 秒镜头，不再与批量视频循环跳转", async () => {
    seedProject();
    const shots = Array.from({ length: 14 }, (_, index) => {
      const shotNumber = index + 1;
      const shotCode = `SH${String(shotNumber).padStart(3, "0")}`;
      const recommended = shotNumber === 1 ? 8 : shotNumber % 3 === 0 ? 12 : 8;
      const currentDuration = shotNumber === 1 ? 8 : 5;
      return {
        id: `shot-${shotNumber}`,
        shot_code: shotCode,
        name: `镜头任务 ${shotNumber}`,
        recommended_duration_seconds: recommended,
        duration_reason: `按镜头密度建议 ${recommended} 秒`,
        confirmed_storyboard_vp_basis_block_id: `vp-draft-${shotNumber}`,
        versions: [
          {
            id: `vp-final-${shotNumber}`,
            shot_id: `shot-${shotNumber}`,
            version_number: 2,
            schema_version: "vp_precision_18_v1",
            package_stage: "final_execution",
            status: "confirmed_current",
            duration_seconds: currentDuration,
            basis_vp_block_id: `vp-draft-${shotNumber}`,
            precision_items: [],
            prompt_copy: "旧版成片提示词",
            validation_items: [],
            meaning_chain: {},
          },
          {
            id: `vp-draft-${shotNumber}`,
            shot_id: `shot-${shotNumber}`,
            version_number: 1,
            schema_version: "vp_precision_18_v1",
            package_stage: "director_draft",
            status: "confirmed_current",
            duration_seconds: currentDuration,
            precision_items: [],
            prompt_copy: "故事板提示词",
            validation_items: [],
            meaning_chain: {},
          },
        ],
      };
    });
    const partialLegacyWorkspace = {
      ...videoPackages,
      scenes: [{ ...videoPackages.scenes[0], shots }],
    };
    api.fetchVideoPackages.mockResolvedValue(partialLegacyWorkspace);
    const queuedJob = {
      id: "vp-job-13",
      project_id: project.id,
      scene_id: "scene-1",
      operation: "duration_rebuild",
      status: "queued",
      total_count: 13,
      completed_count: 0,
      failed_count: 0,
      current_shot_code: "",
      message: "等待后台重建 13 个镜头",
      error_message: "",
      created_at: "2026-08-05T00:00:00Z",
      updated_at: "2026-08-05T00:00:00Z",
    };
    api.startVpDurationRebuild.mockResolvedValue(queuedJob);
    api.cancelVpGenerationJob.mockResolvedValue({
      ...queuedJob,
      status: "cancelled",
      message: "已停止后续重建，保留已完成的 0/13 个镜头",
    });
    api.fetchLatestVpGenerationJob
      .mockResolvedValueOnce(null)
      .mockResolvedValue(queuedJob);

    render(
      <MemoryRouter initialEntries={["/video-package"]}>
        <App />
      </MemoryRouter>,
    );

    expect(
      await screen.findByText("修正剩余 13 个旧版 5 秒镜头"),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("link", { name: "去批量视频" }),
    ).not.toBeInTheDocument();
    fireEvent.click(
      screen.getByRole("button", { name: "按主规则重建本场时长" }),
    );
    await acceptWorkbenchConfirm(
      "确认按镜头节奏重建分镜提示词",
      "确认重建时长",
    );

    await waitFor(() =>
      expect(api.startVpDurationRebuild).toHaveBeenCalledWith("scene-1"),
    );
    expect(api.generateAiVpBlock).not.toHaveBeenCalled();
    expect(await screen.findByText("后台重建中：0/13")).toBeInTheDocument();
    expect(screen.getByText("等待后台重建 13 个镜头")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "停止后续重建" }));
    await acceptWorkbenchConfirm("停止后台时长重建？", "停止后续重建");
    await waitFor(() =>
      expect(api.cancelVpGenerationJob).toHaveBeenCalledWith("vp-job-13"),
    );
    expect(
      await screen.findByText("后台重建已停止：剩余 13 个镜头"),
    ).toBeInTheDocument();

    fireEvent.click(screen.getByRole("link", { name: /成本与设置/ }));
    await screen.findByRole("heading", { name: "AI 服务设置" });
    fireEvent.click(screen.getByRole("link", { name: /故事板提示词/ }));

    expect(await screen.findByText("后台重建中：0/13")).toBeInTheDocument();
    expect(
      api.fetchLatestVpGenerationJob.mock.calls.length,
    ).toBeGreaterThanOrEqual(2);
  });

  it.skip("批量视频缺少已确认执行包时先在当前页同步条件，避免页面循环", async () => {
    seedProject();
    api.fetchBatchVideo.mockResolvedValue({
      ...huimengBatchWorkspace,
      jobs: [
        {
          ...huimengBatchWorkspace.jobs[0],
          tasks: [
            {
              ...huimengBatchWorkspace.jobs[0].tasks[0],
              status: "blocked",
              missing_items: ["缺少已确认的 VP-PRECISION-18 正式执行包。"],
            },
          ],
        },
      ],
    });
    api.fetchLiveReadiness.mockResolvedValue({
      ...liveReadiness,
      ready: false,
      gate_items: [
        {
          label: "视频包",
          passed: false,
          detail: "缺少已确认的 VP-PRECISION-18 正式执行包。",
        },
      ],
    });
    api.fetchJimengCliReadiness.mockResolvedValue({
      ...jimengCliReadiness,
      ready: false,
    });

    render(
      <MemoryRouter initialEntries={["/batch-video"]}>
        <App />
      </MemoryRouter>,
    );

    fireEvent.click(
      await screen.findByRole("button", { name: "重新检查当前条件" }),
    );
    await waitFor(() =>
      expect(api.refreshBatchTaskPreflight).toHaveBeenCalledWith("task-1"),
    );
  });

  it.skip("服务时长校验串线时在批量页原地重算，不再跳回提示词页", async () => {
    seedProject();
    api.fetchBatchVideo.mockResolvedValue({
      ...huimengBatchWorkspace,
      jobs: [
        {
          ...huimengBatchWorkspace.jobs[0],
          submission_channel: "jimeng",
          tasks: [
            {
              ...huimengBatchWorkspace.jobs[0].tasks[0],
              status: "blocked",
              canonical_request: { duration_seconds: 8, resolution: "720p" },
              missing_items: ["Seedance 单条视频必须在 1-15 秒内。"],
            },
          ],
        },
      ],
    });
    api.fetchLocalEnvStatus.mockResolvedValue({
      ...localEnvStatus,
      video_provider_mode: "jimeng_cli",
    });

    render(
      <MemoryRouter initialEntries={["/batch-video"]}>
        <App />
      </MemoryRouter>,
    );

    expect(
      await screen.findByText("重新按当前视频服务校验"),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("link", { name: "去处理这个缺项" }),
    ).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "按当前服务重新校验" }));
    await waitFor(() =>
      expect(api.refreshBatchTaskPreflight).toHaveBeenCalledWith("task-1"),
    );
  });

  it.skip("即梦全能参考绑定可在批量页手动替换并保存", async () => {
    seedProject();
    api.fetchBatchVideo.mockResolvedValue(huimengBatchWorkspace);
    api.fetchLocalEnvStatus.mockResolvedValue({
      ...localEnvStatus,
      video_provider_mode: "jimeng_cli",
    });
    api.fetchJimengCliReadiness.mockResolvedValue({
      ...jimengCliReadiness,
      reference_bindings: [
        {
          token: "@图片1",
          asset_id: "sb-1",
          asset_type: "storyboard",
          role: "storyboard",
          label: "当前故事板",
          purpose: "参考构图",
          asset_url: "/sb.png",
        },
      ],
      reference_candidates: [
        {
          asset_id: "sb-1",
          asset_type: "storyboard",
          role: "storyboard",
          label: "当前故事板",
          asset_url: "/sb.png",
        },
        {
          asset_id: "scene-2",
          asset_type: "scene",
          role: "environment",
          label: "替换场景图",
          asset_url: "/scene.png",
        },
      ],
    });

    render(
      <MemoryRouter initialEntries={["/batch-video"]}>
        <App />
      </MemoryRouter>,
    );

    fireEvent.click(await screen.findByText(/核对或替换全能参考绑定/));
    fireEvent.click(screen.getByRole("button", { name: "修改绑定" }));
    fireEvent.change(screen.getByLabelText("@图片1 参考图"), {
      target: { value: "scene-2" },
    });
    fireEvent.click(screen.getByRole("button", { name: "保存参考图绑定" }));
    await waitFor(() =>
      expect(api.updateVideoReferenceBindings).toHaveBeenCalledWith("task-1", [
        "scene-2",
      ]),
    );
  });

  it.skip("从批量视频返回分镜页后再次进入会同步新版时长，不再页面循环", async () => {
    seedProject();
    const oldBatch = {
      ...huimengBatchWorkspace,
      jobs: [
        {
          ...huimengBatchWorkspace.jobs[0],
          tasks: [
            {
              ...huimengBatchWorkspace.jobs[0].tasks[0],
              updated_at: "2026-07-30T09:20:00Z",
              canonical_request: { duration_seconds: 5, resolution: "720p" },
            },
          ],
        },
      ],
    };
    const refreshedBatch = {
      ...oldBatch,
      jobs: [
        {
          ...oldBatch.jobs[0],
          total_seconds: 8,
          tasks: [
            {
              ...oldBatch.jobs[0].tasks[0],
              updated_at: "2026-07-30T09:42:00Z",
              canonical_request: { duration_seconds: 8, resolution: "720p" },
            },
          ],
        },
      ],
    };
    api.fetchBatchVideo
      .mockResolvedValueOnce(oldBatch)
      .mockResolvedValue(refreshedBatch);
    api.fetchLiveReadiness
      .mockResolvedValueOnce({
        ...liveReadiness,
        ready: false,
        gate_items: [
          {
            label: "镜头时长规划",
            passed: false,
            detail: "SH001 仍使用旧版统一 5 秒默认值；主规则建议 8 秒。",
          },
        ],
      })
      .mockResolvedValue(liveReadiness);
    api.fetchVideoPackages.mockResolvedValue({
      ...videoPackages,
      scenes: videoPackages.scenes.map((scene) => ({
        ...scene,
        shots: scene.shots.map((shot) => ({
          ...shot,
          recommended_duration_seconds: 8,
          confirmed_storyboard_vp_basis_block_id: "vp-draft-8",
          versions: [
            {
              id: "vp-final-8",
              shot_id: shot.id,
              version_number: 4,
              schema_version: "vp_precision_18_v1",
              package_stage: "final_execution",
              status: "confirmed_current",
              duration_seconds: 8,
              basis_vp_block_id: "vp-draft-8",
              precision_items: [],
              prompt_copy: "8 秒正式执行提示词",
              validation_items: [],
              meaning_chain: {},
            },
            {
              id: "vp-draft-8",
              shot_id: shot.id,
              version_number: 3,
              schema_version: "vp_precision_18_v1",
              package_stage: "director_draft",
              status: "draft",
              duration_seconds: 8,
              precision_items: [],
              prompt_copy: "8 秒故事板提示词",
              validation_items: [],
              meaning_chain: {},
            },
          ],
        })),
      })),
    });

    render(
      <MemoryRouter initialEntries={["/batch-video"]}>
        <App />
      </MemoryRouter>,
    );

    fireEvent.click(
      await screen.findByRole("link", { name: "去重建镜头时长" }),
    );
    fireEvent.click(await screen.findByRole("link", { name: "去批量视频" }));

    await waitFor(() => expect(api.fetchBatchVideo).toHaveBeenCalledTimes(2));
    await waitFor(() =>
      expect(
        screen.queryByText("先处理：镜头时长规划"),
      ).not.toBeInTheDocument(),
    );
    expect(
      screen.queryByRole("link", { name: "去重建镜头时长" }),
    ).not.toBeInTheDocument();
  });

  it("完整生产缺资产时只显示一个切换无参考图路线入口", async () => {
    seedProject();
    api.fetchVideoPackages.mockResolvedValue({
      ...videoPackages,
      scenes: videoPackages.scenes.map((scene) => ({
        ...scene,
        shots: scene.shots.map((shot) => ({
          ...shot,
          versions: [
            {
              id: "vp-draft-1",
              shot_id: shot.id,
              version_number: 1,
              schema_version: "vp_precision_18_v1",
              package_stage: "director_draft",
              status: "confirmed_current",
              precision_items: [],
              prompt_copy: "故事板参考提示词",
              validation_items: [],
              meaning_chain: {},
            },
          ],
        })),
      })),
    });

    render(
      <MemoryRouter initialEntries={["/video-package"]}>
        <App />
      </MemoryRouter>,
    );

    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: "生成资产绑定版成片提示词" }),
      ).toBeInTheDocument(),
    );
    const switchButtons = screen.getAllByRole("button", {
      name: "不做资产，改用无参考图提示词",
    });
    expect(switchButtons).toHaveLength(1);
    fireEvent.click(switchButtons[0]);
    await waitFor(() =>
      expect(api.updateProjectCreativeGoal).toHaveBeenCalledWith(
        project.id,
        "prompt_storyboard",
      ),
    );
  });

  it.skip("批量视频页将未知费用显示为风险确认，不把它显示成零预算", async () => {
    seedProject();
    render(
      <MemoryRouter initialEntries={["/batch-video"]}>
        <App />
      </MemoryRouter>,
    );
    await waitFor(() =>
      expect(screen.getByText("生成视频")).toBeInTheDocument(),
    );
    expect(
      await screen.findByRole("button", { name: "确认费用风险" }),
    ).toBeInTheDocument();
    expect(screen.getByText(/未知费用不代表 0 或免费/)).toBeInTheDocument();
    fireEvent.click(screen.getByText("可选：查看任务状态"));
    expect(screen.getByText(/费用信息：1 镜头｜5 秒/)).toBeInTheDocument();
    expect(screen.getByText(/无法可靠估价，请人工核对/)).toBeInTheDocument();
    expect(
      screen.queryByText(/预计费用 0|预计 0 CREDITS/),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "提交应急演练" }),
    ).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "查看发送前预览" }));
    await waitFor(() =>
      expect(
        screen.getByText("已生成发送前预览，未发送网络请求"),
      ).toBeInTheDocument(),
    );
    expect(
      screen.queryByText("脱敏请求映射预览｜未发送网络请求"),
    ).not.toBeInTheDocument();
  });

  it("批量视频页不再显示旧开发队列迁移入口", async () => {
    seedProject();
    api.fetchBatchVideo.mockResolvedValue({
      ...batchWorkspace,
      providers: [huimengProvider],
    });
    api.remapBatchVideoProvider.mockResolvedValue({
      ...batchWorkspace,
      providers: [huimengProvider],
    });
    render(
      <MemoryRouter initialEntries={["/batch-video"]}>
        <App />
      </MemoryRouter>,
    );
    await waitFor(() =>
      expect(screen.getByText("生成视频")).toBeInTheDocument(),
    );
    expect(
      screen.queryByText("当前是旧开发队列，不适合正式测试"),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "切换成单镜队列" }),
    ).not.toBeInTheDocument();
    expect(api.remapBatchVideoProvider).not.toHaveBeenCalled();
  });

  it("成本与设置页只保留关键 API 与模型配置", async () => {
    render(
      <MemoryRouter initialEntries={["/settings"]}>
        <App />
      </MemoryRouter>,
    );
    await waitFor(() =>
      expect(screen.getByText("AI 服务设置")).toBeInTheDocument(),
    );
    expect(
      screen.getByText("慧梦 / 绘梦配置（生图与视频）"),
    ).toBeInTheDocument();
    expect(screen.getByText("AI 分析主脑（文字）")).toBeInTheDocument();
    expect(screen.getByText("OpenAI 官方配置（可选）")).toBeInTheDocument();
    expect(screen.getByText("安全原则")).toBeInTheDocument();
    expect(screen.getByText("系统规则")).toBeInTheDocument();
    expect(screen.getByText("AI 分析")).toBeInTheDocument();
    expect(screen.getByText("图像 / 视频")).toBeInTheDocument();
    expect(screen.queryByText("真实单镜验收向导")).not.toBeInTheDocument();
    expect(screen.queryByText("真实文本大脑试跑")).not.toBeInTheDocument();
    expect(screen.queryByText(/规则指纹/)).not.toBeInTheDocument();
    expect(screen.queryByText(/tokens/)).not.toBeInTheDocument();
    expect(api.runTextProviderSmokeTest).not.toHaveBeenCalled();
    expect(screen.getByDisplayValue("gpt-5.5")).toBeInTheDocument();
    expect(screen.getByDisplayValue("image-2")).toBeInTheDocument();
    expect(screen.queryByText("视频服务通道管理")).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "载入 Atlas Cloud 禁用模板" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "演练响应映射" }),
    ).not.toBeInTheDocument();
    expect(screen.queryByText(/Seedance 应急状态演练/)).not.toBeInTheDocument();
  });

  it("成本与设置页支持写入本地 .env 且不回显密钥", async () => {
    render(
      <MemoryRouter initialEntries={["/settings"]}>
        <App />
      </MemoryRouter>,
    );
    await waitFor(() =>
      expect(screen.getByText("AI 服务设置")).toBeInTheDocument(),
    );
    expect(
      screen.queryByDisplayValue("sk-existing-secret"),
    ).not.toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("慧梦 API Key"), {
      target: { value: "hm-test-secret" },
    });
    fireEvent.change(screen.getByLabelText("视频模型"), {
      target: { value: "seedance-2.0-fast" },
    });
    fireEvent.click(screen.getByLabelText("允许真实单镜视频（仍需逐次确认）"));
    fireEvent.click(screen.getByRole("button", { name: "保存设置" }));
    await waitFor(() =>
      expect(api.updateLocalEnv).toHaveBeenCalledWith(
        expect.objectContaining({
          confirm_local_env_write: true,
          huimengi_api_key: "hm-test-secret",
          text_model: "gpt-5.5",
          huimengi_image_model: "image-2",
          huimengi_video_model: "seedance-2.0-fast",
          huimengi_model_id: "seedance-2.0-fast",
          enable_real_seedance: true,
          video_provider_mode: "huimeng_live",
        }),
      ),
    );
    await waitFor(() =>
      expect(screen.getByText(/已保存到本机 \.env/)).toBeInTheDocument(),
    );
    expect(
      screen.queryByDisplayValue("hm-test-secret"),
    ).not.toBeInTheDocument();
  });

  it("设置页可切换文字主脑服务并自动填入服务地址", async () => {
    render(
      <MemoryRouter initialEntries={["/settings"]}>
        <App />
      </MemoryRouter>,
    );
    await waitFor(() =>
      expect(screen.getByText("AI 分析主脑（文字）")).toBeInTheDocument(),
    );
    expect(
      screen.getByDisplayValue("https://api.huimengi.com/v1"),
    ).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("文字服务"), {
      target: { value: "kimi" },
    });
    expect(
      screen.getByDisplayValue("https://api.moonshot.cn/v1"),
    ).toBeInTheDocument();
    expect(
      screen.getByDisplayValue("kimi-k2-0905-preview"),
    ).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("文字服务"), {
      target: { value: "deepseek" },
    });
    expect(
      screen.getByDisplayValue("https://api.deepseek.com/v1"),
    ).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("文字服务 API Key"), {
      target: { value: "sk-kimi-secret" },
    });
    fireEvent.click(screen.getByRole("button", { name: "保存设置" }));
    await waitFor(() =>
      expect(api.updateLocalEnv).toHaveBeenCalledWith(
        expect.objectContaining({
          confirm_local_env_write: true,
          text_api_key: "sk-kimi-secret",
          text_base_url: "https://api.deepseek.com/v1",
          text_model: "deepseek-chat",
        }),
      ),
    );
    expect(
      screen.queryByDisplayValue("sk-kimi-secret"),
    ).not.toBeInTheDocument();
  });

  it("设置页可切换生图服务为即时 API 并保存独立配置", async () => {
    render(
      <MemoryRouter initialEntries={["/settings"]}>
        <App />
      </MemoryRouter>,
    );
    await waitFor(() =>
      expect(screen.getByText("AI 服务设置")).toBeInTheDocument(),
    );
    expect(screen.getByDisplayValue("image-2")).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("生图服务"), {
      target: { value: "openai_images" },
    });
    expect(screen.queryByDisplayValue("image-2")).not.toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("生图 Base URL（即时 API）"), {
      target: { value: "https://api.openai.com/v1" },
    });
    fireEvent.change(screen.getByLabelText("生图模型（即时 API）"), {
      target: { value: "gpt-image-1" },
    });
    fireEvent.change(screen.getByLabelText("生图 API Key（即时 API 专用）"), {
      target: { value: "sk-image-secret" },
    });
    fireEvent.click(screen.getByRole("button", { name: "保存设置" }));
    await waitFor(() =>
      expect(api.updateLocalEnv).toHaveBeenCalledWith(
        expect.objectContaining({
          image_provider_mode: "openai_images",
          image_api_key: "sk-image-secret",
          image_base_url: "https://api.openai.com/v1",
          image_model: "gpt-image-1",
        }),
      ),
    );
    expect(
      screen.queryByDisplayValue("sk-image-secret"),
    ).not.toBeInTheDocument();
  });

  it("设置页可切换视频服务为即梦 CLI 并隐藏慧梦视频字段", async () => {
    render(
      <MemoryRouter initialEntries={["/settings"]}>
        <App />
      </MemoryRouter>,
    );
    await waitFor(() =>
      expect(screen.getByText("AI 服务设置")).toBeInTheDocument(),
    );
    expect(screen.getByLabelText("视频模型")).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("视频服务"), {
      target: { value: "jimeng_cli" },
    });
    expect(screen.queryByLabelText("视频模型")).not.toBeInTheDocument();
    expect(
      screen.getByText(/即梦 CLI 通道使用你电脑上已安装并登录的 dreamina 命令/),
    ).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "保存设置" }));
    await waitFor(() =>
      expect(api.updateLocalEnv).toHaveBeenCalledWith(
        expect.objectContaining({
          video_provider_mode: "jimeng_cli",
        }),
      ),
    );
  });

  it("设置页可将 Seedance 2.5 Mock 设为新队列默认服务", async () => {
    render(
      <MemoryRouter initialEntries={["/settings"]}>
        <App />
      </MemoryRouter>,
    );
    await waitFor(() =>
      expect(screen.getByText("AI 服务设置")).toBeInTheDocument(),
    );

    fireEvent.change(screen.getByLabelText("视频服务"), {
      target: { value: "volcengine_seedance25" },
    });
    expect(screen.queryByLabelText("视频模型")).not.toBeInTheDocument();
    expect(
      screen.getByText(/首期只运行 Seedance 2.5 本地 Mock/),
    ).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "保存设置" }));
    await waitFor(() =>
      expect(api.updateLocalEnv).toHaveBeenCalledWith(
        expect.objectContaining({
          video_provider_mode: "volcengine_seedance25",
        }),
      ),
    );
  });

  it("成本与设置页不再展示试跑证据和工程细节", async () => {
    render(
      <MemoryRouter initialEntries={["/settings"]}>
        <App />
      </MemoryRouter>,
    );
    await waitFor(() =>
      expect(screen.getByText("AI 服务设置")).toBeInTheDocument(),
    );
    expect(
      screen.queryByRole("button", { name: "真实试跑一次" }),
    ).not.toBeInTheDocument();
    expect(screen.queryByText("真实模型结果")).not.toBeInTheDocument();
    expect(screen.queryByText("完整系统文件")).not.toBeInTheDocument();
    expect(screen.queryByText("调用与费用线索")).not.toBeInTheDocument();
    expect(api.runTextProviderSmokeTest).not.toHaveBeenCalled();
  });

  it("成本与设置页在文本 Key 缺失时只显示简洁待配置状态", async () => {
    api.fetchTextProviderStatus.mockResolvedValue({
      ...textProviderStatus,
      ready: false,
      huimengi_api_key_configured: false,
      blocking_reason: "请配置慧梦 Key 与文本模型。",
    });
    render(
      <MemoryRouter initialEntries={["/settings"]}>
        <App />
      </MemoryRouter>,
    );
    await waitFor(() =>
      expect(screen.getByText("AI 服务设置")).toBeInTheDocument(),
    );
    expect(screen.getByText("请配置慧梦 Key 与文本模型。")).toBeInTheDocument();
    expect(screen.queryByText("缺少｜慧梦 API Key")).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "真实试跑一次" }),
    ).not.toBeInTheDocument();
  });

  it.skip("批量视频页对慧梦服务通道显示真实单镜操作", async () => {
    seedProject();
    api.fetchBatchVideo.mockResolvedValue(huimengBatchWorkspace);
    render(
      <MemoryRouter initialEntries={["/batch-video"]}>
        <App />
      </MemoryRouter>,
    );
    await waitFor(() =>
      expect(screen.getByText("生成视频")).toBeInTheDocument(),
    );
    await waitFor(() =>
      expect(screen.getByText("慧梦 API提交条件")).toBeInTheDocument(),
    );
    expect(screen.getByText(/单镜 \/ 1-15 秒 \/ 720p/)).toBeInTheDocument();
    expect(await screen.findByText("技术条件已通过")).toBeInTheDocument();
    await waitFor(() =>
      expect(screen.getByText(/慧梦 API 条件已通过/)).toBeInTheDocument(),
    );
    fireEvent.click(screen.getByRole("button", { name: "提交这个镜头" }));
    await acceptWorkbenchConfirm("确认提交真实视频", "确认提交");
    await waitFor(() =>
      expect(api.submitLiveVideoTask).toHaveBeenCalledWith("task-1"),
    );
  });

  it.skip("批量视频页选择即梦路线时不再被慧梦服务模式阻塞", async () => {
    seedProject();
    api.fetchBatchVideo.mockResolvedValue(batchWorkspace);
    api.fetchLocalEnvStatus.mockResolvedValue({
      ...localEnvStatus,
      video_provider_mode: "jimeng_cli",
    });
    api.fetchJimengCliStatus.mockResolvedValue({
      ...jimengCliStatus,
      installed: true,
      logged_in: true,
      ready: true,
    });
    api.fetchJimengCliReadiness.mockResolvedValue({
      ...jimengCliReadiness,
      ready: false,
      gate_items: [
        { label: "即梦 CLI", passed: true, detail: "已安装 dreamina" },
        { label: "即梦账号", passed: true, detail: "已登录" },
        { label: "预算确认", passed: false, detail: "请先确认费用风险" },
        { label: "任务状态", passed: false, detail: "等待费用确认" },
      ],
    });

    render(
      <MemoryRouter initialEntries={["/batch-video"]}>
        <App />
      </MemoryRouter>,
    );

    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: "即梦 CLI（已就绪）" }),
      ).toHaveClass("bg-cyan-400"),
    );
    expect(screen.getByText("即梦 CLI提交条件")).toBeInTheDocument();
    expect(await screen.findByText("技术条件已通过")).toBeInTheDocument();
    expect(
      await screen.findByText(
        /“预算确认、任务状态”会在完成上方条件和费用确认后自动解除/,
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "确认费用风险" }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("link", { name: "去补齐条件" }),
    ).not.toBeInTheDocument();
  });

  it.skip("即梦提交前可以选择模型并重新触发费用确认", async () => {
    seedProject();
    api.fetchBatchVideo.mockResolvedValue(huimengBatchWorkspace);
    api.fetchLocalEnvStatus.mockResolvedValue({
      ...localEnvStatus,
      video_provider_mode: "jimeng_cli",
    });
    api.fetchJimengCliStatus.mockResolvedValue({
      ...jimengCliStatus,
      installed: true,
      logged_in: true,
      ready: true,
    });
    api.fetchJimengCliReadiness.mockResolvedValue({
      ...jimengCliReadiness,
      ready: true,
      model_id: "seedance2.0_vip",
      gate_items: jimengCliReadiness.gate_items.map((item) => ({
        ...item,
        passed: true,
      })),
    });

    render(
      <MemoryRouter initialEntries={["/batch-video"]}>
        <App />
      </MemoryRouter>,
    );

    const picker = await screen.findByLabelText("本次即梦视频模型");
    expect(picker).toHaveValue("seedance2.0_vip");
    expect(picker).toBeEnabled();
    expect(
      screen.getByRole("option", { name: "即梦 Seedance 2.0 VIP（默认）" }),
    ).toBeInTheDocument();
    expect(
      screen.getByText("提交前可手动选择模型；切换后需要重新确认费用风险。"),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/准确积分由即梦按模型、时长、分辨率和参考素材实时计算/),
    ).toBeInTheDocument();
    fireEvent.change(picker, { target: { value: "seedance2.0mini" } });
    await waitFor(() =>
      expect(api.updateJimengCliModel).toHaveBeenCalledWith(
        "task-1",
        "seedance2.0mini",
      ),
    );
  });

  it.skip("批量视频页选择慧梦路线后可原页修复视频服务模式", async () => {
    seedProject();
    api.fetchBatchVideo.mockResolvedValue(batchWorkspace);
    api.fetchLocalEnvStatus.mockResolvedValue({
      ...localEnvStatus,
      video_provider_mode: "jimeng_cli",
    });
    api.fetchLiveReadiness.mockResolvedValue({
      ...liveReadiness,
      ready: false,
      gate_items: [
        {
          label: "视频服务模式",
          passed: false,
          detail: "当前 VIDEO_PROVIDER_MODE=jimeng_cli",
        },
        { label: "预算确认", passed: false, detail: "等待费用确认" },
      ],
    });

    render(
      <MemoryRouter initialEntries={["/batch-video"]}>
        <App />
      </MemoryRouter>,
    );
    fireEvent.click(await screen.findByRole("button", { name: "慧梦 API" }));

    expect(
      await screen.findByText("必须处理｜视频服务模式"),
    ).toBeInTheDocument();
    expect(screen.getAllByText(/改用即梦 CLI 时可忽略/).length).toBeGreaterThan(
      0,
    );
    fireEvent.click(
      screen.getAllByRole("button", { name: "切换到慧梦 API 模式" })[0],
    );
    await waitFor(() =>
      expect(api.updateLocalEnv).toHaveBeenCalledWith({
        confirm_local_env_write: true,
        video_provider_mode: "huimeng_live",
      }),
    );
  });

  it("批量视频页可独立于设置页切换本次队列服务", async () => {
    seedProject();
    const jimengQueue = {
      ...batchWorkspace,
      providers: [genericProvider, huimengProvider],
      jobs: [
        {
          ...batchWorkspace.jobs[0],
          provider_profile_id: genericProvider.id,
          provider_name: genericProvider.display_name,
          submission_channel: "jimeng" as const,
        },
      ],
    };
    const huimengQueue = {
      ...jimengQueue,
      jobs: [
        {
          ...jimengQueue.jobs[0],
          provider_profile_id: huimengProvider.id,
          provider_name: huimengProvider.display_name,
          submission_channel: "huimeng" as const,
        },
      ],
    };
    api.fetchBatchVideo.mockResolvedValue(jimengQueue);
    api.fetchLocalEnvStatus.mockResolvedValue({
      ...localEnvStatus,
      video_provider_mode: "jimeng_cli",
    });
    api.updateBatchVideoSubmissionChannel.mockResolvedValue(huimengQueue);

    render(
      <MemoryRouter initialEntries={["/batch-video"]}>
        <App />
      </MemoryRouter>,
    );

    expect(await screen.findByRole("button", { name: "即梦 CLI" })).toHaveClass(
      "bg-cyan-400",
    );
    expect(screen.getByText(/设置页只决定新队列默认值/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "慧梦 API" }));
    await waitFor(() =>
      expect(api.updateBatchVideoSubmissionChannel).toHaveBeenCalledWith(
        "job-1",
        "huimeng",
        "huimeng_live",
      ),
    );
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "慧梦 API" })).toHaveClass(
        "bg-orange-500",
      ),
    );
  });

  it.skip("批量视频页面只读取后台状态，切换页面不会由浏览器驱动服务商任务", async () => {
    seedProject();
    const submittedWorkspace = {
      ...huimengBatchWorkspace,
      jobs: [
        {
          ...huimengBatchWorkspace.jobs[0],
          tasks: [
            {
              ...huimengBatchWorkspace.jobs[0].tasks[0],
              status: "submitted",
              progress_percent: 25,
              progress_label: "已进入服务商队列",
              external_task_id: "hm-task-001",
              external_provider: "huimeng_live",
            },
          ],
        },
      ],
    };
    const importedWorkspace = {
      ...huimengBatchWorkspace,
      jobs: [
        {
          ...huimengBatchWorkspace.jobs[0],
          tasks: [
            {
              ...huimengBatchWorkspace.jobs[0].tasks[0],
              status: "imported",
              progress_percent: 100,
              progress_label: "本地保存完成",
              storage_status: "local",
              external_task_id: "hm-task-001",
              external_provider: "huimeng_live",
              result_video_path: "07_results/generated_videos/demo.mp4",
              local_file_path:
                "/tmp/projects/PRJ001/07_results/generated_videos/demo.mp4",
              results: [
                {
                  id: "result-1",
                  version_number: 1,
                  source: "huimeng_live",
                  status: "imported",
                  video_url:
                    "/api/projects/PRJ001/assets/07_results/generated_videos/demo.mp4",
                },
              ],
            },
          ],
        },
      ],
    };
    api.fetchBatchVideo
      .mockResolvedValueOnce(submittedWorkspace)
      .mockResolvedValue(importedWorkspace);
    render(
      <MemoryRouter initialEntries={["/batch-video"]}>
        <App />
      </MemoryRouter>,
    );

    expect(await screen.findByText("视频生成监控")).toBeInTheDocument();
    expect(screen.getByText("已进入服务商队列")).toBeInTheDocument();
    expect(
      screen.getByText("后台监控中：每 5 秒同步服务状态，无需停留在本页"),
    ).toBeInTheDocument();
    expect(
      screen.getByText("服务商未提供可验证的生成百分比"),
    ).toBeInTheDocument();
    expect(
      screen.getByText("系统只展示服务商真实阶段，不用固定百分比模拟进度。"),
    ).toBeInTheDocument();
    fireEvent.click(screen.getByRole("link", { name: /^开始 / }));
    await waitFor(() =>
      expect(screen.getAllByText("当前主任务").length).toBeGreaterThan(0),
    );
    expect(api.pollLiveVideoTask).not.toHaveBeenCalled();
    expect(api.downloadLiveVideoTask).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("link", { name: /^批量视频 / }));
    expect((await screen.findAllByText("本地保存完成")).length).toBeGreaterThan(
      0,
    );
    expect(
      screen.getAllByText(
        "/tmp/projects/PRJ001/07_results/generated_videos/demo.mp4",
      ).length,
    ).toBeGreaterThan(0);
    expect(
      screen.getByRole("link", { name: "下载本地视频" }),
    ).toBeInTheDocument();
    expect(screen.getByLabelText("SH001 视频预览")).toHaveAttribute(
      "src",
      expect.stringContaining(
        "/api/projects/PRJ001/assets/07_results/generated_videos/demo.mp4",
      ),
    );
    expect(screen.getByText("正在播放项目本地副本。")).toBeInTheDocument();
    expect(screen.getByText("请先预览并验收 SH001")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "去预览并验收" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "通过并继续下一镜" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "这个视频需要重做" }),
    ).toBeInTheDocument();
    expect(
      screen.queryByText("请使用上方主任务按钮处理"),
    ).not.toBeInTheDocument();
    expect(screen.queryByText("慧梦 API提交条件")).not.toBeInTheDocument();
  });

  it.skip("批量视频失败时说明原因、成片影响和修正入口", async () => {
    seedProject();
    api.fetchBatchVideo.mockResolvedValue({
      ...huimengBatchWorkspace,
      jobs: [
        {
          ...huimengBatchWorkspace.jobs[0],
          tasks: [
            {
              ...huimengBatchWorkspace.jobs[0].tasks[0],
              status: "failed",
              progress_percent: 100,
              progress_label: "生成失败",
              storage_status: "failed",
              external_task_id: "hm-task-failed",
              external_provider: "huimeng_live",
              error_message: "content moderation policy rejected",
            },
          ],
        },
      ],
    });

    render(
      <MemoryRouter initialEntries={["/batch-video"]}>
        <App />
      </MemoryRouter>,
    );

    expect(await screen.findByText("生成失败")).toBeInTheDocument();
    expect(
      screen.getByText("提示词或参考素材未通过服务商内容审核。"),
    ).toBeInTheDocument();
    expect(
      screen.getAllByText(/当前版本无法生成，需要调整敏感描述或替换参考素材/)
        .length,
    ).toBeGreaterThan(0);
    expect(
      screen.getByRole("link", { name: "修改成片提示词" }),
    ).toHaveAttribute("href", "/video-package");
  });

  it.skip("即梦最终生成失败时明确说明已计费且不会自动重试", async () => {
    seedProject();
    api.fetchBatchVideo.mockResolvedValue({
      ...huimengBatchWorkspace,
      jobs: [
        {
          ...huimengBatchWorkspace.jobs[0],
          tasks: [
            {
              ...huimengBatchWorkspace.jobs[0].tasks[0],
              status: "failed",
              progress_percent: 100,
              progress_label: "生成失败",
              storage_status: "failed",
              external_task_id: "jm-task-failed",
              external_provider: "jimeng_cli",
              error_message: "generation failed: final generation failed",
            },
          ],
        },
      ],
    });

    render(
      <MemoryRouter initialEntries={["/batch-video"]}>
        <App />
      </MemoryRouter>,
    );

    expect(
      await screen.findByText(
        "即梦已接收并计费，但最终生成阶段失败；服务商没有返回更具体的失败原因。",
      ),
    ).toBeInTheDocument();
    expect(
      screen.getAllByText(/不要直接重复提交，否则可能再次扣除积分/).length,
    ).toBeGreaterThan(0);
  });

  it.skip("任务引用历史故事板时同时展示错误提交图和当前正式版", async () => {
    seedProject();
    api.fetchBatchVideo.mockResolvedValue({
      ...huimengBatchWorkspace,
      jobs: [
        {
          ...huimengBatchWorkspace.jobs[0],
          tasks: [
            {
              ...huimengBatchWorkspace.jobs[0].tasks[0],
              status: "failed",
              external_provider: "jimeng_cli",
              storyboard_url: "/local-assets/PRJ001/history.svg",
              current_storyboard_url: "/local-assets/PRJ001/current.png",
              storyboard_reference_status: "history",
              storyboard_reference_note:
                "本次实际提交的是历史故事板 history.svg；当前正式版为 current.png。",
            },
          ],
        },
      ],
    });

    render(
      <MemoryRouter initialEntries={["/batch-video"]}>
        <App />
      </MemoryRouter>,
    );

    expect(
      await screen.findByText("本次已提交参考（错误）"),
    ).toBeInTheDocument();
    expect(screen.getByText("当前正式故事板")).toBeInTheDocument();
    expect(screen.getByText(/本次实际提交的是历史故事板/)).toBeInTheDocument();
  });

  it("流程体检按阶段汇总问题，不再提供伪修正和重复摘要", async () => {
    seedProject();
    render(
      <MemoryRouter initialEntries={["/check-fix?tab=fix"]}>
        <App />
      </MemoryRouter>,
    );
    await waitFor(() =>
      expect(screen.getByText("检查当前场是否可以继续")).toBeInTheDocument(),
    );
    expect(screen.getByText("1 个阶段未完成 · 1 个检查项")).toBeInTheDocument();
    expect(screen.getByText("查看 1 个具体检查项")).toBeInTheDocument();
    expect(screen.queryByRole("checkbox")).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /确认修正并生成处理记录/ }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByText("可选：生成一段好读的体检说明"),
    ).not.toBeInTheDocument();
  });

  it("体检发现视频包阻塞时直接给出分镜提示词处理入口", async () => {
    seedProject();
    const videoPackageReview = {
      ...workflowReview,
      reports: [
        {
          ...workflowReview.reports[0],
          issues: [
            {
              ...workflowReview.reports[0].issues[0],
              category: "video_package",
              target_type: "vp_block",
              title: "SH001 缺少已确认视频包",
              detail: "请在故事板确认后生成 VP-Block。",
            },
          ],
        },
      ],
    };
    api.fetchWorkflowReview.mockResolvedValue(videoPackageReview);
    api.generateWorkflowReport.mockResolvedValue(videoPackageReview);

    render(
      <MemoryRouter initialEntries={["/check-fix?tab=check"]}>
        <App />
      </MemoryRouter>,
    );

    const action = await screen.findByRole("link", {
      name: "去生成成片提示词",
    });
    expect(action).toHaveAttribute("href", "/video-package");
    expect(
      screen.getByText("下一步：生成并确认当前场的成片提示词"),
    ).toBeInTheDocument();
  });

  it("旧流程定位链接也直接展示当前处理入口", async () => {
    seedProject();
    render(
      <MemoryRouter initialEntries={["/check-fix?tab=one-click"]}>
        <App />
      </MemoryRouter>,
    );
    expect(
      await screen.findByRole("link", { name: "去故事板处理" }),
    ).toHaveAttribute("href", "/storyboards");
    expect(
      screen.queryByRole("button", { name: "定位下一步" }),
    ).not.toBeInTheDocument();
  });

  it("检查页可直接打开统一检查页", async () => {
    seedProject();
    render(
      <MemoryRouter initialEntries={["/check-fix?tab=check"]}>
        <App />
      </MemoryRouter>,
    );
    await waitFor(() =>
      expect(screen.getByText("检查当前场是否可以继续")).toBeInTheDocument(),
    );
  });
});
