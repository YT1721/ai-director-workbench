import { useEffect, useMemo, useState } from "react";
import {
  Archive,
  ArrowRight,
  Download,
  FolderKanban,
  Pencil,
  PlusCircle,
  RotateCcw,
  Search,
  Trash2,
} from "lucide-react";
import { useLocation, useNavigate } from "react-router-dom";

import { CreativeIntakePanel } from "../components/CreativeIntakePanel";
import { ErrorBanner } from "../components/ErrorBanner";
import { fetchProjectOverview, projectExportUrl } from "../services/api";
import { useWorkbenchStore } from "../stores/useWorkbenchStore";
import { workbenchPageClass } from "../styles/layout";
import type { ProjectOverview } from "../types/workbench";

type FilterMode = "active" | "archived" | "all";

const filterLabels: Record<FilterMode, string> = {
  active: "进行中",
  archived: "已归档",
  all: "全部",
};

function formatDate(value: string): string {
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

function statusClass(project: ProjectOverview): string {
  if (project.is_archived)
    return "border-zinc-600 bg-zinc-800/35 text-zinc-400";
  if (project.source_file_count === 0)
    return "border-red-400/55 bg-red-400/8 text-red-200";
  if (project.short_status.includes("缺少"))
    return "border-orange-400/65 bg-orange-400/10 text-orange-200";
  return "border-emerald-400/55 bg-emerald-400/8 text-emerald-200";
}

export function HomePage() {
  const navigate = useNavigate();
  const location = useLocation();
  const {
    activeProject,
    error,
    isBusy,
    clearError,
    loadProjects,
    openProject,
    updateActiveProject,
    setActiveProjectArchived,
    deleteProjectPermanently,
  } = useWorkbenchStore();
  const [projects, setProjects] = useState<ProjectOverview[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [filter, setFilter] = useState<FilterMode>("all");
  const [query, setQuery] = useState("");
  const [showNewProject, setShowNewProject] = useState(
    location.hash === "#new-project",
  );
  const [isLoading, setIsLoading] = useState(true);
  const [localError, setLocalError] = useState<string | null>(null);
  const [editName, setEditName] = useState("");
  const [editDescription, setEditDescription] = useState("");
  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false);
  const [manageOpen, setManageOpen] = useState(false);

  const refresh = async () => {
    setIsLoading(true);
    setLocalError(null);
    try {
      const overview = await fetchProjectOverview(true);
      setProjects(overview);
      setSelectedId((current) => {
        if (current && overview.some((project) => project.id === current))
          return current;
        return null;
      });
      await loadProjects({ restoreActive: false });
    } catch (error) {
      setLocalError((error as Error).message);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    void refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const handleRefresh = () => void refresh();
    window.addEventListener("project-console-refresh", handleRefresh);
    return () =>
      window.removeEventListener("project-console-refresh", handleRefresh);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeProject?.id]);

  useEffect(() => {
    if (location.hash === "#new-project") setShowNewProject(true);
  }, [location.hash]);

  const selectedProject = useMemo(
    () => projects.find((project) => project.id === selectedId) ?? null,
    [projects, selectedId],
  );

  useEffect(() => {
    if (!selectedProject) {
      setEditName("");
      setEditDescription("");
      setDeleteConfirmOpen(false);
      return;
    }
    setEditName(selectedProject.name);
    setEditDescription(selectedProject.description);
    setDeleteConfirmOpen(false);
  }, [selectedProject?.id]);

  const visibleProjects = projects.filter((project) => {
    if (filter === "active" && project.is_archived) return false;
    if (filter === "archived" && !project.is_archived) return false;
    const keyword = query.trim().toLowerCase();
    if (!keyword) return true;
    return `${project.project_code} ${project.name} ${project.description}`
      .toLowerCase()
      .includes(keyword);
  });

  const selectProject = async (project: ProjectOverview) => {
    setSelectedId(project.id);
    await openProject(project.id);
  };

  const continueProject = async (project: ProjectOverview) => {
    await selectProject(project);
    navigate(project.primary_action_href || "/start-plan#source-intake");
  };

  const saveEdit = async () => {
    if (!selectedProject) return;
    await openProject(selectedProject.id);
    await updateActiveProject(editName, editDescription);
    await refresh();
  };

  const toggleArchive = async (archived: boolean) => {
    if (!selectedProject) return;
    await openProject(selectedProject.id);
    await setActiveProjectArchived(archived);
    await refresh();
  };

  const hardDelete = async () => {
    if (!selectedProject) return;
    await deleteProjectPermanently(selectedProject.id, selectedProject.name);
    setDeleteConfirmOpen(false);
    setManageOpen(false);
    setSelectedId(null);
    await refresh();
  };

  return (
    <div className={workbenchPageClass}>
      <section className="border border-white/12 bg-[#151b21]/90 p-7">
        <div className="flex items-start justify-between gap-6">
          <div>
            <p className="text-xs tracking-[0.18em] text-orange-400">
              项目总控台
            </p>
            <h1 className="mt-2 text-4xl font-semibold tracking-wide text-zinc-100">
              选择项目，或上传新剧本开始
            </h1>
            <p className="mt-3 max-w-3xl text-sm leading-6 text-zinc-400">
              这里是工作台入口。你可以继续旧项目、查看归档项目，或者新建项目上传新的剧本
              / 分镜资料。
            </p>
          </div>
          <button
            type="button"
            onClick={() => {
              setShowNewProject((value) => !value);
              if (!showNewProject) {
                window.requestAnimationFrame(() => {
                  document
                    .querySelector("#new-project")
                    ?.scrollIntoView?.({ behavior: "smooth", block: "start" });
                });
              }
            }}
            className="flex shrink-0 items-center gap-2 bg-orange-500 px-5 py-3 text-sm font-semibold text-black transition hover:bg-orange-400"
          >
            <PlusCircle size={17} />
            新建项目
          </button>
        </div>

        <div className="mt-7 grid grid-cols-4 gap-4">
          <div className="border border-white/10 bg-black/15 p-4">
            <p className="text-xs text-zinc-500">全部项目</p>
            <p className="mt-2 text-2xl font-semibold text-zinc-100">
              {projects.length}
            </p>
          </div>
          <div className="border border-emerald-400/25 bg-emerald-400/7 p-4">
            <p className="text-xs text-emerald-300">进行中</p>
            <p className="mt-2 text-2xl font-semibold text-emerald-100">
              {projects.filter((project) => !project.is_archived).length}
            </p>
          </div>
          <div className="border border-zinc-500/25 bg-zinc-500/7 p-4">
            <p className="text-xs text-zinc-400">已归档</p>
            <p className="mt-2 text-2xl font-semibold text-zinc-200">
              {projects.filter((project) => project.is_archived).length}
            </p>
          </div>
          <div className="border border-orange-400/25 bg-orange-400/7 p-4">
            <p className="text-xs text-orange-300">当前项目</p>
            <p className="mt-2 truncate text-lg font-semibold text-orange-100">
              {activeProject
                ? `${activeProject.project_code}｜${activeProject.name}`
                : "尚未选择"}
            </p>
          </div>
        </div>
      </section>

      {localError || error ? (
        <div className="mt-5">
          <ErrorBanner
            message={localError ?? error ?? ""}
            onClose={() => {
              setLocalError(null);
              clearError();
            }}
          />
        </div>
      ) : null}

      {showNewProject ? (
        <div id="new-project" className="mt-6 scroll-mt-28">
          <CreativeIntakePanel
            mode="create"
            onComplete={() => {
              void refresh();
              navigate("/start-plan#ai-director-analysis");
            }}
          />
        </div>
      ) : null}

      <section className="mt-6 border border-white/12 bg-[#151b21]/80 p-5">
        <div className="flex items-center justify-between gap-4">
          <div>
            <h2 className="text-xl font-semibold text-zinc-100">项目列表</h2>
            <p className="mt-1 text-sm text-zinc-500">
              点击项目卡片会进入它的开始 / 规划页；点“管理”会打开项目管理窗口。
            </p>
          </div>
          <div className="flex items-center gap-2">
            {(["active", "archived", "all"] as FilterMode[]).map((mode) => (
              <button
                key={mode}
                type="button"
                onClick={() => setFilter(mode)}
                className={`border px-3 py-2 text-xs transition ${
                  filter === mode
                    ? "border-orange-400 bg-orange-400/10 text-orange-200"
                    : "border-white/12 text-zinc-400 hover:border-orange-400/40 hover:text-zinc-200"
                }`}
              >
                {filterLabels[mode]}
              </button>
            ))}
          </div>
        </div>

        <label className="mt-4 flex items-center gap-2 border border-white/12 bg-black/15 px-3 py-2 text-sm text-zinc-500">
          <Search size={16} />
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="搜索项目编号、名称或说明"
            className="w-full bg-transparent text-zinc-100 outline-none placeholder:text-zinc-600"
          />
        </label>

        <div className="mt-4 grid grid-cols-3 gap-3">
          {isLoading ? (
            <p className="col-span-3 border border-white/10 bg-black/10 p-5 text-sm text-zinc-500">
              正在读取项目列表...
            </p>
          ) : visibleProjects.length === 0 ? (
            <div className="col-span-3 border border-dashed border-white/15 bg-black/10 p-8 text-center">
              <FolderKanban className="mx-auto text-zinc-500" size={28} />
              <p className="mt-3 text-sm text-zinc-300">
                这里还没有符合条件的项目。
              </p>
              <button
                type="button"
                onClick={() => setShowNewProject(true)}
                className="mt-4 border border-orange-400/50 px-4 py-2 text-sm text-orange-200 hover:bg-orange-400/10"
              >
                新建第一个项目
              </button>
            </div>
          ) : (
            visibleProjects.map((project) => (
              <article
                key={project.id}
                onClick={() => {
                  if (project.is_archived) {
                    setSelectedId(project.id);
                    setManageOpen(true);
                    return;
                  }
                  void continueProject(project);
                }}
                className={`block w-full border p-4 text-left transition ${
                  manageOpen && selectedProject?.id === project.id
                    ? "border-orange-400 bg-orange-400/8"
                    : activeProject?.id === project.id
                      ? "border-emerald-400/45 bg-emerald-400/6"
                      : "border-white/10 bg-black/10 hover:border-orange-400/40"
                } ${project.is_archived ? "cursor-default opacity-70" : "cursor-pointer"}`}
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="min-w-0">
                    <p className="text-xs tracking-[0.16em] text-orange-300">
                      {project.project_code}
                    </p>
                    <h3 className="mt-1 truncate text-lg font-semibold text-zinc-100">
                      {project.name}
                    </h3>
                    <p className="mt-2 line-clamp-2 text-sm leading-6 text-zinc-500">
                      {project.description || "暂无项目说明"}
                    </p>
                  </div>
                  <span
                    className={`shrink-0 border px-2.5 py-1 text-xs ${statusClass(project)}`}
                  >
                    {project.is_archived ? "已归档" : project.short_status}
                  </span>
                </div>
                <div className="mt-4 grid grid-cols-4 gap-2 text-xs text-zinc-500">
                  <span>集：{project.episode_count}</span>
                  <span>场：{project.scene_count}</span>
                  <span>镜头：{project.shot_count}</span>
                  <span>资料：{project.source_file_count}</span>
                </div>
                <div className="mt-3 flex items-center justify-between border-t border-white/8 pt-3 text-xs">
                  <span className="text-zinc-500">
                    更新：{formatDate(project.updated_at)}
                  </span>
                  <span className="text-orange-200">
                    下一步：{project.current_stage}
                  </span>
                </div>
                <div className="mt-4 grid grid-cols-1 gap-2">
                  <button
                    type="button"
                    aria-label={`管理 ${project.project_code}`}
                    onClick={(event) => {
                      event.stopPropagation();
                      setSelectedId(project.id);
                      setManageOpen(true);
                    }}
                    className="border border-white/15 px-3 py-2 text-xs text-zinc-300 transition hover:border-sky-400/45 hover:text-sky-200"
                  >
                    管理
                  </button>
                </div>
              </article>
            ))
          )}
        </div>
      </section>

      {selectedProject && manageOpen ? (
        <div className="fixed inset-0 z-40 grid place-items-center bg-black/65 px-6">
          <aside className="max-h-[88vh] w-[760px] overflow-auto border border-white/12 bg-[#151b21] p-6 shadow-2xl shadow-black/40">
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="text-xs tracking-[0.16em] text-orange-400">
                  项目管理
                </p>
                <h2 className="mt-2 text-2xl font-semibold text-zinc-100">
                  {selectedProject.project_code}｜{selectedProject.name}
                </h2>
                <p className="mt-3 text-sm leading-6 text-zinc-400">
                  {selectedProject.description ||
                    "暂无项目说明。可以在下方补充题材、目标画幅或当前阶段。"}
                </p>
              </div>
              <button
                type="button"
                onClick={() => setManageOpen(false)}
                className="border border-white/15 px-3 py-2 text-sm text-zinc-300 transition hover:bg-white/5"
              >
                关闭
              </button>
            </div>

            <div className="mt-5 border border-orange-400/25 bg-orange-400/7 p-4">
              <p className="text-sm font-semibold text-orange-100">
                下一步建议：{selectedProject.current_stage}
              </p>
              <p className="mt-2 text-sm leading-6 text-zinc-400">
                {selectedProject.short_status}
              </p>
              <button
                type="button"
                disabled={selectedProject.is_archived}
                onClick={() => void continueProject(selectedProject)}
                className="mt-4 flex w-full items-center justify-center gap-2 bg-orange-500 px-4 py-3 text-sm font-semibold text-black transition hover:bg-orange-400 disabled:cursor-not-allowed disabled:bg-zinc-700 disabled:text-zinc-400"
              >
                {selectedProject.primary_action_label || "继续工作"}
                <ArrowRight size={16} />
              </button>
              {selectedProject.is_archived ? (
                <p className="mt-3 text-xs text-zinc-500">
                  已归档项目需要先恢复，才能继续创作。
                </p>
              ) : null}
            </div>

            <div className="mt-5 space-y-3">
              <label className="block text-xs text-zinc-400">
                项目名称
                <input
                  value={editName}
                  onChange={(event) => setEditName(event.target.value)}
                  className="mt-2 w-full border border-white/15 bg-black/15 px-3 py-2.5 text-sm text-white outline-none focus:border-orange-400/70"
                />
              </label>
              <label className="block text-xs text-zinc-400">
                项目说明
                <textarea
                  value={editDescription}
                  onChange={(event) => setEditDescription(event.target.value)}
                  className="mt-2 min-h-24 w-full resize-y border border-white/15 bg-black/15 px-3 py-3 text-sm text-white outline-none focus:border-orange-400/70"
                />
              </label>
              <button
                type="button"
                disabled={isBusy || !editName.trim()}
                onClick={() => void saveEdit()}
                className="flex w-full items-center justify-center gap-2 border border-emerald-400/45 px-4 py-2.5 text-sm text-emerald-200 transition hover:bg-emerald-400/10 disabled:opacity-40"
              >
                <Pencil size={15} />
                保存项目信息
              </button>
            </div>

            <div className="mt-5 grid grid-cols-2 gap-3">
              <a
                href={projectExportUrl(selectedProject.id)}
                className="flex items-center justify-center gap-2 border border-sky-400/45 px-3 py-2.5 text-sm text-sky-200 transition hover:bg-sky-400/10"
              >
                <Download size={15} />
                导出存档
              </a>
              <button
                type="button"
                disabled={isBusy}
                onClick={() => void toggleArchive(!selectedProject.is_archived)}
                className="flex items-center justify-center gap-2 border border-white/15 px-3 py-2.5 text-sm text-zinc-300 transition hover:border-orange-400/45 hover:text-orange-200 disabled:opacity-40"
              >
                {selectedProject.is_archived ? (
                  <RotateCcw size={15} />
                ) : (
                  <Archive size={15} />
                )}
                {selectedProject.is_archived ? "恢复项目" : "归档隐藏"}
              </button>
            </div>

            <div className="mt-6 border border-red-400/25 bg-red-400/7 p-4">
              <p className="flex items-center gap-2 text-sm font-semibold text-red-200">
                <Trash2 size={15} />
                删除项目
              </p>
              <p className="mt-2 text-xs leading-5 text-zinc-500">
                删除前建议先导出存档。删除会移除数据库记录和本地项目目录，不能在应用内恢复。
              </p>
              <button
                type="button"
                disabled={isBusy}
                onClick={() => setDeleteConfirmOpen(true)}
                className="mt-3 w-full border border-red-400/60 px-4 py-2.5 text-sm text-red-200 transition hover:bg-red-400/10 disabled:cursor-not-allowed disabled:opacity-35"
              >
                删除这个项目
              </button>
            </div>
          </aside>
        </div>
      ) : null}

      {selectedProject && deleteConfirmOpen ? (
        <div className="fixed inset-0 z-50 grid place-items-center bg-black/65 px-6">
          <div className="w-[520px] border border-red-400/35 bg-[#151b21] p-6 shadow-2xl shadow-black/40">
            <p className="text-xs tracking-[0.18em] text-red-300">危险操作</p>
            <h2 className="mt-2 text-2xl font-semibold text-zinc-100">
              确认删除这个项目？
            </h2>
            <p className="mt-3 text-sm leading-6 text-zinc-400">
              将删除{" "}
              <span className="font-semibold text-red-200">
                {selectedProject.project_code}｜{selectedProject.name}
              </span>{" "}
              的数据库记录和本地项目目录。删除后不能在应用内恢复。
            </p>
            <div className="mt-5 border border-red-400/20 bg-red-400/7 p-3 text-sm leading-6 text-red-100">
              建议先点“导出存档”。如果你只是暂时不用，点“归档隐藏”会更安全。
            </div>
            <div className="mt-6 grid grid-cols-2 gap-3">
              <button
                type="button"
                onClick={() => setDeleteConfirmOpen(false)}
                className="border border-white/15 px-4 py-3 text-sm text-zinc-300 transition hover:bg-white/5"
              >
                取消
              </button>
              <button
                type="button"
                disabled={isBusy}
                onClick={() => void hardDelete()}
                className="border border-red-400 bg-red-500/15 px-4 py-3 text-sm font-semibold text-red-100 transition hover:bg-red-500/25 disabled:opacity-40"
              >
                确认删除
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
