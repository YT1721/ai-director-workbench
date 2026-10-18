from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

import httpx

TEXT_PROVIDER_TIMEOUT = httpx.Timeout(240.0, connect=20.0)


@dataclass(frozen=True)
class TextSummaryResult:
    text: str
    input_tokens: int = 0
    cached_input_tokens: int = 0
    output_tokens: int = 0
    reasoning_tokens: int = 0
    finish_reason: str = ""


class TextProviderEmptyResponseError(RuntimeError):
    def __init__(self, *, finish_reason: str = "", output_tokens: int = 0, reasoning_tokens: int = 0):
        self.finish_reason = finish_reason
        self.output_tokens = output_tokens
        self.reasoning_tokens = reasoning_tokens
        super().__init__(
            "text_provider_empty_response "
            f"finish_reason={finish_reason or 'unknown'} "
            f"output_tokens={output_tokens} reasoning_tokens={reasoning_tokens}"
        )


class TextProvider(Protocol):
    def generate(self, instructions: str, input_text: str) -> TextSummaryResult: ...
    def summarize(self, report_json: str) -> TextSummaryResult: ...


class OpenAIResponsesTextProvider:
    def __init__(self, api_key: str, model: str, max_output_tokens: int = 4000):
        self.api_key = api_key
        self.model = model
        self.max_output_tokens = max_output_tokens

    def summarize(self, report_json: str) -> TextSummaryResult:
        return self.generate(
            "你是影视制作检查助手。只根据结构化检查结果输出简短中文摘要，不提出额外生成任务。",
            report_json,
        )

    def generate(self, instructions: str, input_text: str) -> TextSummaryResult:
        response = httpx.post(
            "https://api.openai.com/v1/responses",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={
                "model": self.model,
                "store": False,
                "max_output_tokens": self.max_output_tokens,
                "instructions": instructions,
                "input": input_text,
            },
            timeout=TEXT_PROVIDER_TIMEOUT,
        )
        response.raise_for_status()
        payload: dict[str, Any] = response.json()
        usage = payload.get("usage") or {}
        details = usage.get("input_tokens_details") or {}
        output_details = usage.get("output_tokens_details") or {}
        text = payload.get("output_text") or self._extract_text(payload)
        return TextSummaryResult(
            text=text.strip(),
            input_tokens=int(usage.get("input_tokens") or 0),
            cached_input_tokens=int(details.get("cached_tokens") or 0),
            output_tokens=int(usage.get("output_tokens") or 0),
            reasoning_tokens=int(output_details.get("reasoning_tokens") or 0),
            finish_reason=str((payload.get("incomplete_details") or {}).get("reason") or payload.get("status") or ""),
        )

    @staticmethod
    def _extract_text(payload: dict[str, Any]) -> str:
        return "".join(
            part.get("text", "")
            for item in payload.get("output", [])
            for part in item.get("content", [])
            if part.get("type") == "output_text"
        )


class HuimengChatTextProvider:
    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        max_output_tokens: int = 4000,
        *,
        structured_json: bool = False,
        disable_reasoning: bool = False,
    ):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.max_output_tokens = max_output_tokens
        self.structured_json = structured_json
        self.disable_reasoning = disable_reasoning

    def summarize(self, report_json: str) -> TextSummaryResult:
        return self.generate(
            "你是影视制作检查助手。只根据结构化检查结果输出简短中文摘要，不提出额外生成任务。",
            report_json,
        )

    def generate(self, instructions: str, input_text: str) -> TextSummaryResult:
        request_payload: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": instructions},
                {"role": "user", "content": input_text},
            ],
            "max_tokens": self.max_output_tokens,
        }
        if self.structured_json:
            request_payload["response_format"] = {"type": "json_object"}
        if self.disable_reasoning and any(marker in self.model.lower() for marker in ("deepseek", "glm")):
            request_payload["reasoning_effort"] = "none"
            request_payload["thinking"] = {"type": "disabled"}
        response = httpx.post(
            f"{self.base_url}/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            json=request_payload,
            timeout=TEXT_PROVIDER_TIMEOUT,
        )
        response.raise_for_status()
        payload: dict[str, Any] = response.json()
        usage = payload.get("usage") or {}
        completion_details = usage.get("completion_tokens_details") or {}
        choices = payload.get("choices") or []
        message = choices[0].get("message", {}) if choices else {}
        text = message.get("content") or payload.get("output_text") or ""
        return TextSummaryResult(
            text=str(text).strip(),
            input_tokens=int(usage.get("prompt_tokens") or usage.get("input_tokens") or 0),
            cached_input_tokens=int((usage.get("prompt_tokens_details") or {}).get("cached_tokens") or 0),
            output_tokens=int(usage.get("completion_tokens") or usage.get("output_tokens") or 0),
            reasoning_tokens=int(completion_details.get("reasoning_tokens") or 0),
            finish_reason=str(choices[0].get("finish_reason") or "") if choices else "",
        )
