import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { BatchProductionWorkbench } from "../pages/BatchVideoPage";
import type { BatchJob, BatchTask } from "../types/videos";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

function task(overrides: Partial<BatchTask> = {}): BatchTask {
  return {
    id: "task-1",
    shot_id: "shot-1",
    shot_code: "SH001",
    status: "ready",
    missing_items: [],
    canonical_request: {
      prompt: "人物沿泥地缓慢前进，镜头保持低机位。",
      duration_seconds: 8,
      resolution: "720p",
      provider_options: { jimeng_model_version: "seedance2.0_vip" },
    },
    retry_count: 0,
    error_message: "",
    storyboard_url: null,
    reference_bindings: [
      {
        token: "@图片1",
        asset_id: "asset-1",
        asset_type: "scene",
        role: "environment",
        label: "泥地训练场",
        purpose: "锁定场景空间",
      },
    ],
    reference_candidates: [
      {
        asset_id: "asset-1",
        asset_type: "scene",
        role: "environment",
        label: "泥地训练场",
      },
      {
        asset_id: "asset-2",
        asset_type: "prop",
        role: "product",
        label: "越野摩托车",
      },
    ],
    reference_bindings_confirmed: false,
    results: [],
    ...overrides,
  };
}

function job(tasks: BatchTask[], overrides: Partial<BatchJob> = {}): BatchJob {
  return {
    id: "job-1",
    scene_id: "scene-1",
    scope_code: "EP01SC01",
    provider_profile_id: "jimeng",
    provider_name: "即梦 CLI",
    submission_channel: "jimeng",
    status: "draft",
    budget_confirmed: false,
    estimated_cost: null,
    cost_estimate_status: "unknown",
    cost_estimate_note: "费用未知",
    cost_source_url: "",
    currency: "CREDITS",
    total_seconds: tasks.reduce(
      (sum, item) => sum + Number(item.canonical_request.duration_seconds ?? 0),
      0,
    ),
    jimeng_zip_url: null,
    tasks,
    ...overrides,
  };
}

const models = [
  {
    id: "seedance2.0_vip",
    label: "即梦 Seedance 2.0 VIP",
    speed_label: "会员通道",
    cost_label: "VIP",
    description: "默认成片模型",
    supported_resolutions: ["720p"],
    min_duration: 4,
    max_duration: 15,
  },
];

function renderWorkbench(
  currentJob: BatchJob,
  channel: "huimeng" | "jimeng" | "volcengine_seedance25" = "jimeng",
  availableModels = models,
) {
  const callbacks = {
    onRebuildBatch: vi.fn(),
    onConfirmAllBindings: vi.fn(),
    onConfirmTask: vi.fn(),
    onSaveBindings: vi.fn(),
    onResetBindings: vi.fn(),
    onModelChange: vi.fn(),
    onBatchModelChange: vi.fn(),
    onGenerationSettingsChange: vi.fn(),
    onConfirmCost: vi.fn(),
    onLaunch: vi.fn(),
    onRetry: vi.fn(),
    onReview: vi.fn(),
    onApproveAll: vi.fn(),
    onImport: vi.fn(),
  };
  render(
    <BatchProductionWorkbench
      job={currentJob}
      models={availableModels}
      submissionChannel={channel}
      supervisorStatus={{
        enabled: true,
        running: true,
        poll_interval_seconds: 5,
        active_task_count: 0,
        last_cycle_at: null,
        last_success_at: null,
        last_error: "",
      }}
      monitorError=""
      busy={false}
      expectedTaskCount={currentJob.tasks.length}
      {...callbacks}
    />,
  );
  return callbacks;
}

describe("真正的批量视频生产工作台", () => {
  it("集中展示全部镜头和参考绑定，并可修改顺序后保存", () => {
    const first = task();
    const second = task({
      id: "task-2",
      shot_id: "shot-2",
      shot_code: "SH002",
    });
    const callbacks = renderWorkbench(job([first, second]));

    expect(screen.getByText("全镜头全能参考纵览")).toBeInTheDocument();
    expect(screen.getByText("SH001")).toBeInTheDocument();
    expect(screen.getByText("SH002")).toBeInTheDocument();
    fireEvent.click(screen.getAllByRole("button", { name: "修改参考绑定" })[0]);
    fireEvent.click(screen.getByRole("button", { name: "+ 图片｜越野摩托车" }));
    fireEvent.click(screen.getByRole("button", { name: /保存绑定与顺序/ }));
    expect(callbacks.onSaveBindings).toHaveBeenCalledWith(first, [
      "asset-1",
      "asset-2",
    ]);
  });

  it("存在阻塞镜头时禁止整批启动", () => {
    renderWorkbench(
      job([task({ status: "blocked", missing_items: ["缺少已确认故事板"] })]),
    );
    expect(
      screen.getByText(/整批启动不会发出任何付费请求/),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /定位并处理 1 个阻塞/ }),
    ).toBeEnabled();
    expect(
      screen.queryByRole("button", { name: /一键启动全部镜头/ }),
    ).not.toBeInTheDocument();
  });

  it("已保存镜头不锁死剩余镜头，可统一确认后继续生产", () => {
    const preserved = task({
      status: "imported",
      external_task_id: "provider-saved",
      reference_bindings_confirmed: false,
      results: [
        {
          id: "result-1",
          version_number: 1,
          source: "jimeng_cli",
          status: "pending",
          video_url: "/saved.mp4",
        },
      ],
    });
    const pending = task({
      id: "task-2",
      shot_id: "shot-2",
      shot_code: "SH002",
      status: "awaiting_budget_confirm",
    });
    const callbacks = renderWorkbench(
      job([preserved, pending], { status: "awaiting_budget_confirm" }),
    );

    expect(screen.getByText(/绑定 1\/2/)).toBeInTheDocument();
    const taskConfirmButtons = screen.getAllByRole("button", {
      name: "确认本镜头绑定",
    });
    expect(taskConfirmButtons[0]).toBeDisabled();
    expect(taskConfirmButtons[1]).toBeEnabled();
    fireEvent.click(
      screen.getByRole("button", { name: "确认剩余 1 个镜头绑定" }),
    );
    expect(callbacks.onConfirmAllBindings).toHaveBeenCalledTimes(1);
  });

  it("恢复提示中的检查按钮会定位到参考核对区", () => {
    const scrollIntoView = vi.fn();
    Object.defineProperty(HTMLElement.prototype, "scrollIntoView", {
      configurable: true,
      value: scrollIntoView,
    });
    vi.spyOn(window, "requestAnimationFrame").mockImplementation((callback) => {
      callback(0);
      return 1;
    });
    renderWorkbench(
      job([task({ status: "awaiting_budget_confirm" })], {
        status: "awaiting_budget_confirm",
      }),
    );

    fireEvent.click(
      screen.getByRole("button", { name: "去检查并确认参考绑定" }),
    );
    expect(scrollIntoView).toHaveBeenCalledTimes(1);
  });

  it("后台监控展示真实任务 ID，单条失败不影响其他镜头", () => {
    const callbacks = renderWorkbench(
      job(
        [
          task({
            status: "failed",
            external_task_id: "provider-failed",
            error_message: "余额不足",
          }),
          task({
            id: "task-2",
            shot_id: "shot-2",
            shot_code: "SH002",
            status: "processing",
            external_task_id: "provider-running",
          }),
        ],
        { batch_authorized: true, status: "partial_failed" },
      ),
    );
    expect(screen.getByText(/provider-failed/)).toBeInTheDocument();
    expect(screen.getByText(/provider-running/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /修正后重试本镜头/ }));
    expect(callbacks.onRetry).toHaveBeenCalledTimes(1);
  });

  it("进入生产监控后仍显示本次模型，并明确锁定已提交任务", () => {
    renderWorkbench(
      job(
        [task({ status: "processing", external_task_id: "provider-running" })],
        { batch_authorized: true, status: "processing" },
      ),
    );

    expect(
      screen.getByRole("combobox", { name: "本批次视频模型" }),
    ).toHaveValue("seedance2.0_vip");
    expect(
      screen.getByRole("combobox", { name: "本批次视频模型" }),
    ).toBeDisabled();
    expect(screen.getByText(/任务已提交，模型已锁定/)).toBeInTheDocument();
  });

  it("模型目录加载失败时显示明确提示，不静默隐藏模型配置", () => {
    renderWorkbench(job([task()]), "jimeng", []);

    expect(screen.getByText("模型目录未加载")).toBeInTheDocument();
    expect(screen.getByText(/刷新页面后重试/)).toBeInTheDocument();
  });

  it("失败恢复后明确提示尚未提交，并在当前页完成重新授权", () => {
    const recovered = task({
      status: "awaiting_budget_confirm",
      reference_bindings_confirmed: true,
    });
    const callbacks = renderWorkbench(
      job([recovered], {
        status: "awaiting_budget_confirm",
        budget_confirmed: false,
        batch_authorized: false,
      }),
    );

    expect(
      screen.getByText("生产尚未重新启动，当前没有向服务商提交新任务"),
    ).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /2 生产监控/ }));
    expect(screen.getByText(/当前批次处于安全暂停状态/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /确认费用风险并继续/ }));
    expect(callbacks.onConfirmCost).toHaveBeenCalledTimes(1);
  });

  it("费用已确认后在同一恢复区提供继续后台生产按钮", () => {
    const recovered = task({
      status: "ready",
      reference_bindings_confirmed: true,
    });
    const callbacks = renderWorkbench(
      job([recovered], {
        status: "ready",
        budget_confirmed: true,
        batch_authorized: false,
      }),
    );

    fireEvent.click(screen.getByRole("button", { name: /一键继续后台生产/ }));
    expect(callbacks.onLaunch).toHaveBeenCalledTimes(1);
  });

  it("完成后可集中预览、单条通过或批量通过", () => {
    const completed = task({
      status: "imported",
      reference_bindings_confirmed: true,
      results: [
        {
          id: "result-1",
          version_number: 1,
          source: "jimeng_cli",
          status: "pending",
          video_url: "/video.mp4",
        },
      ],
    });
    const callbacks = renderWorkbench(
      job([completed], {
        status: "awaiting_review",
        batch_authorized: true,
        budget_confirmed: true,
      }),
    );
    expect(screen.getByText("集中预览与验收")).toBeInTheDocument();
    expect(document.querySelector("video")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "通过" }));
    expect(callbacks.onReview).toHaveBeenCalledWith(completed, "confirm");
    fireEvent.click(
      screen.getByRole("button", { name: /批量通过全部待验收视频/ }),
    );
    expect(callbacks.onApproveAll).toHaveBeenCalledTimes(1);
  });

  it("Seedance 2.5 显示智能时长和多媒体参考", () => {
    const editableTask = task({
      status: "awaiting_budget_confirm",
      reference_bindings_confirmed: false,
      canonical_request: {
        prompt: "@图片1 负责镜头，@视频1 负责动作，@音频1 负责声音。",
        provider_model_id: "doubao-seedance-2-5-260628",
        duration_mode: "smart",
        duration_seconds: 8,
        resolution: "720p",
      },
      reference_candidates: [
        {
          asset_id: "asset-1",
          asset_type: "scene",
          role: "environment",
          label: "泥地训练场",
          media_type: "image",
        },
        {
          asset_id: "video-1",
          asset_type: "source",
          role: "source_video",
          label: "动作参考.mp4",
          media_type: "video",
        },
        {
          asset_id: "audio-1",
          asset_type: "source",
          role: "source_audio",
          label: "节奏参考.wav",
          media_type: "audio",
        },
      ],
    });
    const seedanceModels = [
      {
        id: "doubao-seedance-2-5-260628",
        provider_type: "volcengine_seedance25",
        provider_model_id: "doubao-seedance-2-5-260628",
        label: "火山方舟 Seedance 2.5（Mock）",
        speed_label: "官方模型能力",
        cost_label: "费用未知",
        description: "不会发送外部请求",
        supported_resolutions: ["480p", "720p"],
        min_duration: 4,
        max_duration: 30,
        supports_smart_duration: true,
        is_mock_only: true,
      },
    ];
    const callbacks = renderWorkbench(
      job([editableTask], {
        provider_profile_id: "volcengine_seedance25",
        provider_name: "火山方舟 Seedance 2.5（Mock）",
        submission_channel: "volcengine_seedance25",
        status: "awaiting_budget_confirm",
        batch_authorized: false,
      }),
      "volcengine_seedance25",
      seedanceModels,
    );

    expect(screen.getAllByText(/智能时长/).length).toBeGreaterThan(0);
    fireEvent.click(screen.getByRole("button", { name: "修改参考绑定" }));
    expect(
      screen.getByRole("button", { name: "+ 视频｜动作参考.mp4" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "+ 音频｜节奏参考.wav" }),
    ).toBeInTheDocument();
    expect(callbacks.onGenerationSettingsChange).not.toHaveBeenCalled();
  });

  it("Seedance 2.5 明确标识 Mock 结果", () => {
    const mockTask = task({
      status: "mock_completed",
      storage_status: "mock",
      provider_status: "mock_artifact_saved",
      canonical_request: {
        prompt: "@图片1 负责镜头。",
        provider_model_id: "doubao-seedance-2-5-260628",
        duration_mode: "smart",
        duration_seconds: 8,
        resolution: "720p",
      },
    });
    renderWorkbench(
      job([mockTask], {
        provider_profile_id: "volcengine_seedance25",
        provider_name: "火山方舟 Seedance 2.5（Mock）",
        submission_channel: "volcengine_seedance25",
        status: "mock_completed",
        batch_authorized: false,
      }),
      "volcengine_seedance25",
      [
        {
          id: "doubao-seedance-2-5-260628",
          label: "火山方舟 Seedance 2.5（Mock）",
          speed_label: "官方模型能力",
          cost_label: "费用未知",
          description: "不会发送外部请求",
          supported_resolutions: ["480p", "720p"],
          min_duration: 4,
          max_duration: 30,
        },
      ],
    );

    fireEvent.click(screen.getByRole("button", { name: /2 生产监控/ }));
    expect(screen.getByText(/模拟任务｜未发送外部请求/)).toBeInTheDocument();
    expect(screen.getByText(/不生成可播放视频/)).toBeInTheDocument();
  });
});
