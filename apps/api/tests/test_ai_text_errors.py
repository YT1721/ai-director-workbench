from app.services.ai_text import _friendly_text_provider_error


def test_remote_disconnect_error_is_explained_without_automatic_retry() -> None:
    message = _friendly_text_provider_error(
        RuntimeError("Server disconnected without sending a response.")
    )

    assert "项目和已保存资料没有损坏" in message
    assert "没有取得可保存的分析结果" in message
    assert "没有自动重试" in message
    assert "从剧本识别资产" in message
    assert "Server disconnected" not in message
