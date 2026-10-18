export type SystemPromptStatus = {
  loaded: boolean;
  filename: string;
  version: string;
  provider_mode: string;
  last_updated?: string | null;
  error?: string | null;
};

export type SeedanceSkillStatus = {
  installed: boolean;
  pinned_commit: string;
  vendor_path: string;
  module_count: number;
  license_present: boolean;
};
