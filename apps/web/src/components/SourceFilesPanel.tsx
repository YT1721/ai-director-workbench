import { FileImage, FileText, Upload } from "lucide-react";
import { useRef, useState } from "react";

import { useWorkbenchStore } from "../stores/useWorkbenchStore";

function formatSize(bytes: number) {
  return bytes < 1024 * 1024
    ? `${Math.max(1, Math.round(bytes / 1024))} KB`
    : `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

export function SourceFilesPanel() {
  const { activeProject, sourceFiles, uploadFile, isBusy } =
    useWorkbenchStore();
  const [category, setCategory] = useState<
    "script" | "storyboard_table" | "storyboard_table_image" | "reference"
  >("script");
  const [file, setFile] = useState<File | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  if (!activeProject) return null;

  return (
    <section className="min-w-0 overflow-hidden border border-white/15 bg-[#151b21]/90 p-5">
      <div className="flex items-center gap-2 text-orange-300">
        <Upload size={18} />
        <h2 className="font-semibold tracking-wide">上传本地素材</h2>
      </div>
      <p className="mt-2 text-xs leading-5 text-zinc-500">
        剧本 / 分镜文档：TXT / MD / PDF / DOCX /
        XLSX。参考素材支持图片、MP4/MOV/WEBM 视频和 MP3/WAV/M4A/AAC
        音频。单文件最多 25 MB。
      </p>
      <form
        className="mt-4 grid min-w-0 grid-cols-[150px_minmax(0,1fr)_auto] gap-3"
        onSubmit={async (event) => {
          event.preventDefault();
          if (!file) return;
          await uploadFile(category, file);
          setFile(null);
          if (inputRef.current) inputRef.current.value = "";
        }}
      >
        <select
          aria-label="素材类型"
          value={category}
          onChange={(event) =>
            setCategory(
              event.target.value as
                | "script"
                | "storyboard_table"
                | "storyboard_table_image"
                | "reference",
            )
          }
          className="border border-white/15 bg-[#11171c] px-3 py-2 text-sm text-zinc-200 outline-none"
        >
          <option value="script">剧本文件</option>
          <option value="storyboard_table">分镜表文档</option>
          <option value="storyboard_table_image">分镜表图片</option>
          <option value="reference">参考图片 / 视频 / 音频</option>
        </select>
        <input
          ref={inputRef}
          aria-label="选择素材文件"
          type="file"
          accept={
            category === "script" || category === "storyboard_table"
              ? ".txt,.md,.pdf,.docx,.xlsx"
              : category === "reference"
                ? ".png,.jpg,.jpeg,.webp,.mp4,.mov,.m4v,.webm,.mp3,.wav,.m4a,.aac"
                : ".png,.jpg,.jpeg,.webp"
          }
          onChange={(event) => setFile(event.target.files?.[0] ?? null)}
          className="w-full min-w-0 max-w-full border border-white/15 bg-black/10 px-3 py-2 text-xs text-zinc-400 file:mr-3 file:border-0 file:bg-orange-500 file:px-3 file:py-1 file:text-xs file:text-black"
        />
        <button
          disabled={!file || isBusy}
          type="submit"
          className="bg-orange-500 px-4 py-2 text-sm font-medium text-black disabled:opacity-45"
        >
          保存素材
        </button>
      </form>
      <div className="mt-5 space-y-2">
        {sourceFiles.length === 0 ? (
          <p className="text-sm text-zinc-500">还没有上传素材。</p>
        ) : (
          sourceFiles.map((item) => (
            <div
              key={item.id}
              className="flex items-center justify-between gap-3 border border-white/10 px-3 py-2.5 text-sm"
            >
              <div className="flex min-w-0 items-center gap-3">
                {item.category === "script" ||
                item.category === "script_text" ||
                item.category === "storyboard_table" ? (
                  <FileText size={17} className="shrink-0 text-orange-300" />
                ) : (
                  <FileImage size={17} className="shrink-0 text-orange-300" />
                )}
                <span className="truncate text-zinc-300">
                  {item.original_filename}
                </span>
              </div>
              <span className="shrink-0 text-xs text-zinc-500">
                {formatSize(item.size_bytes)}
              </span>
            </div>
          ))
        )}
      </div>
    </section>
  );
}
