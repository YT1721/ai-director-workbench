from __future__ import annotations

import json

from sqlmodel import Session, select

from app.models import (
    AssetRequirement,
    CharacterMasterVersion,
    CostumeVersion,
    PropAssetVersion,
    SceneAssetVersion,
)


def _target_for_version(session: Session, asset_id: str) -> tuple[str, str] | None:
    version = session.get(CharacterMasterVersion, asset_id)
    if version:
        return "character", version.character_id
    version = session.get(CostumeVersion, asset_id)
    if version:
        return "costume", version.costume_id
    version = session.get(SceneAssetVersion, asset_id)
    if version:
        return "scene", version.scene_asset_id
    version = session.get(PropAssetVersion, asset_id)
    if version:
        return "prop", version.prop_asset_id
    return None


def requirement_allows_version(
    session: Session,
    project_id: str,
    asset_id: str,
    scene_id: str | None = None,
) -> bool:
    target = _target_for_version(session, asset_id)
    if target is None:
        return True
    asset_type, target_id = target
    requirements = list(session.exec(select(AssetRequirement).where(
        AssetRequirement.project_id == project_id,
        AssetRequirement.is_current == True,  # noqa: E712
        AssetRequirement.asset_type == asset_type,
        AssetRequirement.target_id == target_id,
    )).all())
    if not requirements:
        return True
    relevant: list[AssetRequirement] = []
    for requirement in requirements:
        try:
            scene_ids = list(json.loads(requirement.scene_ids_json or "[]"))
        except (TypeError, ValueError):
            scene_ids = []
        if scene_id and scene_ids and scene_id not in scene_ids:
            continue
        relevant.append(requirement)
    if not relevant:
        return True
    return any(item.reference_mode != "text_only" for item in relevant)


def text_only_asset_descriptions_for_scene(
    session: Session,
    project_id: str,
    scene_id: str,
) -> list[dict[str, str]]:
    results: list[dict[str, str]] = []
    requirements = session.exec(select(AssetRequirement).where(
        AssetRequirement.project_id == project_id,
        AssetRequirement.is_current == True,  # noqa: E712
        AssetRequirement.reference_mode == "text_only",
    ).order_by(AssetRequirement.asset_type, AssetRequirement.created_at)).all()
    for requirement in requirements:
        try:
            scene_ids = list(json.loads(requirement.scene_ids_json or "[]"))
        except (TypeError, ValueError):
            scene_ids = []
        if scene_ids and scene_id not in scene_ids:
            continue
        description = (requirement.text_prompt or requirement.description).strip()
        if not description:
            continue
        results.append({
            "asset_type": requirement.asset_type,
            "name": requirement.name,
            "description": description,
        })
    return results
