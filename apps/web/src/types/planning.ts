export type SourceTextExtraction = {
  id: string;
  project_id: string;
  source_file_id: string;
  version_number: number;
  status: "extracted" | "unsupported" | "error";
  text_relative_path: string;
  character_count: number;
  line_count: number;
  preview: string;
  error: string;
  created_at: string;
};

export type PlanningDraftItem = {
  id: string;
  draft_id: string;
  project_id: string;
  episode_code: string;
  scene_code: string;
  shot_code: string;
  source_excerpt: string;
  suggested_task: string;
  status: string;
  created_at: string;
};

export type PlanningDraft = {
  id: string;
  project_id: string;
  source_extraction_id: string | null;
  version_number: number;
  status: "draft" | "applied" | "saved_not_applied";
  summary: string;
  draft_json: string;
  applied_at: string | null;
  created_at: string;
  items: PlanningDraftItem[];
};
