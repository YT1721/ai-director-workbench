from __future__ import annotations

from pydantic import BaseModel, Field


class LocalEnvStatusView(BaseModel):
    openai_api_key_configured: bool
    openai_model_director: str = ""
    openai_text_model: str
    openai_model_routine: str
    openai_image_model_production: str = ""
    openai_image_model_draft: str = ""
    openai_image_model: str
    openai_max_output_tokens: int
    text_provider_mode: str
    enable_real_text_analysis: bool
    enable_real_openai: bool
    enable_real_image_generation: bool
    huimengi_api_key_configured: bool
    huimengi_text_base_url: str
    huimengi_text_model: str
    text_api_key_configured: bool = False
    text_base_url: str = ""
    text_model: str = ""
    text_service_label: str = ""
    image_provider_mode: str = "huimeng_tasks"
    image_api_key_configured: bool = False
    image_base_url: str = ""
    image_model: str = ""
    huimengi_image_base_url: str
    huimengi_image_model: str
    huimengi_video_base_url: str
    huimengi_video_model: str
    huimengi_base_url: str
    huimengi_model_id: str
    enable_real_seedance: bool
    seedance_real_submit_enabled: bool = False
    video_provider_mode: str
    default_video_provider_id: str = ""
    seedance_aggregator_base_url: str = ""
    seedance_aggregator_create_task_path: str = ""
    seedance_aggregator_get_task_path_template: str = ""
    seedance_aggregator_auth_type: str = ""
    seedance_aggregator_auth_header: str = ""
    seedance_aggregator_auth_prefix: str = ""
    seedance_aggregator_model_id: str = ""
    seedance_aggregator_api_key_configured: bool = False
    env_file_exists: bool
    env_file_path: str
    secret_policy: str


class LocalEnvUpdate(BaseModel):
    confirm_local_env_write: bool = False
    openai_api_key: str = Field(default="", max_length=4000)
    openai_model_director: str = Field(default="", max_length=160)
    openai_text_model: str = Field(default="", max_length=160)
    openai_model_routine: str = Field(default="", max_length=120)
    openai_image_model_production: str = Field(default="", max_length=160)
    openai_image_model_draft: str = Field(default="", max_length=160)
    openai_image_model: str = Field(default="", max_length=160)
    openai_max_output_tokens: int | None = Field(default=None, ge=256, le=16000)
    text_provider_mode: str = Field(default="", max_length=80)
    enable_real_text_analysis: bool | None = None
    enable_real_openai: bool | None = None
    enable_real_image_generation: bool | None = None
    huimengi_api_key: str = Field(default="", max_length=4000)
    huimengi_text_base_url: str = Field(default="", max_length=500)
    huimengi_text_model: str = Field(default="", max_length=160)
    text_api_key: str = Field(default="", max_length=4000)
    text_base_url: str = Field(default="", max_length=500)
    text_model: str = Field(default="", max_length=160)
    image_provider_mode: str = Field(default="", max_length=80)
    image_api_key: str = Field(default="", max_length=4000)
    image_base_url: str = Field(default="", max_length=500)
    image_model: str = Field(default="", max_length=160)
    huimengi_image_base_url: str = Field(default="", max_length=500)
    huimengi_image_model: str = Field(default="", max_length=160)
    huimengi_video_base_url: str = Field(default="", max_length=500)
    huimengi_video_model: str = Field(default="", max_length=160)
    huimengi_base_url: str = Field(default="", max_length=500)
    huimengi_model_id: str = Field(default="", max_length=160)
    enable_real_seedance: bool | None = None
    seedance_real_submit_enabled: bool | None = None
    video_provider_mode: str = Field(default="", max_length=80)
    default_video_provider_id: str = Field(default="", max_length=120)
    seedance_aggregator_api_key: str = Field(default="", max_length=4000)
    seedance_aggregator_base_url: str = Field(default="", max_length=500)
    seedance_aggregator_create_task_path: str = Field(default="", max_length=500)
    seedance_aggregator_get_task_path_template: str = Field(default="", max_length=500)
    seedance_aggregator_auth_type: str = Field(default="", max_length=80)
    seedance_aggregator_auth_header: str = Field(default="", max_length=120)
    seedance_aggregator_auth_prefix: str = Field(default="", max_length=120)
    seedance_aggregator_model_id: str = Field(default="", max_length=180)
