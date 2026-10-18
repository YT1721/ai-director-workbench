import type { FlowNav } from "../types/flowNav";

export type CreativeGoal =
  | "full_pipeline"
  | "prompt_storyboard"
  | "asset_only"
  | "analysis_plan";

export const creativeGoalOptions: Record<
  CreativeGoal,
  { title: string; short: string; detail: string; stopAfter: string }
> = {
  full_pipeline: {
    title: "完整生产流程",
    short: "一路做到视频队列",
    detail:
      "适合正式项目：剧本、导演分析、规划、导演方案、分镜提示词、黑白故事板、资产图和批量视频都会依次推进。",
    stopAfter: "批量视频队列准备完成",
  },
  prompt_storyboard: {
    title: "只要分镜提示词和故事板",
    short: "提示词 + 故事板",
    detail:
      "适合创意验证：先拿到导演分镜提示词并确认故事板，再生成无参考图成片提示词；人物、场景资产图可以不做。",
    stopAfter: "无参考图成片提示词与故事板确认完成",
  },
  asset_only: {
    title: "只做资产图",
    short: "资产图",
    detail:
      "适合只想整理人物、场景、道具图的情况。仍建议先上传剧本并完成导演分析，这样资产图才不会偏离剧情和镜头气质。",
    stopAfter: "人物、服装、场景资产确认完成",
  },
  analysis_plan: {
    title: "只要导演分析和分镜规划",
    short: "分析 + 规划",
    detail:
      "适合前期创作：只看剧本拆解、导演方案和场次镜头规划，不进入分镜提示词、故事板或资产图。",
    stopAfter: "分镜规划确认完成",
  },
};

export function goalTargetReached(
  goal: CreativeGoal,
  flow: FlowNav | null,
): boolean {
  if (!flow) return false;
  const done = (key: string) =>
    flow.directory.find((item) => item.key === key)?.status_level === "done";
  if (goal === "analysis_plan") return done("plan");
  if (goal === "asset_only") return done("assets");
  if (goal === "prompt_storyboard")
    return (
      done("video_package_draft") && done("storyboard") && done("video_package")
    );
  return [
    "start",
    "plan",
    "director_option",
    "video_package_draft",
    "storyboard",
    "assets",
    "video_package",
    "batch_video",
  ].every(done);
}

export function goalNextHint(goal: CreativeGoal, flow: FlowNav | null): string {
  if (!flow) return creativeGoalOptions[goal].detail;
  if (goalTargetReached(goal, flow)) {
    return `本次目标已完成：${creativeGoalOptions[goal].stopAfter}。可以在这里停下，也可以切换为“完整生产流程”继续往后做。`;
  }
  if (goal === "prompt_storyboard") {
    return "本次目标是拿到导演分镜提示词、确认故事板，再生成无参考图成片提示词。正式资产图可以不做，但无法保证人物、服装和场景跨镜一致。";
  }
  if (goal === "asset_only") {
    return "本次目标是生成或上传人物、场景、道具资产图。建议先完成导演分析和规划，让资产图服务剧情，而不是只做漂亮孤图。";
  }
  if (goal === "analysis_plan") {
    return "本次目标是完成导演分析和分镜规划。确认分镜规划后就可以停下，不必继续做资产和视频。";
  }
  return "本次目标是完整生产流程。系统会按：分镜提示词、故事板、资产图、资产绑定版成片提示词、批量视频继续提醒。";
}
