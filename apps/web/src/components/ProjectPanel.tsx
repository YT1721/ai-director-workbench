import { Archive, FolderOpen, RotateCcw, Save } from "lucide-react";
import { useEffect, useState } from "react";

import { useWorkbenchStore } from "../stores/useWorkbenchStore";
import { ProjectCreateForm } from "./ProjectCreateForm";

export function ProjectPanel() {
  const {
    projects,
    activeProject,
    isBusy,
    openProject,
    updateActiveProject,
    setActiveProjectArchived,
  } = useWorkbenchStore();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");

  useEffect(() => {
    setName(activeProject?.name ?? "");
    setDescription(activeProject?.description ?? "");
  }, [activeProject]);

  return (
    <div className="space-y-4">
      <section className="border border-white/15 bg-[#151b21]/90 p-5">
        <div className="flex items-center gap-2 text-orange-300">
          <FolderOpen size={18} />
          <h2 className="font-semibold tracking-wide">打开项目</h2>
        </div>
        <select
          aria-label="当前项目"
          value={activeProject?.id ?? ""}
          onChange={(event) => void openProject(event.target.value)}
          className="mt-4 w-full border border-white/15 bg-[#11171c] px-3 py-2.5 text-sm text-zinc-100 outline-none focus:border-orange-400/70"
        >
          <option value="" disabled>
            请选择项目
          </option>
          {projects.map((project) => (
            <option key={project.id} value={project.id}>
              {project.project_code}｜{project.name}
              {project.is_archived ? "（已归档）" : ""}
            </option>
          ))}
        </select>
      </section>

      <ProjectCreateForm />

      {activeProject && (
        <form
          className="border border-white/15 bg-[#151b21]/90 p-5"
          onSubmit={(event) => {
            event.preventDefault();
            void updateActiveProject(name, description);
          }}
        >
          <p className="text-xs tracking-[0.16em] text-orange-400">
            {activeProject.project_code}
          </p>
          <h2 className="mt-2 font-semibold tracking-wide text-zinc-100">
            项目信息
          </h2>
          <input
            aria-label="编辑项目名称"
            value={name}
            onChange={(event) => setName(event.target.value)}
            className="mt-4 w-full border border-white/15 bg-black/15 px-3 py-2.5 text-sm text-white outline-none focus:border-orange-400/70"
          />
          <textarea
            aria-label="编辑项目说明"
            value={description}
            onChange={(event) => setDescription(event.target.value)}
            placeholder="项目说明"
            className="mt-3 min-h-20 w-full border border-white/15 bg-black/15 px-3 py-2.5 text-sm text-white outline-none focus:border-orange-400/70"
          />
          <div className="mt-4 grid grid-cols-2 gap-2">
            <button
              disabled={isBusy}
              className="flex items-center justify-center gap-2 border border-white/15 px-3 py-2 text-sm text-zinc-200 hover:border-orange-400/60"
              type="submit"
            >
              <Save size={15} /> 保存信息
            </button>
            <button
              disabled={isBusy}
              className="flex items-center justify-center gap-2 border border-white/15 px-3 py-2 text-sm text-zinc-200 hover:border-orange-400/60"
              type="button"
              onClick={() =>
                void setActiveProjectArchived(!activeProject.is_archived)
              }
            >
              {activeProject.is_archived ? (
                <RotateCcw size={15} />
              ) : (
                <Archive size={15} />
              )}
              {activeProject.is_archived ? "恢复项目" : "归档项目"}
            </button>
          </div>
        </form>
      )}
    </div>
  );
}
