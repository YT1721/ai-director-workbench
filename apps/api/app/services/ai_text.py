from __future__ import annotations

import hashlib
import json
from uuid import uuid4

from fastapi import HTTPException
from sqlmodel import Session, select

from app.config import Settings
from app.models import (
    AiTextRun,
    Character,
    CharacterMasterVersion,
    CostUsageLog,
    Costume,
    CostumeVersion,
    Episode,
    PlanningDraft,
    PlanningDraftItem,
    Project,
    RequestCacheRecord,
    Scene,
    SceneAsset,
    SceneAssetVersion,
    SceneCharacterBinding,
    Shot,
    SourceTextExtraction,
    StoryboardShotVersion,
    VpBlock,
    WorkflowCheckReport,
)
from app.providers import (
    HuimengChatTextProvider,
    OpenAIResponsesTextProvider,
    TextProvider,
    TextProviderEmptyResponseError,
    TextSummaryResult,
)
from app.schemas.workflows import AiTextRunCreate, AiTextRunView, TextProviderStatusView
from app.services.planning import read_extraction_text
from app.services.projects import get_project
from app.services.system_prompt import load_system_prompt_status


SYSTEM_VERSION_KEY = "V7.0-Plus-R1-FLOW-NAV-VP-PRECISION-18"

MODULE_LABELS = {
    "director_analysis": "导演启动分析",
    "planning_draft": "分镜规划",
    "asset_brief": "资产文字建议",
    "asset_inventory": "剧本资产清单识别",
    "storyboard_brief": "故事板文字拆解",
    "vp_precision_18": "分镜提示词",
    "workflow_check_summary": "检查摘要",
    "fix_suggestion": "修正建议",
    "one_click_advice": "一键推进建议",
    "batch_prompt_brief": "批量视频文字建议",
    "provider_smoke_test": "真实文本大脑试跑",
}

MODULE_OUTPUT_TOKEN_LIMITS = {
    "provider_smoke_test": 160,
    "director_analysis": 1800,
    "planning_draft": 8000,
    "asset_brief": 2200,
    "asset_inventory": 5000,
    "storyboard_brief": 2200,
    "vp_precision_18": 12000,
    "workflow_check_summary": 900,
    "fix_suggestion": 1200,
    "one_click_advice": 1200,
    "batch_prompt_brief": 1200,
}


def _json(value: str, fallback):
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return fallback


def _run_view(run: AiTextRun, cache_hit: bool | None = None) -> AiTextRunView:
    return AiTextRunView(
        id=run.id,
        project_id=run.project_id,
        report_id=run.report_id,
        source_extraction_id=run.source_extraction_id,
        target_type=run.target_type,
        target_id=run.target_id,
        module_type=run.module_type,
        provider=run.provider,
        model_name=run.model_name,
        response_text=run.response_text,
        response_json=run.response_json,
        status=run.status,
        error_message=run.error_message,
        cache_hit=run.cache_hit if cache_hit is None else cache_hit,
        input_tokens=run.input_tokens,
        cached_input_tokens=run.cached_input_tokens,
        output_tokens=run.output_tokens,
        created_at=run.created_at,
    )


_TEXT_SERVICE_LABELS = {
    "https://api.huimengi.com/v1": "慧梦",
    "https://api.moonshot.cn/v1": "Kimi",
    "https://api.deepseek.com/v1": "DeepSeek",
    "https://open.bigmodel.cn/api/paas/v4": "智谱 GLM",
    "https://generativelanguage.googleapis.com/v1beta/openai": "Gemini",
}


def text_service_label(base_url: str) -> str:
    """根据文字服务地址推断服务名称，用于状态展示。"""
    return _TEXT_SERVICE_LABELS.get((base_url or "").rstrip("/"), "自定义服务")


def text_provider_status(settings: Settings) -> TextProviderStatusView:
    mode = settings.text_provider_mode if settings.text_provider_mode in {"huimeng_chat", "openai_responses"} else "huimeng_chat"
    system_status = load_system_prompt_status(settings.system_prompt_file, settings.provider_mode)
    system_hash_short = ""
    if system_status.loaded:
        try:
            system_hash_short = hashlib.sha256(settings.system_prompt_file.read_text(encoding="utf-8").encode()).hexdigest()[:12]
        except OSError:
            system_hash_short = ""
    service = text_service_label(settings.text_base_url)
    if mode == "huimeng_chat":
        configured = settings.enable_real_text_analysis and bool(settings.text_api_key) and bool(settings.text_model)
        ready = configured and system_status.loaded
        reason = "" if ready else (
            system_status.error if configured and not system_status.loaded else f"请开启真实文本分析，并在设置页配置{service}的 Key 与模型。"
        )
        label = f"{service} 文本通道（{settings.text_model}）"
    else:
        openai_model = settings.openai_text_model or settings.openai_model_routine
        configured = settings.enable_real_text_analysis and bool(settings.openai_api_key) and bool(openai_model)
        ready = configured and system_status.loaded
        reason = "" if ready else (
            system_status.error if configured and not system_status.loaded else "请开启真实文本分析，并配置 OpenAI Key 与文本模型。"
        )
        label = "OpenAI 官方文本通道"
    return TextProviderStatusView(
        mode=mode,
        mode_label=label,
        real_text_enabled=settings.enable_real_text_analysis,
        requires_user_confirmation=True,
        uses_full_system_prompt=system_status.loaded,
        system_prompt_loaded=system_status.loaded,
        system_prompt_filename=system_status.filename,
        system_prompt_version=system_status.version,
        system_prompt_sha256_short=system_hash_short,
        openai_api_key_configured=bool(settings.openai_api_key),
        openai_model=settings.openai_text_model or settings.openai_model_routine,
        huimengi_api_key_configured=bool(settings.huimengi_api_key),
        huimengi_text_base_url=settings.huimengi_text_base_url,
        huimengi_text_model=settings.huimengi_text_model,
        text_api_key_configured=bool(settings.text_api_key),
        text_base_url=settings.text_base_url,
        text_model=settings.text_model,
        text_service_label=service,
        ready=ready,
        blocking_reason=reason,
        network_policy="正式创作只使用真实文本 AI；请求必须开启真实分析、配置 Key，并在任务页逐次确认。不会自动生成图片或提交视频。",
    )


def _resolve_provider(
    settings: Settings,
    provider_mode: str | None,
    confirm_live_request: bool,
    provider: TextProvider | None = None,
    allow_legacy_openai: bool = False,
    max_output_tokens: int | None = None,
    structured_json: bool = False,
    disable_reasoning: bool = False,
) -> tuple[str, str, TextProvider]:
    mode = provider_mode or settings.text_provider_mode or "huimeng_chat"
    if mode not in {"huimeng_chat", "openai_responses"}:
        raise HTTPException(400, "真实文本通道只允许 huimeng_chat 或 openai_responses。")
    if not settings.enable_real_text_analysis and not (allow_legacy_openai and mode == "openai_responses" and settings.enable_real_openai):
        raise HTTPException(409, "请先在设置页开启真实文本分析总开关。")
    if not confirm_live_request:
        raise HTTPException(409, "真实文本分析必须在页面逐次人工确认。")
    if mode == "huimeng_chat":
        if not settings.text_api_key or not settings.text_model:
            raise HTTPException(409, "请先在设置页配置文字服务的 Key 和模型。")
        return "huimeng_chat", settings.text_model, provider or HuimengChatTextProvider(
            settings.text_api_key,
            settings.text_base_url,
            settings.text_model,
            max_output_tokens or settings.openai_max_output_tokens,
            structured_json=structured_json,
            disable_reasoning=disable_reasoning,
        )
    openai_model = settings.openai_text_model or settings.openai_model_routine
    if not settings.openai_api_key or not openai_model:
        raise HTTPException(409, "请先在设置页配置 OpenAI Key 和文本模型。")
    return "openai_responses", openai_model, provider or OpenAIResponsesTextProvider(
        settings.openai_api_key,
        openai_model,
        max_output_tokens or settings.openai_max_output_tokens,
    )


def _module_output_limit(settings: Settings, module_type: str) -> int:
    configured_limit = max(160, settings.openai_max_output_tokens)
    module_limit = MODULE_OUTPUT_TOKEN_LIMITS.get(module_type, 1800)
    if module_type == "vp_precision_18":
        # 完整 18 项 JSON 的历史有效输出通常超过 4K；这里保证结构化结果有足够空间。
        return max(configured_limit, module_limit)
    return min(configured_limit, module_limit)


def _require_non_empty_result(result: TextSummaryResult) -> None:
    if result.text.strip():
        return
    raise TextProviderEmptyResponseError(
        finish_reason=result.finish_reason,
        output_tokens=result.output_tokens,
        reasoning_tokens=result.reasoning_tokens,
    )


def _friendly_text_provider_error(cause: Exception) -> str:
    if isinstance(cause, TextProviderEmptyResponseError):
        if cause.finish_reason in {"length", "max_tokens"} or (
            cause.output_tokens > 0 and cause.reasoning_tokens >= cause.output_tokens
        ):
            return (
                "AI 服务已用完本次输出额度，但没有返回最终正文。系统没有保存空结果，也不会自动重试以避免重复费用。"
                "请提高输出上限或关闭模型深度思考后，再手动生成。"
            )
        return (
            "AI 服务本次返回了空正文。系统没有保存空结果，也不会自动重试以避免重复费用。"
            "请稍后手动重试；如果连续出现，请切换文本模型。"
        )
    raw = str(cause)
    lowered = raw.lower()
    if (
        "server disconnected without sending a response" in lowered
        or "remoteprotocolerror" in lowered
        or "peer closed connection" in lowered
        or "connection reset" in lowered
    ):
        return (
            "AI 服务在返回结果前中断了连接。你的项目和已保存资料没有损坏，但本次没有取得可保存的分析结果。"
            "为避免重复请求可能产生两次费用，系统没有自动重试。请稍后手动点击“从剧本识别资产”；"
            "如果连续出现，请到“成本与设置”切换文本服务，或缩短本次处理的剧本范围。"
        )
    if "504" in raw or "gateway time" in lowered:
        return (
            "文本大脑服务通道超时（504）。这通常是慧梦接口繁忙或本次输入较长导致的，"
            "不是你的项目数据损坏。请稍后重试，或先减少剧本文本范围后再生成。"
        )
    if "timeout" in lowered or "timed out" in lowered:
        return "文本大脑请求超时。请稍后重试；如果连续失败，建议缩短输入文本或切换服务通道。"
    if "401" in raw or "unauthorized" in lowered:
        return "文本大脑鉴权失败。请到“成本与设置”检查 API Key 是否正确。"
    if "429" in raw or "rate limit" in lowered or "too many" in lowered:
        return "文本大脑请求过于频繁或额度受限。请稍后重试，或检查服务商额度。"
    if "server error" in lowered or "bad gateway" in lowered or "502" in raw or "503" in raw:
        return "文本大脑服务商暂时返回服务错误。请稍后重试；本地项目数据已保留。"
    return f"文本大脑调用失败：{raw}"


def _latest_extraction(session: Session, project_id: str) -> SourceTextExtraction | None:
    return session.exec(
        select(SourceTextExtraction)
        .where(SourceTextExtraction.project_id == project_id, SourceTextExtraction.status == "extracted")
        .order_by(SourceTextExtraction.created_at.desc())
    ).first()


def _project_scope(session: Session, project: Project) -> str:
    episode = session.exec(select(Episode).where(Episode.project_id == project.id).order_by(Episode.episode_code)).first()
    scene = session.exec(select(Scene).where(Scene.episode_id == episode.id).order_by(Scene.scene_code)).first() if episode else None
    if episode and scene:
        return f"{episode.episode_code}{scene.scene_code}"
    if episode:
        return episode.episode_code
    return project.project_code


def _target_context(session: Session, payload: AiTextRunCreate) -> str:
    if payload.target_type == "shot" and payload.target_id:
        shot = session.get(Shot, payload.target_id)
        if shot:
            scene = session.get(Scene, shot.scene_id)
            return f"目标镜头：{shot.shot_code}｜{shot.name}\n目标场：{scene.scene_code if scene else '未知'}\n"
    if payload.target_type or payload.target_id:
        return f"目标对象：{payload.target_type or '未指定'}｜{payload.target_id}\n"
    return ""


def _load_system_rules(settings: Settings) -> tuple[str, str]:
    status = load_system_prompt_status(settings.system_prompt_file, settings.provider_mode)
    if not status.loaded:
        raise HTTPException(500, f"系统主文件未载入，不能执行真实 AI 分析：{status.error}")
    try:
        content = settings.system_prompt_file.read_text(encoding="utf-8")
    except OSError as cause:
        raise HTTPException(500, "系统主文件无法读取，不能执行真实 AI 分析。") from cause
    if not content.strip():
        raise HTTPException(500, "系统主文件为空，不能执行真实 AI 分析。")
    return content, hashlib.sha256(content.encode()).hexdigest()


def _build_instructions(settings: Settings, module_type: str) -> tuple[str, str]:
    label = MODULE_LABELS.get(module_type, "文字分析")
    system_rules, system_hash = _load_system_rules(settings)
    extra = ""
    if module_type == "planning_draft":
        extra = (
            "\n规划阶段必须一次性输出当前输入文本范围内的完整分镜规划，不要只输出示例、摘要或单个镜头。"
            "请按 EP / SC / SH 拆分：有“第X场 / SC / 镜头 / SH”标记时优先遵循原文结构；"
            "没有明确标记时，按地点变化、时间变化、人物行动、信息揭示、情绪转折、视觉动作段落拆分。"
            "planning_items 必须覆盖输入文本中所有可识别的场次和镜头；多段剧情通常应输出多条。"
            "除非原文确实只有一个短镜头，否则禁止只返回 1 条。"
            "每条只写一个可拍镜头，source_excerpt 摘取原文依据，suggested_task 写导演级镜头任务。"
            "最多输出 120 条；如果文本很长，也要优先覆盖当前上传文本的完整剧情链路，不要只截取开头。"
            "\n分镜规划必须输出可被应用解析的 JSON，不要只写自然语言。格式如下：\n"
            "```json\n"
            "{\"planning_items\":["
            "{\"episode_code\":\"EP01\",\"scene_code\":\"SC01\",\"shot_code\":\"SH001\",\"source_excerpt\":\"原文依据 1\",\"suggested_task\":\"镜头任务 1\"},"
            "{\"episode_code\":\"EP01\",\"scene_code\":\"SC01\",\"shot_code\":\"SH002\",\"source_excerpt\":\"原文依据 2\",\"suggested_task\":\"镜头任务 2\"}"
            "]}\n"
            "```\n"
            "JSON 前后可以有人类说明，但 JSON 内字段名必须保持不变。"
        )
    elif module_type == "director_analysis":
        extra = (
            "\n导演分析必须覆盖：题材判断、人物关系、核心冲突、视觉风格、镜头语言、下一步建议。"
            "请控制在 1600 字以内，输出 6 个清晰小节，每节 3-5 条，避免长篇散文。"
            "必须包含一个小节，标题为“可选导演方案”。该小节严格输出原系统五大导演方案，每行格式固定为："
            "“方案一：原剧情版，适合什么、视觉重点、主要风险。”"
            "“方案二：唯美画意版，适合什么、视觉重点、主要风险。”"
            "“方案三：G版打斗特效版，适合什么、视觉重点、主要风险。”"
            "“方案四：H解说模式，适合什么、视觉重点、主要风险。”"
            "“方案五：推荐导演方案，结合当前剧本自动生成一个定制化导演风格名称，适合什么、视觉重点、主要风险。”"
            "如果某类方案不适合当前剧本，也必须保留该行并说明“不推荐用于本项目的原因”，不能省略。"
            "必须紧接着输出一个小节，标题为“AI推荐结论”，格式固定为："
            "“推荐采用：方案X｜方案名”"
            "“推荐理由：一句话说明为什么最适合当前剧本。”"
            "“备用选择：方案X｜方案名，适合用户想达到什么效果。”"
            "“风险提醒：一句话说明采用推荐方案最需要注意的风险。”"
        )
    elif module_type == "asset_inventory":
        extra = (
            "\n请从当前剧本正文中整理人物、人物本场服装、场景和道具，并判断它们应作为关键视觉参考还是只用文字描述。"
            "只提取正文有依据的内容，不要虚构；scene_scope_codes 只能使用工作台现有 EPxxSCxx 范围。"
            "reference_mode 只能是 visual 或 text_only。只有命名或反复出现的主角身份、英雄产品或品牌物、"
            "必须跨镜头一致的独特主场景、推动剧情且外观必须准确的关键道具才设为 visual。"
            "普通配角、通用服装、背景环境细节和临时道具应设为 text_only，留给视频模型合理补全。"
            "宁可少选关键参考，也不要把剧本中出现的每项内容都做成图片，避免参考素材互相牵制。"
            "必须覆盖当前输入正文的完整范围，并严格只返回下面结构的 JSON，不要 Markdown 代码围栏："
            "{\"characters\":[{\"name\":\"\",\"description\":\"\",\"reference_mode\":\"visual\",\"importance_reason\":\"\",\"text_prompt\":\"\",\"visual_prompt\":\"\",\"evidence\":\"\","
            "\"scene_scope_codes\":[\"EP01SC01\"],\"costume\":{\"name\":\"\",\"description\":\"\",\"reference_mode\":\"text_only\",\"importance_reason\":\"\",\"text_prompt\":\"\",\"visual_prompt\":\"\"}}],"
            "\"scenes\":[{\"scope_code\":\"EP01SC01\",\"name\":\"\",\"description\":\"\",\"spatial_layout\":\"\","
            "\"time_weather_light\":\"\",\"key_props\":\"\",\"palette_mood\":\"\",\"reference_mode\":\"visual\",\"importance_reason\":\"\",\"text_prompt\":\"\",\"visual_prompt\":\"\",\"evidence\":\"\"}],"
            "\"props\":[{\"name\":\"\",\"category\":\"剧情道具\",\"description\":\"\",\"visual_details\":\"\","
            "\"reference_mode\":\"text_only\",\"importance_reason\":\"\",\"text_prompt\":\"\",\"visual_prompt\":\"\",\"evidence\":\"\",\"scene_scope_codes\":[\"EP01SC01\"]}]}。"
            "visual 项的 visual_prompt 必须可直接用于生成单项资产图；text_only 项必须提供可直接并入视频提示词的 text_prompt，visual_prompt 可为空。人物服装必须归属对应人物。"
        )
    elif module_type == "asset_brief":
        extra = "\n资产建议必须拆成人物、服装、场景三类；只输出文字设定和生成建议，不虚构已经存在的图片资产。"
    elif module_type == "storyboard_brief":
        extra = "\n故事板拆解必须给出建议格数、关键画面、构图、景别、机位、动作节点和与分镜提示词时间段的对应关系。"
    elif module_type == "vp_precision_18":
        extra = (
            "\n必须输出严格 JSON，键名为 vp_precision_18，数组必须恰好 18 项。"
            "每项必须包含 number、title、content；number 从 1 到 18；第 4 项 content 必须是可直接复制给视频模型的完整中文视频提示词。"
            "18 项标题必须对应：镜头编号/时长/画幅/目标模型、镜头任务/导演意图、输入参考资产、完整视频提示词、分时段镜头描述、景别、机位、运镜、构图、主体动作、微表情/物体状态/环境动态、光线/氛围、音效说明、轴线与空间连续性约束、强约束、负面约束、截尾帧、上下镜衔接。"
        )
    elif module_type == "provider_smoke_test":
        extra = "\n这是一次极小的真实连接试跑。只返回 80 字以内中文确认，不要输出系统规则正文，不要生成创作内容。"
    instructions = (
        "下面是必须遵守的系统主规则。你要按这套系统工作，而不是按普通聊天助手工作。\n"
        "【系统主规则开始】\n"
        f"{system_rules}\n"
        "【系统主规则结束】\n\n"
        "本应用的安全边界：只做文字分析、文字规划、文字提示词或文字建议，不生成图片，不提交视频，不调用任何第三方生成任务。\n"
        "必须使用中文，面向影视创作者，说人话，同时保留 V7 系统要求的导演判断、视觉把握、镜头质量和 FLOW-NAV 推进逻辑。\n"
        f"当前任务：{label}。\n"
        "输出要求：先给结论，再给可执行清单；如果资料不足，明确说明缺什么，不要假装已经完成。"
        f"{extra}"
    )
    return instructions, system_hash


def _build_input(session: Session, settings: Settings, project: Project, payload: AiTextRunCreate) -> tuple[str, SourceTextExtraction | None]:
    extraction = session.get(SourceTextExtraction, payload.source_extraction_id) if payload.source_extraction_id else _latest_extraction(session, project.id)
    source_text = ""
    if extraction:
        if extraction.project_id != project.id:
            raise HTTPException(400, "文本提取记录不属于当前项目。")
        source_text = read_extraction_text(settings.projects_root, project, extraction)
    source_text = source_text[:50000]
    context_text = _workbench_context(session, project, payload)
    input_text = (
        f"项目：{project.project_code}｜{project.name}\n"
        f"当前范围：{_project_scope(session, project)}\n"
        f"{_target_context(session, payload)}"
        f"用户补充要求：{payload.user_note or '无'}\n"
        f"工作台现有上下文：\n{context_text}\n"
        f"资料正文节选：\n{source_text or '暂无可解析正文，请基于现有目标对象给出谨慎建议。'}"
    )
    return input_text, extraction


def _project_scenes(session: Session, project: Project) -> list[tuple[Episode, Scene]]:
    rows: list[tuple[Episode, Scene]] = []
    episodes = session.exec(
        select(Episode)
        .where(Episode.project_id == project.id, Episode.is_archived == False)  # noqa: E712
        .order_by(Episode.episode_code)
    ).all()
    for episode in episodes:
        scenes = session.exec(
            select(Scene)
            .where(Scene.episode_id == episode.id, Scene.is_archived == False)  # noqa: E712
            .order_by(Scene.scene_code)
        ).all()
        rows.extend((episode, scene) for scene in scenes)
    return rows


def _project_shots(session: Session, project: Project) -> list[tuple[Episode, Scene, Shot]]:
    rows: list[tuple[Episode, Scene, Shot]] = []
    for episode, scene in _project_scenes(session, project):
        shots = session.exec(
            select(Shot)
            .where(Shot.scene_id == scene.id, Shot.is_archived == False)  # noqa: E712
            .order_by(Shot.shot_code)
        ).all()
        rows.extend((episode, scene, shot) for shot in shots)
    return rows


def _latest_by_field(session: Session, model, field, value):
    return session.exec(select(model).where(field == value).order_by(model.version_number.desc())).first()


def _project_tree_context(session: Session, project: Project) -> str:
    lines = [f"创作目标：{project.creative_goal}", f"项目说明：{project.description or '未填写'}", "项目结构："]
    for episode, scene, shot in _project_shots(session, project)[:80]:
        lines.append(f"- {episode.episode_code}｜{scene.scene_code}｜{shot.shot_code}：{shot.name}")
    return "\n".join(lines)


def _recent_ai_context(session: Session, project: Project, payload: AiTextRunCreate) -> str:
    runs = session.exec(
        select(AiTextRun)
        .where(AiTextRun.project_id == project.id, AiTextRun.status == "completed")
        .order_by(AiTextRun.created_at.desc())
        .limit(6)
    ).all()
    runs = [
        run for run in runs
        if not (
            run.module_type == payload.module_type
            and run.target_type == payload.target_type
            and run.target_id == payload.target_id
            and run.source_extraction_id == payload.source_extraction_id
        )
    ][:6]
    if not runs:
        return "近期真实 AI 记录：暂无。"
    lines = ["近期真实 AI 记录："]
    for run in runs:
        excerpt = " ".join(run.response_text.split())[:240]
        lines.append(f"- {run.module_type}｜{run.provider}｜{run.model_name}：{excerpt}")
    return "\n".join(lines)


def _planning_context(session: Session, project: Project) -> str:
    draft = session.exec(
        select(PlanningDraft)
        .where(PlanningDraft.project_id == project.id)
        .order_by(PlanningDraft.version_number.desc())
    ).first()
    if not draft:
        return "分镜规划：暂无。"
    items = session.exec(
        select(PlanningDraftItem)
        .where(PlanningDraftItem.draft_id == draft.id)
        .order_by(PlanningDraftItem.shot_code)
        .limit(12)
    ).all()
    lines = [f"分镜规划：V{draft.version_number}｜{draft.status}｜{draft.summary}"]
    for item in items:
        lines.append(f"- {item.episode_code}{item.scene_code}{item.shot_code}：{item.suggested_task}｜依据：{item.source_excerpt[:120]}")
    return "\n".join(lines)


def _asset_context(session: Session, project: Project) -> str:
    lines = ["资产状态："]
    characters = session.exec(
        select(Character)
        .where(Character.project_id == project.id, Character.is_archived == False)  # noqa: E712
        .order_by(Character.character_code)
        .limit(12)
    ).all()
    if characters:
        lines.append("人物：")
        for character in characters:
            master = _latest_by_field(session, CharacterMasterVersion, CharacterMasterVersion.character_id, character.id)
            costumes = session.exec(
                select(Costume)
                .where(Costume.character_id == character.id, Costume.is_archived == False)  # noqa: E712
                .order_by(Costume.costume_code)
                .limit(4)
            ).all()
            costume_bits = []
            for costume in costumes:
                version = _latest_by_field(session, CostumeVersion, CostumeVersion.costume_id, costume.id)
                costume_bits.append(f"{costume.costume_code}/{costume.usage_context}/{version.status if version else '无版本'}")
            lines.append(
                f"- {character.character_code}｜{character.name}｜{character.identity_temperament or '身份气质未填'}｜"
                f"母版：{master.status if master else '无'}｜服装：{'; '.join(costume_bits) or '无'}"
            )
    else:
        lines.append("人物：暂无。")
    scene_rows = _project_scenes(session, project)[:20]
    if scene_rows:
        lines.append("场景：")
        for episode, scene in scene_rows:
            scene_asset = session.exec(select(SceneAsset).where(SceneAsset.scene_id == scene.id)).first()
            version = _latest_by_field(session, SceneAssetVersion, SceneAssetVersion.scene_asset_id, scene_asset.id) if scene_asset else None
            binding_count = len(session.exec(select(SceneCharacterBinding).where(SceneCharacterBinding.scene_id == scene.id)).all())
            lines.append(
                f"- {episode.episode_code}{scene.scene_code}｜{scene.name}｜"
                f"场景资产：{version.status if version else '无'}｜人物绑定：{binding_count}"
                f"{'｜' + scene_asset.description[:120] if scene_asset and scene_asset.description else ''}"
            )
    return "\n".join(lines)


def _storyboard_video_context(session: Session, project: Project, payload: AiTextRunCreate) -> str:
    rows = _project_shots(session, project)
    if payload.target_type == "shot" and payload.target_id:
        rows = [row for row in rows if row[2].id == payload.target_id] or rows
    lines = ["故事板与分镜提示词状态："]
    for episode, scene, shot in rows[:20]:
        storyboard = _latest_by_field(session, StoryboardShotVersion, StoryboardShotVersion.shot_id, shot.id)
        draft_vp = session.exec(
            select(VpBlock)
            .where(VpBlock.shot_id == shot.id, VpBlock.package_stage == "director_draft")
            .order_by(VpBlock.version_number.desc())
        ).first()
        final_vp = session.exec(
            select(VpBlock)
            .where(VpBlock.shot_id == shot.id, VpBlock.package_stage == "final_execution")
            .order_by(VpBlock.version_number.desc())
        ).first()
        lines.append(
            f"- {episode.episode_code}{scene.scene_code}{shot.shot_code}｜{shot.name}｜"
            f"故事板：{storyboard.status if storyboard else '无'}"
            f"{f'/{storyboard.storyboard_grid}格/轴线{storyboard.axis_validation_status}' if storyboard else ''}｜"
            f"故事板参考提示词：{draft_vp.status if draft_vp else '无'}｜成片提示词：{final_vp.status if final_vp else '无'}"
        )
        if draft_vp and draft_vp.prompt_copy:
            lines.append(f"  草案提示词摘录：{draft_vp.prompt_copy[:300]}")
        if storyboard and storyboard.grid_reason:
            lines.append(f"  故事板排版依据：{storyboard.grid_reason[:240]}")
    return "\n".join(lines)


def _workbench_context(session: Session, project: Project, payload: AiTextRunCreate) -> str:
    parts = [
        _project_tree_context(session, project),
        _planning_context(session, project),
        _asset_context(session, project),
        _storyboard_video_context(session, project, payload),
        _recent_ai_context(session, project, payload),
    ]
    return "\n\n".join(parts)[:30000]


def run_project_ai_text(
    session: Session,
    settings: Settings,
    project_id: str,
    payload: AiTextRunCreate,
    provider: TextProvider | None = None,
) -> AiTextRunView:
    project = get_project(session, project_id)
    provider_name, model_name, resolved_provider = _resolve_provider(
        settings,
        payload.provider_mode,
        payload.confirm_live_request,
        provider,
        max_output_tokens=_module_output_limit(settings, payload.module_type),
        structured_json=payload.module_type == "vp_precision_18",
        disable_reasoning=payload.module_type == "vp_precision_18",
    )
    instructions, system_hash = _build_instructions(settings, payload.module_type)
    input_text, extraction = _build_input(session, settings, project, payload)
    input_hash = hashlib.sha256(input_text.encode()).hexdigest()
    base_key = hashlib.sha256(
        f"{provider_name}|{model_name}|{payload.module_type}|{SYSTEM_VERSION_KEY}|{system_hash}|{input_hash}|standard".encode()
    ).hexdigest()
    invalid_cache_record: RequestCacheRecord | None = None
    if not payload.force_regenerate:
        cached = session.exec(select(RequestCacheRecord).where(RequestCacheRecord.cache_key == base_key)).first()
        cached_run = session.get(AiTextRun, cached.result_reference_id) if cached else None
        if cached_run and cached_run.status == "completed" and cached_run.response_text.strip():
            cached_run.cache_hit = True
            session.add(cached_run)
            session.add(CostUsageLog(
                provider=cached_run.provider,
                model_name=cached_run.model_name,
                module_type=payload.module_type,
                text_run_id=cached_run.id,
                cache_key=cached_run.cache_key,
                cache_hit=True,
                input_tokens=cached_run.input_tokens,
                cached_input_tokens=cached_run.cached_input_tokens,
                output_tokens=cached_run.output_tokens,
            ))
            session.commit()
            session.refresh(cached_run)
            return _run_view(cached_run, cache_hit=True)
        invalid_cache_record = cached
    key = base_key if not payload.force_regenerate else f"{base_key}:regen:{uuid4().hex}"
    result: TextSummaryResult | None = None
    try:
        result = resolved_provider.generate(instructions, input_text)
        _require_non_empty_result(result)
        run = AiTextRun(
            project_id=project.id,
            source_extraction_id=extraction.id if extraction else None,
            target_type=payload.target_type,
            target_id=payload.target_id,
            module_type=payload.module_type,
            provider=provider_name,
            model_name=model_name,
            cache_key=key,
            input_hash=input_hash,
            response_text=result.text,
            response_json=json.dumps({"text": result.text, "system_version": SYSTEM_VERSION_KEY, "system_prompt_sha256": system_hash}, ensure_ascii=False),
            input_tokens=result.input_tokens,
            cached_input_tokens=result.cached_input_tokens,
            output_tokens=result.output_tokens,
        )
    except Exception as cause:
        run = AiTextRun(
            project_id=project.id,
            source_extraction_id=extraction.id if extraction else None,
            target_type=payload.target_type,
            target_id=payload.target_id,
            module_type=payload.module_type,
            provider=provider_name,
            model_name=model_name,
            cache_key=key,
            input_hash=input_hash,
            response_text="",
            response_json="{}",
            status="failed",
            error_message=str(cause),
            input_tokens=result.input_tokens if result else 0,
            cached_input_tokens=result.cached_input_tokens if result else 0,
            output_tokens=result.output_tokens if result else 0,
        )
        session.add(run)
        session.flush()
        if result:
            session.add(CostUsageLog(
                provider=provider_name,
                model_name=model_name,
                module_type=payload.module_type,
                text_run_id=run.id,
                cache_key=key,
                input_tokens=result.input_tokens,
                cached_input_tokens=result.cached_input_tokens,
                output_tokens=result.output_tokens,
            ))
        session.commit()
        session.refresh(run)
        raise HTTPException(502, _friendly_text_provider_error(cause)) from cause
    session.add(run)
    session.flush()
    if invalid_cache_record:
        invalid_cache_record.result_reference_id = run.id
        invalid_cache_record.module_type = payload.module_type
        session.add(invalid_cache_record)
    else:
        session.add(RequestCacheRecord(cache_key=key, module_type=payload.module_type, result_reference_id=run.id))
    session.add(CostUsageLog(
        provider=provider_name,
        model_name=model_name,
        module_type=payload.module_type,
        text_run_id=run.id,
        cache_key=key,
        input_tokens=run.input_tokens,
        cached_input_tokens=run.cached_input_tokens,
        output_tokens=run.output_tokens,
    ))
    session.commit()
    session.refresh(run)
    return _run_view(run)


def run_text_provider_smoke_test(
    session: Session,
    settings: Settings,
    payload: AiTextRunCreate,
    provider: TextProvider | None = None,
) -> AiTextRunView:
    payload.module_type = "provider_smoke_test"
    provider_name, model_name, resolved_provider = _resolve_provider(
        settings,
        payload.provider_mode,
        payload.confirm_live_request,
        provider,
        max_output_tokens=_module_output_limit(settings, "provider_smoke_test"),
    )
    instructions, system_hash = _build_instructions(settings, "provider_smoke_test")
    input_text = (
        "请确认当前 AI导演工作台已经通过真实文本模型接入 V7.0 Plus R1｜UCODE-9 + FLOW-NAV + VP-PRECISION-18。"
        "只输出一句中文确认，并提醒正式创作仍需在任务页逐次确认。"
    )
    input_hash = hashlib.sha256(input_text.encode()).hexdigest()
    key = hashlib.sha256(
        f"{provider_name}|{model_name}|provider_smoke_test|{SYSTEM_VERSION_KEY}|{system_hash}|{input_hash}|live-smoke|{uuid4().hex}".encode()
    ).hexdigest()
    try:
        result = resolved_provider.generate(instructions, input_text)
        _require_non_empty_result(result)
    except Exception as cause:
        run = AiTextRun(
            project_id=None,
            module_type="provider_smoke_test",
            provider=provider_name,
            model_name=model_name,
            cache_key=key,
            input_hash=input_hash,
            response_text="",
            response_json="{}",
            status="failed",
            error_message=str(cause),
        )
        session.add(run)
        session.commit()
        session.refresh(run)
        raise HTTPException(502, _friendly_text_provider_error(cause)) from cause
    run = AiTextRun(
        project_id=None,
        module_type="provider_smoke_test",
        provider=provider_name,
        model_name=model_name,
        cache_key=key,
        input_hash=input_hash,
        response_text=result.text,
        response_json=json.dumps({"text": result.text, "system_version": SYSTEM_VERSION_KEY, "system_prompt_sha256": system_hash}, ensure_ascii=False),
        input_tokens=result.input_tokens,
        cached_input_tokens=result.cached_input_tokens,
        output_tokens=result.output_tokens,
    )
    session.add(run)
    session.flush()
    session.add(CostUsageLog(
        provider=provider_name,
        model_name=model_name,
        module_type="provider_smoke_test",
        text_run_id=run.id,
        cache_key=key,
        input_tokens=run.input_tokens,
        cached_input_tokens=run.cached_input_tokens,
        output_tokens=run.output_tokens,
    ))
    session.commit()
    session.refresh(run)
    return _run_view(run)


def list_project_ai_text_runs(session: Session, project_id: str) -> list[AiTextRunView]:
    get_project(session, project_id)
    runs = session.exec(
        select(AiTextRun)
        .where(AiTextRun.project_id == project_id)
        .order_by(AiTextRun.created_at.desc())
    ).all()
    return [_run_view(run) for run in runs]


def summarize_report_with_text_provider(
    session: Session,
    report_id: str,
    settings: Settings,
    confirm_live_request: bool,
    force_regenerate: bool,
    provider: TextProvider | None = None,
) -> AiTextRunView:
    report = session.get(WorkflowCheckReport, report_id)
    if not report:
        raise HTTPException(404, "检查报告不存在。")
    legacy_openai_summary = settings.enable_real_openai and not settings.enable_real_text_analysis
    payload = AiTextRunCreate(
        module_type="workflow_check_summary",
        target_type="workflow_check_report",
        target_id=report.id,
        provider_mode="openai_responses" if legacy_openai_summary else (settings.text_provider_mode or "huimeng_chat"),
        confirm_live_request=confirm_live_request,
        force_regenerate=force_regenerate,
    )
    provider_name, model_name, resolved_provider = _resolve_provider(
        settings,
        payload.provider_mode,
        payload.confirm_live_request,
        provider,
        allow_legacy_openai=legacy_openai_summary,
        max_output_tokens=_module_output_limit(settings, "workflow_check_summary"),
    )
    instructions, system_hash = _build_instructions(settings, "workflow_check_summary")
    input_hash = hashlib.sha256(report.report_json.encode()).hexdigest()
    base_key = hashlib.sha256(
        f"{provider_name}|{model_name}|workflow_check_summary|{SYSTEM_VERSION_KEY}|{system_hash}|{input_hash}|standard".encode()
    ).hexdigest()
    if not force_regenerate:
        cached = session.exec(select(RequestCacheRecord).where(RequestCacheRecord.cache_key == base_key)).first()
        cached_run = session.get(AiTextRun, cached.result_reference_id) if cached else None
        if cached_run:
            cached_run.cache_hit = True
            session.add(cached_run)
            session.add(CostUsageLog(
                provider=cached_run.provider,
                model_name=cached_run.model_name,
                module_type="workflow_check_summary",
                text_run_id=cached_run.id,
                cache_key=cached_run.cache_key,
                cache_hit=True,
                input_tokens=cached_run.input_tokens,
                cached_input_tokens=cached_run.cached_input_tokens,
                output_tokens=cached_run.output_tokens,
            ))
            session.commit()
            session.refresh(cached_run)
            return _run_view(cached_run, cache_hit=True)
    key = base_key if not force_regenerate else f"{base_key}:regen:{uuid4().hex}"
    result = resolved_provider.generate(instructions, report.report_json)
    _require_non_empty_result(result)
    run = AiTextRun(
        project_id=report.project_id,
        report_id=report.id,
        target_type="workflow_check_report",
        target_id=report.id,
        module_type="workflow_check_summary",
        provider=provider_name,
        model_name=model_name,
        cache_key=key,
        input_hash=input_hash,
        response_text=result.text,
        response_json=json.dumps({"text": result.text, "system_version": SYSTEM_VERSION_KEY, "system_prompt_sha256": system_hash}, ensure_ascii=False),
        input_tokens=result.input_tokens,
        cached_input_tokens=result.cached_input_tokens,
        output_tokens=result.output_tokens,
    )
    session.add(run)
    session.flush()
    session.add(RequestCacheRecord(cache_key=key, module_type="workflow_check_summary", result_reference_id=run.id))
    session.add(CostUsageLog(
        provider=provider_name,
        model_name=model_name,
        module_type="workflow_check_summary",
        text_run_id=run.id,
        cache_key=key,
        input_tokens=result.input_tokens,
        cached_input_tokens=result.cached_input_tokens,
        output_tokens=result.output_tokens,
    ))
    session.commit()
    session.refresh(run)
    return _run_view(run)
