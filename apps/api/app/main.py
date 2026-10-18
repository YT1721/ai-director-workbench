from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import Settings
from app.database import create_database_engine, initialize_database
from app.routers.ai_text import router as ai_text_router
from app.routers.assets import router as assets_router
from app.routers.flow_nav import router as flow_nav_router
from app.routers.local_env import router as local_env_router
from app.routers.planning import router as planning_router
from app.routers.seedance_os import router as seedance_os_router
from app.routers.storyboards import router as storyboards_router
from app.routers.videos import router as videos_router
from app.routers.workbench import router as workbench_router
from app.routers.workflows import router as workflows_router
from app.schemas.system import HealthResponse, SystemPromptStatusResponse
from app.services.system_prompt import load_system_prompt_status
from app.services.image_task_supervisor import ImageTaskSupervisor
from app.services.video_task_supervisor import VideoTaskSupervisor
from app.services.vp_generation_supervisor import VpGenerationSupervisor
from app.providers.jimeng_cli import detect_jimeng_cli_capabilities


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved_settings = settings or Settings.from_environment()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        resolved_settings.projects_root.mkdir(parents=True, exist_ok=True)
        engine = create_database_engine(resolved_settings)
        initialize_database(engine, resolved_settings)
        app.state.database_engine = engine
        supervisor = VideoTaskSupervisor(engine, resolved_settings)
        vp_supervisor = VpGenerationSupervisor(engine, resolved_settings)
        image_supervisor = ImageTaskSupervisor(engine, resolved_settings)
        app.state.video_task_supervisor = supervisor
        app.state.vp_generation_supervisor = vp_supervisor
        app.state.image_task_supervisor = image_supervisor
        app.state.system_prompt_status = load_system_prompt_status(
            resolved_settings.system_prompt_file,
            resolved_settings.provider_mode,
        )
        # Capability probing only reads local CLI version/help and never submits a task.
        app.state.jimeng_cli_capabilities = await asyncio.to_thread(detect_jimeng_cli_capabilities)
        supervisor.start()
        vp_supervisor.start()
        image_supervisor.start()
        yield
        image_supervisor.stop()
        vp_supervisor.stop()
        supervisor.stop()
        engine.dispose()

    app = FastAPI(
        title="AI导演工作台 API",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.state.settings = resolved_settings
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(resolved_settings.cors_origins),
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["*"],
    )
    app.mount(
        "/local-assets",
        StaticFiles(directory=resolved_settings.projects_root, check_dir=False),
        name="local-assets",
    )
    app.include_router(workbench_router)
    app.include_router(flow_nav_router)
    app.include_router(assets_router)
    app.include_router(storyboards_router)
    app.include_router(videos_router)
    app.include_router(workflows_router)
    app.include_router(planning_router)
    app.include_router(ai_text_router)
    app.include_router(local_env_router)
    app.include_router(seedance_os_router)

    @app.get("/health", response_model=HealthResponse)
    def health(request: Request) -> HealthResponse:
        status = request.app.state.system_prompt_status
        return HealthResponse(
            status="ok",
            database="initialized",
            provider_mode=resolved_settings.provider_mode,
            system_prompt=status,
        )

    @app.get(
        "/api/system-prompt/status",
        response_model=SystemPromptStatusResponse,
    )
    def system_prompt_status(request: Request) -> SystemPromptStatusResponse:
        return request.app.state.system_prompt_status

    return app


app = create_app()
