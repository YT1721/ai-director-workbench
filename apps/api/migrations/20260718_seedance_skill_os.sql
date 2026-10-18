-- Seedance Skill OS compatibility migration.
-- Runtime initialization creates the new tables through SQLModel; these ALTERs
-- document the additions required for existing databases.
ALTER TABLE vp_blocks ADD COLUMN video_unit_id VARCHAR;
ALTER TABLE vp_blocks ADD COLUMN vp_prompt_full TEXT NOT NULL DEFAULT '';
ALTER TABLE vp_blocks ADD COLUMN reference_tag_map_json TEXT NOT NULL DEFAULT '{}';
ALTER TABLE vp_blocks ADD COLUMN preserved_constraints_json TEXT NOT NULL DEFAULT '[]';
ALTER TABLE vp_blocks ADD COLUMN removed_redundancy_json TEXT NOT NULL DEFAULT '[]';
ALTER TABLE vp_blocks ADD COLUMN prompt_budget_report_json TEXT NOT NULL DEFAULT '{}';
ALTER TABLE vp_blocks ADD COLUMN compile_warnings_json TEXT NOT NULL DEFAULT '[]';
ALTER TABLE batch_video_tasks ADD COLUMN video_unit_id VARCHAR;
ALTER TABLE video_units ADD COLUMN storyboard_version_id VARCHAR;
ALTER TABLE video_units ADD COLUMN prompt_time_ranges_json TEXT NOT NULL DEFAULT '[]';
ALTER TABLE director_project_states ADD COLUMN completed_video_unit_ids_json TEXT NOT NULL DEFAULT '[]';
ALTER TABLE director_project_states ADD COLUMN reserved_video_unit_ids_json TEXT NOT NULL DEFAULT '[]';
ALTER TABLE surface_profiles ADD COLUMN verification_date DATETIME;
ALTER TABLE surface_profiles ADD COLUMN duration_range_json TEXT NOT NULL DEFAULT '{}';
ALTER TABLE surface_profiles ADD COLUMN prompt_budget INTEGER NOT NULL DEFAULT 6000;
ALTER TABLE surface_profiles ADD COLUMN reference_tag_convention VARCHAR NOT NULL DEFAULT '@参考N';
ALTER TABLE surface_profiles ADD COLUMN supported_modes_json TEXT NOT NULL DEFAULT '[]';
ALTER TABLE surface_profiles ADD COLUMN reference_limits_json TEXT NOT NULL DEFAULT '{}';
ALTER TABLE surface_profiles ADD COLUMN first_last_frame_support BOOLEAN NOT NULL DEFAULT 0;
ALTER TABLE surface_profiles ADD COLUMN edit_support BOOLEAN NOT NULL DEFAULT 0;
ALTER TABLE surface_profiles ADD COLUMN extend_support BOOLEAN NOT NULL DEFAULT 0;
ALTER TABLE surface_profiles ADD COLUMN audio_behavior VARCHAR NOT NULL DEFAULT 'provider_defined';
ALTER TABLE surface_profiles ADD COLUMN resolutions_json TEXT NOT NULL DEFAULT '[]';
ALTER TABLE surface_profiles ADD COLUMN aspect_ratios_json TEXT NOT NULL DEFAULT '[]';
ALTER TABLE surface_profiles ADD COLUMN region VARCHAR NOT NULL DEFAULT '';
ALTER TABLE surface_profiles ADD COLUMN pricing_json TEXT NOT NULL DEFAULT '{}';
ALTER TABLE surface_profiles ADD COLUMN authorization_requirements_json TEXT NOT NULL DEFAULT '{}';
ALTER TABLE surface_profiles ADD COLUMN known_constraints_json TEXT NOT NULL DEFAULT '[]';

-- New tables are created by SQLModel.metadata.create_all:
-- director_project_states, scene_directing_states, surface_profiles,
-- video_units, reference_role_maps, take_reviews.
