export type VideoReferenceBinding = {
  token: string;
  asset_id: string;
  asset_type:
    | "storyboard"
    | "scene"
    | "character"
    | "costume"
    | "prop"
    | "source";
  role:
    | "storyboard"
    | "environment"
    | "character"
    | "costume"
    | "product"
    | "prop_detail"
    | "environment_detail"
    | "source_video"
    | "source_audio";
  label: string;
  purpose: string;
  media_type?: "image" | "video" | "audio";
  must_preserve?: string;
  must_not_transfer?: string;
  asset_path?: string;
  asset_url?: string;
  version_status?: "current" | "history";
};

export type VpBlock = {
  id: string;
  shot_id: string;
  version_number: number;
  has_character: boolean;
  schema_version: string;
  package_stage: "director_draft" | "final_execution";
  prompt: string;
  negative_prompt: string;
  duration_seconds: number;
  aspect_ratio: string;
  resolution: string;
  generation_mode: string;
  provider_profile_id: string;
  status: string;
  prompt_copy: string;
  basis_vp_block_id: string | null;
  storyboard_version_id: string | null;
  precision_items: { number: number; title: string; content: unknown }[];
  director_technique: string;
  close_in_start_time: string;
  close_in_from_shot_size: string;
  close_in_to_shot_size: string;
  close_in_target_detail: string;
  close_in_emotional_meaning: string;
  close_in_return_to_character: boolean;
  close_in_tail_frame: string;
  detail_shot_candidates: string[];
  selected_detail_shot: string;
  detail_shot_time_range: string;
  detail_shot_meaning: string;
  detail_shot_relation_to_character: string;
  montage_type: string;
  montage_goal: string;
  montage_shot_count: number;
  montage_entry_point: string;
  montage_exit_point: string;
  montage_rhythm: string;
  montage_return_to_main_story: string;
  symbolic_object: string;
  object_state_change: string;
  symbolic_meaning: string;
  object_state_time_range: string;
  relation_to_character_emotion: string;
  meaning_chain: Record<string, unknown>;
  asset_summary: string[];
  validation_items: string[];
  provider_prompt_preview?: string;
  reference_bindings?: VideoReferenceBinding[];
};
export type VideoPackageWorkspace = {
  project_id: string;
  project_code: string;
  scenes: {
    id: string;
    scope_code: string;
    name: string;
    shots: {
      id: string;
      shot_code: string;
      name: string;
      recommended_duration_seconds?: number;
      duration_reason?: string;
      confirmed_storyboard_vp_basis_block_id?: string | null;
      versions: VpBlock[];
    }[];
  }[];
};
export type ProviderProfile = {
  id: string;
  display_name: string;
  provider_type: string;
  is_enabled: boolean;
  is_default: boolean;
  base_url: string;
  create_task_path: string;
  get_task_path_template: string;
  cancel_task_path_template?: string;
  auth_type: string;
  auth_header_name: string;
  auth_prefix: string;
  auth_env_key_name: string;
  config?: Record<string, unknown>;
  capabilities: Record<string, unknown>;
  price_configs: Record<string, unknown>[];
  validation_message: string;
};
export type ProviderProfileDraft = Omit<
  ProviderProfile,
  "id" | "is_default" | "validation_message"
>;
export type ProviderTemplate = {
  template_id: string;
  title: string;
  description: string;
  outbound_requests_enabled: boolean;
  profile: ProviderProfileDraft;
};
export type LiveProviderStatus = {
  provider_mode: string;
  real_seedance_enabled: boolean;
  huimengi_api_key_configured: boolean;
  huimengi_video_base_url: string;
  huimengi_video_model: string;
  huimengi_base_url: string;
  huimengi_model_id: string;
  live_video_task: string;
  single_task_limit: string;
  network_policy: string;
};
export type LiveReadinessGate = {
  label: string;
  passed: boolean;
  detail: string;
};
export type LiveReadiness = {
  ready: boolean;
  provider_name: string;
  model_id: string;
  gate_items: LiveReadinessGate[];
  risk_notice: string;
  requires_user_confirmation: boolean;
};
export type JimengCliStatus = {
  installed: boolean;
  logged_in: boolean;
  ready: boolean;
  command: string;
  account_summary: string;
  credit_summary: string;
  output_dir: string;
  blocking_reason: string;
  cli_version?: string;
  install_hint: string;
};
export type JimengCliReadiness = {
  ready: boolean;
  provider_name: string;
  model_id: string;
  gate_items: LiveReadinessGate[];
  risk_notice: string;
  requires_user_confirmation: boolean;
  prompt_preview: string;
  asset_count: number;
  reference_bindings?: VideoReferenceBinding[];
  reference_candidates?: VideoReferenceCandidate[];
};
export type VideoReferenceCandidate = {
  asset_id: string;
  asset_type: VideoReferenceBinding["asset_type"];
  role: VideoReferenceBinding["role"];
  label: string;
  purpose?: string;
  media_type?: "image" | "video" | "audio";
  asset_url?: string;
};
export type VideoTaskSupervisorStatus = {
  enabled: boolean;
  running: boolean;
  poll_interval_seconds: number;
  active_task_count: number;
  last_cycle_at: string | null;
  last_success_at: string | null;
  last_error: string;
};
export type VpGenerationJob = {
  id: string;
  project_id: string;
  scene_id: string;
  operation: "duration_rebuild";
  status:
    | "queued"
    | "running"
    | "retrying"
    | "completed"
    | "failed"
    | "cancelled";
  total_count: number;
  completed_count: number;
  failed_count: number;
  current_shot_code: string;
  message: string;
  error_message: string;
  created_at: string;
  updated_at: string;
};
export type VideoProviderModel = {
  id: string;
  label: string;
  speed_label: string;
  cost_label: string;
  description: string;
  supported_resolutions: string[];
  min_duration: number;
  max_duration: number;
  provider_type?: string;
  provider_model_id?: string;
  supports_smart_duration?: boolean;
  is_mock_only?: boolean;
  mock_only?: boolean;
  capability_source?: string;
  cli_version?: string;
  available?: boolean;
  unavailable_reason?: string;
  duration_range?: number[];
  reference_limits?: {
    images?: number;
    videos?: number;
    audios?: number;
    total?: number;
  };
};
export type JimengVideoModel = VideoProviderModel;
export type VideoGenerationSettings = {
  provider_model_id?: string;
  generation_mode?: string;
  duration_mode?: "smart" | "specified";
  duration_seconds?: number | null;
  resolution?: "480p" | "720p";
  prompt_optimization_enabled?: boolean;
};
export type VideoReferenceItemUpdate = {
  asset_id: string;
  media_type: "image" | "video" | "audio";
  purpose: string;
  must_preserve?: string;
  must_not_transfer?: string;
};
export type ProviderPreflight = {
  profile_id: string;
  provider_type: string;
  config_valid: boolean;
  secret_configured: boolean;
  documentation_url: string;
  price_source_url: string;
  price_configured: boolean;
  request_mapping_complete: boolean;
  response_mapping_complete: boolean;
  outbound_requests_enabled: boolean;
  ready_for_live_test: boolean;
  checklist: string[];
};
export type ProviderRequestPreview = {
  task_id: string;
  provider_profile_id: string;
  canonical_request: Record<string, unknown>;
  mapped_request_preview: Record<string, unknown>;
  missing_items: string[];
  outbound_request_sent: boolean;
};
export type ProviderResponsePreview = {
  profile_id: string;
  normalized_response: Record<string, unknown>;
  missing_items: string[];
  sample_saved: boolean;
  outbound_requests_sent: boolean;
  result_downloaded: boolean;
};
export type BatchTask = {
  id: string;
  shot_id: string;
  shot_code: string;
  status: string;
  external_task_id?: string | null;
  external_provider?: string;
  result_video_path?: string | null;
  local_file_path?: string;
  remote_video_url?: string;
  storage_status?: "pending" | "online" | "local" | "failed" | "mock";
  progress_percent?: number;
  progress_label?: string;
  provider_status?: string;
  provider_status_detail?: string;
  provider_queue_status?: string;
  provider_queue_position?: number | null;
  provider_queue_length?: number | null;
  updated_at?: string;
  missing_items: string[];
  canonical_request: Record<string, unknown>;
  retry_count: number;
  error_message: string;
  storyboard_url: string | null;
  current_storyboard_url?: string | null;
  storyboard_reference_status?: "current" | "history" | "missing";
  storyboard_reference_note?: string;
  provider_prompt_preview?: string;
  reference_bindings?: VideoReferenceBinding[];
  reference_candidates?: VideoReferenceCandidate[];
  reference_bindings_confirmed?: boolean;
  reference_bindings_confirmed_at?: string | null;
  reference_binding_status?: "current" | "historical_snapshot";
  reference_binding_note?: string;
  results: {
    id: string;
    version_number: number;
    source: string;
    status: string;
    video_url: string;
  }[];
};
export type BatchJob = {
  id: string;
  scene_id: string;
  scope_code: string;
  provider_profile_id: string;
  provider_name: string;
  submission_channel?: "huimeng" | "jimeng" | "volcengine_seedance25";
  status: string;
  budget_confirmed: boolean;
  estimated_cost: number | null;
  batch_authorized?: boolean;
  dispatch_enabled?: boolean;
  launched_at?: string | null;
  cost_estimate_status: "estimated" | "unknown";
  cost_estimate_note: string;
  cost_source_url: string;
  currency: string;
  total_seconds: number;
  jimeng_zip_url: string | null;
  tasks: BatchTask[];
  task_counts?: Record<string, number>;
};
export type BatchWorkspace = {
  project_id: string;
  project_code: string;
  providers: ProviderProfile[];
  scenes: {
    id: string;
    scope_code: string;
    name: string;
    shot_count?: number;
    confirmed_video_count?: number;
  }[];
  jobs: BatchJob[];
};
