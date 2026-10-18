from pydantic import BaseModel


class SystemPromptStatusResponse(BaseModel):
    loaded: bool
    filename: str
    version: str
    provider_mode: str
    last_updated: str | None = None
    error: str | None = None


class HealthResponse(BaseModel):
    status: str
    database: str
    provider_mode: str
    system_prompt: SystemPromptStatusResponse
