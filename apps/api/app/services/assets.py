from __future__ import annotations

import json
from io import BytesIO
from pathlib import Path
from typing import Literal, TypeVar
from urllib.parse import quote

from fastapi import HTTPException
from PIL import Image
from sqlmodel import Session, SQLModel, select

from app.config import Settings
from app.models import (
    AssetRequirement,
    Character,
    CharacterMasterVersion,
    Costume,
    CostumeVersion,
    Episode,
    ImageGenerationJob,
    Project,
    PropAsset,
    PropAssetVersion,
    Scene,
    SceneAsset,
    SceneAssetVersion,
    SceneCharacterBinding,
    ScenePropBinding,
    StoryboardShotVersion,
    Shot,
)
from app.models.workbench import utc_now
from app.providers.image import HuimengImageProvider, OpenAIImagesProvider
from app.services.image_download import download_image_with_url_refresh
from app.schemas.assets import (
    AssetImageGateItem,
    AssetImageJobView,
    AssetImageReadinessView,
    AssetImageActionCreate,
    AssetVersionView,
    AssetWorkspaceView,
    AssetRequirementView,
    BindingCreate,
    BindingView,
    CharacterCreate,
    CharacterView,
    ConsistencyCheckView,
    CostumeCreate,
    CostumeView,
    PropAssetView,
    PropBindingView,
    SceneAssetCreate,
    SceneAssetView,
    SceneSummaryView,
)
from app.services.projects import _next_code, _project_root, get_project


VersionKind = Literal["character-master", "costume", "scene", "prop"]
AssetImageTargetKind = Literal["character-master", "costume", "scene", "prop"]
ASSET_UPLOAD_MAX_BYTES = 25 * 1024 * 1024
ASSET_UPLOAD_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
VersionModel = TypeVar(
    "VersionModel",
    CharacterMasterVersion,
    CostumeVersion,
    SceneAssetVersion,
    PropAssetVersion,
)


def character_project_id(session: Session, character_id: str) -> str:
    character = session.get(Character, character_id)
    if character is None:
        raise HTTPException(status_code=404, detail="人物不存在。")
    return character.project_id


def costume_project_id(session: Session, costume_id: str) -> str:
    costume = session.get(Costume, costume_id)
    if costume is None:
        raise HTTPException(status_code=404, detail="服装不存在。")
    return character_project_id(session, costume.character_id)


def scene_project_id(session: Session, scene_id: str) -> str:
    _, _, project = _scene_with_project(session, scene_id)
    return project.id


def scene_asset_project_id(session: Session, scene_asset_id: str) -> str:
    scene_asset = session.get(SceneAsset, scene_asset_id)
    if scene_asset is None:
        raise HTTPException(status_code=404, detail="场景资产不存在。")
    return scene_project_id(session, scene_asset.scene_id)


def prop_project_id(session: Session, prop_id: str) -> str:
    prop = session.get(PropAsset, prop_id)
    if prop is None:
        raise HTTPException(status_code=404, detail="道具不存在。")
    return prop.project_id


def asset_version_project_id(session: Session, kind: VersionKind, version_id: str) -> str:
    if kind == "character-master":
        version = session.get(CharacterMasterVersion, version_id)
        if version is None:
            raise HTTPException(status_code=404, detail="人物母版版本不存在。")
        return character_project_id(session, version.character_id)
    if kind == "costume":
        version = session.get(CostumeVersion, version_id)
        if version is None:
            raise HTTPException(status_code=404, detail="服装版本不存在。")
        return costume_project_id(session, version.costume_id)
    if kind == "scene":
        version = session.get(SceneAssetVersion, version_id)
        if version is None:
            raise HTTPException(status_code=404, detail="场景版本不存在。")
        return scene_asset_project_id(session, version.scene_asset_id)
    if kind == "prop":
        version = session.get(PropAssetVersion, version_id)
        if version is None:
            raise HTTPException(status_code=404, detail="道具版本不存在。")
        return prop_project_id(session, version.prop_asset_id)
    raise HTTPException(status_code=400, detail="不支持该资产版本类型。")


def _scene_with_project(session: Session, scene_id: str) -> tuple[Scene, Episode, Project]:
    scene = session.get(Scene, scene_id)
    if scene is None:
        raise HTTPException(status_code=404, detail="场不存在。")
    episode = session.get(Episode, scene.episode_id)
    if episode is None:
        raise HTTPException(status_code=404, detail="集不存在。")
    return scene, episode, get_project(session, episode.project_id)


def _scope_code(episode: Episode, scene: Scene) -> str:
    return f"{episode.episode_code}{scene.scene_code}"


def _asset_url(project: Project, asset_path: str) -> str:
    return f"/local-assets/{quote(project.project_code)}/{quote(asset_path)}"


def _next_version(values: list[int]) -> int:
    return max(values, default=0) + 1


def _active_version(versions: list[VersionModel]) -> VersionModel | None:
    return next(
        (version for version in versions if version.status in {"confirmed_current", "locked"}),
        None,
    )


def create_character(
    session: Session,
    project_id: str,
    payload: CharacterCreate,
) -> Character:
    project = get_project(session, project_id)
    codes = list(
        session.exec(
            select(Character.character_code).where(Character.project_id == project.id)
        ).all()
    )
    character = Character(
        project_id=project.id,
        character_code=_next_code(codes, "CH", 2),
        **payload.model_dump(),
    )
    session.add(character)
    session.commit()
    session.refresh(character)
    return character


def create_costume(session: Session, character_id: str, payload: CostumeCreate) -> Costume:
    character = session.get(Character, character_id)
    if character is None:
        raise HTTPException(status_code=404, detail="人物不存在。")
    codes = list(
        session.exec(
            select(Costume.costume_code).where(Costume.character_id == character.id)
        ).all()
    )
    costume = Costume(
        character_id=character.id,
        costume_code=_next_code(codes, "C", 2),
        **payload.model_dump(),
    )
    session.add(costume)
    session.commit()
    session.refresh(costume)
    return costume


def upsert_scene_asset(
    session: Session,
    scene_id: str,
    payload: SceneAssetCreate,
) -> SceneAsset:
    scene, _, _ = _scene_with_project(session, scene_id)
    scene_asset = session.exec(
        select(SceneAsset).where(
            SceneAsset.scene_id == scene.id,
            SceneAsset.name == payload.name.strip(),
        )
    ).first()
    if scene_asset is None:
        scene_asset = SceneAsset(scene_id=scene.id, **payload.model_dump())
    else:
        for key, value in payload.model_dump().items():
            setattr(scene_asset, key, value)
        scene_asset.updated_at = utc_now()
    session.add(scene_asset)
    session.commit()
    session.refresh(scene_asset)
    return scene_asset


def _normalize_asset_image_status(status: str | None, image_url: str | None = None) -> str:
    value = str(status or "").strip().lower().replace("-", "_").replace(" ", "_")
    if value in {"downloaded", "imported"}:
        return "downloaded"
    if value in {"completed", "complete", "success", "succeeded", "done", "finished"}:
        return "completed"
    if value in {"failed", "failure", "error", "cancelled", "canceled"}:
        return "failed"
    if value in {"processing", "running", "generating", "in_progress"}:
        return "processing"
    if value in {"submitted", "pending", "queued", "waiting", "created", ""}:
        return "completed" if image_url else "submitted"
    return "completed" if image_url else value


def _asset_image_job_view(job: ImageGenerationJob, project: Project) -> AssetImageJobView:
    return AssetImageJobView(
        id=job.id,
        project_id=job.project_id,
        target_type=job.target_type,
        target_id=job.target_id,
        provider=job.provider,
        model_name=job.model_name,
        external_task_id=job.external_task_id,
        status=_normalize_asset_image_status(job.status, job.remote_result_url),
        remote_result_url=job.remote_result_url,
        image_url=_asset_url(project, job.result_image_path) if job.result_image_path else None,
        error_message=job.error_message,
        created_at=job.created_at,
    )


def list_asset_image_jobs(
    session: Session,
    project_id: str,
) -> list[AssetImageJobView]:
    project = get_project(session, project_id)
    jobs = list(
        session.exec(
            select(ImageGenerationJob)
            .where(ImageGenerationJob.project_id == project.id)
            .where(
                ImageGenerationJob.target_type.in_(
                    ["character-master", "costume", "scene", "prop"]
                )
            )
            .order_by(ImageGenerationJob.created_at.desc())
        ).all()
    )
    return [_asset_image_job_view(job, project) for job in jobs]


def _asset_image_context(
    session: Session,
    kind: AssetImageTargetKind,
    target_id: str,
) -> tuple[str, str, Project, object]:
    if kind == "character-master":
        character = session.get(Character, target_id)
        if character is None:
            raise HTTPException(status_code=404, detail="人物不存在。")
        return "人物基础图", character.id, get_project(session, character.project_id), character
    if kind == "costume":
        costume = session.get(Costume, target_id)
        if costume is None:
            raise HTTPException(status_code=404, detail="服装不存在。")
        character = session.get(Character, costume.character_id)
        return "服装图", costume.id, get_project(session, character.project_id), costume
    if kind == "scene":
        scene_asset = session.get(SceneAsset, target_id)
        if scene_asset is None:
            raise HTTPException(status_code=404, detail="场景资产不存在。")
        return "场景设定图", scene_asset.id, get_project(session, scene_project_id(session, scene_asset.scene_id)), scene_asset
    if kind == "prop":
        prop = session.get(PropAsset, target_id)
        if prop is None:
            raise HTTPException(status_code=404, detail="道具不存在。")
        return "道具资产图", prop.id, get_project(session, prop.project_id), prop
    raise HTTPException(status_code=400, detail="不支持该资产图片类型。")


def _costume_active_master(session: Session, costume: Costume) -> CharacterMasterVersion | None:
    character = session.get(Character, costume.character_id)
    master_versions = list(
        session.exec(
            select(CharacterMasterVersion)
            .where(CharacterMasterVersion.character_id == character.id)
            .order_by(CharacterMasterVersion.version_number.desc())
        ).all()
    )
    return _active_version(master_versions)


def asset_image_readiness(
    session: Session,
    settings: Settings,
    kind: AssetImageTargetKind,
    target_id: str,
) -> AssetImageReadinessView:
    asset_type, _, _, target = _asset_image_context(session, kind, target_id)
    gates = [
        AssetImageGateItem(
            label="已开启真实生图闸门",
            passed=settings.enable_real_image_generation,
            detail="在设置页开启“真实生图逐次确认”后才允许发起生图请求。",
        ),
        AssetImageGateItem(
            label="生图服务 Key 已配置",
            passed=bool(settings.image_api_key),
            detail="密钥只读取本机 .env，接口不会返回密钥正文。",
        ),
        AssetImageGateItem(
            label="生图模型已填写",
            passed=bool(settings.image_model.strip()),
            detail=settings.image_model or "请填写要使用的生图模型 ID。",
        ),
    ]
    if settings.image_provider_mode == "openai_images":
        gates.append(
            AssetImageGateItem(
                label="生图服务地址已填写",
                passed=bool(settings.image_base_url.strip()),
                detail=settings.image_base_url or "请填写即时生图 API 的 Base URL。",
            )
        )
    if kind == "costume":
        master = _costume_active_master(session, target)  # type: ignore[arg-type]
        gates.append(
            AssetImageGateItem(
                label="已有确认人物基础图",
                passed=master is not None,
                detail="服装图必须基于已确认的人物基础图，避免换衣服时把人换掉。",
            )
        )
    instant_mode = settings.image_provider_mode == "openai_images"
    provider_label = f"{settings.image_model}（即时 API）" if instant_mode else f"慧梦 {settings.huimengi_image_model}"
    return AssetImageReadinessView(
        ready=all(item.passed for item in gates),
        asset_type=asset_type,
        provider_name=provider_label,
        model_id=settings.image_model if instant_mode else settings.huimengi_image_model,
        gate_items=gates,
        risk_notice="这一步只生成当前资产的一张图片，不生成视频；提交前请人工核对生图服务的价格。",
        requires_user_confirmation=True,
    )


def _asset_image_prompt(
    session: Session,
    kind: AssetImageTargetKind,
    target: object,
) -> str:
    requirement = session.exec(
        select(AssetRequirement)
        .where(
            AssetRequirement.target_id == target.id,
            AssetRequirement.is_current == True,  # noqa: E712
        )
        .order_by(AssetRequirement.updated_at.desc())
    ).first()
    confirmed_visual_prompt = requirement.visual_prompt.strip() if requirement else ""

    def with_confirmed_requirement(base_prompt: str) -> str:
        if not confirmed_visual_prompt:
            return base_prompt
        return (
            f"{base_prompt}\n\n"
            "本次已确认的视觉要求（优先执行，不得被通用模板覆盖）：\n"
            f"{confirmed_visual_prompt}"
        )

    if kind == "character-master":
        character = target
        return with_confirmed_requirement(
            "生成影视项目前期使用的高端杂志化真人角色资产 Bible 设定卡。\n"
            "唯一风格：米白/奶油白/浅暖灰背景，真人写实质感，影视角色资产板排版。\n"
            "画面必须包含：主肖像、全身多角度视图、动作姿态参考、表情研究、发型细节、面部细节、服装材质、饰品细节、道具参考、配色参考和整体气质说明。\n"
            "禁止：二次元、卡通、概念草图式人物卡、简陋设定板、海报字、多人物、改变年龄和身份气质。\n"
            f"角色名：{character.name}\n"
            f"脸型：{character.face_shape}\n"
            f"五官：{character.facial_features}\n"
            f"年龄：{character.age_description}\n"
            f"身高体型：{character.height_description}，{character.body_type}\n"
            f"发型：{character.hair_style}\n"
            f"身份气质：{character.identity_temperament}"
        )
    if kind == "costume":
        costume = target
        character = session.get(Character, costume.character_id)
        return with_confirmed_requirement(
            "生成影视项目前期使用的真人角色服装资产板，风格与人物角色资产 Bible 保持一致：米白/奶油白/浅暖灰背景，高端杂志化真人写实质感。\n"
            "画面重点：服装正背侧视图、面料纹理、层次结构、饰品细节、穿着姿态和角色气质延续。核心要求：只换服装，不换人。\n"
            "严格保持人物的脸、年龄、骨相、体型、身高、发型和身份气质；不要把角色变成另一个人。\n"
            "禁止：二次元、卡通、概念草图式服装板、简陋设定板、海报字。\n"
            f"角色：{character.name}\n"
            f"角色固定特征：{character.face_shape}；{character.facial_features}；{character.age_description}；{character.body_type}；{character.hair_style}；{character.identity_temperament}\n"
            f"服装使用场合：{costume.usage_context}\n"
            f"服装说明：{costume.description or '按场合设计，但保持角色身份。'}"
        )
    if kind == "prop":
        prop = target
        return with_confirmed_requirement(
            "生成影视项目前期使用的写实道具资产图，纯净浅灰背景，清楚展示正面、侧面、背面、材质、磨损和关键细节。\n"
            "画面只保留一个道具，不要人物，不要场景，不要海报字；造型必须符合剧情年代、用途和叙事功能。\n"
            f"道具名称：{prop.name}\n"
            f"分类：{prop.category}\n"
            f"剧情说明：{prop.description}\n"
            f"外观细节：{prop.visual_details}"
        )
    scene_asset = target
    scene, episode, _ = _scene_with_project(session, scene_asset.scene_id)
    return with_confirmed_requirement(
        "生成影视项目前期使用的场景设定图，强调空间关系、光线、道具和可拍摄性。\n"
        "要求：电影感、写实、清晰空间布局、不要海报字、不要人物抢戏。\n"
        f"场次：{episode.episode_code}{scene.scene_code}｜{scene.name}\n"
        f"场景说明：{scene_asset.description}\n"
        f"空间布局：{scene_asset.spatial_layout}\n"
        f"时间/天气/光线：{scene_asset.time_weather_light}\n"
        f"关键道具：{scene_asset.key_props}\n"
        f"主色/氛围：{scene_asset.palette_mood}"
    )


def submit_asset_image_job(
    session: Session,
    settings: Settings,
    kind: AssetImageTargetKind,
    target_id: str,
    confirm_live_request: bool,
) -> AssetImageJobView:
    readiness = asset_image_readiness(session, settings, kind, target_id)
    if not readiness.ready:
        missing = "；".join(item.label for item in readiness.gate_items if not item.passed)
        raise HTTPException(status_code=409, detail=f"还不能真实生图：{missing}")
    if not confirm_live_request:
        raise HTTPException(status_code=409, detail="真实生图必须由你在页面逐次确认。")
    _, normalized_target_id, project, target = _asset_image_context(session, kind, target_id)
    prompt = _asset_image_prompt(session, kind, target)
    if settings.image_provider_mode == "openai_images":
        instant = OpenAIImagesProvider()
        try:
            image_bytes, raw, request_payload = instant.generate_image(
                settings.image_base_url,
                settings.image_api_key,
                settings.image_model,
                prompt,
            )
        except Exception as cause:
            raise HTTPException(status_code=502, detail=f"图片生成失败：{cause}") from cause
        job = ImageGenerationJob(
            project_id=project.id,
            target_type=kind,
            target_id=normalized_target_id,
            provider="openai_images",
            model_name=settings.image_model,
            prompt=prompt,
            request_json=json.dumps(request_payload, ensure_ascii=False),
            response_snapshot_json=json.dumps(raw, ensure_ascii=False),
            external_task_id="",
            remote_result_url="",
            status="downloaded",
        )
        session.add(job)
        session.flush()
        _save_asset_image_as_new_version(session, settings.projects_root, project, job, image_bytes)
        job.updated_at = utc_now()
        session.add(job)
        session.commit()
        session.refresh(job)
        return _asset_image_job_view(job, project)
    provider = HuimengImageProvider()
    try:
        normalized, raw, request_payload = provider.submit_task(
            settings.huimengi_image_base_url,
            settings.huimengi_api_key,
            settings.huimengi_image_model,
            prompt,
            ratio="16:9",
            quality="medium",
            resolution="2k",
        )
    except Exception as cause:  # pragma: no cover
        raise HTTPException(status_code=502, detail=f"慧梦生图提交失败：{cause}") from cause
    job = ImageGenerationJob(
        project_id=project.id,
        target_type=kind,
        target_id=normalized_target_id,
        provider="huimeng_image",
        model_name=settings.huimengi_image_model,
        prompt=prompt,
        request_json=json.dumps(request_payload, ensure_ascii=False),
        response_snapshot_json=json.dumps(raw, ensure_ascii=False),
        external_task_id=str(normalized.get("task_id") or ""),
        remote_result_url=str(normalized.get("image_url") or ""),
        status=_normalize_asset_image_status(
            str(normalized.get("status") or "submitted"),
            str(normalized.get("image_url") or ""),
        ),
        error_message=str(normalized.get("error_message") or ""),
    )
    session.add(job)
    session.commit()
    session.refresh(job)
    return _asset_image_job_view(job, project)


def poll_asset_image_job(
    session: Session,
    settings: Settings,
    job_id: str,
    confirm_live_request: bool,
) -> AssetImageJobView:
    if not confirm_live_request:
        raise HTTPException(status_code=409, detail="查询真实生图任务也需要页面确认，避免误触发外部请求。")
    job = session.get(ImageGenerationJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="生图任务不存在。")
    project = get_project(session, job.project_id)
    if job.target_type not in {"character-master", "costume", "scene", "prop"}:
        raise HTTPException(status_code=400, detail="这不是资产生图任务。")
    if not settings.huimengi_api_key:
        raise HTTPException(status_code=409, detail="慧梦 Key 未配置。")
    if not job.external_task_id:
        raise HTTPException(status_code=409, detail="该生图任务缺少外部任务 ID，无法查询。")
    provider = HuimengImageProvider()
    try:
        normalized, raw = provider.poll_task(
            settings.huimengi_image_base_url,
            settings.huimengi_api_key,
            job.external_task_id,
        )
    except Exception as cause:  # pragma: no cover
        raise HTTPException(status_code=502, detail=f"慧梦生图查询失败：{cause}") from cause
    job.remote_result_url = str(normalized.get("image_url") or job.remote_result_url)
    job.status = _normalize_asset_image_status(
        str(normalized.get("status") or job.status),
        job.remote_result_url,
    )
    job.error_message = str(normalized.get("error_message") or "")
    job.response_snapshot_json = json.dumps(raw, ensure_ascii=False)
    job.updated_at = utc_now()
    session.add(job)
    session.commit()
    session.refresh(job)
    return _asset_image_job_view(job, project)


def _save_downloaded_asset_image(image_bytes: bytes, target_path: Path) -> None:
    target_path.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(BytesIO(image_bytes)) as image:
        image.convert("RGB").save(target_path, "PNG")


def upload_asset_image_file(
    session: Session,
    projects_root: Path,
    kind: AssetImageTargetKind,
    target_id: str,
    filename: str,
    image_bytes: bytes,
) -> AssetWorkspaceView:
    if not image_bytes:
        raise HTTPException(status_code=400, detail="没有收到图片文件。")
    if len(image_bytes) > ASSET_UPLOAD_MAX_BYTES:
        raise HTTPException(status_code=413, detail="单张资产图不能超过 25 MB。")
    suffix = Path(filename or "").suffix.lower()
    if suffix not in ASSET_UPLOAD_EXTENSIONS:
        raise HTTPException(status_code=400, detail="资产图只支持 PNG / JPG / JPEG / WEBP。")

    _, _, project, target = _asset_image_context(session, kind, target_id)
    try:
        with Image.open(BytesIO(image_bytes)) as image:
            normalized = BytesIO()
            image.convert("RGB").save(normalized, "PNG")
            normalized_bytes = normalized.getvalue()
    except Exception as cause:
        raise HTTPException(status_code=400, detail="无法读取这张图片，请换一张 PNG / JPG / WEBP。") from cause

    if kind == "character-master":
        character = target
        values = list(
            session.exec(
                select(CharacterMasterVersion.version_number).where(
                    CharacterMasterVersion.character_id == character.id
                )
            ).all()
        )
        number = _next_version(values)
        asset_path = (
            f"02_characters/masters/{character.character_code}/"
            f"{character.character_code}_master_upload_v{number:03d}.png"
        )
        _save_downloaded_asset_image(normalized_bytes, _project_root(projects_root, project) / asset_path)
        session.add(CharacterMasterVersion(character_id=character.id, version_number=number, asset_path=asset_path))
    elif kind == "costume":
        costume = target
        character = session.get(Character, costume.character_id)
        master = _costume_active_master(session, costume)
        if master is None:
            raise HTTPException(status_code=409, detail="上传服装图前，请先确认人物基础图。")
        values = list(
            session.exec(
                select(CostumeVersion.version_number).where(CostumeVersion.costume_id == costume.id)
            ).all()
        )
        number = _next_version(values)
        asset_path = (
            f"02_characters/costumes/{character.character_code}/{costume.costume_code}/"
            f"{character.character_code}_{costume.costume_code}_upload_v{number:03d}.png"
        )
        _save_downloaded_asset_image(normalized_bytes, _project_root(projects_root, project) / asset_path)
        session.add(CostumeVersion(
            costume_id=costume.id,
            character_master_version_id=master.id,
            version_number=number,
            asset_path=asset_path,
        ))
    elif kind == "scene":
        scene_asset = target
        scene, episode, _ = _scene_with_project(session, scene_asset.scene_id)
        values = list(
            session.exec(
                select(SceneAssetVersion.version_number).where(
                    SceneAssetVersion.scene_asset_id == scene_asset.id
                )
            ).all()
        )
        number = _next_version(values)
        scope = _scope_code(episode, scene)
        asset_path = (
            f"03_scenes/{scope}/{scene_asset.id}/"
            f"scene_asset_upload_v{number:03d}.png"
        )
        _save_downloaded_asset_image(normalized_bytes, _project_root(projects_root, project) / asset_path)
        session.add(SceneAssetVersion(scene_asset_id=scene_asset.id, version_number=number, asset_path=asset_path))
    else:
        prop = target
        values = list(
            session.exec(
                select(PropAssetVersion.version_number).where(
                    PropAssetVersion.prop_asset_id == prop.id
                )
            ).all()
        )
        number = _next_version(values)
        asset_path = f"04_props/{prop.prop_code}/{prop.prop_code}_upload_v{number:03d}.png"
        _save_downloaded_asset_image(normalized_bytes, _project_root(projects_root, project) / asset_path)
        session.add(PropAssetVersion(prop_asset_id=prop.id, version_number=number, asset_path=asset_path))

    session.commit()
    return asset_workspace(session, project.id)


def download_asset_image_job(
    session: Session,
    settings: Settings,
    projects_root: Path,
    job_id: str,
    confirm_live_request: bool,
) -> AssetWorkspaceView:
    if not confirm_live_request:
        raise HTTPException(status_code=409, detail="下载真实生图结果必须由你在页面逐次确认。")
    job = session.get(ImageGenerationJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="生图任务不存在。")
    if job.target_type not in {"character-master", "costume", "scene", "prop"}:
        raise HTTPException(status_code=400, detail="这不是资产生图任务。")
    project = get_project(session, job.project_id)
    if job.result_image_path and (_project_root(projects_root, project) / job.result_image_path).is_file():
        if job.status != "downloaded":
            job.status = "downloaded"
            job.updated_at = utc_now()
            session.add(job)
            session.commit()
        return asset_workspace(session, project.id)
    if (
        _normalize_asset_image_status(job.status, job.remote_result_url) != "completed"
        or not job.remote_result_url
    ):
        raise HTTPException(status_code=409, detail="生图任务尚未完成，不能下载结果。")
    provider = HuimengImageProvider()
    image_bytes = download_image_with_url_refresh(session, settings, job, provider)
    _save_asset_image_as_new_version(session, projects_root, project, job, image_bytes)
    job.status = "downloaded"
    job.updated_at = utc_now()
    session.add(job)
    session.commit()
    return asset_workspace(session, project.id)


def _save_asset_image_as_new_version(
    session: Session,
    projects_root: Path,
    project: Project,
    job: ImageGenerationJob,
    image_bytes: bytes,
) -> str:
    if job.target_type == "character-master":
        character = session.get(Character, job.target_id)
        values = list(
            session.exec(
                select(CharacterMasterVersion.version_number).where(
                    CharacterMasterVersion.character_id == character.id
                )
            ).all()
        )
        number = _next_version(values)
        asset_path = (
            f"02_characters/masters/{character.character_code}/"
            f"{character.character_code}_master_real_v{number:03d}.png"
        )
        _save_downloaded_asset_image(image_bytes, _project_root(projects_root, project) / asset_path)
        session.add(CharacterMasterVersion(character_id=character.id, version_number=number, asset_path=asset_path))
    elif job.target_type == "costume":
        costume = session.get(Costume, job.target_id)
        character = session.get(Character, costume.character_id)
        master = _costume_active_master(session, costume)
        if master is None:
            raise HTTPException(status_code=409, detail="下载服装图前需要已确认人物基础图。")
        values = list(
            session.exec(
                select(CostumeVersion.version_number).where(CostumeVersion.costume_id == costume.id)
            ).all()
        )
        number = _next_version(values)
        asset_path = (
            f"02_characters/costumes/{character.character_code}/{costume.costume_code}/"
            f"{character.character_code}_{costume.costume_code}_real_v{number:03d}.png"
        )
        _save_downloaded_asset_image(image_bytes, _project_root(projects_root, project) / asset_path)
        session.add(CostumeVersion(
            costume_id=costume.id,
            character_master_version_id=master.id,
            version_number=number,
            asset_path=asset_path,
        ))
    elif job.target_type == "scene":
        scene_asset = session.get(SceneAsset, job.target_id)
        scene, episode, _ = _scene_with_project(session, scene_asset.scene_id)
        values = list(
            session.exec(
                select(SceneAssetVersion.version_number).where(
                    SceneAssetVersion.scene_asset_id == scene_asset.id
                )
            ).all()
        )
        number = _next_version(values)
        scope = _scope_code(episode, scene)
        asset_path = (
            f"03_scenes/{scope}/{scene_asset.id}/"
            f"scene_asset_real_v{number:03d}.png"
        )
        _save_downloaded_asset_image(image_bytes, _project_root(projects_root, project) / asset_path)
        session.add(SceneAssetVersion(scene_asset_id=scene_asset.id, version_number=number, asset_path=asset_path))
    else:
        prop = session.get(PropAsset, job.target_id)
        values = list(
            session.exec(
                select(PropAssetVersion.version_number).where(
                    PropAssetVersion.prop_asset_id == prop.id
                )
            ).all()
        )
        number = _next_version(values)
        asset_path = f"04_props/{prop.prop_code}/{prop.prop_code}_real_v{number:03d}.png"
        _save_downloaded_asset_image(image_bytes, _project_root(projects_root, project) / asset_path)
        session.add(PropAssetVersion(prop_asset_id=prop.id, version_number=number, asset_path=asset_path))

    job.result_image_path = asset_path
    return asset_path


def upsert_binding(
    session: Session,
    scene_id: str,
    payload: BindingCreate,
) -> SceneCharacterBinding:
    scene, _, project = _scene_with_project(session, scene_id)
    character = session.get(Character, payload.character_id)
    master = session.get(CharacterMasterVersion, payload.character_master_version_id)
    costume_version = session.get(CostumeVersion, payload.costume_version_id)
    if character is None or character.project_id != project.id:
        raise HTTPException(status_code=400, detail="人物不属于当前项目。")
    if (
        master is None
        or master.character_id != character.id
        or master.status not in {"confirmed_current", "locked"}
    ):
        raise HTTPException(status_code=409, detail="请选择已确认或锁定的人物母版。")
    costume = session.get(Costume, costume_version.costume_id) if costume_version else None
    if (
        costume_version is None
        or costume is None
        or costume.character_id != character.id
        or costume_version.status not in {"confirmed_current", "locked"}
    ):
        raise HTTPException(status_code=409, detail="请选择已确认或锁定的本场服装。")
    if costume_version.character_master_version_id != master.id:
        raise HTTPException(status_code=409, detail="服装版本与人物母版版本不一致。")

    binding = session.exec(
        select(SceneCharacterBinding).where(
            SceneCharacterBinding.scene_id == scene.id,
            SceneCharacterBinding.character_id == character.id,
        )
    ).first()
    if binding is None:
        binding = SceneCharacterBinding(
            scene_id=scene.id,
            character_id=character.id,
            character_master_version_id=master.id,
            costume_version_id=costume_version.id,
        )
    binding.character_master_version_id = master.id
    binding.costume_version_id = costume_version.id
    binding.scene_state = payload.scene_state.strip()
    binding.hair_change_reason = payload.hair_change_reason.strip()
    binding.consistency_status = "passed"
    binding.consistency_notes = "人物母版与服装版本已绑定；故事板与视频包阶段会继续执行引用检查。"
    binding.updated_at = utc_now()
    session.add(binding)
    session.commit()
    session.refresh(binding)
    return binding


def transition_version(
    session: Session,
    kind: VersionKind,
    version_id: str,
    action: Literal["confirm", "lock", "unlock", "rollback"],
) -> None:
    if kind not in {"character-master", "costume", "scene", "prop"}:
        raise HTTPException(status_code=400, detail="不支持该资产版本类型。")
    if action not in {"confirm", "lock", "unlock", "rollback"}:
        raise HTTPException(status_code=400, detail="不支持该版本操作。")
    model, owner_field = {
        "character-master": (CharacterMasterVersion, "character_id"),
        "costume": (CostumeVersion, "costume_id"),
        "scene": (SceneAssetVersion, "scene_asset_id"),
        "prop": (PropAssetVersion, "prop_asset_id"),
    }[kind]
    version = session.get(model, version_id)
    if version is None:
        raise HTTPException(status_code=404, detail="资产版本不存在。")
    owner_id = getattr(version, owner_field)
    siblings = list(
        session.exec(
            select(model)
            .where(getattr(model, owner_field) == owner_id)
            .order_by(model.version_number)
        ).all()
    )
    locked = next((item for item in siblings if item.status == "locked"), None)
    if locked is not None and locked.id != version.id:
        raise HTTPException(status_code=409, detail="已有锁定版本，不能切换当前版。")
    if action == "unlock":
        if version.status != "locked":
            raise HTTPException(status_code=409, detail="该版本没有锁定，无需解锁。")
        version.status = "confirmed_current"
    elif action == "lock":
        version.status = "locked"
    else:
        for sibling in siblings:
            if sibling.id != version.id and sibling.status == "confirmed_current":
                sibling.status = "confirmed_history"
                sibling.updated_at = utc_now()
                session.add(sibling)
        if version.status != "locked":
            version.status = "confirmed_current"
    version.updated_at = utc_now()
    session.add(version)
    session.commit()


def _version_view(project: Project, version: VersionModel) -> AssetVersionView:
    return AssetVersionView(
        id=version.id,
        version_number=version.version_number,
        asset_path=version.asset_path,
        asset_url=_asset_url(project, version.asset_path),
        status=version.status,
        created_at=version.created_at,
    )


def _binding_view(
    session: Session,
    project: Project,
    binding: SceneCharacterBinding,
) -> BindingView:
    scene, episode, _ = _scene_with_project(session, binding.scene_id)
    character = session.get(Character, binding.character_id)
    master = session.get(CharacterMasterVersion, binding.character_master_version_id)
    costume_version = session.get(CostumeVersion, binding.costume_version_id)
    costume = session.get(Costume, costume_version.costume_id)
    hair_ok = "发" not in binding.scene_state or bool(binding.hair_change_reason)
    scene_shots = list(session.exec(select(Shot).where(Shot.scene_id == scene.id)).all())
    storyboard_ok = any(
        version.status in {"confirmed_current", "locked"}
        and version.style_validation_status == "passed"
        and version.axis_validation_status == "passed"
        for shot in scene_shots
        for version in session.exec(
            select(StoryboardShotVersion).where(StoryboardShotVersion.shot_id == shot.id)
        ).all()
    )
    checks = [
        ConsistencyCheckView(key="master", label="人物母版已确认", status="passed", detail=f"V{master.version_number:03d}"),
        ConsistencyCheckView(key="costume", label="本场服装已确认", status="passed", detail=f"{costume.costume_code} V{costume_version.version_number:03d}"),
        ConsistencyCheckView(key="identity", label="年龄 / 体型 / 身高锁定", status="passed", detail="服装派生保留身份特征"),
        ConsistencyCheckView(
            key="hair",
            label="发型未改变，或已填写变化原因",
            status="passed" if hair_ok else "failed",
            detail=binding.hair_change_reason or "未登记发型变化",
        ),
        ConsistencyCheckView(
            key="storyboard",
            label="故事板与视频块已关联资产 ID",
            status="passed" if storyboard_ok else "pending",
            detail="已存在风格与轴线通过的确认故事板" if storyboard_ok else "等待确认故事板",
        ),
    ]
    return BindingView(
        id=binding.id,
        scene_id=scene.id,
        scope_code=_scope_code(episode, scene),
        character_id=character.id,
        character_name=character.name,
        character_master_version_id=master.id,
        character_master_version_number=master.version_number,
        costume_version_id=costume_version.id,
        costume_code=costume.costume_code,
        costume_version_number=costume_version.version_number,
        scene_state=binding.scene_state,
        hair_change_reason=binding.hair_change_reason,
        consistency_status="passed" if hair_ok else "failed",
        checks=checks,
    )


def asset_workspace(session: Session, project_id: str) -> AssetWorkspaceView:
    project = get_project(session, project_id)
    characters = list(
        session.exec(
            select(Character)
            .where(Character.project_id == project.id)
            .order_by(Character.character_code)
        ).all()
    )
    character_views: list[CharacterView] = []
    for character in characters:
        master_versions = list(
            session.exec(
                select(CharacterMasterVersion)
                .where(CharacterMasterVersion.character_id == character.id)
                .order_by(CharacterMasterVersion.version_number.desc())
            ).all()
        )
        costumes = list(
            session.exec(
                select(Costume)
                .where(Costume.character_id == character.id)
                .order_by(Costume.costume_code)
            ).all()
        )
        costume_views: list[CostumeView] = []
        for costume in costumes:
            versions = list(
                session.exec(
                    select(CostumeVersion)
                    .where(CostumeVersion.costume_id == costume.id)
                    .order_by(CostumeVersion.version_number.desc())
                ).all()
            )
            costume_views.append(
                CostumeView(
                    **costume.model_dump(),
                    versions=[_version_view(project, version) for version in versions],
                )
            )
        character_views.append(
            CharacterView(
                **character.model_dump(),
                master_versions=[
                    _version_view(project, version) for version in master_versions
                ],
                costumes=costume_views,
            )
        )

    episodes = list(
        session.exec(
            select(Episode)
            .where(Episode.project_id == project.id)
            .order_by(Episode.episode_code)
        ).all()
    )
    scene_summaries: list[SceneSummaryView] = []
    scene_asset_views: list[SceneAssetView] = []
    for episode in episodes:
        scenes = list(
            session.exec(
                select(Scene)
                .where(Scene.episode_id == episode.id)
                .order_by(Scene.scene_code)
            ).all()
        )
        for scene in scenes:
            scope = _scope_code(episode, scene)
            scene_summaries.append(
                SceneSummaryView(
                    id=scene.id,
                    scope_code=scope,
                    scene_code=scene.scene_code,
                    name=scene.name,
                )
            )
            scene_assets = list(
                session.exec(
                    select(SceneAsset)
                    .where(SceneAsset.scene_id == scene.id)
                    .order_by(SceneAsset.created_at)
                ).all()
            )
            for scene_asset in scene_assets:
                versions = list(
                    session.exec(
                        select(SceneAssetVersion)
                        .where(SceneAssetVersion.scene_asset_id == scene_asset.id)
                        .order_by(SceneAssetVersion.version_number.desc())
                    ).all()
                )
                scene_asset_views.append(
                    SceneAssetView(
                        **scene_asset.model_dump(),
                        scope_code=scope,
                        scene_name=scene.name,
                        versions=[_version_view(project, version) for version in versions],
                    )
                )

    bindings = list(
        session.exec(
            select(SceneCharacterBinding).order_by(SceneCharacterBinding.created_at)
        ).all()
    )
    scope_by_scene_id = {scene.id: scene.scope_code for scene in scene_summaries}
    requirements = list(
        session.exec(
            select(AssetRequirement)
            .where(
                AssetRequirement.project_id == project.id,
                AssetRequirement.is_current == True,  # noqa: E712
            )
            .order_by(AssetRequirement.asset_type, AssetRequirement.created_at)
        ).all()
    )
    requirement_views: list[AssetRequirementView] = []
    for requirement in requirements:
        try:
            scene_ids = list(json.loads(requirement.scene_ids_json or "[]"))
        except (TypeError, ValueError):
            scene_ids = []
        requirement_views.append(
            AssetRequirementView(
                id=requirement.id,
                inventory_version=requirement.inventory_version,
                asset_type=requirement.asset_type,
                name=requirement.name,
                description=requirement.description,
                visual_prompt=requirement.visual_prompt,
                reference_mode=requirement.reference_mode if requirement.reference_mode in {"visual", "text_only"} else "visual",
                importance_reason=requirement.importance_reason,
                text_prompt=requirement.text_prompt,
                evidence=requirement.evidence,
                scene_ids=scene_ids,
                scene_scope_codes=[scope_by_scene_id[item] for item in scene_ids if item in scope_by_scene_id],
                target_id=requirement.target_id,
                status=requirement.status,
            )
        )

    props = list(
        session.exec(
            select(PropAsset)
            .where(PropAsset.project_id == project.id)
            .order_by(PropAsset.prop_code)
        ).all()
    )
    prop_views: list[PropAssetView] = []
    for prop in props:
        versions = list(
            session.exec(
                select(PropAssetVersion)
                .where(PropAssetVersion.prop_asset_id == prop.id)
                .order_by(PropAssetVersion.version_number.desc())
            ).all()
        )
        prop_views.append(
            PropAssetView(
                **prop.model_dump(),
                versions=[_version_view(project, version) for version in versions],
            )
        )

    prop_bindings = list(session.exec(select(ScenePropBinding)).all())
    prop_binding_views: list[PropBindingView] = []
    prop_by_id = {item.id: item for item in props}
    for binding in prop_bindings:
        prop = prop_by_id.get(binding.prop_asset_id)
        version = session.get(PropAssetVersion, binding.prop_asset_version_id)
        if prop is None or version is None or binding.scene_id not in scope_by_scene_id:
            continue
        prop_binding_views.append(
            PropBindingView(
                id=binding.id,
                scene_id=binding.scene_id,
                scope_code=scope_by_scene_id[binding.scene_id],
                prop_asset_id=prop.id,
                prop_name=prop.name,
                prop_asset_version_id=version.id,
                prop_version_number=version.version_number,
                usage_note=binding.usage_note,
            )
        )
    return AssetWorkspaceView(
        project_id=project.id,
        project_code=project.project_code,
        characters=character_views,
        scenes=scene_summaries,
        scene_assets=scene_asset_views,
        bindings=[
            _binding_view(session, project, binding)
            for binding in bindings
            if session.get(Character, binding.character_id).project_id == project.id
        ],
        requirements=requirement_views,
        props=prop_views,
        prop_bindings=prop_binding_views,
    )
