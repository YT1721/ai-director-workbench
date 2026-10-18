export type AssetVersion = {
  id: string;
  version_number: number;
  asset_path: string;
  asset_url: string;
  status:
    | "draft"
    | "confirmed_current"
    | "confirmed_history"
    | "locked"
    | "rejected";
  created_at: string;
};

export type AssetImageTargetKind =
  | "character-master"
  | "costume"
  | "scene"
  | "prop";

export type AssetImageReadiness = {
  ready: boolean;
  asset_type: string;
  provider_name: string;
  model_id: string;
  gate_items: { label: string; passed: boolean; detail: string }[];
  risk_notice: string;
  requires_user_confirmation: boolean;
};

export type AssetImageJob = {
  id: string;
  project_id: string;
  target_type: AssetImageTargetKind | string;
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
  error_message: string;
  created_at: string;
};

export type Costume = {
  id: string;
  costume_code: string;
  usage_context: string;
  description: string;
  is_archived: boolean;
  versions: AssetVersion[];
};

export type Character = {
  id: string;
  character_code: string;
  name: string;
  face_shape: string;
  facial_features: string;
  age_description: string;
  height_description: string;
  body_type: string;
  hair_style: string;
  identity_temperament: string;
  is_archived: boolean;
  master_versions: AssetVersion[];
  costumes: Costume[];
};

export type AssetScene = {
  id: string;
  scope_code: string;
  scene_code: string;
  name: string;
};

export type SceneAsset = {
  id: string;
  scene_id: string;
  scope_code: string;
  scene_name: string;
  name: string;
  description: string;
  spatial_layout: string;
  time_weather_light: string;
  key_props: string;
  palette_mood: string;
  versions: AssetVersion[];
};

export type PropAsset = {
  id: string;
  prop_code: string;
  name: string;
  category: string;
  description: string;
  visual_details: string;
  is_archived: boolean;
  versions: AssetVersion[];
};

export type AssetRequirement = {
  id: string;
  inventory_version: number;
  asset_type: "character" | "costume" | "scene" | "prop";
  name: string;
  description: string;
  visual_prompt: string;
  reference_mode: "visual" | "text_only";
  importance_reason: string;
  text_prompt: string;
  evidence: string;
  scene_ids: string[];
  scene_scope_codes: string[];
  target_id: string;
  status: "identified" | "image_ready" | "bound" | "text_ready" | string;
};

export type PropBinding = {
  id: string;
  scene_id: string;
  prop_id: string;
  prop_name: string;
  prop_version_id: string;
  prop_version_number: number;
  placement_note: string;
};

export type ConsistencyCheck = {
  key: string;
  label: string;
  status: "passed" | "failed" | "pending";
  detail: string;
};

export type SceneBinding = {
  id: string;
  scene_id: string;
  scope_code: string;
  character_id: string;
  character_name: string;
  character_master_version_id: string;
  character_master_version_number: number;
  costume_version_id: string;
  costume_code: string;
  costume_version_number: number;
  scene_state: string;
  hair_change_reason: string;
  consistency_status: "passed" | "failed";
  checks: ConsistencyCheck[];
};

export type AssetWorkspace = {
  project_id: string;
  project_code: string;
  characters: Character[];
  scenes: AssetScene[];
  scene_assets: SceneAsset[];
  bindings: SceneBinding[];
  requirements?: AssetRequirement[];
  props?: PropAsset[];
  prop_bindings?: PropBinding[];
};

export type CharacterDraft = {
  name: string;
  face_shape: string;
  facial_features: string;
  age_description: string;
  height_description: string;
  body_type: string;
  hair_style: string;
  identity_temperament: string;
};

export type SceneAssetDraft = {
  name: string;
  description: string;
  spatial_layout: string;
  time_weather_light: string;
  key_props: string;
  palette_mood: string;
};
