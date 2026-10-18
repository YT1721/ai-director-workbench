export type DirectorOptionConfirmation = {
  id: string;
  episode_id: string;
  version_number: number;
  option_name: string;
  notes: string;
  status: string;
  created_at: string;
};

export type FlowNavItem = {
  key: string;
  label: string;
  command: string;
  marker: "已完成" | "当前建议" | "待进行" | "可选辅助";
  status_level: "done" | "current" | "blocked" | "pending" | "optional";
  short_status: string;
  detail: string;
  href: string;
};

export type FlowNav = {
  project_id: string;
  project_code: string;
  project_name: string;
  scope_code: string;
  current_stage: string;
  completed_labels: string[];
  pending_labels: string[];
  director_option: DirectorOptionConfirmation | null;
  directory: FlowNavItem[];
  next_command: string;
  next_reason: string;
  blocking_reason: string;
  primary_action_label: string;
  primary_action_href: string;
};
