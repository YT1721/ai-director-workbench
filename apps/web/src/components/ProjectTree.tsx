import { Archive, Plus, RotateCcw } from "lucide-react";

import { useWorkbenchStore } from "../stores/useWorkbenchStore";

function SmallButton({
  label,
  onClick,
}: {
  label: string;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      onClick={onClick}
      className="grid size-7 place-items-center border border-white/10 text-zinc-500 transition hover:border-orange-400/50 hover:text-orange-300"
    >
      {label.includes("新增") ? (
        <Plus size={14} />
      ) : label.includes("恢复") ? (
        <RotateCcw size={13} />
      ) : (
        <Archive size={13} />
      )}
    </button>
  );
}

export function ProjectTree() {
  const {
    activeProject,
    selection,
    addEpisode,
    addScene,
    addShot,
    renameItem,
    setItemArchived,
    setSelection,
  } = useWorkbenchStore();

  if (!activeProject) return null;

  const rename = (
    kind: "episodes" | "scenes" | "shots",
    id: string,
    currentName: string,
  ) => {
    const name = window.prompt("请输入新名称", currentName)?.trim();
    if (name && name !== currentName) void renameItem(kind, id, name);
  };

  return (
    <section className="border border-white/15 bg-[#151b21]/90">
      <div className="flex items-center justify-between border-b border-white/10 px-4 py-3">
        <div>
          <h2 className="font-semibold tracking-wide text-zinc-100">
            集 / 场 / 镜头
          </h2>
          <p className="mt-1 text-xs text-zinc-500">点击编号切换当前范围</p>
        </div>
        <SmallButton label="新增一集" onClick={() => void addEpisode()} />
      </div>
      <div className="max-h-[520px] overflow-auto p-3">
        {activeProject.episodes.map((episode) => (
          <div
            key={episode.id}
            className={`mb-3 border border-white/10 p-2 ${episode.is_archived ? "opacity-45" : ""}`}
          >
            <div className="flex items-center gap-2">
              <button
                type="button"
                className={`flex-1 text-left text-sm font-medium ${
                  selection.episodeId === episode.id
                    ? "text-orange-300"
                    : "text-zinc-200"
                }`}
                onClick={() =>
                  setSelection({
                    episodeId: episode.id,
                    sceneId: undefined,
                    shotId: undefined,
                  })
                }
                onDoubleClick={() =>
                  rename("episodes", episode.id, episode.name)
                }
              >
                {episode.episode_code}｜{episode.name}
              </button>
              {!episode.is_archived && (
                <SmallButton
                  label={`为 ${episode.episode_code} 新增场`}
                  onClick={() => void addScene(episode.id)}
                />
              )}
              <SmallButton
                label={`${episode.is_archived ? "恢复" : "归档"} ${episode.episode_code}`}
                onClick={() =>
                  void setItemArchived(
                    "episodes",
                    episode.id,
                    !episode.is_archived,
                  )
                }
              />
            </div>
            <div className="mt-2 space-y-2 pl-3">
              {episode.scenes.map((scene) => (
                <div
                  key={scene.id}
                  className={`border-l border-white/10 pl-3 ${scene.is_archived ? "opacity-45" : ""}`}
                >
                  <div className="flex items-center gap-2 py-1">
                    <button
                      type="button"
                      className={`flex-1 text-left text-sm ${
                        selection.sceneId === scene.id
                          ? "text-orange-300"
                          : "text-zinc-400"
                      }`}
                      onClick={() =>
                        setSelection({
                          episodeId: episode.id,
                          sceneId: scene.id,
                          shotId: undefined,
                        })
                      }
                      onDoubleClick={() =>
                        rename("scenes", scene.id, scene.name)
                      }
                    >
                      {scene.scene_code}｜{scene.name}
                    </button>
                    {!scene.is_archived && (
                      <SmallButton
                        label={`为 ${scene.scene_code} 新增镜头`}
                        onClick={() => void addShot(scene.id)}
                      />
                    )}
                    <SmallButton
                      label={`${scene.is_archived ? "恢复" : "归档"} ${scene.scene_code}`}
                      onClick={() =>
                        void setItemArchived(
                          "scenes",
                          scene.id,
                          !scene.is_archived,
                        )
                      }
                    />
                  </div>
                  <div className="space-y-1 pl-3">
                    {scene.shots.map((shot) => (
                      <div
                        key={shot.id}
                        className={`flex items-center gap-2 ${shot.is_archived ? "opacity-45" : ""}`}
                      >
                        <button
                          type="button"
                          className={`flex-1 py-1 text-left text-xs ${
                            selection.shotId === shot.id
                              ? "text-orange-300"
                              : "text-zinc-500"
                          }`}
                          onClick={() =>
                            setSelection({
                              episodeId: episode.id,
                              sceneId: scene.id,
                              shotId: shot.id,
                            })
                          }
                          onDoubleClick={() =>
                            rename("shots", shot.id, shot.name)
                          }
                        >
                          {shot.shot_code}｜{shot.name}
                        </button>
                        <SmallButton
                          label={`${shot.is_archived ? "恢复" : "归档"} ${shot.shot_code}`}
                          onClick={() =>
                            void setItemArchived(
                              "shots",
                              shot.id,
                              !shot.is_archived,
                            )
                          }
                        />
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
      <p className="border-t border-white/10 px-4 py-3 text-xs text-zinc-500">
        提示：双击名称可以重命名。归档不会删除本地文件。
      </p>
    </section>
  );
}
