from __future__ import annotations

from datetime import datetime

from sqlmodel import Field, SQLModel

from app.models.workbench import new_id, utc_now


class Character(SQLModel, table=True):
    __tablename__ = "characters"

    id: str = Field(default_factory=new_id, primary_key=True)
    project_id: str = Field(foreign_key="projects.id", index=True)
    character_code: str = Field(index=True)
    name: str
    face_shape: str = ""
    facial_features: str = ""
    age_description: str = ""
    height_description: str = ""
    body_type: str = ""
    hair_style: str = ""
    identity_temperament: str = ""
    is_archived: bool = False
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class CharacterMasterVersion(SQLModel, table=True):
    __tablename__ = "character_master_versions"

    id: str = Field(default_factory=new_id, primary_key=True)
    character_id: str = Field(foreign_key="characters.id", index=True)
    version_number: int
    asset_path: str
    status: str = "draft"
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class Costume(SQLModel, table=True):
    __tablename__ = "costumes"

    id: str = Field(default_factory=new_id, primary_key=True)
    character_id: str = Field(foreign_key="characters.id", index=True)
    costume_code: str = Field(index=True)
    usage_context: str
    description: str = ""
    is_archived: bool = False
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class CostumeVersion(SQLModel, table=True):
    __tablename__ = "costume_versions"

    id: str = Field(default_factory=new_id, primary_key=True)
    costume_id: str = Field(foreign_key="costumes.id", index=True)
    character_master_version_id: str = Field(
        foreign_key="character_master_versions.id",
        index=True,
    )
    version_number: int
    asset_path: str
    status: str = "draft"
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class SceneAsset(SQLModel, table=True):
    __tablename__ = "scene_assets"

    id: str = Field(default_factory=new_id, primary_key=True)
    scene_id: str = Field(foreign_key="scenes.id", index=True)
    name: str = ""
    description: str = ""
    spatial_layout: str = ""
    time_weather_light: str = ""
    key_props: str = ""
    palette_mood: str = ""
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class SceneAssetVersion(SQLModel, table=True):
    __tablename__ = "scene_asset_versions"

    id: str = Field(default_factory=new_id, primary_key=True)
    scene_asset_id: str = Field(foreign_key="scene_assets.id", index=True)
    version_number: int
    asset_path: str
    status: str = "draft"
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class SceneCharacterBinding(SQLModel, table=True):
    __tablename__ = "scene_character_bindings"

    id: str = Field(default_factory=new_id, primary_key=True)
    scene_id: str = Field(foreign_key="scenes.id", index=True)
    character_id: str = Field(foreign_key="characters.id", index=True)
    character_master_version_id: str = Field(
        foreign_key="character_master_versions.id",
        index=True,
    )
    costume_version_id: str = Field(foreign_key="costume_versions.id", index=True)
    scene_state: str = ""
    hair_change_reason: str = ""
    consistency_status: str = "passed"
    consistency_notes: str = ""
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class PropAsset(SQLModel, table=True):
    __tablename__ = "prop_assets"

    id: str = Field(default_factory=new_id, primary_key=True)
    project_id: str = Field(foreign_key="projects.id", index=True)
    prop_code: str = Field(index=True)
    name: str
    category: str = "剧情道具"
    description: str = ""
    visual_details: str = ""
    is_archived: bool = False
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class PropAssetVersion(SQLModel, table=True):
    __tablename__ = "prop_asset_versions"

    id: str = Field(default_factory=new_id, primary_key=True)
    prop_asset_id: str = Field(foreign_key="prop_assets.id", index=True)
    version_number: int
    asset_path: str
    status: str = "draft"
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class ScenePropBinding(SQLModel, table=True):
    __tablename__ = "scene_prop_bindings"

    id: str = Field(default_factory=new_id, primary_key=True)
    scene_id: str = Field(foreign_key="scenes.id", index=True)
    prop_asset_id: str = Field(foreign_key="prop_assets.id", index=True)
    prop_asset_version_id: str = Field(foreign_key="prop_asset_versions.id", index=True)
    usage_note: str = ""
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class AssetRequirement(SQLModel, table=True):
    __tablename__ = "asset_requirements"

    id: str = Field(default_factory=new_id, primary_key=True)
    project_id: str = Field(foreign_key="projects.id", index=True)
    source_extraction_id: str | None = Field(default=None, index=True)
    analysis_run_id: str | None = Field(default=None, index=True)
    inventory_version: int = 1
    is_current: bool = True
    asset_type: str = Field(index=True)
    name: str
    description: str = ""
    visual_prompt: str = ""
    reference_mode: str = Field(default="visual", index=True)
    importance_reason: str = ""
    text_prompt: str = ""
    evidence: str = ""
    scene_ids_json: str = "[]"
    target_id: str = Field(default="", index=True)
    status: str = "identified"
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
