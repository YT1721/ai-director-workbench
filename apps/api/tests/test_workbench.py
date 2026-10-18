from __future__ import annotations

from pathlib import Path
import zipfile

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.models.videos import VpBlock
from app.services.projects import MAX_UPLOAD_BYTES, PROJECT_SUBDIRECTORIES
from tests.test_system import SYSTEM_PROMPT_FILENAME, build_settings
from app.main import create_app


def build_client(tmp_path: Path) -> TestClient:
    prompt_file = tmp_path / SYSTEM_PROMPT_FILENAME
    prompt_file.write_text("剧本视觉化创作系统 V7.0 Plus R1 UCODE-9 FLOW-NAV VP-PRECISION-18 DIRECTOR-TECH PLUS UNIFIED-SB 统一故事板 特写进连接器", encoding="utf-8")
    settings = build_settings(tmp_path, prompt_file)
    return TestClient(create_app(settings))


def create_project(client: TestClient, name: str = "测试项目") -> dict:
    response = client.post("/api/projects", json={"name": name, "description": "本地测试"})
    assert response.status_code == 201
    return response.json()


def build_docx_bytes(paragraphs: list[str]) -> bytes:
    from io import BytesIO

    content = "".join(
        f"<w:p><w:r><w:t>{paragraph}</w:t></w:r></w:p>"
        for paragraph in paragraphs
    )
    data = BytesIO()
    with zipfile.ZipFile(data, "w") as archive:
        archive.writestr(
            "[Content_Types].xml",
            """<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>""",
        )
        archive.writestr(
            "word/document.xml",
            f"""<?xml version="1.0" encoding="UTF-8"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>{content}</w:body>
</w:document>""",
        )
    return data.getvalue()


def build_xlsx_bytes(rows: list[list[str]]) -> bytes:
    from io import BytesIO

    sheet_rows = []
    for row_index, row in enumerate(rows, start=1):
        cells = []
        for column_index, value in enumerate(row, start=1):
            column = chr(ord("A") + column_index - 1)
            cells.append(
                f'<c r="{column}{row_index}" t="inlineStr"><is><t>{value}</t></is></c>'
            )
        sheet_rows.append(f'<row r="{row_index}">{"".join(cells)}</row>')
    data = BytesIO()
    with zipfile.ZipFile(data, "w") as archive:
        archive.writestr(
            "[Content_Types].xml",
            """<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
  <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
</Types>""",
        )
        archive.writestr(
            "_rels/.rels",
            """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>""",
        )
        archive.writestr(
            "xl/workbook.xml",
            """<?xml version="1.0" encoding="UTF-8"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheets><sheet name="分镜表" sheetId="1" r:id="rId1"/></sheets>
</workbook>""",
        )
        archive.writestr(
            "xl/_rels/workbook.xml.rels",
            """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
</Relationships>""",
        )
        archive.writestr(
            "xl/worksheets/sheet1.xml",
            f"""<?xml version="1.0" encoding="UTF-8"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <sheetData>{"".join(sheet_rows)}</sheetData>
</worksheet>""",
        )
    return data.getvalue()


def test_create_project_builds_default_tree_and_local_directories(tmp_path: Path) -> None:
    with build_client(tmp_path) as client:
        project = create_project(client)

    assert project["project_code"] == "PRJ001"
    assert project["episodes"][0]["episode_code"] == "EP01"
    assert project["episodes"][0]["scenes"][0]["scene_code"] == "SC01"
    assert project["episodes"][0]["scenes"][0]["shots"][0]["shot_code"] == "SH001"
    assert project["creative_goal"] == "full_pipeline"
    for relative_path in PROJECT_SUBDIRECTORIES:
        assert (tmp_path / "projects" / "PRJ001" / relative_path).is_dir()


def test_real_acceptance_project_prepares_source_without_fake_ai_runs(tmp_path: Path) -> None:
    with build_client(tmp_path) as client:
        response = client.post("/api/projects/real-acceptance", json={})
        project = response.json()
        sources = client.get(f"/api/projects/{project['id']}/source-files").json()
        extractions = client.get(f"/api/projects/{project['id']}/source-text-extractions").json()
        ai_runs = client.get(f"/api/projects/{project['id']}/ai-text-runs").json()

    assert response.status_code == 201
    assert project["name"] == "真实验收短片"
    assert project["episodes"][0]["episode_code"] == "EP01"
    assert project["episodes"][0]["scenes"][0]["scene_code"] == "SC01"
    assert project["episodes"][0]["scenes"][0]["shots"][0]["shot_code"] == "SH001"
    assert sources[0]["category"] == "script_text"
    assert extractions[0]["status"] == "extracted"
    assert "镜头一" in extractions[0]["preview"]
    assert ai_runs == []


def test_project_creative_goal_is_saved_per_project(tmp_path: Path) -> None:
    with build_client(tmp_path) as client:
        project = create_project(client)
        response = client.patch(
            f"/api/projects/{project['id']}/creative-goal",
            json={"creative_goal": "asset_only"},
        )
        detail = client.get(f"/api/projects/{project['id']}")
        invalid = client.patch(
            f"/api/projects/{project['id']}/creative-goal",
            json={"creative_goal": "skip_everything"},
        )

    assert response.status_code == 200
    assert response.json()["creative_goal"] == "asset_only"
    assert detail.json()["creative_goal"] == "asset_only"
    assert invalid.status_code == 422


def test_prompt_storyboard_goal_marks_assets_optional_in_flow_nav(tmp_path: Path) -> None:
    with build_client(tmp_path) as client:
        project = create_project(client)
        full_flow = client.get(f"/api/projects/{project['id']}/flow-nav").json()
        response = client.patch(
            f"/api/projects/{project['id']}/creative-goal",
            json={"creative_goal": "prompt_storyboard"},
        )
        light_flow = client.get(f"/api/projects/{project['id']}/flow-nav").json()

    assert response.status_code == 200
    full_items = {item["key"]: item for item in full_flow["directory"]}
    light_items = {item["key"]: item for item in light_flow["directory"]}
    full_order = [item["key"] for item in full_flow["directory"]]
    light_order = [item["key"] for item in light_flow["directory"]]
    assert full_items["assets"]["marker"] != "可选辅助"
    assert full_items["video_package_draft"]["label"] == "故事板提示词"
    assert full_order.index("video_package_draft") < full_order.index("storyboard")
    assert full_order.index("storyboard") < full_order.index("assets")
    assert full_order.index("assets") < full_order.index("video_package")
    assert light_items["assets"]["marker"] == "可选辅助"
    assert light_items["assets"]["status_level"] == "optional"
    assert light_items["assets"]["short_status"] == "资产可选，需要一致性时再做"
    assert light_order.index("video_package_draft") < light_order.index("storyboard")
    assert light_order.index("storyboard") < light_order.index("video_package")
    assert light_order.index("video_package") < light_order.index("assets")
    assert "文生视频提示词" in light_items["video_package"]["detail"]


def test_flow_nav_does_not_mark_legacy_five_second_prompts_complete(tmp_path: Path) -> None:
    with build_client(tmp_path) as client:
        project = create_project(client)
        shot = project["episodes"][0]["scenes"][0]["shots"][0]
        with Session(client.app.state.database_engine) as session:
            draft = VpBlock(
                shot_id=shot["id"],
                version_number=1,
                package_stage="director_draft",
                prompt="旧版 5 秒分镜提示词",
                negative_prompt="",
                duration_seconds=5,
                provider_profile_id="mock",
                status="confirmed_current",
            )
            session.add(draft)
            session.commit()
            session.refresh(draft)
            session.add(VpBlock(
                shot_id=shot["id"],
                version_number=2,
                package_stage="final_execution",
                basis_vp_block_id=draft.id,
                prompt="旧版 5 秒成片提示词",
                negative_prompt="",
                duration_seconds=5,
                provider_profile_id="mock",
                status="confirmed_current",
            ))
            session.commit()

        flow = client.get(f"/api/projects/{project['id']}/flow-nav").json()

    items = {item["key"]: item for item in flow["directory"]}
    assert items["video_package_draft"]["status_level"] != "done"
    assert items["video_package_draft"]["short_status"] == "1 个旧版 5 秒镜头待重建"
    assert items["video_package"]["status_level"] != "done"
    assert items["video_package"]["short_status"] == "需先重建镜头时长"


def test_hierarchy_codes_increment_and_archive_records_can_restore(tmp_path: Path) -> None:
    with build_client(tmp_path) as client:
        project = create_project(client)
        project_id = project["id"]
        first_episode = project["episodes"][0]
        first_scene = first_episode["scenes"][0]

        response = client.post(f"/api/projects/{project_id}/episodes")
        assert response.status_code == 201
        assert response.json()["episodes"][1]["episode_code"] == "EP02"

        response = client.post(f"/api/episodes/{first_episode['id']}/scenes")
        assert response.status_code == 201
        assert response.json()["episodes"][0]["scenes"][1]["scene_code"] == "SC02"

        response = client.post(f"/api/scenes/{first_scene['id']}/shots")
        assert response.status_code == 201
        assert response.json()["episodes"][0]["scenes"][0]["shots"][1]["shot_code"] == "SH002"

        response = client.delete(f"/api/projects/{project_id}")
        assert response.json()["is_archived"] is True
        assert client.get("/api/projects").json() == []

        response = client.get("/api/projects", params={"include_archived": True})
        assert response.json()[0]["is_archived"] is True

        response = client.post(f"/api/projects/{project_id}/restore")
        assert response.json()["is_archived"] is False


def test_project_overview_export_and_hard_delete_are_safe(tmp_path: Path) -> None:
    with build_client(tmp_path) as client:
        project = create_project(client, "可删除测试项目")
        project_id = project["id"]
        source = client.post(
            f"/api/projects/{project_id}/source-files/text",
            json={
                "category": "script_text",
                "title": "第一场剧本",
                "content": "第一场：雨夜。镜头一：人物走入长廊。",
            },
        ).json()
        overview = client.get("/api/projects/overview").json()
        archive = client.get(f"/api/projects/{project_id}/export")
        wrong_delete = client.post(
            f"/api/projects/{project_id}/hard-delete",
            json={"confirm_delete": True, "confirm_project_name": "错误项目名"},
        )
        missing_confirm = client.post(
            f"/api/projects/{project_id}/hard-delete",
            json={"confirm_delete": False, "confirm_project_name": "可删除测试项目"},
        )
        delete = client.post(
            f"/api/projects/{project_id}/hard-delete",
            json={"confirm_delete": True, "confirm_project_name": "可删除测试项目"},
        )
        after = client.get("/api/projects", params={"include_archived": True}).json()

    assert overview[0]["project_code"] == "PRJ001"
    assert overview[0]["source_file_count"] == 1
    assert overview[0]["episode_count"] == 1
    assert overview[0]["scene_count"] == 1
    assert overview[0]["shot_count"] == 1
    assert archive.status_code == 200
    zip_path = tmp_path / "project_export.zip"
    zip_path.write_bytes(archive.content)
    with zipfile.ZipFile(zip_path) as exported:
        names = exported.namelist()
        assert "PRJ001/project_manifest.json" in names
        assert f"PRJ001/{source['relative_path']}" in names
        assert not any(".env" in name for name in names)
    assert wrong_delete.status_code == 400
    assert missing_confirm.status_code == 400
    assert delete.status_code == 204
    assert after == []
    assert not (tmp_path / "projects" / "PRJ001").exists()


def test_reveal_in_folder_opens_only_paths_inside_project(tmp_path: Path, monkeypatch) -> None:
    opened_commands: list[list[str]] = []

    class FakePopen:
        def __init__(self, command, stdout=None, stderr=None):
            opened_commands.append(list(command))

    monkeypatch.setattr("app.services.projects.subprocess.Popen", FakePopen)
    with build_client(tmp_path) as client:
        project = create_project(client, "定位文件夹测试项目")
        project_id = project["id"]
        project_root = tmp_path / "projects" / project["project_code"]
        asset_file = project_root / "01_sources" / "示例.txt"
        asset_file.parent.mkdir(parents=True, exist_ok=True)
        asset_file.write_text("测试文件", encoding="utf-8")

        root_reveal = client.post(
            f"/api/projects/{project_id}/reveal",
            json={"relative_path": ""},
        )
        file_reveal = client.post(
            f"/api/projects/{project_id}/reveal",
            json={"relative_path": "01_sources/示例.txt"},
        )
        traversal = client.post(
            f"/api/projects/{project_id}/reveal",
            json={"relative_path": "../../outside"},
        )
        missing = client.post(
            f"/api/projects/{project_id}/reveal",
            json={"relative_path": "01_sources/不存在.png"},
        )

    assert root_reveal.status_code == 200
    assert root_reveal.json()["opened"] is True
    assert file_reveal.status_code == 200
    assert traversal.status_code == 400
    assert missing.status_code == 404
    assert opened_commands[0] == ["open", str(project_root.resolve())]
    assert opened_commands[1] == ["open", "-R", str(asset_file.resolve())]
    assert len(opened_commands) == 2


def test_upload_saves_supported_files_without_overwriting_same_name(tmp_path: Path) -> None:
    with build_client(tmp_path) as client:
        project = create_project(client)
        project_id = project["id"]

        first = client.post(
            f"/api/projects/{project_id}/source-files",
            data={"category": "script"},
            files={"file": ("剧本.txt", b"first", "text/plain")},
        )
        second = client.post(
            f"/api/projects/{project_id}/source-files",
            data={"category": "script"},
            files={"file": ("剧本.txt", b"second", "text/plain")},
        )
        invalid = client.post(
            f"/api/projects/{project_id}/source-files",
            data={"category": "script"},
            files={"file": ("剧本.exe", b"no", "application/octet-stream")},
        )

    assert first.status_code == 201
    assert second.status_code == 201
    assert invalid.status_code == 400
    assert first.json()["stored_filename"] != second.json()["stored_filename"]
    assert (tmp_path / "projects" / "PRJ001" / first.json()["relative_path"]).read_bytes() == b"first"
    assert (tmp_path / "projects" / "PRJ001" / second.json()["relative_path"]).read_bytes() == b"second"


def test_save_text_source_file_creates_local_txt_metadata(tmp_path: Path) -> None:
    with build_client(tmp_path) as client:
        project = create_project(client)
        response = client.post(
            f"/api/projects/{project['id']}/source-files/text",
            json={
                "category": "script_text",
                "title": "第一场剧本",
                "content": "皇城夜雨，人物在殿前对峙。",
            },
        )

    assert response.status_code == 201
    payload = response.json()
    assert payload["category"] == "script_text"
    assert payload["content_type"] == "text/plain; charset=utf-8"
    saved = tmp_path / "projects" / "PRJ001" / payload["relative_path"]
    assert saved.read_text(encoding="utf-8") == "皇城夜雨，人物在殿前对峙。"


def test_text_extraction_and_ucode_start_is_manual_record_only(tmp_path: Path) -> None:
    with build_client(tmp_path) as client:
        project = create_project(client)
        source = client.post(
            f"/api/projects/{project['id']}/source-files/text",
            json={
                "category": "script_text",
                "title": "第一集剧本",
                "content": "第一场 宫门外\n镜头一：雨夜对峙。\n镜头二：旧信落地。",
            },
        ).json()
        extraction = client.post(f"/api/source-files/{source['id']}/extract-text")
        run = client.post(
            f"/api/projects/{project['id']}/ucode-runs",
            json={"ucode_action": "start", "scope_code": "EP01", "additional_request": "资料来源：第一集剧本"},
        )

    assert extraction.status_code == 201
    assert extraction.json()["status"] == "extracted"
    assert extraction.json()["character_count"] > 0
    assert "手动记录已保存" in run.json()["result_summary"]
    assert "不是 AI 分析结果" in run.json()["result_summary"]


def test_txt_md_docx_and_xlsx_uploads_can_extract_text_but_pdf_is_unsupported(tmp_path: Path) -> None:
    with build_client(tmp_path) as client:
        project = create_project(client)
        txt = client.post(
            f"/api/projects/{project['id']}/source-files",
            data={"category": "script"},
            files={"file": ("剧本.txt", "第一场\n镜头一：开场".encode("utf-8"), "text/plain")},
        ).json()
        md = client.post(
            f"/api/projects/{project['id']}/source-files",
            data={"category": "storyboard_table"},
            files={"file": ("分镜.md", "SC01\nSH001：远景".encode("utf-8"), "text/markdown")},
        ).json()
        pdf = client.post(
            f"/api/projects/{project['id']}/source-files",
            data={"category": "script"},
            files={"file": ("剧本.pdf", b"%PDF", "application/pdf")},
        ).json()
        docx = client.post(
            f"/api/projects/{project['id']}/source-files",
            data={"category": "script"},
            files={"file": ("剧本.docx", build_docx_bytes(["第一场 宫门外", "镜头一：雨夜对峙。", "镜头二：旧信落地。"]), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
        ).json()
        xlsx = client.post(
            f"/api/projects/{project['id']}/source-files",
            data={"category": "storyboard_table"},
            files={
                "file": (
                    "分镜表.xlsx",
                    build_xlsx_bytes([
                        ["场次", "镜头", "画面"],
                        ["第一场", "镜头一", "女孩走进雨夜长廊。"],
                        ["第一场", "镜头二", "旧信从桌面滑落。"],
                    ]),
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            },
        ).json()
        txt_extraction = client.post(f"/api/source-files/{txt['id']}/extract-text").json()
        md_extraction = client.post(f"/api/source-files/{md['id']}/extract-text").json()
        docx_extraction = client.post(f"/api/source-files/{docx['id']}/extract-text").json()
        xlsx_extraction = client.post(f"/api/source-files/{xlsx['id']}/extract-text").json()
        pdf_extraction = client.post(f"/api/source-files/{pdf['id']}/extract-text").json()

    assert txt_extraction["status"] == "extracted"
    assert md_extraction["status"] == "extracted"
    assert docx_extraction["status"] == "extracted"
    assert docx_extraction["line_count"] == 3
    assert "镜头二" in docx_extraction["preview"]
    assert xlsx_extraction["status"] == "extracted"
    assert xlsx_extraction["line_count"] == 3
    assert "女孩走进雨夜长廊" in xlsx_extraction["preview"]
    assert pdf_extraction["status"] == "unsupported"
    assert "暂未解析正文" in pdf_extraction["error"]


def test_docx_extraction_can_create_short_drama_planning_items(tmp_path: Path) -> None:
    with build_client(tmp_path) as client:
        project = create_project(client)
        docx = client.post(
            f"/api/projects/{project['id']}/source-files",
            data={"category": "script"},
            files={"file": ("前十集.docx", build_docx_bytes([
                "第一集",
                "朝天殿",
                "人物：李道生、文武百官",
                "△大殿之上，文武百官跪拜叩首。",
                "李道生：三千道果，留待有缘人吧！",
                "第二集",
                "2-1，英魂学院-英魂台",
                "△李伊伊站在英魂碑前方。",
            ]), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
        ).json()
        extraction = client.post(f"/api/source-files/{docx['id']}/extract-text").json()
        draft = client.post(
            f"/api/projects/{project['id']}/planning-drafts",
            json={"source_extraction_id": extraction["id"]},
        )

    assert extraction["status"] == "extracted"
    assert draft.status_code == 410
    assert "用 AI 生成分镜规划" in draft.json()["detail"]


def test_upload_storyboard_table_image_is_saved_without_parsing(tmp_path: Path) -> None:
    with build_client(tmp_path) as client:
        project = create_project(client)
        response = client.post(
            f"/api/projects/{project['id']}/source-files",
            data={"category": "storyboard_table_image"},
            files={"file": ("分镜表.png", b"fake-png", "image/png")},
        )

    assert response.status_code == 201
    payload = response.json()
    assert payload["category"] == "storyboard_table_image"
    assert payload["relative_path"].startswith("00_source/references/storyboard_style/")
    assert (tmp_path / "projects" / "PRJ001" / payload["relative_path"]).read_bytes() == b"fake-png"


def test_local_planning_draft_endpoint_is_disabled(tmp_path: Path) -> None:
    with build_client(tmp_path) as client:
        project = create_project(client)
        source = client.post(
            f"/api/projects/{project['id']}/source-files/text",
            json={
                "category": "script_text",
                "title": "规划文本",
                "content": "第一场 宫门外\n镜头一：雨夜对峙。\n镜头二：旧信落地。\n第二场 大殿内\n镜头一：众人沉默。",
            },
        ).json()
        extraction = client.post(f"/api/source-files/{source['id']}/extract-text").json()
        draft = client.post(
            f"/api/projects/{project['id']}/planning-drafts",
            json={"source_extraction_id": extraction["id"], "max_items": 8},
        )

    assert draft.status_code == 410
    assert "本地规则分镜规划已停用" in draft.json()["detail"]


def test_disabled_local_planning_draft_does_not_touch_complex_project_tree(tmp_path: Path) -> None:
    with build_client(tmp_path) as client:
        project = create_project(client)
        first_scene = project["episodes"][0]["scenes"][0]
        client.post(f"/api/scenes/{first_scene['id']}/shots")
        source = client.post(
            f"/api/projects/{project['id']}/source-files/text",
            json={"category": "script_text", "title": "规划文本", "content": "第一场\n镜头一：开场。"},
        ).json()
        extraction = client.post(f"/api/source-files/{source['id']}/extract-text").json()
        draft = client.post(
            f"/api/projects/{project['id']}/planning-drafts",
            json={"source_extraction_id": extraction["id"]},
        )
        detail = client.get(f"/api/projects/{project['id']}").json()

    assert draft.status_code == 410
    assert len(detail["episodes"][0]["scenes"][0]["shots"]) == 2


def test_upload_rejects_files_larger_than_25_mb(tmp_path: Path) -> None:
    with build_client(tmp_path) as client:
        project = create_project(client)
        response = client.post(
            f"/api/projects/{project['id']}/source-files",
            data={"category": "reference"},
            files={"file": ("large.png", b"x" * (MAX_UPLOAD_BYTES + 1), "image/png")},
        )

    assert response.status_code == 413
    references_root = tmp_path / "projects" / "PRJ001" / "00_source" / "references"
    assert not [path for path in references_root.rglob("*") if path.is_file()]


def test_ucode_mock_run_creates_checkpoint_only_when_required(tmp_path: Path) -> None:
    with build_client(tmp_path) as client:
        project = create_project(client)
        project_id = project["id"]
        start = client.post(
            f"/api/projects/{project_id}/ucode-runs",
            json={
                "ucode_action": "start",
                "scope_code": "EP01",
                "additional_request": "先做导演分析",
            },
        )
        check = client.post(
            f"/api/projects/{project_id}/ucode-runs",
            json={
                "ucode_action": "check",
                "scope_code": "EP01SC01",
                "additional_request": "",
            },
        )
        history = client.get(f"/api/projects/{project_id}/ucode-runs")

    assert start.status_code == 201
    assert start.json()["checkpoint_required"] is True
    assert "手动记录已保存" in start.json()["result_summary"]
    assert "不是 AI 分析结果" in start.json()["result_summary"]
    assert len(start.json()["checkpoints"]) == 1
    assert check.status_code == 201
    assert check.json()["checkpoint_required"] is False
    assert check.json()["checkpoints"] == []
    assert len(history.json()) == 2


def test_flow_nav_requires_manual_director_option_confirmation(tmp_path: Path) -> None:
    with build_client(tmp_path) as client:
        project = create_project(client)
        episode = project["episodes"][0]
        initial = client.get(f"/api/projects/{project['id']}/flow-nav").json()
        assert initial["current_stage"] == "上传剧本 / 分镜资料"
        assert initial["blocking_reason"] == "当前项目还没有剧本或分镜资料，所以不能进入导演分析。"
        assert initial["directory"][0]["status_level"] == "blocked"
        assert initial["directory"][0]["short_status"] == "请先上传资料"
        client.post(
            f"/api/projects/{project['id']}/source-files/text",
            json={"category": "script_text", "title": "剧本", "content": "第一场剧情"},
        )
        waiting = client.get(f"/api/projects/{project['id']}/flow-nav").json()
        assert waiting["current_stage"] == "真实 AI 导演分析"
        assert waiting["primary_action_href"] == "/start-plan#ai-director-analysis"
        confirmed = client.post(
            f"/api/episodes/{episode['id']}/director-option-confirmations",
            json={"option_name": "克制压迫版", "notes": "人工确认"},
        )
        assert confirmed.status_code == 201
        assert confirmed.json()["current_stage"] == "真实 AI 导演分析"
        assert confirmed.json()["director_option"]["option_name"] == "克制压迫版"
        assert confirmed.json()["director_option"]["option_name"] == "克制压迫版"
