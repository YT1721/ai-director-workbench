import { useEffect, useMemo, useState } from "react";
import {
  CheckCircle2,
  ChevronDown,
  RefreshCw,
  ShieldAlert,
} from "lucide-react";

import {
  DirectorStatusPanel,
  DirectorWorkbenchFrame,
  GuideActionCard,
  GuidePrimaryButton,
  GuideProgressToast,
  GuideSecondaryAction,
  type DirectorStageItem,
} from "../components/Guide";
import { fetchWorkflowReview, generateWorkflowReport } from "../services/api";
import { useWorkbenchStore } from "../stores/useWorkbenchStore";
import { workbenchPageClass } from "../styles/layout";
import type { WorkflowIssue, WorkflowReview } from "../types/workflows";

type NextStepAction = {
  href: string;
  label: string;
  task: string;
  impact: string;
};

type IssueGroup = NextStepAction & {
  key: string;
  title: string;
  issues: WorkflowIssue[];
};

const stageAction: Record<string, NextStepAction> = {
  assets: {
    href: "/assets",
    label: "去资产图处理",
    task: "补齐并确认当前场的资产图",
    impact: "资产未确认会让人物身份、服装和场景空间在后续画面中漂移。",
  },
  storyboards: {
    href: "/storyboards",
    label: "去故事板处理",
    task: "生成并确认当前场的故事板",
    impact: "故事板风格或轴线不稳定，会直接影响镜头连续性和最终成片可剪辑性。",
  },
  video_package: {
    href: "/video-package",
    label: "去生成成片提示词",
    task: "生成并确认当前场的成片提示词",
    impact: "缺少正式成片提示词时，视频服务拿不到镜头动作、连续性和资产约束。",
  },
  batch_queue: {
    href: "/batch-video",
    label: "去批量视频处理",
    task: "建立队列并完成视频服务与费用确认",
    impact: "队列、服务或费用条件未通过时，系统不会发送真实视频请求。",
  },
};

function stageKey(category: string) {
  if (category === "assets") return "assets";
  if (category === "storyboard" || category === "axis") return "storyboards";
  if (category === "video_package") return "video_package";
  return "batch_queue";
}

function issueGroups(
  report: WorkflowReview["reports"][number] | undefined,
): IssueGroup[] {
  if (!report) return [];
  const groups = new Map<string, WorkflowIssue[]>();
  for (const issue of report.issues) {
    const key = stageKey(issue.category);
    groups.set(key, [...(groups.get(key) ?? []), issue]);
  }
  return [...groups.entries()].map(([key, issues]) => ({
    key,
    title: stageAction[key].task,
    issues,
    ...stageAction[key],
  }));
}

export function CheckFixPage() {
  const { activeProject, projects, loadProjects } = useWorkbenchStore();
  const [data, setData] = useState<WorkflowReview | null>(null);
  const [sceneId, setSceneId] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [busyMessage, setBusyMessage] = useState("");

  useEffect(() => {
    if (!projects.length) void loadProjects();
  }, [loadProjects, projects.length]);

  useEffect(() => {
    if (!activeProject) return;
    setBusy(true);
    setBusyMessage("正在检查当前场…");
    void fetchWorkflowReview(activeProject.id)
      .then((next) => {
        const nextSceneId = sceneId || next.scenes[0]?.id || "";
        setSceneId(nextSceneId);
        if (!nextSceneId) return next;
        return generateWorkflowReport(nextSceneId);
      })
      .then(setData)
      .catch((cause: Error) => setError(cause.message))
      .finally(() => {
        setBusy(false);
        setBusyMessage("");
      });
  }, [activeProject]); // eslint-disable-line react-hooks/exhaustive-deps

  const report = useMemo(
    () => data?.reports.find((item) => item.scene_id === sceneId),
    [data, sceneId],
  );
  const groups = useMemo(() => issueGroups(report), [report]);
  const currentGroup = groups[0];

  const runCheck = (targetSceneId = sceneId) => {
    if (!targetSceneId) return;
    setBusy(true);
    setBusyMessage(report ? "正在重新检查当前场…" : "正在检查当前场…");
    setError("");
    void generateWorkflowReport(targetSceneId)
      .then(setData)
      .catch((cause: Error) => setError(cause.message))
      .finally(() => {
        setBusy(false);
        setBusyMessage("");
      });
  };

  const checkTitle = currentGroup
    ? `下一步：${currentGroup.task}`
    : report?.ready_for_next
      ? "当前场已通过检查"
      : "检查当前场是否可以继续";
  const checkDescription = currentGroup
    ? `${currentGroup.issues.length} 个检查项属于同一个阻塞阶段。先完成这一阶段，再回来重新检查；下游条件会在之后按顺序核对。`
    : report?.ready_for_next
      ? "资产、故事板、成片提示词、视频队列和费用条件均已通过，可以继续生成或提交。"
      : "系统会按制作顺序检查资产、故事板、成片提示词和视频提交条件，只展示当前最早需要处理的阶段。";

  const stageItems: DirectorStageItem[] = [
    {
      title: "选择当前场",
      detail: sceneId ? "已选择" : "请选择一个场",
      status: sceneId ? "done" : "current",
    },
    {
      title: "检查制作条件",
      detail: report ? "已有最新检查结果" : "等待检查",
      status: report ? "done" : "current",
    },
    {
      title: "处理当前阻塞",
      detail: currentGroup
        ? currentGroup.task
        : report
          ? "没有阻塞项"
          : "检查后确认",
      status: currentGroup ? "current" : report ? "done" : "pending",
    },
    {
      title: "继续创作",
      detail: report?.ready_for_next ? "可以继续" : "完成当前阶段后继续",
      status: report?.ready_for_next ? "done" : "pending",
    },
  ];

  return (
    <div className={workbenchPageClass}>
      {busy ? (
        <GuideProgressToast label={busyMessage || "正在检查当前场…"} />
      ) : null}
      <p className="text-xs tracking-[.18em] text-orange-400">V7｜流程体检</p>
      <div className="flex items-end justify-between gap-4">
        <div>
          <h1 className="mt-2 text-4xl font-semibold">
            检查当前场是否可以继续
          </h1>
          <p className="mt-3 text-sm text-zinc-400">
            这里不生成内容，也不伪装成自动修复。它只提前发现会造成画面漂移、镜头不连续或提交失败的问题。
          </p>
        </div>
        <select
          aria-label="选择检查场景"
          className="border border-white/15 bg-[#11171c] px-3 py-2 text-sm"
          value={sceneId}
          onChange={(event) => {
            setSceneId(event.target.value);
            runCheck(event.target.value);
          }}
        >
          {data?.scenes.map((scene) => (
            <option key={scene.id} value={scene.id}>
              {scene.scope_code}｜{scene.name}
            </option>
          ))}
        </select>
      </div>

      {error && (
        <p className="mt-4 border-l-2 border-red-400 px-4 py-3 text-sm text-red-200">
          {error}
        </p>
      )}

      <DirectorWorkbenchFrame
        main={
          <GuideActionCard
            title={checkTitle}
            description={checkDescription}
            tone={report?.ready_for_next ? "done" : "current"}
            progressLabel={busy ? busyMessage : undefined}
          >
            <div className="flex items-center gap-3">
              {currentGroup ? (
                <GuidePrimaryButton href={currentGroup.href}>
                  {currentGroup.label}
                </GuidePrimaryButton>
              ) : report?.ready_for_next ? (
                <GuidePrimaryButton href="/batch-video">
                  继续批量视频
                </GuidePrimaryButton>
              ) : (
                <GuidePrimaryButton
                  disabled={!sceneId || busy}
                  loading={busy}
                  loadingLabel="正在检查当前场…"
                  onClick={() => runCheck()}
                >
                  检查当前场
                </GuidePrimaryButton>
              )}
              {report ? (
                <GuideSecondaryAction
                  disabled={!sceneId || busy}
                  onClick={() => runCheck()}
                >
                  <RefreshCw size={15} />
                  重新检查
                </GuideSecondaryAction>
              ) : null}
            </div>
          </GuideActionCard>
        }
        aside={
          <DirectorStatusPanel
            title="检查进度"
            description="只展示最早的阻塞阶段，完成后再检查下一阶段。"
            items={stageItems}
          />
        }
      />

      <section className="mt-6">
        {report ? (
          <ReportCard report={report} groups={groups} />
        ) : (
          <p className="border border-dashed border-white/15 p-5 text-sm text-zinc-500">
            还没有检查记录。准备进入视频生成前，检查一次当前场即可。
          </p>
        )}
      </section>
    </div>
  );
}

function ReportCard({
  report,
  groups,
}: {
  report: WorkflowReview["reports"][number];
  groups: IssueGroup[];
}) {
  if (report.ready_for_next) {
    return (
      <article className="border border-emerald-400/30 bg-emerald-400/5 p-5">
        <div className="flex items-center gap-3">
          <CheckCircle2 className="text-emerald-300" />
          <div>
            <h2 className="text-lg font-semibold">当前场可以继续</h2>
            <p className="mt-1 text-sm text-zinc-400">
              本次检查没有发现会阻止后续制作或真实提交的问题。
            </p>
          </div>
        </div>
      </article>
    );
  }

  return (
    <article className="border border-white/15 bg-[#151b21] p-5">
      <div className="flex items-center justify-between gap-4">
        <div>
          <p className="text-xs text-zinc-500">{report.scope_code}｜最近检查</p>
          <h2 className="mt-2 text-lg font-semibold">
            {groups.length} 个阶段未完成 · {report.issues.length} 个检查项
          </h2>
        </div>
        <ShieldAlert className="text-red-300" />
      </div>

      <div className="mt-4 space-y-3">
        {groups.map((group) => (
          <section
            className="border border-orange-400/25 bg-orange-400/5 p-4"
            key={group.key}
          >
            <p className="text-sm font-semibold text-orange-200">
              {group.title}
            </p>
            <p className="mt-2 text-sm leading-6 text-zinc-400">
              {group.impact}
            </p>
            <details className="mt-3 border-t border-white/10 pt-3">
              <summary className="flex cursor-pointer list-none items-center gap-2 text-xs text-zinc-400 hover:text-zinc-200">
                <ChevronDown size={14} />
                查看 {group.issues.length} 个具体检查项
              </summary>
              <div className="mt-3 divide-y divide-white/10 border border-white/10">
                {group.issues.map((issue) => (
                  <div className="p-3" key={issue.id}>
                    <p className="text-sm text-zinc-200">{issue.title}</p>
                    <p className="mt-1 text-xs leading-5 text-zinc-500">
                      {issue.detail}
                    </p>
                  </div>
                ))}
              </div>
            </details>
          </section>
        ))}
      </div>
    </article>
  );
}
