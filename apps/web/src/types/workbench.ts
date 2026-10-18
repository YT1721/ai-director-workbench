export type ProjectSummary = {
  id: string;
  project_code: string;
  name: string;
  description: string;
  creative_goal:
    | "full_pipeline"
    | "prompt_storyboard"
    | "asset_only"
    | "analysis_plan";
  is_archived: boolean;
  created_at: string;
  updated_at: string;
};

export type Shot = {
  id: string;
  shot_code: string;
  name: string;
  is_archived: boolean;
};

export type Scene = {
  id: string;
  scene_code: string;
  name: string;
  is_archived: boolean;
  shots: Shot[];
};

export type Episode = {
  id: string;
  episode_code: string;
  name: string;
  is_archived: boolean;
  scenes: Scene[];
};

export type ProjectDetail = ProjectSummary & {
  episodes: Episode[];
};

export type ProjectOverview = ProjectSummary & {
  episode_count: number;
  scene_count: number;
  shot_count: number;
  source_file_count: number;
  current_stage: string;
  short_status: string;
  primary_action_label: string;
  primary_action_href: string;
};

export type SourceFile = {
  id: string;
  project_id: string;
  category:
    | "script"
    | "reference"
    | "script_text"
    | "storyboard_table"
    | "storyboard_table_image";
  original_filename: string;
  stored_filename: string;
  relative_path: string;
  content_type?: string | null;
  size_bytes: number;
  created_at: string;
};

export type WorkflowCheckpoint = {
  id: string;
  title: string;
  status: string;
  created_at: string;
};

export type UcodeRun = {
  id: string;
  project_id: string;
  ucode_action: string;
  scope_code: string;
  additional_request: string;
  command_text: string;
  status: string;
  result_summary: string;
  checkpoint_required: boolean;
  created_at: string;
  checkpoints: WorkflowCheckpoint[];
};

export type CommandDraft = {
  action: string;
  scopeCode: string;
  additionalRequest: string;
};

export type SourceInputCategory =
  | "script_text"
  | "script"
  | "storyboard_table"
  | "storyboard_table_image"
  | "reference";

export type IntakeDraft =
  | {
      kind: "text";
      category: "script_text" | "storyboard_table";
      title: string;
      content: string;
    }
  | {
      kind: "file";
      category:
        | "script"
        | "storyboard_table"
        | "storyboard_table_image"
        | "reference";
      file: File;
    };
