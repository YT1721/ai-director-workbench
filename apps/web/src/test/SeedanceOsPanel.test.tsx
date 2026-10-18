import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const api = vi.hoisted(() => ({
  compileSeedanceVideoUnit: vi.fn(),
  createSeedanceVideoUnit: vi.fn(),
  fetchSeedanceOsWorkspace: vi.fn(),
  reviewSeedanceTake: vi.fn(),
}));

vi.mock("../services/api", () => api);

import { SeedanceOsPanel } from "../components/SeedanceOsPanel";
import type { SeedanceOsWorkspace } from "../types/seedanceOs";

const workspace: SeedanceOsWorkspace = {
  project: { id: "project-1", project_code: "PRJ001", name: "测试项目" },
  state: {
    canon: {},
    completed_video_unit_ids: [],
    reserved_video_unit_ids: [],
  },
  candidates: [
    {
      episode_code: "EP01",
      scene_id: "scene-1",
      scene_code: "SC01",
      shot_id: "shot-1",
      shot_code: "SH001",
      shot_name: "人物转身看向门口",
      storyboard_version_id: "storyboard-1",
      storyboard_version: 2,
      storyboard_status: "confirmed",
      storyboard_grid: 6,
      prompt_time_ranges: ["0.0s-1.0s", "1.0s-3.0s", "3.0s-5.0s"],
      vp_block_id: "vp-1",
      vp_block_version: 2,
      vp_block_status: "confirmed",
      duration_seconds: 18,
      precision_18: Array.from({ length: 18 }, (_, index) => ({
        number: index + 1,
      })),
      existing_video_unit_ids: [],
      next_unit_index: 1,
    },
  ],
  video_units: [],
  surface_profiles: [],
  limits: {
    max_video_unit_seconds: 15,
    max_extension_depth: 2,
    provider_submission_requires_confirmation: true,
  },
};

describe("SeedanceOsPanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.fetchSeedanceOsWorkspace.mockResolvedValue(workspace);
    api.createSeedanceVideoUnit.mockResolvedValue({ id: "unit-1" });
    api.compileSeedanceVideoUnit.mockResolvedValue({
      vp_prompt_copy: "可复制提示词",
    });
    api.reviewSeedanceTake.mockResolvedValue({ id: "review-1" });
  });

  it("显示生产约束，并以不超过 15 秒建立视频单元", async () => {
    render(<SeedanceOsPanel projectId="project-1" />);

    expect(await screen.findByText("生产视频单元")).toBeInTheDocument();
    expect(screen.getByText("每单元 15 秒")).toBeInTheDocument();
    expect(screen.getByText("始终需要人工确认")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "建立生产视频单元" }));

    await waitFor(() =>
      expect(api.createSeedanceVideoUnit).toHaveBeenCalledTimes(1),
    );
    expect(api.createSeedanceVideoUnit).toHaveBeenCalledWith(
      "project-1",
      expect.objectContaining({
        shot_id: "shot-1",
        storyboard_version_id: "storyboard-1",
        duration_seconds: 15,
      }),
    );
  });

  it("可编译提示词；通过成片前必须填写真实尾帧", async () => {
    api.fetchSeedanceOsWorkspace.mockResolvedValue({
      ...workspace,
      candidates: [
        { ...workspace.candidates[0], existing_video_unit_ids: ["unit-1"] },
      ],
      video_units: [
        {
          id: "unit-1",
          project_id: "project-1",
          scene_id: "scene-1",
          shot_id: "shot-1",
          shot_code: "SH001",
          shot_name: "人物转身看向门口",
          scene_code: "SC01",
          unit_index: 1,
          unit_type: "standalone",
          duration_seconds: 5,
          extension_depth: 0,
          reanchor_required: false,
          event_density_score: 4,
          status: "draft",
          prompt_time_ranges: ["0.0s-1.0s", "1.0s-3.0s", "3.0s-5.0s"],
          allocation: {},
          intended_start_state: {},
          intended_end_state: {},
          continuity_handoff: {},
          reference_roles: [],
          vp_block_id: "vp-1",
          vp_block_version: 2,
          precision_18: workspace.candidates[0].precision_18,
          vp_prompt_full: "",
          vp_prompt_copy: "",
          take_reviews: [],
        },
      ],
    });

    render(<SeedanceOsPanel projectId="project-1" />);

    fireEvent.click(
      await screen.findByRole("button", { name: "编译可复制视频提示词" }),
    );
    await waitFor(() =>
      expect(api.compileSeedanceVideoUnit).toHaveBeenCalledWith(
        "unit-1",
        "vp-1",
      ),
    );

    fireEvent.click(screen.getByText("成片回来后：验收这一条"));
    fireEvent.click(screen.getByRole("button", { name: "通过并记录尾帧" }));
    expect(
      await screen.findByText(
        "通过成片前，请写清楚真实尾帧停在哪里，后续镜头会从这个状态继续。",
      ),
    ).toBeInTheDocument();
    expect(api.reviewSeedanceTake).not.toHaveBeenCalled();
  });

  it("旧版统一 5 秒镜头不能直接建立生产单元", async () => {
    const onDurationRebuildCountChange = vi.fn();
    api.fetchSeedanceOsWorkspace.mockResolvedValue({
      ...workspace,
      candidates: [
        {
          ...workspace.candidates[0],
          duration_seconds: 5,
          recommended_duration_seconds: 10,
          duration_reason: "包含多个连续动作；建议 10 秒。",
          duration_needs_rebuild: true,
        },
      ],
    });

    render(
      <SeedanceOsPanel
        projectId="project-1"
        onDurationRebuildCountChange={onDurationRebuildCountChange}
      />,
    );

    expect(await screen.findByText("必须先处理")).toBeInTheDocument();
    expect(
      await screen.findByText("检测到 1 个旧版统一 5 秒镜头"),
    ).toBeInTheDocument();
    expect(screen.getByText(/不能继续正式视频生成/)).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "去按主规则重建" }),
    ).toHaveAttribute("href", "/video-package");
    expect(screen.getByText(/主规则建议 10 秒/)).toBeInTheDocument();
    expect(
      screen.getAllByRole("button", { name: "建立生产视频单元" }).at(-1),
    ).toBeDisabled();
    await waitFor(() =>
      expect(onDurationRebuildCountChange).toHaveBeenCalledWith(1),
    );
  });
});
