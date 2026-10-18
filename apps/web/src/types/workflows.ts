export type WorkflowIssue = {
  id: string;
  category: string;
  severity: string;
  target_type: string;
  target_id: string;
  title: string;
  detail: string;
  fixable: boolean;
  status: string;
};

export type CheckReport = {
  id: string;
  project_id: string;
  scene_id: string;
  scope_code: string;
  version_number: number;
  status: string;
  ready_for_next: boolean;
  issues: WorkflowIssue[];
  created_at: string;
};

export type TextSummary = {
  id: string;
  report_id: string | null;
  provider: string;
  model_name: string;
  response_text: string;
  cache_hit: boolean;
  input_tokens: number;
  cached_input_tokens: number;
  output_tokens: number;
  created_at: string;
};

export type AiTextRun = {
  id: string;
  project_id: string | null;
  report_id: string | null;
  source_extraction_id: string | null;
  target_type: string;
  target_id: string;
  module_type: string;
  provider: string;
  model_name: string;
  response_text: string;
  response_json: string;
  status: string;
  error_message: string;
  cache_hit: boolean;
  input_tokens: number;
  cached_input_tokens: number;
  output_tokens: number;
  created_at: string;
};

export type FixRun = {
  id: string;
  issue_id: string;
  target_type: string;
  created_version_id: string | null;
  status: string;
  message: string;
  created_at: string;
};

export type OneClickRun = {
  id: string;
  scene_id: string;
  status: string;
  current_stage: string;
  message: string;
  progress: { stage: string; status: string }[];
  created_at: string;
};

export type WorkflowReview = {
  project_id: string;
  project_code: string;
  scenes: { id: string; scope_code: string; name: string }[];
  reports: CheckReport[];
  fix_runs: FixRun[];
  one_click_runs: OneClickRun[];
  summaries: TextSummary[];
  text_runs: AiTextRun[];
};

export type RealTextAcceptanceItem = {
  key: string;
  label: string;
  status: "done" | "current" | "pending" | string;
  evidence: string;
  action_label: string;
  action_href: string;
  provider: string;
  model_name: string;
  output_tokens: number;
  created_at: string | null;
};

export type RealTextAcceptance = {
  project_id: string;
  project_code: string;
  ready: boolean;
  current_label: string;
  primary_action_label: string;
  primary_action_href: string;
  summary: string;
  items: RealTextAcceptanceItem[];
};

export type TextProviderStatus = {
  mode: string;
  mode_label: string;
  real_text_enabled: boolean;
  requires_user_confirmation: boolean;
  uses_full_system_prompt: boolean;
  system_prompt_loaded: boolean;
  system_prompt_filename: string;
  system_prompt_version: string;
  system_prompt_sha256_short: string;
  openai_api_key_configured: boolean;
  openai_model: string;
  huimengi_api_key_configured: boolean;
  huimengi_text_base_url: string;
  huimengi_text_model: string;
  text_api_key_configured: boolean;
  text_base_url: string;
  text_model: string;
  text_service_label: string;
  ready: boolean;
  blocking_reason: string;
  network_policy: string;
};

export type AiTextRunCreate = {
  module_type: string;
  source_extraction_id?: string | null;
  target_type?: string;
  target_id?: string;
  provider_mode?: string | null;
  confirm_live_request?: boolean;
  force_regenerate?: boolean;
  user_note?: string;
};

export type AiProviderStatus = {
  mode: string;
  real_openai_enabled: boolean;
  api_key_configured: boolean;
  text_model_configured: boolean;
  text_model: string;
  routine_model_configured: boolean;
  routine_model: string;
  image_model_configured: boolean;
  image_model: string;
  image_provider_mode: string;
  live_task: string;
  network_policy: string;
};

export type LocalEnvStatus = {
  openai_api_key_configured: boolean;
  openai_text_model: string;
  openai_model_routine: string;
  openai_image_model: string;
  openai_max_output_tokens: number;
  text_provider_mode: string;
  enable_real_text_analysis: boolean;
  enable_real_openai: boolean;
  enable_real_image_generation: boolean;
  huimengi_api_key_configured: boolean;
  huimengi_text_base_url: string;
  huimengi_text_model: string;
  text_api_key_configured: boolean;
  text_base_url: string;
  text_model: string;
  text_service_label: string;
  image_provider_mode: string;
  image_api_key_configured: boolean;
  image_base_url: string;
  image_model: string;
  huimengi_image_base_url: string;
  huimengi_image_model: string;
  huimengi_video_base_url: string;
  huimengi_video_model: string;
  huimengi_base_url: string;
  huimengi_model_id: string;
  enable_real_seedance: boolean;
  video_provider_mode: string;
  env_file_exists: boolean;
  env_file_path: string;
  secret_policy: string;
};

export type LocalEnvUpdate = {
  confirm_local_env_write: boolean;
  openai_api_key?: string;
  openai_text_model?: string;
  openai_model_routine?: string;
  openai_image_model?: string;
  openai_max_output_tokens?: number;
  text_provider_mode?: string;
  enable_real_text_analysis?: boolean;
  enable_real_openai?: boolean;
  enable_real_image_generation?: boolean;
  huimengi_api_key?: string;
  huimengi_text_base_url?: string;
  huimengi_text_model?: string;
  text_api_key?: string;
  text_base_url?: string;
  text_model?: string;
  image_provider_mode?: string;
  image_api_key?: string;
  image_base_url?: string;
  image_model?: string;
  huimengi_image_base_url?: string;
  huimengi_image_model?: string;
  huimengi_video_base_url?: string;
  huimengi_video_model?: string;
  huimengi_base_url?: string;
  huimengi_model_id?: string;
  enable_real_seedance?: boolean;
  video_provider_mode?: string;
};
