import { ArrowRight, CheckCircle2, CircleAlert } from "lucide-react";

import type { FlowNav } from "../types/flowNav";
import type { ProjectSummary } from "../types/workbench";
import type { LiveProviderStatus } from "../types/videos";
import type { LocalEnvStatus, TextProviderStatus } from "../types/workflows";

type RealRunChecklistProps = {
  activeProject?: ProjectSummary | null;
  flowNav?: FlowNav | null;
  textStatus?: TextProviderStatus | null;
  localEnv?: LocalEnvStatus | null;
  liveStatus?: LiveProviderStatus | null;
  compact?: boolean;
  onPrimaryAction?: (href: string) => void;
  onPrepareAcceptanceProject?: () => void;
  preparingAcceptanceProject?: boolean;
};

function serviceItems(
  textStatus?: TextProviderStatus | null,
  localEnv?: LocalEnvStatus | null,
  liveStatus?: LiveProviderStatus | null,
) {
  const textReady = Boolean(textStatus?.ready);
  const imageReady = Boolean(
    localEnv?.enable_real_image_generation &&
    localEnv.huimengi_api_key_configured &&
    localEnv.huimengi_image_model,
  );
  const videoReady = Boolean(
    liveStatus?.real_seedance_enabled &&
    liveStatus.huimengi_api_key_configured &&
    liveStatus.provider_mode === "huimeng_live",
  );
  return [
    {
      key: "text",
      label: "AI 分析",
      ready: textReady,
      detail: textReady
        ? `已就绪：${textStatus?.mode_label}`
        : textStatus?.blocking_reason ||
          "请配置慧梦 GPT-5.5 或 OpenAI 官方文本模型。",
    },
    {
      key: "image",
      label: "真实生图",
      ready: imageReady,
      detail: imageReady
        ? `已就绪：${localEnv?.huimengi_image_model}`
        : "请配置慧梦 Key、image-2，并开启真实生图逐次确认。",
    },
    {
      key: "video",
      label: "真实视频",
      ready: videoReady,
      detail: videoReady
        ? `已就绪：${liveStatus?.huimengi_video_model || liveStatus?.huimengi_model_id}`
        : "请配置慧梦 Key、开启真实单镜闸门，并保持视频模式为慧梦真实单镜。",
    },
  ];
}

export function realRunPrimaryAction({
  activeProject,
  flowNav,
  textStatus,
  localEnv,
  liveStatus,
}: Pick<
  RealRunChecklistProps,
  "activeProject" | "flowNav" | "textStatus" | "localEnv" | "liveStatus"
>) {
  const items = serviceItems(textStatus, localEnv, liveStatus);
  const textService = items.find((item) => item.key === "text");
  const imageService = items.find((item) => item.key === "image");
  const videoService = items.find((item) => item.key === "video");
  if (!textService?.ready) {
    return {
      label: "先配置 AI 分析",
      href: "/settings",
      reason: `${textService?.label ?? "AI 分析"}还没就绪；没有它就无法像 ChatGPT 使用系统文件那样分析剧本。`,
    };
  }
  if (!activeProject) {
    return {
      label: "上传资料开始",
      href: "/start-plan#source-intake",
      reason: "还没有当前项目。",
    };
  }
  const nextHref = flowNav?.primary_action_href || "/start-plan";
  if (
    (nextHref.includes("/assets") || nextHref.includes("/storyboards")) &&
    !imageService?.ready
  ) {
    return {
      label: "先配置真实生图",
      href: "/settings",
      reason:
        "当前下一步如果要生成正式资产图，需要 image-2；黑白故事板草稿可以先按分镜提示词推进。",
    };
  }
  if (nextHref.includes("/batch-video") && !videoService?.ready) {
    return {
      label: "先配置真实视频",
      href: "/settings",
      reason:
        "当前下一步会进入真实单镜视频验收，需要 Seedance 视频通道和预算闸门。",
    };
  }
  return {
    label: flowNav?.primary_action_label || "查看当前下一步",
    href: nextHref,
    reason:
      flowNav?.blocking_reason ||
      flowNav?.next_reason ||
      "真实模型服务已就绪，按当前项目流程推进。",
  };
}

export function RealRunChecklist({
  activeProject,
  flowNav,
  textStatus,
  localEnv,
  liveStatus,
  compact = false,
  onPrimaryAction,
  onPrepareAcceptanceProject,
  preparingAcceptanceProject = false,
}: RealRunChecklistProps) {
  const service = serviceItems(textStatus, localEnv, liveStatus);
  const projectReady = Boolean(activeProject && flowNav);
  const action = realRunPrimaryAction({
    activeProject,
    flowNav,
    textStatus,
    localEnv,
    liveStatus,
  });
  const items = [
    ...service,
    {
      key: "project",
      label: "当前项目",
      ready: projectReady,
      detail: projectReady
        ? `${activeProject?.project_code}｜下一步：${flowNav?.current_stage}`
        : "先上传剧本或分镜表，系统会创建项目并进入 AI 分析。",
    },
  ];

  return (
    <section
      className={`border border-cyan-400/25 bg-cyan-400/5 ${compact ? "p-4" : "p-5"}`}
    >
      <div className="flex items-start justify-between gap-5">
        <div>
          <p className="text-xs tracking-[0.18em] text-cyan-200">
            真实跑通检查
          </p>
          <h2
            className={`${compact ? "mt-1 text-lg" : "mt-2 text-xl"} font-semibold text-zinc-100`}
          >
            像 ChatGPT 使用系统文件一样跑完整流程
          </h2>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-zinc-400">
            不用猜下一步。这里会检查 AI
            分析、生图、视频和当前项目进度；但不会一开始就要求你配齐所有服务。先跑剧本分析，到了图片或视频阶段再补对应通道。
          </p>
        </div>
        {onPrimaryAction ? (
          <div className="flex shrink-0 flex-col gap-2">
            <button
              type="button"
              onClick={() => onPrimaryAction(action.href)}
              className="bg-cyan-300 px-4 py-2 text-sm font-semibold text-black transition hover:bg-cyan-200"
            >
              {action.label}
            </button>
            {onPrepareAcceptanceProject ? (
              <button
                type="button"
                disabled={preparingAcceptanceProject}
                onClick={onPrepareAcceptanceProject}
                className="border border-cyan-300/40 px-4 py-2 text-xs text-cyan-100 transition hover:bg-cyan-300/10 disabled:opacity-40"
              >
                {preparingAcceptanceProject
                  ? "正在准备验收项目"
                  : "一键准备真实验收项目"}
              </button>
            ) : null}
          </div>
        ) : (
          <a
            href={action.href}
            className="shrink-0 bg-cyan-300 px-4 py-2 text-sm font-semibold text-black transition hover:bg-cyan-200"
          >
            {action.label}
          </a>
        )}
      </div>
      <div
        className={`mt-4 grid ${compact ? "grid-cols-2" : "grid-cols-4"} gap-3`}
      >
        {items.map((item) => (
          <div
            className={`border p-3 text-xs ${
              item.ready
                ? "border-emerald-400/30 bg-emerald-400/7 text-emerald-100"
                : "border-red-400/30 bg-red-400/7 text-red-100"
            }`}
            key={item.key}
          >
            <p className="flex items-center gap-2 font-semibold">
              {item.ready ? (
                <CheckCircle2 size={14} />
              ) : (
                <CircleAlert size={14} />
              )}
              {item.ready ? "已就绪" : "缺少"}｜{item.label}
            </p>
            <p className="mt-2 leading-5 text-zinc-400">{item.detail}</p>
          </div>
        ))}
      </div>
      <p className="mt-4 flex items-center gap-2 border-l-2 border-cyan-300 bg-cyan-300/7 px-3 py-2 text-sm text-cyan-100">
        <ArrowRight size={15} />
        现在只做：{action.label}。{action.reason}
      </p>
    </section>
  );
}
