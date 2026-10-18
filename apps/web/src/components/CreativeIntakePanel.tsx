import { FileText, ImageUp, Rocket, Upload } from "lucide-react";
import { useRef, useState } from "react";

import { useWorkbenchStore } from "../stores/useWorkbenchStore";
import type { IntakeDraft } from "../types/workbench";

type CreativeIntakePanelProps = {
  mode: "create" | "attach";
  onComplete?: () => void;
};

const inputModes = [
  {
    key: "script_text",
    title: "粘贴剧本 / 创意文本",
    helper: "最适合第一步。系统会保存为本地 TXT，随后进入 AI 导演分析。",
    icon: FileText,
  },
  {
    key: "script_file",
    title: "上传剧本 / 分镜文档",
    helper:
      "支持 TXT / MD / DOCX / XLSX 本地解析；PDF 会先保存，后续再开放解析。",
    icon: Upload,
  },
  {
    key: "storyboard_table_image",
    title: "上传分镜表图片",
    helper: "支持 PNG / JPG / JPEG / WEBP。图片会先保存，不做视觉识别。",
    icon: ImageUp,
  },
] as const;

type InputMode = (typeof inputModes)[number]["key"];

function fileAccept(mode: InputMode) {
  return mode === "storyboard_table_image"
    ? ".png,.jpg,.jpeg,.webp"
    : ".txt,.md,.pdf,.docx,.xlsx";
}

export function CreativeIntakePanel({
  mode,
  onComplete,
}: CreativeIntakePanelProps) {
  const {
    activeProject,
    isBusy,
    error,
    clearError,
    startProjectFromIntake,
    attachIntakeAndStart,
  } = useWorkbenchStore();
  const [projectName, setProjectName] = useState("");
  const [description, setDescription] = useState("");
  const [inputMode, setInputMode] = useState<InputMode>("script_text");
  const [title, setTitle] = useState("第一份剧本资料");
  const [content, setContent] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const needsProjectName = mode === "create";
  const canSubmit =
    !isBusy &&
    (!needsProjectName || projectName.trim()) &&
    (inputMode === "script_text" ? content.trim() : file);

  const submit = async () => {
    if (!canSubmit) return;
    clearError();
    let intake: IntakeDraft;
    if (inputMode === "script_text") {
      intake = {
        kind: "text",
        category: "script_text",
        title: title.trim() || "第一份剧本资料",
        content,
      };
    } else {
      intake = {
        kind: "file",
        category:
          inputMode === "script_file" ? "script" : "storyboard_table_image",
        file: file!,
      };
    }
    if (mode === "create") {
      await startProjectFromIntake(projectName, description, intake);
    } else {
      await attachIntakeAndStart(intake);
    }
    setContent("");
    setFile(null);
    if (inputRef.current) inputRef.current.value = "";
    onComplete?.();
  };

  return (
    <section
      id="source-intake"
      className="border border-orange-400/30 bg-[#151b21]/95 p-6 shadow-xl shadow-black/10"
    >
      <div className="flex items-start justify-between gap-5">
        <div>
          <p className="text-xs tracking-[0.18em] text-orange-400">第一步</p>
          <h2 className="mt-2 text-2xl font-semibold text-zinc-100">
            上传剧本 / 分镜表开始
          </h2>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-zinc-400">
            你只需要先给系统一份资料。系统会在本地保存资料，自动创建项目结构；下一步用
            AI 执行 V7｜开始｜EP01 导演分析。
          </p>
        </div>
        <span className="rounded-full border border-emerald-400/30 px-3 py-1 text-xs text-emerald-300">
          AI 分析优先｜逐次确认
        </span>
      </div>

      {needsProjectName ? (
        <div className="mt-5 grid grid-cols-[1fr_1.2fr] gap-4">
          <label className="text-xs text-zinc-400">
            项目名称
            <input
              value={projectName}
              onChange={(event) => setProjectName(event.target.value)}
              placeholder="例如：测试短片"
              className="mt-2 w-full border border-white/15 bg-black/15 px-3 py-2.5 text-sm text-white outline-none transition focus:border-orange-400/70"
            />
          </label>
          <label className="text-xs text-zinc-400">
            项目说明（可选）
            <input
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              placeholder="题材、目标画幅、当前阶段"
              className="mt-2 w-full border border-white/15 bg-black/15 px-3 py-2.5 text-sm text-white outline-none transition focus:border-orange-400/70"
            />
          </label>
        </div>
      ) : (
        <p className="mt-5 text-sm text-zinc-400">
          当前项目：
          <span className="text-zinc-100">
            {activeProject?.project_code}｜{activeProject?.name}
          </span>
        </p>
      )}

      <div className="mt-5 grid grid-cols-3 gap-3">
        {inputModes.map(({ key, title: modeTitle, helper, icon: Icon }) => (
          <button
            key={key}
            type="button"
            onClick={() => {
              setInputMode(key);
              setFile(null);
              if (inputRef.current) inputRef.current.value = "";
            }}
            className={`min-h-28 border p-4 text-left transition ${
              inputMode === key
                ? "border-orange-400 bg-orange-400/10 text-orange-200"
                : "border-white/15 bg-black/10 text-zinc-300 hover:border-orange-400/50"
            }`}
          >
            <Icon size={19} className="text-orange-300" />
            <p className="mt-3 text-sm font-semibold">{modeTitle}</p>
            <p className="mt-2 text-xs leading-5 text-zinc-500">{helper}</p>
          </button>
        ))}
      </div>

      {inputMode === "script_text" ? (
        <div className="mt-5 grid grid-cols-[260px_minmax(0,1fr)] gap-4">
          <label className="text-xs text-zinc-400">
            资料标题
            <input
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              className="mt-2 w-full border border-white/15 bg-black/15 px-3 py-2.5 text-sm text-white outline-none"
            />
          </label>
          <label className="text-xs text-zinc-400">
            粘贴剧本 / 分镜文本
            <textarea
              value={content}
              onChange={(event) => setContent(event.target.value)}
              placeholder="把剧本、小说片段、分镜表文本或创意说明粘贴到这里。"
              className="mt-2 min-h-36 w-full resize-y border border-white/15 bg-black/15 px-3 py-3 text-sm text-white outline-none"
            />
          </label>
        </div>
      ) : (
        <label className="mt-5 block text-xs text-zinc-400">
          选择本地文件
          <input
            ref={inputRef}
            type="file"
            accept={fileAccept(inputMode)}
            onChange={(event) => setFile(event.target.files?.[0] ?? null)}
            className="mt-2 w-full border border-white/15 bg-black/15 px-3 py-2 text-sm text-zinc-400 file:mr-3 file:border-0 file:bg-orange-500 file:px-3 file:py-1 file:text-xs file:text-black"
          />
        </label>
      )}

      {error ? <p className="mt-4 text-sm text-red-300">{error}</p> : null}

      <button
        type="button"
        disabled={!canSubmit}
        onClick={submit}
        className="mt-5 flex w-full items-center justify-center gap-2 bg-orange-500 px-4 py-3 text-sm font-semibold text-black transition hover:bg-orange-400 disabled:opacity-45"
      >
        <Rocket size={17} />
        {mode === "create" ? "创建项目并保存资料" : "保存资料，下一步 AI 分析"}
      </button>
    </section>
  );
}
