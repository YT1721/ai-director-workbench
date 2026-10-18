export interface SeedanceCandidate {
  episode_code: string;
  scene_id: string;
  scene_code: string;
  shot_id: string;
  shot_code: string;
  shot_name: string;
  storyboard_version_id: string | null;
  storyboard_version: number | null;
  storyboard_status: string | null;
  storyboard_grid: number | null;
  prompt_time_ranges: string[];
  vp_block_id: string | null;
  vp_block_version: number | null;
  vp_block_status: string | null;
  duration_seconds: number;
  recommended_duration_seconds?: number;
  duration_reason?: string;
  duration_needs_rebuild?: boolean;
  precision_18: Array<Record<string, unknown>>;
  existing_video_unit_ids: string[];
  next_unit_index: number;
}

export interface SeedanceTakeReview {
  id: string;
  source_video_path: string;
  observed_start_state: Record<string, unknown>;
  observed_end_state: Record<string, unknown>;
  review_status: "pending" | "accepted" | "rejected";
  rejection_reasons: string[];
  reviewer_notes: string;
  created_at: string;
}

export interface SeedanceVideoUnit {
  id: string;
  project_id: string;
  scene_id: string;
  shot_id: string;
  shot_code: string;
  shot_name: string;
  scene_code: string;
  unit_index: number;
  unit_type: string;
  duration_seconds: number;
  extension_depth: number;
  reanchor_required: boolean;
  event_density_score: number;
  status: string;
  prompt_time_ranges: string[];
  allocation: Record<string, unknown>;
  intended_start_state: Record<string, unknown>;
  intended_end_state: Record<string, unknown>;
  continuity_handoff: Record<string, unknown>;
  reference_roles: Array<Record<string, unknown>>;
  vp_block_id: string | null;
  vp_block_version: number | null;
  precision_18: Array<Record<string, unknown>>;
  vp_prompt_full: string;
  vp_prompt_copy: string;
  take_reviews: SeedanceTakeReview[];
}

export interface SeedanceOsWorkspace {
  project: { id: string; project_code: string; name: string };
  state:
    | ({
        canon: Record<string, unknown>;
        completed_video_unit_ids: string[];
        reserved_video_unit_ids: string[];
      } & Record<string, unknown>)
    | null;
  candidates: SeedanceCandidate[];
  video_units: SeedanceVideoUnit[];
  surface_profiles: Array<Record<string, unknown>>;
  limits: {
    max_video_unit_seconds: number;
    max_extension_depth: number;
    provider_submission_requires_confirmation: boolean;
  };
}

export interface SeedancePromptCompileResult {
  vp_prompt_full: string;
  vp_prompt_copy: string;
  reference_tag_map: Array<Record<string, unknown>>;
  preserved_constraints: string[];
  removed_redundancy: string[];
  prompt_budget_report: Record<string, unknown>;
  compile_warnings: string[];
  skill_modules: string[];
}
