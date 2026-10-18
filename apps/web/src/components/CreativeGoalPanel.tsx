import { CheckCircle2, Flag, Sparkles } from "lucide-react";

import { useWorkbenchStore } from "../stores/useWorkbenchStore";
import type { FlowNav } from "../types/flowNav";
import {
  creativeGoalOptions,
  goalNextHint,
  goalTargetReached,
  type CreativeGoal,
} from "../utils/creativeGoal";

type CreativeGoalPanelProps = {
  flow?: FlowNav | null;
  compact?: boolean;
};

const goalOrder: CreativeGoal[] = [
  "full_pipeline",
  "prompt_storyboard",
  "asset_only",
  "analysis_plan",
];

export function CreativeGoalPanel({
  flow = null,
  compact = false,
}: CreativeGoalPanelProps) {
  const creativeGoal = useWorkbenchStore((state) => state.creativeGoal);
  const setCreativeGoal = useWorkbenchStore((state) => state.setCreativeGoal);
  const reached = goalTargetReached(creativeGoal, flow);

  return (
    <section
      className={`border border-white/12 bg-[#10161b] ${compact ? "p-4" : "p-5"}`}
    >
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 text-orange-300">
            <Flag size={16} />
            <p className="text-xs tracking-[0.16em]">本次创作目标</p>
          </div>
          <h2
            className={`${compact ? "mt-2 text-base" : "mt-2 text-xl"} font-semibold text-zinc-100`}
          >
            {creativeGoalOptions[creativeGoal].title}
          </h2>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-zinc-400">
            {goalNextHint(creativeGoal, flow)}
          </p>
        </div>
        <span
          className={
            reached
              ? "border border-emerald-400/40 px-3 py-1 text-xs text-emerald-200"
              : "border border-orange-400/40 px-3 py-1 text-xs text-orange-200"
          }
        >
          {reached ? "本次目标已满足" : "继续按目标推进"}
        </span>
      </div>

      <div
        className={`mt-4 grid ${compact ? "grid-cols-4 gap-2" : "grid-cols-4 gap-3"}`}
      >
        {goalOrder.map((goal) => {
          const selected = creativeGoal === goal;
          const option = creativeGoalOptions[goal];
          return (
            <button
              key={goal}
              type="button"
              onClick={() => setCreativeGoal(goal)}
              className={`${compact ? "min-h-20" : "min-h-24"} border p-3 text-left transition ${
                selected
                  ? "border-orange-400 bg-orange-400/10 text-orange-100"
                  : "border-white/10 bg-black/10 text-zinc-400 hover:border-orange-400/40 hover:text-zinc-200"
              }`}
            >
              <div className="flex items-center gap-2">
                {selected ? (
                  <CheckCircle2 size={15} className="text-orange-300" />
                ) : (
                  <Sparkles size={15} className="text-zinc-500" />
                )}
                <p className="text-sm font-semibold">{option.short}</p>
              </div>
              <p className="mt-2 text-xs leading-5 opacity-75">
                {compact ? option.stopAfter : option.detail}
              </p>
            </button>
          );
        })}
      </div>

      <p className="mt-4 border-l-2 border-sky-400/50 bg-sky-400/6 px-3 py-2 text-xs leading-5 text-sky-100/80">
        灵活不是跳过导演判断：剧本理解、镜头拆分、时间段描述和视觉连续性仍是核心。目标模式只决定“这次做到哪里停”。
      </p>
    </section>
  );
}
