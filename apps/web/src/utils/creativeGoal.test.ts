import { describe, expect, it } from "vitest";

import type { FlowNav } from "../types/flowNav";
import { goalTargetReached } from "./creativeGoal";

function flowWithStatuses(
  statuses: Record<string, "done" | "current">,
): FlowNav {
  return {
    project_id: "project-1",
    project_code: "PRJ001",
    project_name: "测试项目",
    scope_code: "EP01SC01",
    current_stage: "故事板提示词",
    completed_labels: [],
    pending_labels: [],
    director_option: null,
    directory: Object.entries(statuses).map(([key, status]) => ({
      key,
      label: key,
      command: key,
      marker: status === "done" ? "已完成" : "当前建议",
      status_level: status,
      short_status: key,
      detail: key,
      href: "/",
    })),
    next_command: "",
    next_reason: "",
    blocking_reason: "",
    primary_action_label: "",
    primary_action_href: "/",
  };
}

describe("完整生产目标状态", () => {
  it("已有批量队列但上游提示词过期时不显示目标已完成", () => {
    const required = {
      start: "done",
      plan: "done",
      director_option: "done",
      video_package_draft: "current",
      storyboard: "done",
      assets: "done",
      video_package: "done",
      batch_video: "done",
    } as const;

    expect(goalTargetReached("full_pipeline", flowWithStatuses(required))).toBe(
      false,
    );
  });
});
