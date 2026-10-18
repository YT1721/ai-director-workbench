from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class CharacterCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    face_shape: str = Field(default="", max_length=300)
    facial_features: str = Field(default="", max_length=500)
    age_description: str = Field(default="", max_length=120)
    height_description: str = Field(default="", max_length=120)
    body_type: str = Field(default="", max_length=120)
    hair_style: str = Field(default="", max_length=200)
    identity_temperament: str = Field(default="", max_length=500)


class CostumeCreate(BaseModel):
    usage_context: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=800)


class SceneAssetCreate(BaseModel):
    name: str = Field(default="", max_length=200)
    description: str = Field(default="", max_length=800)
    spatial_layout: str = Field(default="", max_length=800)
    time_weather_light: str = Field(default="", max_length=500)
    key_props: str = Field(default="", max_length=500)
    palette_mood: str = Field(default="", max_length=500)


class BindingCreate(BaseModel):
    character_id: str
    character_master_version_id: str
    costume_version_id: str
    scene_state: str = Field(default="", max_length=500)
    hair_change_reason: str = Field(default="", max_length=500)


class AssetInventoryAnalyzeCreate(BaseModel):
    provider_mode: str | None = None
    confirm_live_request: bool = False
    force_regenerate: bool = False


class AssetRequirementUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=1200)
    visual_prompt: str | None = Field(default=None, max_length=3000)
    reference_mode: Literal["visual", "text_only"] | None = None
    importance_reason: str | None = Field(default=None, max_length=1200)
    text_prompt: str | None = Field(default=None, max_length=3000)
    scene_ids: list[str] | None = None


class AssetVersionView(BaseModel):
    id: str
    version_number: int
    asset_path: str
    asset_url: str
    status: str
    created_at: datetime


class CostumeView(BaseModel):
    id: str
    costume_code: str
    usage_context: str
    description: str
    is_archived: bool
    versions: list[AssetVersionView]


class CharacterView(BaseModel):
    id: str
    character_code: str
    name: str
    face_shape: str
    facial_features: str
    age_description: str
    height_description: str
    body_type: str
    hair_style: str
    identity_temperament: str
    is_archived: bool
    master_versions: list[AssetVersionView]
    costumes: list[CostumeView]


class SceneSummaryView(BaseModel):
    id: str
    scope_code: str
    scene_code: str
    name: str


class SceneAssetView(BaseModel):
    id: str
    scene_id: str
    scope_code: str
    scene_name: str
    name: str = ""
    description: str
    spatial_layout: str
    time_weather_light: str
    key_props: str
    palette_mood: str
    versions: list[AssetVersionView]


class PropAssetView(BaseModel):
    id: str
    prop_code: str
    name: str
    category: str
    description: str
    visual_details: str
    is_archived: bool
    versions: list[AssetVersionView]


class AssetRequirementView(BaseModel):
    id: str
    inventory_version: int
    asset_type: str
    name: str
    description: str
    visual_prompt: str
    reference_mode: Literal["visual", "text_only"]
    importance_reason: str
    text_prompt: str
    evidence: str
    scene_ids: list[str]
    scene_scope_codes: list[str]
    target_id: str
    status: str


class PropBindingView(BaseModel):
    id: str
    scene_id: str
    scope_code: str
    prop_asset_id: str
    prop_name: str
    prop_asset_version_id: str
    prop_version_number: int
    usage_note: str


class ConsistencyCheckView(BaseModel):
    key: str
    label: str
    status: str
    detail: str


class BindingView(BaseModel):
    id: str
    scene_id: str
    scope_code: str
    character_id: str
    character_name: str
    character_master_version_id: str
    character_master_version_number: int
    costume_version_id: str
    costume_code: str
    costume_version_number: int
    scene_state: str
    hair_change_reason: str
    consistency_status: str
    checks: list[ConsistencyCheckView]


class AssetWorkspaceView(BaseModel):
    project_id: str
    project_code: str
    characters: list[CharacterView]
    scenes: list[SceneSummaryView]
    scene_assets: list[SceneAssetView]
    bindings: list[BindingView]
    requirements: list[AssetRequirementView] = Field(default_factory=list)
    props: list[PropAssetView] = Field(default_factory=list)
    prop_bindings: list[PropBindingView] = Field(default_factory=list)


class AssetImageGateItem(BaseModel):
    label: str
    passed: bool
    detail: str


class AssetImageReadinessView(BaseModel):
    ready: bool
    asset_type: str
    provider_name: str
    model_id: str
    gate_items: list[AssetImageGateItem]
    risk_notice: str
    requires_user_confirmation: bool = True


class AssetImageActionCreate(BaseModel):
    confirm_live_request: bool = False


class AssetImageJobView(BaseModel):
    id: str
    project_id: str
    target_type: str
    target_id: str
    provider: str
    model_name: str
    external_task_id: str
    status: str
    remote_result_url: str
    image_url: str | None
    error_message: str
    created_at: datetime
