from __future__ import annotations

from app.config import Settings
from app.providers.text import HuimengChatTextProvider
from app.services.ai_text import _module_output_limit


class _FakeResponse:
    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return {
            "choices": [{
                "finish_reason": "stop",
                "message": {"content": '{"vp_precision_18": []}', "reasoning_content": "内部推理"},
            }],
            "usage": {
                "prompt_tokens": 100,
                "completion_tokens": 80,
                "completion_tokens_details": {"reasoning_tokens": 30},
            },
        }


def test_huimeng_structured_request_disables_reasoning_and_records_finish_metadata(monkeypatch) -> None:
    captured: dict = {}

    def fake_post(url: str, **kwargs):
        captured["url"] = url
        captured["json"] = kwargs["json"]
        return _FakeResponse()

    monkeypatch.setattr("app.providers.text.httpx.post", fake_post)
    provider = HuimengChatTextProvider(
        "secret",
        "https://example.test/v1",
        "deepseek-v4.1-flash",
        12000,
        structured_json=True,
        disable_reasoning=True,
    )

    result = provider.generate("严格输出 JSON", "生成分镜提示词")

    assert captured["url"] == "https://example.test/v1/chat/completions"
    assert captured["json"]["max_tokens"] == 12000
    assert captured["json"]["response_format"] == {"type": "json_object"}
    assert captured["json"]["reasoning_effort"] == "none"
    assert captured["json"]["thinking"] == {"type": "disabled"}
    assert result.text == '{"vp_precision_18": []}'
    assert result.finish_reason == "stop"
    assert result.reasoning_tokens == 30


def test_vp_precision_output_budget_is_large_enough_for_full_18_item_json(tmp_path) -> None:
    settings = Settings(
        repo_root=tmp_path,
        database_url=f"sqlite:///{tmp_path / 'app.db'}",
        projects_root=tmp_path / "projects",
        system_prompt_file=tmp_path / "prompt.txt",
        provider_mode="jimeng_cli",
        cors_origins=("http://localhost:6001",),
        openai_max_output_tokens=4000,
    )

    assert _module_output_limit(settings, "vp_precision_18") == 12000
