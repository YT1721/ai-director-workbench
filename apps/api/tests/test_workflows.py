from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.main import create_app
from app.models import AiTextRun, CostUsageLog, PlanningDraft, WorkflowCheckReport, WorkflowIssue
from app.providers.text import TextSummaryResult
from tests.test_system import SYSTEM_PROMPT_FILENAME, build_settings
from tests.test_workbench import build_client, create_project


def _create_report(client: TestClient, scene_id: str) -> dict:
    response = client.post(f"/api/scenes/{scene_id}/workflow-check-reports")
    assert response.status_code == 201
    return response.json()["reports"][0]


def test_check_report_summary_requires_real_text_brain_and_one_click_gate(tmp_path: Path) -> None:
    with build_client(tmp_path) as client:
        project = create_project(client)
        scene_id = project["episodes"][0]["scenes"][0]["id"]
        report = _create_report(client, scene_id)

        assert report["ready_for_next"] is False
        assert {item["category"] for item in report["issues"]} == {"storyboard"}
        assert all(item["category"] not in {"video_package", "batch_queue"} for item in report["issues"])

        summary = client.post(f"/api/workflow-check-reports/{report['id']}/summarize", json={})
        assert summary.status_code == 409
        assert "真实文本分析" in summary.json()["detail"] or "文本模型" in summary.json()["detail"]
        review = client.get(f"/api/projects/{project['id']}/workflow-review").json()
        assert review["summaries"] == []

        one_click = client.post(f"/api/scenes/{scene_id}/one-click-runs")
        assert one_click.status_code == 201
        assert one_click.json()["status"] == "paused_at_gate"
        assert one_click.json()["current_stage"] == "storyboards"


def test_real_text_acceptance_tracks_project_ai_evidence(tmp_path: Path) -> None:
    with build_client(tmp_path) as client:
        project = create_project(client)
        initial = client.get(f"/api/projects/{project['id']}/real-text-acceptance").json()

        assert initial["ready"] is False
        assert initial["current_label"] == "真实导演启动分析"
        assert "密钥" not in str(initial)
        assert "系统主规则开始" not in str(initial)

        with Session(client.app.state.database_engine) as session:
            session.add(AiTextRun(
                project_id=project["id"],
                module_type="director_analysis",
                provider="huimeng_chat",
                model_name="gpt-5.5",
                cache_key="acceptance-test",
                input_hash="hash",
                response_text="真实导演分析结果",
                response_json="{}",
                output_tokens=123,
            ))
            session.commit()

        next_state = client.get(f"/api/projects/{project['id']}/real-text-acceptance").json()

    assert next_state["items"][0]["status"] == "done"
    assert next_state["items"][0]["provider"] == "huimeng_chat"
    assert next_state["items"][0]["output_tokens"] == 123
    assert next_state["current_label"] == "真实规划草案"


def test_fix_batch_does_not_generate_local_scene_asset_fallback(tmp_path: Path) -> None:
    with build_client(tmp_path) as client:
        project = create_project(client)
        scene_id = project["episodes"][0]["scenes"][0]["id"]
        workspace = client.post(f"/api/scenes/{scene_id}/assets", json={"description": "宫殿", "spatial_layout": "左右对峙"}).json()
        scene_asset = workspace["scene_assets"][0]
        with Session(client.app.state.database_engine) as session:
            report = WorkflowCheckReport(
                project_id=project["id"],
                scene_id=scene_id,
                version_number=1,
            )
            session.add(report)
            session.flush()
            issue = WorkflowIssue(
                report_id=report.id,
                category="assets",
                target_type="scene_asset",
                target_id=scene_asset["id"],
                title="缺少已确认场景资产",
                detail="请先准备并确认当前场景设定板。",
                fixable=True,
            )
            session.add(issue)
            session.commit()
            session.refresh(issue)

        missing_confirm = client.post("/api/workflow-issues/fix-batch", json={"issue_ids": [issue.id]})
        assert missing_confirm.status_code == 409

        fixed = client.post("/api/workflow-issues/fix-batch", json={"issue_ids": [issue.id], "confirm_fix": True})
        assert fixed.status_code == 200
        run = fixed.json()["fix_runs"][0]
        assert run["status"] == "needs_manual"
        assert run["created_version_id"] is None
        assert "真实生图" in run["message"]
        assets = client.get(f"/api/projects/{project['id']}/assets").json()
        assert assets["scene_assets"][0]["versions"] == []
        assert assets["scene_assets"][0]["id"] == scene_asset["id"]


def test_real_openai_summary_requires_confirmation_and_reuses_cache(tmp_path: Path, monkeypatch) -> None:
    prompt_file = tmp_path / SYSTEM_PROMPT_FILENAME
    prompt_file.write_text("剧本视觉化创作系统 V7.0 Plus R1 UCODE-9 FLOW-NAV VP-PRECISION-18 DIRECTOR-TECH PLUS UNIFIED-SB 统一故事板 特写进连接器 TEST_SYSTEM_RULES", encoding="utf-8")
    settings = replace(
        build_settings(tmp_path, prompt_file),
        text_provider_mode="openai_responses",
        enable_real_openai=True,
        openai_api_key="test-only",
        openai_model_routine="test-model",
    )
    calls = []

    class FakeProvider:
        def __init__(self, *args, **kwargs):
            pass

        def generate(self, instructions: str, input_text: str) -> TextSummaryResult:
            calls.append((instructions, input_text))
            return TextSummaryResult("真实路径替身摘要", input_tokens=20, cached_input_tokens=5, output_tokens=8)

        def summarize(self, report_json: str) -> TextSummaryResult:
            raise AssertionError("检查摘要必须走统一系统主规则 generate 路径")

    monkeypatch.setattr("app.services.ai_text.OpenAIResponsesTextProvider", FakeProvider)
    app = create_app(settings)
    with TestClient(app) as client:
        project = create_project(client)
        scene_id = project["episodes"][0]["scenes"][0]["id"]
        report = _create_report(client, scene_id)
        blocked = client.post(f"/api/workflow-check-reports/{report['id']}/summarize", json={})
        assert blocked.status_code == 409
        first = client.post(f"/api/workflow-check-reports/{report['id']}/summarize", json={"confirm_live_request": True})
        second = client.post(f"/api/workflow-check-reports/{report['id']}/summarize", json={"confirm_live_request": True})
        assert first.json()["provider"] == "openai_responses"
        assert second.json()["cache_hit"] is True
        assert len(calls) == 1
        assert "TEST_SYSTEM_RULES" in calls[0][0]
        assert "TEST_SYSTEM_RULES" not in first.text
        with Session(app.state.database_engine) as session:
            usage = session.exec(select(CostUsageLog)).first()
            assert (usage.input_tokens, usage.cached_input_tokens, usage.output_tokens) == (20, 5, 8)


def test_text_provider_status_and_huimeng_director_analysis_are_controlled(tmp_path: Path, monkeypatch) -> None:
    prompt_file = tmp_path / SYSTEM_PROMPT_FILENAME
    prompt_file.write_text("剧本视觉化创作系统 V7.0 Plus R1 UCODE-9 FLOW-NAV VP-PRECISION-18 DIRECTOR-TECH PLUS UNIFIED-SB 统一故事板 特写进连接器 TEST_SYSTEM_RULES", encoding="utf-8")
    settings = replace(
        build_settings(tmp_path, prompt_file),
        text_provider_mode="huimeng_chat",
        enable_real_text_analysis=True,
        huimengi_api_key="hm-secret",
        huimengi_text_model="gpt-5.5",
    )
    calls = []

    class FakeHuimengProvider:
        def __init__(self, *args, **kwargs):
            pass

        def generate(self, instructions: str, input_text: str) -> TextSummaryResult:
            calls.append((instructions, input_text))
            return TextSummaryResult("慧梦替身导演分析", input_tokens=30, output_tokens=12)

        def summarize(self, report_json: str) -> TextSummaryResult:
            return TextSummaryResult("慧梦替身摘要")

    monkeypatch.setattr("app.services.ai_text.HuimengChatTextProvider", FakeHuimengProvider)
    with TestClient(create_app(settings)) as client:
        project = create_project(client)
        source = client.post(
            f"/api/projects/{project['id']}/source-files/text",
            json={"category": "script_text", "title": "剧本", "content": "第一场\n镜头一：主角推门而入。"},
        ).json()
        extraction = client.post(f"/api/source-files/{source['id']}/extract-text").json()

        status = client.get("/api/text-provider/status")
        blocked = client.post(
            f"/api/projects/{project['id']}/director-analyses/ai",
            json={"module_type": "director_analysis", "source_extraction_id": extraction["id"]},
        )
        first = client.post(
            f"/api/projects/{project['id']}/director-analyses/ai",
            json={"module_type": "director_analysis", "source_extraction_id": extraction["id"], "confirm_live_request": True},
        )
        second = client.post(
            f"/api/projects/{project['id']}/director-analyses/ai",
            json={"module_type": "director_analysis", "source_extraction_id": extraction["id"], "confirm_live_request": True},
        )

    assert status.status_code == 200
    assert status.json()["ready"] is True
    assert status.json()["uses_full_system_prompt"] is True
    assert status.json()["system_prompt_loaded"] is True
    assert status.json()["system_prompt_filename"] == SYSTEM_PROMPT_FILENAME
    assert len(status.json()["system_prompt_sha256_short"]) == 12
    assert "hm-secret" not in status.text
    assert "TEST_SYSTEM_RULES" not in status.text
    assert blocked.status_code == 409
    assert first.status_code == 201
    assert first.json()["provider"] == "huimeng_chat"
    assert first.json()["response_text"] == "慧梦替身导演分析"
    assert second.json()["cache_hit"] is True
    assert len(calls) == 1
    assert "TEST_SYSTEM_RULES" in calls[0][0]
    assert "工作台现有上下文" in calls[0][1]
    assert "项目结构" in calls[0][1]
    assert "EP01｜SC01｜SH001" in calls[0][1]
    assert "TEST_SYSTEM_RULES" not in first.text


def test_text_provider_504_error_returns_human_message(tmp_path: Path, monkeypatch) -> None:
    prompt_file = tmp_path / SYSTEM_PROMPT_FILENAME
    prompt_file.write_text("剧本视觉化创作系统 V7.0 Plus R1 UCODE-9 FLOW-NAV VP-PRECISION-18 DIRECTOR-TECH PLUS UNIFIED-SB 统一故事板 特写进连接器", encoding="utf-8")
    settings = replace(
        build_settings(tmp_path, prompt_file),
        text_provider_mode="huimeng_chat",
        enable_real_text_analysis=True,
        huimengi_api_key="hm-secret",
        huimengi_text_model="gpt-5.5",
    )

    class TimeoutHuimengProvider:
        def __init__(self, *args, **kwargs):
            pass

        def generate(self, instructions: str, input_text: str) -> TextSummaryResult:
            raise RuntimeError("Server error '504 Gateway Time-out' for url 'https://api.huimengi.com/v1/chat/completions'")

        def summarize(self, report_json: str) -> TextSummaryResult:
            raise RuntimeError("Server error '504 Gateway Time-out'")

    monkeypatch.setattr("app.services.ai_text.HuimengChatTextProvider", TimeoutHuimengProvider)
    with TestClient(create_app(settings)) as client:
        project = create_project(client)
        source = client.post(
            f"/api/projects/{project['id']}/source-files/text",
            json={"category": "script_text", "title": "剧本", "content": "第一场\n镜头一：主角推门而入。"},
        ).json()
        extraction = client.post(f"/api/source-files/{source['id']}/extract-text").json()
        response = client.post(
            f"/api/projects/{project['id']}/asset-briefs/ai",
            json={"module_type": "asset_brief", "source_extraction_id": extraction["id"], "confirm_live_request": True},
        )

    assert response.status_code == 502
    assert "文本大脑服务通道超时（504）" in response.text
    assert "项目数据损坏" in response.text
    assert "developer.mozilla.org" not in response.text
    assert "hm-secret" not in response.text


def test_text_provider_smoke_test_requires_confirmation_and_uses_full_system_prompt(tmp_path: Path, monkeypatch) -> None:
    prompt_file = tmp_path / SYSTEM_PROMPT_FILENAME
    prompt_file.write_text("剧本视觉化创作系统 V7.0 Plus R1 UCODE-9 FLOW-NAV VP-PRECISION-18 DIRECTOR-TECH PLUS UNIFIED-SB 统一故事板 特写进连接器 TEST_SYSTEM_RULES", encoding="utf-8")
    settings = replace(
        build_settings(tmp_path, prompt_file),
        text_provider_mode="huimeng_chat",
        enable_real_text_analysis=True,
        huimengi_api_key="hm-secret",
        huimengi_text_model="gpt-5.5",
    )
    calls = []

    class FakeHuimengProvider:
        def __init__(self, *args, **kwargs):
            pass

        def generate(self, instructions: str, input_text: str) -> TextSummaryResult:
            calls.append((instructions, input_text))
            return TextSummaryResult("真实文本大脑已接入完整 V7 主系统，正式创作仍需逐次确认。", input_tokens=18, output_tokens=9)

        def summarize(self, report_json: str) -> TextSummaryResult:
            raise AssertionError("试跑必须走 generate")

    monkeypatch.setattr("app.services.ai_text.HuimengChatTextProvider", FakeHuimengProvider)
    app = create_app(settings)
    with TestClient(app) as client:
        blocked = client.post("/api/text-provider/smoke-test", json={"module_type": "provider_smoke_test"})
        first = client.post(
            "/api/text-provider/smoke-test",
            json={"module_type": "provider_smoke_test", "confirm_live_request": True},
        )
        with Session(app.state.database_engine) as session:
            run = session.exec(select(AiTextRun).where(AiTextRun.module_type == "provider_smoke_test")).first()
            usage = session.exec(select(CostUsageLog).where(CostUsageLog.module_type == "provider_smoke_test")).first()

    assert blocked.status_code == 409
    assert first.status_code == 201
    assert first.json()["project_id"] is None
    assert first.json()["provider"] == "huimeng_chat"
    assert first.json()["model_name"] == "gpt-5.5"
    assert first.json()["input_tokens"] == 18
    assert first.json()["output_tokens"] == 9
    assert len(calls) == 1
    assert "TEST_SYSTEM_RULES" in calls[0][0]
    assert "TEST_SYSTEM_RULES" not in first.text
    assert "hm-secret" not in first.text
    assert run is not None
    assert usage is not None
    assert usage.text_run_id == run.id


def test_ai_planning_draft_parses_structured_json_output(tmp_path: Path, monkeypatch) -> None:
    prompt_file = tmp_path / SYSTEM_PROMPT_FILENAME
    prompt_file.write_text("剧本视觉化创作系统 V7.0 Plus R1 UCODE-9 FLOW-NAV VP-PRECISION-18 DIRECTOR-TECH PLUS UNIFIED-SB 统一故事板 特写进连接器 TEST_SYSTEM_RULES", encoding="utf-8")
    settings = replace(
        build_settings(tmp_path, prompt_file),
        text_provider_mode="huimeng_chat",
        enable_real_text_analysis=True,
        huimengi_api_key="hm-secret",
        huimengi_text_model="gpt-5.5",
    )
    calls = []

    class FakeHuimengProvider:
        def __init__(self, *args, **kwargs):
            pass

        def generate(self, instructions: str, input_text: str) -> TextSummaryResult:
            calls.append((instructions, input_text))
            return TextSummaryResult(
                "规划如下：\n```json\n"
                '{"planning_items":['
                '{"episode_code":"EP01","scene_code":"SC01","shot_code":"SH001","source_excerpt":"女孩推门进入雨夜茶馆","suggested_task":"中景跟拍女孩推门，建立雨夜空间"},'
                '{"episode_code":"EP01","scene_code":"SC01","shot_code":"SH002","source_excerpt":"信纸被风吹落","suggested_task":"特写信纸落地，制造悬念"}'
                "]}\n```",
                input_tokens=40,
                output_tokens=30,
            )

            def summarize(self, report_json: str) -> TextSummaryResult:
                raise AssertionError("分镜规划必须走 generate")

    monkeypatch.setattr("app.services.ai_text.HuimengChatTextProvider", FakeHuimengProvider)
    with TestClient(create_app(settings)) as client:
        project = create_project(client)
        source = client.post(
            f"/api/projects/{project['id']}/source-files/text",
            json={"category": "script_text", "title": "剧本", "content": "第一场\n女孩推门进入雨夜茶馆。信纸被风吹落。"},
        ).json()
        extraction = client.post(f"/api/source-files/{source['id']}/extract-text").json()
        draft = client.post(
            f"/api/projects/{project['id']}/planning-drafts/ai",
            json={"module_type": "planning_draft", "source_extraction_id": extraction["id"], "confirm_live_request": True},
        )

    assert draft.status_code == 201
    payload = draft.json()
    assert len(payload["items"]) == 2
    assert payload["items"][0]["shot_code"] == "SH001"
    assert payload["items"][0]["suggested_task"] == "中景跟拍女孩推门，建立雨夜空间"
    assert payload["items"][1]["source_excerpt"] == "信纸被风吹落"
    assert "TEST_SYSTEM_RULES" in calls[0][0]
    assert "工作台现有上下文" in calls[0][1]
    assert "分镜规划：暂无" in calls[0][1]


def test_ai_planning_draft_rejects_unstructured_output_without_local_fallback(tmp_path: Path, monkeypatch) -> None:
    prompt_file = tmp_path / SYSTEM_PROMPT_FILENAME
    prompt_file.write_text("剧本视觉化创作系统 V7.0 Plus R1 UCODE-9 FLOW-NAV VP-PRECISION-18 DIRECTOR-TECH PLUS UNIFIED-SB 统一故事板 特写进连接器 TEST_SYSTEM_RULES", encoding="utf-8")
    settings = replace(
        build_settings(tmp_path, prompt_file),
        text_provider_mode="huimeng_chat",
        enable_real_text_analysis=True,
        huimengi_api_key="hm-secret",
        huimengi_text_model="gpt-5.5",
    )

    class FakeHuimengProvider:
        def __init__(self, *args, **kwargs):
            pass

        def generate(self, instructions: str, input_text: str) -> TextSummaryResult:
            return TextSummaryResult(
                "EP01｜SC01｜SH001：女孩进入雨夜茶馆。这里故意没有 planning_items JSON。",
                input_tokens=30,
                output_tokens=18,
            )

            def summarize(self, report_json: str) -> TextSummaryResult:
                raise AssertionError("分镜规划必须走 generate")

    monkeypatch.setattr("app.services.ai_text.HuimengChatTextProvider", FakeHuimengProvider)
    app = create_app(settings)
    with TestClient(app) as client:
        project = create_project(client)
        source = client.post(
            f"/api/projects/{project['id']}/source-files/text",
            json={"category": "script_text", "title": "剧本", "content": "第一场\n女孩推门进入雨夜茶馆。"},
        ).json()
        extraction = client.post(f"/api/source-files/{source['id']}/extract-text").json()
        draft = client.post(
            f"/api/projects/{project['id']}/planning-drafts/ai",
            json={"module_type": "planning_draft", "source_extraction_id": extraction["id"], "confirm_live_request": True},
        )

        with Session(app.state.database_engine) as session:
            saved_drafts = session.exec(select(PlanningDraft)).all()
            text_runs = session.exec(select(AiTextRun)).all()

    assert draft.status_code == 422
    assert "不会用本地规则兜底" in draft.json()["detail"]
    assert saved_drafts == []
    assert len(text_runs) == 1
    assert text_runs[0].module_type == "planning_draft"
