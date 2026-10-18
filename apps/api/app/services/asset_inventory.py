from __future__ import annotations

import json

from fastapi import HTTPException
from sqlmodel import Session, select

from app.config import Settings
from app.models import (
    AssetRequirement,
    Character,
    CharacterMasterVersion,
    Costume,
    CostumeVersion,
    Episode,
    PropAsset,
    PropAssetVersion,
    Scene,
    SceneAsset,
    SceneAssetVersion,
    SceneCharacterBinding,
    ScenePropBinding,
    SourceTextExtraction,
)
from app.models.workbench import utc_now
from app.schemas.assets import AssetInventoryAnalyzeCreate, AssetRequirementUpdate, AssetWorkspaceView
from app.schemas.workflows import AiTextRunCreate
from app.services.ai_text import run_project_ai_text
from app.services.assets import asset_workspace
from app.services.projects import _next_code, get_project


def _json_result(text: str) -> dict:
    value = text.strip()
    if "```" in value:
        blocks = value.split("```")
        value = next((part.removeprefix("json").strip() for part in blocks if "{" in part), value)
    start, end = value.find("{"), value.rfind("}")
    try:
        parsed = json.loads(value[start : end + 1])
    except (ValueError, json.JSONDecodeError) as cause:
        raise HTTPException(502, "AI 返回的资产清单格式无法读取，请重新生成。") from cause
    if not isinstance(parsed, dict):
        raise HTTPException(502, "AI 返回的资产清单不是有效对象。")
    return parsed


def _scenes(session: Session, project_id: str) -> tuple[dict[str, Scene], list[Scene]]:
    mapping: dict[str, Scene] = {}
    ordered: list[Scene] = []
    for episode in session.exec(select(Episode).where(Episode.project_id == project_id).order_by(Episode.episode_code)).all():
        for scene in session.exec(select(Scene).where(Scene.episode_id == episode.id).order_by(Scene.scene_code)).all():
            mapping[f"{episode.episode_code}{scene.scene_code}"] = scene
            ordered.append(scene)
    return mapping, ordered


def _scene_ids(raw: object, mapping: dict[str, Scene], fallback: list[Scene]) -> list[str]:
    values = raw if isinstance(raw, list) else []
    ids = [mapping[code].id for code in values if isinstance(code, str) and code in mapping]
    return list(dict.fromkeys(ids)) or ([fallback[0].id] if fallback else [])


def _requirement(session: Session, *, project_id: str, extraction_id: str, run_id: str,
                 version: int, asset_type: str, item: dict, target_id: str,
                 scene_ids: list[str]) -> None:
    reference_mode = "text_only" if str(item.get("reference_mode") or "visual").lower() == "text_only" else "visual"
    session.add(AssetRequirement(
        project_id=project_id,
        source_extraction_id=extraction_id,
        analysis_run_id=run_id,
        inventory_version=version,
        asset_type=asset_type,
        name=str(item.get("name") or "未命名资产").strip(),
        description=str(item.get("description") or "").strip(),
        visual_prompt=str(item.get("visual_prompt") or "").strip(),
        reference_mode=reference_mode,
        importance_reason=str(item.get("importance_reason") or "").strip(),
        text_prompt=str(item.get("text_prompt") or item.get("description") or "").strip(),
        evidence=str(item.get("evidence") or "").strip(),
        scene_ids_json=json.dumps(scene_ids, ensure_ascii=False),
        target_id=target_id,
        status="text_ready" if reference_mode == "text_only" else "identified",
    ))


def analyze_asset_inventory(session: Session, settings: Settings, project_id: str,
                            payload: AssetInventoryAnalyzeCreate) -> AssetWorkspaceView:
    project = get_project(session, project_id)
    extraction = session.exec(
        select(SourceTextExtraction)
        .where(SourceTextExtraction.project_id == project.id, SourceTextExtraction.status == "extracted")
        .order_by(SourceTextExtraction.created_at.desc())
    ).first()
    if extraction is None:
        raise HTTPException(409, "请先上传并解析剧本，再识别资产清单。")
    if not payload.confirm_live_request:
        raise HTTPException(409, "识别资产清单会发送剧本文本到已配置的 AI 服务，请先确认本次真实请求。")
    run = run_project_ai_text(session, settings, project.id, AiTextRunCreate(
        module_type="asset_inventory",
        source_extraction_id=extraction.id,
        provider_mode=payload.provider_mode,
        confirm_live_request=True,
        force_regenerate=payload.force_regenerate,
    ))
    data = _json_result(run.response_text)
    scope_map, ordered_scenes = _scenes(session, project.id)
    current = list(session.exec(select(AssetRequirement).where(
        AssetRequirement.project_id == project.id, AssetRequirement.is_current == True  # noqa: E712
    )).all())
    version = max([item.inventory_version for item in current], default=0) + 1
    for item in current:
        item.is_current = False
        item.updated_at = utc_now()
        session.add(item)

    character_codes = list(session.exec(select(Character.character_code).where(Character.project_id == project.id)).all())
    prop_codes = list(session.exec(select(PropAsset.prop_code).where(PropAsset.project_id == project.id)).all())
    for raw in data.get("characters", []):
        if not isinstance(raw, dict) or not str(raw.get("name") or "").strip():
            continue
        name = str(raw["name"]).strip()
        character = session.exec(select(Character).where(Character.project_id == project.id, Character.name == name)).first()
        if character is None:
            code = _next_code(character_codes, "CH", 2); character_codes.append(code)
            character = Character(project_id=project.id, character_code=code, name=name,
                                  identity_temperament=str(raw.get("description") or ""))
            session.add(character); session.flush()
        ids = _scene_ids(raw.get("scene_scope_codes"), scope_map, ordered_scenes)
        _requirement(session, project_id=project.id, extraction_id=extraction.id, run_id=run.id,
                     version=version, asset_type="character", item=raw, target_id=character.id, scene_ids=ids)
        costume_raw = raw.get("costume")
        if isinstance(costume_raw, dict) and str(costume_raw.get("name") or "").strip():
            usage = str(costume_raw["name"]).strip()
            costume = session.exec(select(Costume).where(Costume.character_id == character.id, Costume.usage_context == usage)).first()
            if costume is None:
                codes = list(session.exec(select(Costume.costume_code).where(Costume.character_id == character.id)).all())
                costume = Costume(character_id=character.id, costume_code=_next_code(codes, "C", 2),
                                  usage_context=usage, description=str(costume_raw.get("description") or ""))
                session.add(costume); session.flush()
            costume_item = {**costume_raw, "evidence": raw.get("evidence", "")}
            _requirement(session, project_id=project.id, extraction_id=extraction.id, run_id=run.id,
                         version=version, asset_type="costume", item=costume_item,
                         target_id=costume.id, scene_ids=ids)

    for raw in data.get("scenes", []):
        if not isinstance(raw, dict): continue
        scene = scope_map.get(str(raw.get("scope_code") or ""))
        if scene is None: continue
        name = str(raw.get("name") or "").strip()
        asset = session.exec(
            select(SceneAsset).where(SceneAsset.scene_id == scene.id, SceneAsset.name == name)
        ).first()
        fields = {key: str(raw.get(key) or "") for key in ("description", "spatial_layout", "time_weather_light", "key_props", "palette_mood")}
        if asset is None: asset = SceneAsset(scene_id=scene.id, name=name, **fields)
        else:
            for key, value in fields.items(): setattr(asset, key, value)
        session.add(asset); session.flush()
        _requirement(session, project_id=project.id, extraction_id=extraction.id, run_id=run.id,
                     version=version, asset_type="scene", item=raw, target_id=asset.id, scene_ids=[scene.id])

    for raw in data.get("props", []):
        if not isinstance(raw, dict) or not str(raw.get("name") or "").strip(): continue
        name = str(raw["name"]).strip()
        prop = session.exec(select(PropAsset).where(PropAsset.project_id == project.id, PropAsset.name == name)).first()
        if prop is None:
            code = _next_code(prop_codes, "PR", 2); prop_codes.append(code)
            prop = PropAsset(project_id=project.id, prop_code=code, name=name,
                             category=str(raw.get("category") or "剧情道具"),
                             description=str(raw.get("description") or ""),
                             visual_details=str(raw.get("visual_details") or ""))
            session.add(prop); session.flush()
        ids = _scene_ids(raw.get("scene_scope_codes"), scope_map, ordered_scenes)
        _requirement(session, project_id=project.id, extraction_id=extraction.id, run_id=run.id,
                     version=version, asset_type="prop", item=raw, target_id=prop.id, scene_ids=ids)
    session.commit()
    return asset_workspace(session, project.id)


def update_asset_requirement(session: Session, requirement_id: str,
                             payload: AssetRequirementUpdate) -> AssetWorkspaceView:
    requirement = session.get(AssetRequirement, requirement_id)
    if requirement is None or not requirement.is_current:
        raise HTTPException(404, "资产清单项不存在或已不是当前版本。")
    values = payload.model_dump(exclude_unset=True)
    if "scene_ids" in values:
        _, scenes = _scenes(session, requirement.project_id)
        valid = {scene.id for scene in scenes}
        if any(scene_id not in valid for scene_id in values["scene_ids"]):
            raise HTTPException(400, "包含不属于当前项目的场次。")
        requirement.scene_ids_json = json.dumps(values.pop("scene_ids"), ensure_ascii=False)
    for key, value in values.items(): setattr(requirement, key, value)
    if requirement.reference_mode == "text_only":
        requirement.status = "text_ready"
    elif requirement.status == "text_ready":
        requirement.status = "identified"
    requirement.updated_at = utc_now(); session.add(requirement); session.commit()
    return asset_workspace(session, requirement.project_id)


def auto_bind_assets(session: Session, project_id: str) -> AssetWorkspaceView:
    get_project(session, project_id)
    requirements = list(session.exec(select(AssetRequirement).where(
        AssetRequirement.project_id == project_id, AssetRequirement.is_current == True  # noqa: E712
    )).all())
    active = {"confirmed_current", "locked"}
    for req in requirements:
        if req.reference_mode == "text_only":
            req.status = "text_ready"
            req.updated_at = utc_now()
            session.add(req)
            continue
        # Re-evaluate visual requirements on every run so stale "bound" states
        # cannot survive after a locked/current version is changed or removed.
        req.status = "identified"
        scene_ids = json.loads(req.scene_ids_json or "[]")
        if req.asset_type == "character":
            master = session.exec(select(CharacterMasterVersion).where(
                CharacterMasterVersion.character_id == req.target_id,
                CharacterMasterVersion.status.in_(active))).first()
            costumes = session.exec(select(Costume).where(Costume.character_id == req.target_id)).all()
            costume_version = None
            for costume in costumes:
                costume_version = session.exec(select(CostumeVersion).where(
                    CostumeVersion.costume_id == costume.id,
                    CostumeVersion.status.in_(active),
                )).first()
                if costume_version is not None:
                    break
            # A character master and a costume are separate references. A
            # text-only costume must not prevent a valid locked character from
            # being marked ready for video grounding.
            if master:
                req.status = "bound"
            if master and costume_version:
                for scene_id in scene_ids:
                    binding = session.exec(select(SceneCharacterBinding).where(
                        SceneCharacterBinding.scene_id == scene_id,
                        SceneCharacterBinding.character_id == req.target_id)).first() or SceneCharacterBinding(
                            scene_id=scene_id, character_id=req.target_id,
                            character_master_version_id=master.id, costume_version_id=costume_version.id)
                    binding.character_master_version_id = master.id; binding.costume_version_id = costume_version.id
                    binding.consistency_status = "passed"; session.add(binding)
        elif req.asset_type == "costume":
            version = session.exec(select(CostumeVersion).where(
                CostumeVersion.costume_id == req.target_id, CostumeVersion.status.in_(active))).first()
            if version: req.status = "bound"
        elif req.asset_type == "scene":
            version = session.exec(select(SceneAssetVersion).where(
                SceneAssetVersion.scene_asset_id == req.target_id, SceneAssetVersion.status.in_(active))).first()
            if version: req.status = "bound"
        elif req.asset_type == "prop":
            version = session.exec(select(PropAssetVersion).where(
                PropAssetVersion.prop_asset_id == req.target_id, PropAssetVersion.status.in_(active))).first()
            if version:
                for scene_id in scene_ids:
                    binding = session.exec(select(ScenePropBinding).where(
                        ScenePropBinding.scene_id == scene_id,
                        ScenePropBinding.prop_asset_id == req.target_id)).first() or ScenePropBinding(
                            scene_id=scene_id, prop_asset_id=req.target_id, prop_asset_version_id=version.id)
                    binding.prop_asset_version_id = version.id; session.add(binding)
                req.status = "bound"
        req.updated_at = utc_now(); session.add(req)
    session.commit()
    return asset_workspace(session, project_id)
