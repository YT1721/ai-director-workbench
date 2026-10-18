export type StoryboardStyleLock = {
  enabled: boolean;
  locked: boolean;
  style_name: string;
};

export type AxisPlan = {
  id: string;
  axis_code: string;
  axis_line_description: string;
  camera_safe_side: string;
  character_blocking: string;
  eyeline_direction: string;
  movement_direction: string;
  allow_cross_axis: boolean;
  cross_axis_transition: string;
};

export type StoryboardVersionDraft = {
  shot_size: string;
  camera_angle: string;
  camera_movement: string;
  action_start: string;
  emotion_state: string;
  sound_light: string;
  camera_point: string;
  screen_position: string;
  eyeline_direction: string;
  movement_direction: string;
  camera_side: string;
};

export type StoryboardVersion = StoryboardVersionDraft & {
  id: string;
  version_number: number;
  image_url: string;
  schema_version: string;
  vp_basis_block_id: string | null;
  storyboard_mode: string;
  density_level: "low" | "medium" | "high" | string;
  storyboard_grid: 3 | 4 | 6 | 9 | 12;
  grid_reason: string;
  annotation_layer: Record<string, unknown>;
  prompt_match: {
    grid_index: number;
    time_range: string;
    vp_item_5_node?: string;
  }[];
  timeline_nodes: { time_range: string; description: string }[];
  storyboard_cells: {
    cell_index: number;
    shot_id: string;
    prompt_time_range: string;
    action_note: string;
    camera_note: string;
    composition_note: string;
    meaning_chain_note: string;
    vfx_note: string;
    tail_frame_note: string;
  }[];
  unified_sb_meta: Record<string, unknown>;
  style_validation_status: "passed" | "failed";
  axis_validation_status: "passed" | "failed";
  axis_validation_notes: string;
  status: "draft" | "confirmed_current" | "locked" | "history";
  created_at: string;
  latest_image_job?: StoryboardImageJob | null;
};

export type StoryboardImageReadiness = {
  ready: boolean;
  provider_name: string;
  model_id: string;
  gate_items: { label: string; passed: boolean; detail: string }[];
  risk_notice: string;
  requires_user_confirmation: boolean;
};

export type StoryboardImageJob = {
  id: string;
  project_id: string;
  target_type: string;
  target_id: string;
  provider: string;
  model_name: string;
  external_task_id: string;
  status:
    | "submitted"
    | "processing"
    | "completed"
    | "failed"
    | "downloaded"
    | string;
  remote_result_url: string;
  image_url: string | null;
  prompt: string;
  error_message: string;
  created_at: string;
};

export type StoryboardShot = {
  id: string;
  shot_code: string;
  name: string;
  latest_vp_draft_id?: string | null;
  versions: StoryboardVersion[];
  reuse_assessment?: {
    source_version_id: string;
    source_version_number: number;
    source_image_url: string;
    recommendation: "reuse" | "review" | "regenerate" | string;
    can_reuse: boolean;
    reasons: string[];
    old_grid: number;
    new_grid: number;
    old_time_ranges: string[];
    new_time_ranges: string[];
  } | null;
};

export type StoryboardExecutionPage = {
  id: string;
  version_number: number;
  html_url: string;
  png_url: string;
  status: string;
  created_at: string;
};

export type StoryboardScene = {
  id: string;
  scope_code: string;
  name: string;
  axis_plan: AxisPlan;
  shots: StoryboardShot[];
  execution_pages: StoryboardExecutionPage[];
};

export type StoryboardWorkspace = {
  project_id: string;
  project_code: string;
  style_lock: StoryboardStyleLock;
  scenes: StoryboardScene[];
};

export type PromptStoryboardExport = {
  scene_id: string;
  scope_code: string;
  zip_url: string;
  relative_path: string;
  shot_count: number;
  files: string[];
};
