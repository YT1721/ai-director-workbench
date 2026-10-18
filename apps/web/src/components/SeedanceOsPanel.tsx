import { useCallback, useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  Clipboard,
  Film,
  RefreshCw,
  ShieldCheck,
  XCircle,
} from "lucide-react";

import {
  compileSeedanceVideoUnit,
  createSeedanceVideoUnit,
  fetchSeedanceOsWorkspace,
  reviewSeedanceTake,
} from "../services/api";
import type {
  SeedanceOsWorkspace,
  SeedanceVideoUnit,
} from "../types/seedanceOs";
import { GuideProgressToast, TechDetails } from "./Guide";

const secondaryButton =
  "inline-flex items-center justify-center gap-2 rounded-xl border border-white/12 bg-white/[0.03] px-4 py-2.5 text-sm text-zinc-300 transition hover:border-orange-400/40 hover:text-orange-100 disabled:cursor-not-allowed disabled:opacity-35";
const primaryButton =
  "inline-flex items-center justify-center gap-2 rounded-xl border border-orange-300/50 bg-orange-500 px-5 py-3 text-sm font-semibold text-black shadow-[0_10px_30px_rgba(249,115,22,.2)] transition hover:bg-orange-400 disabled:cursor-not-allowed disabled:opacity-35";

interface SeedanceOsPanelProps {
  projectId: string;
  onDurationRebuildCountChange?: (count: number) => void;
}

function messageFrom(error: unknown): string {
  return error instanceof Error ? error.message : "操作没有完成，请稍后重试。";
}

function formatJsonValue(value: unknown): string {
  if (value === null || value === undefined || value === "") return "未记录";
  if (typeof value === "string") return value;
  return JSON.stringify(value, null, 2);
}

export function SeedanceOsPanel({
  projectId,
  onDurationRebuildCountChange,
}: SeedanceOsPanelProps) {
  const [workspace, setWorkspace] = useState<SeedanceOsWorkspace | null>(null);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [reviewDrafts, setReviewDrafts] = useState<
    Record<string, { source: string; end: string; reason: string }>
  >({});

  const load = useCallback(async () => {
    setError("");
    try {
      setWorkspace(await fetchSeedanceOsWorkspace(projectId));
    } catch (loadError) {
      setError(messageFrom(loadError));
    }
  }, [projectId]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    if (!workspace) return;
    onDurationRebuildCountChange?.(
      workspace.candidates.filter(
        (candidate) => candidate.duration_needs_rebuild,
      ).length,
    );
  }, [workspace, onDurationRebuildCountChange]);

  const run = async (
    label: string,
    action: () => Promise<unknown>,
    success: string,
  ) => {
    setBusy(label);
    setError("");
    setNotice("");
    try {
      await action();
      await load();
      setNotice(success);
    } catch (runError) {
      setError(messageFrom(runError));
    } finally {
      setBusy("");
    }
  };

  const completedIds = new Set(
    workspace?.state?.completed_video_unit_ids ?? [],
  );
  const durationRebuildCandidates =
    workspace?.candidates.filter(
      (candidate) => candidate.duration_needs_rebuild,
    ) ?? [];
  const readyCandidates = useMemo(
    () =>
      workspace?.candidates.filter(
        (candidate) =>
          candidate.storyboard_status === "confirmed" &&
          candidate.vp_block_id &&
          candidate.precision_18.length === 18 &&
          !candidate.duration_needs_rebuild,
      ) ?? [],
    [workspace],
  );

  const createUnit = async (
    candidate: SeedanceOsWorkspace["candidates"][number],
  ) => {
    await run(
      `正在为 ${candidate.shot_code} 建立生产视频单元…`,
      () =>
        createSeedanceVideoUnit(projectId, {
          scene_id: candidate.scene_id,
          shot_id: candidate.shot_id,
          storyboard_version_id: candidate.storyboard_version_id,
          prompt_time_ranges: candidate.prompt_time_ranges,
          unit_index: candidate.next_unit_index,
          unit_type: "standalone",
          duration_seconds: Math.min(
            candidate.duration_seconds || 5,
            workspace?.limits.max_video_unit_seconds ?? 15,
          ),
          intended_start_state: {},
          intended_end_state: { shot_goal: candidate.shot_name },
          continuity_handoff: {
            already_happened: [],
            this_unit_only: [candidate.shot_name],
            reserved_for_later: [],
          },
          references: [],
        }),
      `${candidate.shot_code} 已建立生产视频单元。`,
    );
  };

  const compileUnit = async (unit: SeedanceVideoUnit) => {
    if (!unit.vp_block_id) return;
    await run(
      `正在编译 ${unit.shot_code} 的可复制视频提示词…`,
      () => compileSeedanceVideoUnit(unit.id, unit.vp_block_id as string),
      `${unit.shot_code} 的生产提示词已编译。`,
    );
  };

  const reviewUnit = async (
    unit: SeedanceVideoUnit,
    status: "accepted" | "rejected",
  ) => {
    const draft = reviewDrafts[unit.id] ?? { source: "", end: "", reason: "" };
    if (status === "accepted" && !draft.end.trim()) {
      setError(
        "通过成片前，请写清楚真实尾帧停在哪里，后续镜头会从这个状态继续。",
      );
      return;
    }
    if (status === "rejected" && !draft.reason.trim()) {
      setError(
        "驳回成片前，请填写问题原因。被驳回的成片不会成为下一段的来源。",
      );
      return;
    }
    await run(
      status === "accepted"
        ? `正在验收 ${unit.shot_code}…`
        : `正在记录 ${unit.shot_code} 的问题…`,
      () =>
        reviewSeedanceTake(unit.id, {
          source_video_path: draft.source.trim(),
          observed_start_state: {},
          observed_end_state:
            status === "accepted" ? { description: draft.end.trim() } : {},
          status,
          rejection_reasons: status === "rejected" ? [draft.reason.trim()] : [],
          review_notes: "",
        }),
      status === "accepted"
        ? `${unit.shot_code} 已通过验收，可作为后续视频来源。`
        : `${unit.shot_code} 已驳回，不会进入续拍来源。`,
    );
  };

  const copyPrompt = async (prompt: string) => {
    await navigator.clipboard.writeText(prompt);
    setNotice("可复制视频提示词已复制。这里只复制文字，不会提交付费生成。 ");
  };

  return (
    <section className="mt-7 rounded-[28px] border border-cyan-300/20 bg-[linear-gradient(145deg,rgba(15,31,40,.94),rgba(12,17,23,.98))] p-6 shadow-[0_24px_70px_rgba(0,0,0,.22)]">
      {busy ? <GuideProgressToast label={busy} /> : null}
      <div className="flex items-start justify-between gap-6">
        <div>
          <p className="text-xs font-semibold tracking-[.16em] text-cyan-300">
            SEEDANCE SKILL OS
          </p>
          <h2 className="mt-2 text-2xl font-semibold text-white">
            生产视频单元
          </h2>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-zinc-400">
            把已确认故事板与完整 18 项视频包锁定成不超过 15
            秒的生产单元，再编译可复制提示词并验收真实成片。本区不会自动提交视频服务。
          </p>
        </div>
        <button
          className={secondaryButton}
          disabled={Boolean(busy)}
          onClick={() => void load()}
        >
          <RefreshCw size={15} />
          刷新
        </button>
      </div>

      {durationRebuildCandidates.length > 0 ? (
        <div
          role="alert"
          className="mt-5 border border-orange-400/60 bg-orange-400/10 p-5 shadow-[0_14px_40px_rgba(249,115,22,.12)]"
        >
          <div className="flex flex-col items-start justify-between gap-5 lg:flex-row">
            <div className="flex min-w-0 items-start gap-3">
              <AlertTriangle
                className="mt-0.5 shrink-0 text-orange-300"
                size={22}
              />
              <div>
                <div className="flex flex-wrap items-center gap-2">
                  <span className="border border-orange-300/50 bg-orange-400/15 px-2 py-1 text-xs font-semibold text-orange-100">
                    必须先处理
                  </span>
                  <p className="text-base font-semibold text-orange-100">
                    检测到 {durationRebuildCandidates.length} 个旧版统一 5
                    秒镜头
                  </p>
                </div>
                <p className="mt-2 text-sm leading-6 text-zinc-300">
                  这些时长不是主文件的镜头节奏判断。若不重建，系统不会建立生产视频单元，也不能继续正式视频生成。
                </p>
                <p className="mt-1 text-xs leading-5 text-zinc-400">
                  重建只创建新版分镜提示词，不删除旧版本；随后需按新时间轴重建并确认对应故事板。
                </p>
              </div>
            </div>
            <a
              className={`${primaryButton} w-full shrink-0 sm:w-auto`}
              href="/video-package"
            >
              去按主规则重建
              <ArrowRight size={16} />
            </a>
          </div>
        </div>
      ) : null}

      <div className="mt-5 grid grid-cols-4 gap-3 text-sm">
        <div className="rounded-2xl border border-white/10 bg-black/15 p-4">
          <p className="text-zinc-500">生产上限</p>
          <p className="mt-1 font-semibold text-white">
            每单元 {workspace?.limits.max_video_unit_seconds ?? 15} 秒
          </p>
        </div>
        <div className="rounded-2xl border border-white/10 bg-black/15 p-4">
          <p className="text-zinc-500">可建立镜头</p>
          <p className="mt-1 font-semibold text-white">
            {readyCandidates.length} 个
          </p>
        </div>
        <div className="rounded-2xl border border-white/10 bg-black/15 p-4">
          <p className="text-zinc-500">已建单元</p>
          <p className="mt-1 font-semibold text-white">
            {workspace?.video_units.length ?? 0} 个
          </p>
        </div>
        <div className="rounded-2xl border border-orange-300/20 bg-orange-400/[0.06] p-4">
          <p className="text-orange-200/70">真实提交</p>
          <p className="mt-1 font-semibold text-orange-100">始终需要人工确认</p>
        </div>
      </div>

      {error ? (
        <p className="mt-4 border-l-2 border-red-400 bg-red-400/10 px-4 py-3 text-sm text-red-200">
          {error}
        </p>
      ) : null}
      {notice ? (
        <p className="mt-4 border-l-2 border-emerald-400 bg-emerald-400/10 px-4 py-3 text-sm text-emerald-200">
          {notice}
        </p>
      ) : null}

      <div className="mt-6 space-y-3">
        {workspace?.candidates.map((candidate) => {
          const existing = candidate.existing_video_unit_ids.length > 0;
          const ready =
            candidate.storyboard_status === "confirmed" &&
            Boolean(candidate.vp_block_id) &&
            candidate.precision_18.length === 18 &&
            !candidate.duration_needs_rebuild;
          return (
            <article
              key={candidate.shot_id}
              className="flex items-center justify-between gap-5 rounded-2xl border border-white/10 bg-black/15 p-4"
            >
              <div>
                <div className="flex items-center gap-2">
                  <Film size={16} className="text-orange-300" />
                  <h3 className="font-semibold text-white">
                    {candidate.shot_code}｜{candidate.shot_name}
                  </h3>
                </div>
                <p className="mt-2 text-xs text-zinc-500">
                  故事板{" "}
                  {candidate.storyboard_status === "confirmed"
                    ? "已确认"
                    : "未确认"}
                  ｜18 项视频包 {candidate.precision_18.length}/18｜当前{" "}
                  {Math.min(candidate.duration_seconds, 15)} 秒
                  {candidate.recommended_duration_seconds
                    ? `｜主规则建议 ${candidate.recommended_duration_seconds} 秒`
                    : ""}
                </p>
                {candidate.duration_needs_rebuild ? (
                  <p className="mt-1 text-xs text-orange-300">
                    {candidate.duration_reason}
                  </p>
                ) : null}
              </div>
              {existing ? (
                <span className="inline-flex items-center gap-2 text-sm text-emerald-300">
                  <CheckCircle2 size={16} />
                  已建立
                </span>
              ) : (
                <button
                  className={primaryButton}
                  disabled={!ready || Boolean(busy)}
                  onClick={() => void createUnit(candidate)}
                >
                  建立生产视频单元
                </button>
              )}
            </article>
          );
        })}
      </div>

      {workspace?.video_units.map((unit) => {
        const draft = reviewDrafts[unit.id] ?? {
          source: "",
          end: "",
          reason: "",
        };
        return (
          <article
            key={unit.id}
            className="mt-5 rounded-2xl border border-white/12 bg-[#0d141a] p-5"
          >
            <div className="flex items-start justify-between gap-5">
              <div>
                <p className="text-xs text-cyan-300">
                  视频单元 {unit.unit_index}｜{unit.duration_seconds}{" "}
                  秒｜事件密度 {unit.event_density_score}
                </p>
                <h3 className="mt-1 text-lg font-semibold text-white">
                  {unit.shot_code}｜{unit.shot_name}
                </h3>
                <p className="mt-2 text-xs text-zinc-500">
                  时间轴：{unit.prompt_time_ranges.join(" / ") || "尚未绑定"}
                </p>
              </div>
              {completedIds.has(unit.id) ? (
                <span className="inline-flex items-center gap-2 text-sm text-emerald-300">
                  <ShieldCheck size={16} />
                  真实成片已通过
                </span>
              ) : null}
            </div>

            {!unit.vp_prompt_copy ? (
              <button
                className={`${primaryButton} mt-4`}
                disabled={!unit.vp_block_id || Boolean(busy)}
                onClick={() => void compileUnit(unit)}
              >
                编译可复制视频提示词
              </button>
            ) : (
              <div className="mt-4 rounded-xl border border-cyan-300/15 bg-cyan-300/[0.04] p-4">
                <div className="flex items-center justify-between gap-4">
                  <p className="text-sm font-semibold text-cyan-100">
                    可复制视频提示词
                  </p>
                  <button
                    className={secondaryButton}
                    onClick={() => void copyPrompt(unit.vp_prompt_copy)}
                  >
                    <Clipboard size={14} />
                    复制
                  </button>
                </div>
                <p className="mt-3 whitespace-pre-wrap text-sm leading-6 text-zinc-300">
                  {unit.vp_prompt_copy}
                </p>
              </div>
            )}

            <TechDetails className="mt-4" title="成片回来后：验收这一条">
              <div className="grid grid-cols-2 gap-4 p-1">
                <label className="text-xs text-zinc-400">
                  本地视频路径（可选）
                  <input
                    className="mt-2 w-full rounded-xl border border-white/12 bg-black/20 px-3 py-2 text-sm text-white"
                    value={draft.source}
                    onChange={(event) =>
                      setReviewDrafts((current) => ({
                        ...current,
                        [unit.id]: { ...draft, source: event.target.value },
                      }))
                    }
                    placeholder="07_results/generated_videos/..."
                  />
                </label>
                <label className="text-xs text-zinc-400">
                  真实尾帧停在哪里（通过时必填）
                  <input
                    className="mt-2 w-full rounded-xl border border-white/12 bg-black/20 px-3 py-2 text-sm text-white"
                    value={draft.end}
                    onChange={(event) =>
                      setReviewDrafts((current) => ({
                        ...current,
                        [unit.id]: { ...draft, end: event.target.value },
                      }))
                    }
                    placeholder="例如：人物右手握信，停在门口回头"
                  />
                </label>
                <label className="col-span-2 text-xs text-zinc-400">
                  问题原因（驳回时必填）
                  <input
                    className="mt-2 w-full rounded-xl border border-white/12 bg-black/20 px-3 py-2 text-sm text-white"
                    value={draft.reason}
                    onChange={(event) =>
                      setReviewDrafts((current) => ({
                        ...current,
                        [unit.id]: { ...draft, reason: event.target.value },
                      }))
                    }
                    placeholder="例如：人物身份漂移、轴线错误、尾帧不可续接"
                  />
                </label>
              </div>
              <div className="mt-4 flex gap-3">
                <button
                  className={primaryButton}
                  disabled={Boolean(busy)}
                  onClick={() => void reviewUnit(unit, "accepted")}
                >
                  <CheckCircle2 size={16} />
                  通过并记录尾帧
                </button>
                <button
                  className={secondaryButton}
                  disabled={Boolean(busy)}
                  onClick={() => void reviewUnit(unit, "rejected")}
                >
                  <XCircle size={16} />
                  驳回这条成片
                </button>
              </div>
              {unit.take_reviews.length ? (
                <div className="mt-4 space-y-2">
                  {unit.take_reviews.map((review) => (
                    <p
                      key={review.id}
                      className="rounded-xl bg-black/20 px-3 py-2 text-xs text-zinc-400"
                    >
                      {review.review_status === "accepted"
                        ? "已通过"
                        : "已驳回"}
                      ｜尾帧：{formatJsonValue(review.observed_end_state)}
                      {review.rejection_reasons.length
                        ? `｜原因：${review.rejection_reasons.join("、")}`
                        : ""}
                    </p>
                  ))}
                </div>
              ) : null}
            </TechDetails>
          </article>
        );
      })}
    </section>
  );
}
