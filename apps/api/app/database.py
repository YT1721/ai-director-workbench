from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import inspect, text
from sqlmodel import Session, SQLModel, create_engine, select

from app.config import Settings
from app.models import AppMetadata, UcodeCommand
from app.services.videos import seed_configured_seedance_provider, seed_huimeng_provider, seed_seedance25_provider


UCODE_COMMANDS = (
    ("start", "开始", "V7｜开始｜{scope}", True),
    ("plan", "规划", "V7｜规划｜{scope}", True),
    ("assets", "资产", "V7｜资产｜{scope}", True),
    ("storyboard", "故事板", "V7｜故事板｜{scope}", True),
    ("video_package", "视频包", "V7｜视频包｜{scope}", False),
    ("batch_video", "批量视频", "V7｜批量视频｜{scope}", True),
    ("one_click", "一键推进", "V7｜一键｜{scope}", True),
    ("check", "检查", "V7｜检查｜{scope}", False),
    ("fix", "修正", "V7｜修正｜{scope}", True),
)

LEGACY_TABLE_NAMES = (
    ("project", "projects"),
    ("episode", "episodes"),
    ("scene", "scenes"),
    ("shot", "shots"),
    ("sourcefile", "source_files"),
    ("ucodecommand", "ucode_commands"),
    ("ucodeexecutionrun", "ucode_execution_runs"),
    ("workflowcheckpoint", "workflow_checkpoints"),
)


def create_database_engine(settings: Settings):
    connect_args = (
        {"check_same_thread": False}
        if settings.database_url.startswith("sqlite")
        else {}
    )
    return create_engine(settings.database_url, connect_args=connect_args)


def initialize_database(engine, settings: Settings | None = None) -> None:
    _rename_legacy_tables(engine)
    SQLModel.metadata.create_all(engine)
    _ensure_project_columns(engine)
    _ensure_cost_usage_columns(engine)
    _ensure_ai_text_run_columns(engine)
    _ensure_v7_precision_columns(engine)
    _ensure_director_tech_columns(engine)
    _ensure_seedance_skill_os_columns(engine)
    _ensure_scene_asset_columns(engine)
    _ensure_asset_requirement_columns(engine)
    _ensure_batch_video_columns(engine)
    with Session(engine) as session:
        metadata = session.exec(
            select(AppMetadata).where(AppMetadata.key == "database_initialized")
        ).first()
        if metadata is None:
            session.add(
                AppMetadata(
                    key="database_initialized",
                    value=datetime.now(timezone.utc).isoformat(),
                )
            )
        for action, display_name, default_template, checkpoint_required in UCODE_COMMANDS:
            if session.get(UcodeCommand, action) is None:
                session.add(
                    UcodeCommand(
                        id=action,
                        action=action,
                        display_name=display_name,
                        default_template=default_template,
                        checkpoint_required=checkpoint_required,
                    )
                )
        session.commit()
        seed_huimeng_provider(session)
        if settings:
            seed_configured_seedance_provider(session, settings)
            seed_seedance25_provider(session, settings)


def _rename_legacy_tables(engine) -> None:
    with engine.begin() as connection:
        table_names = set(inspect(connection).get_table_names())
        for old_name, new_name in LEGACY_TABLE_NAMES:
            if old_name in table_names and new_name not in table_names:
                connection.execute(
                    text(f'ALTER TABLE "{old_name}" RENAME TO "{new_name}"')
                )
                table_names.remove(old_name)
                table_names.add(new_name)


def _ensure_project_columns(engine) -> None:
    with engine.begin() as connection:
        existing = {item["name"] for item in inspect(connection).get_columns("projects")}
        if "creative_goal" not in existing:
            connection.execute(
                text(
                    'ALTER TABLE "projects" ADD COLUMN "creative_goal" '
                    "VARCHAR NOT NULL DEFAULT 'full_pipeline'"
                )
            )


def _ensure_scene_asset_columns(engine) -> None:
    """场景资产允许同一场次下存在多个不同地点（name 区分），并去掉 scene_id 唯一索引。"""
    with engine.begin() as connection:
        inspector = inspect(connection)
        if "scene_assets" not in set(inspector.get_table_names()):
            return
        existing = {item["name"] for item in inspector.get_columns("scene_assets")}
        if "name" not in existing:
            connection.execute(
                text("ALTER TABLE \"scene_assets\" ADD COLUMN \"name\" VARCHAR NOT NULL DEFAULT ''")
            )
        for index in inspector.get_indexes("scene_assets"):
            if index.get("unique") and "scene_id" in list(index.get("column_names") or []):
                connection.execute(text(f'DROP INDEX IF EXISTS "{index["name"]}"'))
        connection.execute(
            text('CREATE INDEX IF NOT EXISTS "ix_scene_assets_scene_id" ON "scene_assets" ("scene_id")')
        )


def _ensure_asset_requirement_columns(engine) -> None:
    with engine.begin() as connection:
        inspector = inspect(connection)
        if "asset_requirements" not in set(inspector.get_table_names()):
            return
        existing = {item["name"] for item in inspector.get_columns("asset_requirements")}
        additions = {
            "reference_mode": "VARCHAR NOT NULL DEFAULT 'visual'",
            "importance_reason": "VARCHAR NOT NULL DEFAULT ''",
            "text_prompt": "VARCHAR NOT NULL DEFAULT ''",
        }
        for name, sql_type in additions.items():
            if name not in existing:
                connection.execute(text(f'ALTER TABLE "asset_requirements" ADD COLUMN "{name}" {sql_type}'))


def _ensure_batch_video_columns(engine) -> None:
    with engine.begin() as connection:
        inspector = inspect(connection)
        if "batch_video_jobs" not in set(inspector.get_table_names()):
            return
        existing = {item["name"] for item in inspector.get_columns("batch_video_jobs")}
        job_columns = {
            "submission_channel": "VARCHAR NOT NULL DEFAULT 'jimeng'",
            "batch_authorized": "BOOLEAN NOT NULL DEFAULT 0",
            "dispatch_enabled": "BOOLEAN NOT NULL DEFAULT 0",
            "launched_at": "DATETIME",
        }
        for name, sql_type in job_columns.items():
            if name not in existing:
                connection.execute(text(f'ALTER TABLE "batch_video_jobs" ADD COLUMN "{name}" {sql_type}'))
        task_existing = {item["name"] for item in inspector.get_columns("batch_video_tasks")}
        task_columns = {
            "reference_bindings_fingerprint": "VARCHAR NOT NULL DEFAULT ''",
            "reference_bindings_confirmed_at": "DATETIME",
        }
        for name, sql_type in task_columns.items():
            if name not in task_existing:
                connection.execute(text(f'ALTER TABLE "batch_video_tasks" ADD COLUMN "{name}" {sql_type}'))


def _ensure_cost_usage_columns(engine) -> None:
    columns = {
        "text_run_id": "VARCHAR",
        "cache_key": "VARCHAR NOT NULL DEFAULT ''",
        "cache_hit": "BOOLEAN NOT NULL DEFAULT 0",
        "input_tokens": "INTEGER NOT NULL DEFAULT 0",
        "cached_input_tokens": "INTEGER NOT NULL DEFAULT 0",
        "output_tokens": "INTEGER NOT NULL DEFAULT 0",
    }
    with engine.begin() as connection:
        existing = {item["name"] for item in inspect(connection).get_columns("cost_usage_logs")}
        for name, sql_type in columns.items():
            if name not in existing:
                connection.execute(text(f'ALTER TABLE "cost_usage_logs" ADD COLUMN "{name}" {sql_type}'))


def _ensure_ai_text_run_columns(engine) -> None:
    additions = {
        "project_id": "VARCHAR",
        "source_extraction_id": "VARCHAR",
        "target_type": "VARCHAR NOT NULL DEFAULT ''",
        "target_id": "VARCHAR NOT NULL DEFAULT ''",
        "module_type": "VARCHAR NOT NULL DEFAULT 'workflow_check_summary'",
        "input_hash": "VARCHAR NOT NULL DEFAULT ''",
        "response_json": "VARCHAR NOT NULL DEFAULT '{}'",
        "error_message": "VARCHAR NOT NULL DEFAULT ''",
    }
    with engine.begin() as connection:
        inspector = inspect(connection)
        table_names = set(inspector.get_table_names())
        if "ai_text_runs" not in table_names:
            return
        existing_columns = {item["name"]: item for item in inspector.get_columns("ai_text_runs")}
        if "report_id" in existing_columns and not existing_columns["report_id"].get("nullable", True):
            connection.execute(text("PRAGMA foreign_keys=OFF"))
            connection.execute(text("""
                CREATE TABLE ai_text_runs_v2 (
                    id VARCHAR NOT NULL PRIMARY KEY,
                    project_id VARCHAR,
                    report_id VARCHAR,
                    source_extraction_id VARCHAR,
                    target_type VARCHAR NOT NULL DEFAULT '',
                    target_id VARCHAR NOT NULL DEFAULT '',
                    module_type VARCHAR NOT NULL DEFAULT 'workflow_check_summary',
                    provider VARCHAR NOT NULL,
                    model_name VARCHAR NOT NULL,
                    cache_key VARCHAR NOT NULL,
                    input_hash VARCHAR NOT NULL DEFAULT '',
                    response_text VARCHAR NOT NULL,
                    response_json VARCHAR NOT NULL DEFAULT '{}',
                    status VARCHAR NOT NULL DEFAULT 'completed',
                    error_message VARCHAR NOT NULL DEFAULT '',
                    cache_hit BOOLEAN NOT NULL DEFAULT 0,
                    input_tokens INTEGER NOT NULL DEFAULT 0,
                    cached_input_tokens INTEGER NOT NULL DEFAULT 0,
                    output_tokens INTEGER NOT NULL DEFAULT 0,
                    created_at DATETIME NOT NULL,
                    FOREIGN KEY(project_id) REFERENCES projects (id),
                    FOREIGN KEY(report_id) REFERENCES workflow_check_reports (id),
                    FOREIGN KEY(source_extraction_id) REFERENCES source_text_extractions (id)
                )
            """))
            connection.execute(text("""
                INSERT INTO ai_text_runs_v2 (
                    id, report_id, provider, model_name, cache_key, response_text, status,
                    cache_hit, input_tokens, cached_input_tokens, output_tokens, created_at
                )
                SELECT id, report_id, provider, model_name, cache_key, response_text, status,
                    cache_hit, input_tokens, cached_input_tokens, output_tokens, created_at
                FROM ai_text_runs
            """))
            connection.execute(text("DROP TABLE ai_text_runs"))
            connection.execute(text("ALTER TABLE ai_text_runs_v2 RENAME TO ai_text_runs"))
            connection.execute(text("CREATE INDEX ix_ai_text_runs_project_id ON ai_text_runs (project_id)"))
            connection.execute(text("CREATE INDEX ix_ai_text_runs_report_id ON ai_text_runs (report_id)"))
            connection.execute(text("CREATE INDEX ix_ai_text_runs_source_extraction_id ON ai_text_runs (source_extraction_id)"))
            connection.execute(text("CREATE INDEX ix_ai_text_runs_target_id ON ai_text_runs (target_id)"))
            connection.execute(text("CREATE INDEX ix_ai_text_runs_module_type ON ai_text_runs (module_type)"))
            connection.execute(text("CREATE INDEX ix_ai_text_runs_cache_key ON ai_text_runs (cache_key)"))
            connection.execute(text("CREATE INDEX ix_ai_text_runs_input_hash ON ai_text_runs (input_hash)"))
            connection.execute(text("PRAGMA foreign_keys=ON"))
            return
        for name, sql_type in additions.items():
            if name not in existing_columns:
                connection.execute(text(f'ALTER TABLE "ai_text_runs" ADD COLUMN "{name}" {sql_type}'))


def _ensure_v7_precision_columns(engine) -> None:
    with engine.begin() as connection:
        inspector = inspect(connection)
        vp_columns = {item["name"]: item for item in inspector.get_columns("vp_blocks")}
        needs_vp_rebuild = (
            "schema_version" not in vp_columns
            or not vp_columns["storyboard_version_id"]["nullable"]
            or not vp_columns["scene_asset_version_id"]["nullable"]
        )
        if needs_vp_rebuild:
            connection.execute(text("PRAGMA foreign_keys=OFF"))
            connection.execute(text("""
                CREATE TABLE vp_blocks_v7 (
                    id VARCHAR NOT NULL PRIMARY KEY,
                    shot_id VARCHAR NOT NULL,
                    version_number INTEGER NOT NULL,
                    has_character BOOLEAN NOT NULL DEFAULT 1,
                    character_master_version_id VARCHAR,
                    costume_version_id VARCHAR,
                    scene_asset_version_id VARCHAR,
                    storyboard_version_id VARCHAR,
                    schema_version VARCHAR NOT NULL DEFAULT 'legacy_short_v1',
                    package_stage VARCHAR NOT NULL DEFAULT 'legacy',
                    precision_json VARCHAR NOT NULL DEFAULT '{}',
                    prompt_copy VARCHAR NOT NULL DEFAULT '',
                    basis_vp_block_id VARCHAR,
                    prompt VARCHAR NOT NULL,
                    negative_prompt VARCHAR NOT NULL,
                    duration_seconds INTEGER NOT NULL DEFAULT 5,
                    aspect_ratio VARCHAR NOT NULL DEFAULT '16:9',
                    resolution VARCHAR NOT NULL DEFAULT '720p',
                    generation_mode VARCHAR NOT NULL DEFAULT 'multimodal_reference',
                    provider_profile_id VARCHAR NOT NULL,
                    status VARCHAR NOT NULL DEFAULT 'draft',
                    created_at DATETIME NOT NULL,
                    updated_at DATETIME NOT NULL,
                    FOREIGN KEY(shot_id) REFERENCES shots (id),
                    FOREIGN KEY(character_master_version_id) REFERENCES character_master_versions (id),
                    FOREIGN KEY(costume_version_id) REFERENCES costume_versions (id),
                    FOREIGN KEY(scene_asset_version_id) REFERENCES scene_asset_versions (id),
                    FOREIGN KEY(storyboard_version_id) REFERENCES storyboard_shot_versions (id),
                    FOREIGN KEY(basis_vp_block_id) REFERENCES vp_blocks_v7 (id),
                    FOREIGN KEY(provider_profile_id) REFERENCES video_provider_profiles (id)
                )
            """))
            old_names = [
                "id", "shot_id", "version_number", "has_character",
                "character_master_version_id", "costume_version_id",
                "scene_asset_version_id", "storyboard_version_id", "prompt",
                "negative_prompt", "duration_seconds", "aspect_ratio", "resolution",
                "generation_mode", "provider_profile_id", "status", "created_at", "updated_at",
            ]
            columns = ", ".join(f'"{name}"' for name in old_names)
            connection.execute(text(
                f'INSERT INTO vp_blocks_v7 ({columns}) SELECT {columns} FROM vp_blocks'
            ))
            connection.execute(text("DROP TABLE vp_blocks"))
            connection.execute(text("ALTER TABLE vp_blocks_v7 RENAME TO vp_blocks"))
            connection.execute(text("CREATE INDEX ix_vp_blocks_shot_id ON vp_blocks (shot_id)"))
            connection.execute(text("PRAGMA foreign_keys=ON"))

        storyboard_columns = {
            item["name"] for item in inspect(connection).get_columns("storyboard_shot_versions")
        }
        additions = {
            "schema_version": "VARCHAR NOT NULL DEFAULT 'unified_sb_v1'",
            "vp_basis_block_id": "VARCHAR",
            "storyboard_mode": "VARCHAR NOT NULL DEFAULT 'unified_sb'",
            "density_level": "VARCHAR NOT NULL DEFAULT 'medium'",
            "storyboard_grid": "INTEGER NOT NULL DEFAULT 3",
            "grid_reason": "VARCHAR NOT NULL DEFAULT ''",
            "annotation_layer": "VARCHAR NOT NULL DEFAULT '{}'",
            "prompt_match": "VARCHAR NOT NULL DEFAULT '[]'",
            "prompt_match_json": "VARCHAR NOT NULL DEFAULT '[]'",
            "timeline_nodes_json": "VARCHAR NOT NULL DEFAULT '[]'",
            "storyboard_cells_json": "VARCHAR NOT NULL DEFAULT '[]'",
            "unified_sb_meta_json": "VARCHAR NOT NULL DEFAULT '{}'",
        }
        for name, sql_type in additions.items():
            if name not in storyboard_columns:
                connection.execute(text(
                    f'ALTER TABLE "storyboard_shot_versions" ADD COLUMN "{name}" {sql_type}'
                ))


def _ensure_director_tech_columns(engine) -> None:
    vp_additions = {
        "director_technique": "VARCHAR NOT NULL DEFAULT ''",
        "close_in_start_time": "VARCHAR NOT NULL DEFAULT ''",
        "close_in_from_shot_size": "VARCHAR NOT NULL DEFAULT ''",
        "close_in_to_shot_size": "VARCHAR NOT NULL DEFAULT ''",
        "close_in_target_detail": "VARCHAR NOT NULL DEFAULT ''",
        "close_in_emotional_meaning": "VARCHAR NOT NULL DEFAULT ''",
        "close_in_return_to_character": "BOOLEAN NOT NULL DEFAULT 0",
        "close_in_tail_frame": "VARCHAR NOT NULL DEFAULT ''",
        "detail_shot_candidates_json": "VARCHAR NOT NULL DEFAULT '[]'",
        "selected_detail_shot": "VARCHAR NOT NULL DEFAULT ''",
        "detail_shot_time_range": "VARCHAR NOT NULL DEFAULT ''",
        "detail_shot_meaning": "VARCHAR NOT NULL DEFAULT ''",
        "detail_shot_relation_to_character": "VARCHAR NOT NULL DEFAULT ''",
        "montage_type": "VARCHAR NOT NULL DEFAULT ''",
        "montage_goal": "VARCHAR NOT NULL DEFAULT ''",
        "montage_shot_count": "INTEGER NOT NULL DEFAULT 0",
        "montage_entry_point": "VARCHAR NOT NULL DEFAULT ''",
        "montage_exit_point": "VARCHAR NOT NULL DEFAULT ''",
        "montage_rhythm": "VARCHAR NOT NULL DEFAULT ''",
        "montage_return_to_main_story": "VARCHAR NOT NULL DEFAULT ''",
        "symbolic_object": "VARCHAR NOT NULL DEFAULT ''",
        "object_state_change": "VARCHAR NOT NULL DEFAULT ''",
        "symbolic_meaning": "VARCHAR NOT NULL DEFAULT ''",
        "object_state_time_range": "VARCHAR NOT NULL DEFAULT ''",
        "relation_to_character_emotion": "VARCHAR NOT NULL DEFAULT ''",
        "meaning_chain_json": "VARCHAR NOT NULL DEFAULT '{}'",
    }
    with engine.begin() as connection:
        inspector = inspect(connection)
        tables = set(inspector.get_table_names())
        if "vp_blocks" in tables:
            existing = {item["name"] for item in inspector.get_columns("vp_blocks")}
            for name, sql_type in vp_additions.items():
                if name not in existing:
                    connection.execute(text(f'ALTER TABLE "vp_blocks" ADD COLUMN "{name}" {sql_type}'))


def _ensure_seedance_skill_os_columns(engine) -> None:
    """Add Skill OS links after legacy VP tables have finished rebuilding."""
    table_columns = {
        "vp_blocks": {
            "video_unit_id": "VARCHAR",
            "vp_prompt_full": "TEXT NOT NULL DEFAULT ''",
            "reference_tag_map_json": "TEXT NOT NULL DEFAULT '{}'",
            "preserved_constraints_json": "TEXT NOT NULL DEFAULT '[]'",
            "removed_redundancy_json": "TEXT NOT NULL DEFAULT '[]'",
            "prompt_budget_report_json": "TEXT NOT NULL DEFAULT '{}'",
            "compile_warnings_json": "TEXT NOT NULL DEFAULT '[]'",
        },
        "batch_video_tasks": {
            "video_unit_id": "VARCHAR",
        },
        "director_project_states": {
            "completed_video_unit_ids_json": "TEXT NOT NULL DEFAULT '[]'",
            "reserved_video_unit_ids_json": "TEXT NOT NULL DEFAULT '[]'",
        },
        "surface_profiles": {
            "verification_date": "DATETIME",
            "duration_range_json": "TEXT NOT NULL DEFAULT '{}'",
            "prompt_budget": "INTEGER NOT NULL DEFAULT 6000",
            "reference_tag_convention": "VARCHAR NOT NULL DEFAULT '@参考N'",
            "supported_modes_json": "TEXT NOT NULL DEFAULT '[]'",
            "reference_limits_json": "TEXT NOT NULL DEFAULT '{}'",
            "first_last_frame_support": "BOOLEAN NOT NULL DEFAULT 0",
            "edit_support": "BOOLEAN NOT NULL DEFAULT 0",
            "extend_support": "BOOLEAN NOT NULL DEFAULT 0",
            "audio_behavior": "VARCHAR NOT NULL DEFAULT 'provider_defined'",
            "resolutions_json": "TEXT NOT NULL DEFAULT '[]'",
            "aspect_ratios_json": "TEXT NOT NULL DEFAULT '[]'",
            "region": "VARCHAR NOT NULL DEFAULT ''",
            "pricing_json": "TEXT NOT NULL DEFAULT '{}'",
            "authorization_requirements_json": "TEXT NOT NULL DEFAULT '{}'",
            "known_constraints_json": "TEXT NOT NULL DEFAULT '[]'",
        },
        "video_units": {
            "storyboard_version_id": "VARCHAR",
            "prompt_time_ranges_json": "TEXT NOT NULL DEFAULT '[]'",
        },
    }
    with engine.begin() as connection:
        inspector = inspect(connection)
        tables = set(inspector.get_table_names())
        for table_name, additions in table_columns.items():
            if table_name not in tables:
                continue
            existing = {item["name"] for item in inspector.get_columns(table_name)}
            for name, sql_type in additions.items():
                if name not in existing:
                    connection.execute(
                        text(f'ALTER TABLE "{table_name}" ADD COLUMN "{name}" {sql_type}')
                    )
