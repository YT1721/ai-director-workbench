import { Plus } from "lucide-react";
import { useState } from "react";

import { useWorkbenchStore } from "../stores/useWorkbenchStore";

export function ProjectCreateForm() {
  const createProject = useWorkbenchStore((state) => state.createProject);
  const isBusy = useWorkbenchStore((state) => state.isBusy);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");

  return (
    <form
      className="border border-white/15 bg-[#151b21]/90 p-5"
      onSubmit={async (event) => {
        event.preventDefault();
        if (!name.trim()) return;
        await createProject(name, description);
        setName("");
        setDescription("");
      }}
    >
      <div className="flex items-center gap-2 text-orange-300">
        <Plus size={18} />
        <h2 className="font-semibold tracking-wide">创建新项目</h2>
      </div>
      <label className="mt-4 block text-xs text-zinc-400">
        项目名称
        <input
          required
          value={name}
          onChange={(event) => setName(event.target.value)}
          placeholder="例如：第一部历史短剧"
          className="mt-2 w-full border border-white/15 bg-black/15 px-3 py-2.5 text-sm text-white outline-none transition focus:border-orange-400/70"
        />
      </label>
      <label className="mt-3 block text-xs text-zinc-400">
        项目说明（可选）
        <textarea
          value={description}
          onChange={(event) => setDescription(event.target.value)}
          placeholder="记录题材、目标画幅或当前阶段"
          className="mt-2 min-h-20 w-full resize-y border border-white/15 bg-black/15 px-3 py-2.5 text-sm text-white outline-none transition focus:border-orange-400/70"
        />
      </label>
      <button
        type="submit"
        disabled={isBusy}
        className="mt-4 w-full bg-orange-500 px-4 py-2.5 text-sm font-medium text-black transition hover:bg-orange-400 disabled:opacity-50"
      >
        创建项目并生成 EP01 / SC01 / SH001
      </button>
    </form>
  );
}
