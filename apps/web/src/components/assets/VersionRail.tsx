import { useEffect, useState } from "react";
import {
  Check,
  Download,
  FolderOpen,
  LockKeyhole,
  RotateCcw,
  UnlockKeyhole,
  X,
} from "lucide-react";

import {
  assetImageUrl,
  downloadLocalAsset,
  revealInFolder,
} from "../../services/api";
import type { AssetImageTargetKind, AssetVersion } from "../../types/assets";

const statusText: Record<AssetVersion["status"], string> = {
  draft: "草稿",
  confirmed_current: "当前确认版",
  confirmed_history: "历史确认版",
  locked: "已锁定",
  rejected: "已拒绝",
};

type VersionRailProps = {
  versions: AssetVersion[];
  kind: AssetImageTargetKind;
  assetName?: string;
  projectId?: string;
  onTransition: (
    kind: AssetImageTargetKind,
    versionId: string,
    action: "confirm" | "lock" | "unlock" | "rollback",
  ) => void;
};

function versionLabel(version: AssetVersion) {
  return `V${String(version.version_number).padStart(3, "0")}`;
}

function relativePathFromAssetUrl(assetUrl: string): string {
  const match = assetUrl.match(/\/local-assets\/[^/]+\/(.+)$/);
  return match ? decodeURIComponent(match[1]) : "";
}

export function VersionRail({
  versions,
  kind,
  assetName,
  projectId,
  onTransition,
}: VersionRailProps) {
  const [preview, setPreview] = useState<AssetVersion | null>(null);
  const [downloadHint, setDownloadHint] = useState("");

  useEffect(() => {
    if (!preview) return;
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") setPreview(null);
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [preview]);

  async function saveVersionToLocal(version: AssetVersion) {
    const filename = `${assetName || "资产图"}_${versionLabel(version)}.png`;
    try {
      const result = await downloadLocalAsset(version.asset_url, filename);
      setDownloadHint(
        result.method === "save_picker"
          ? `已保存到你选择的位置：${result.filename}。项目文件夹里也保留一份。`
          : `已交给浏览器下载：${result.filename}。项目文件夹里也保留一份。`,
      );
    } catch (error) {
      setDownloadHint(
        error instanceof Error ? error.message : "下载失败，请稍后再试。",
      );
    }
  }

  async function revealVersionInFolder(version: AssetVersion) {
    if (!projectId) return;
    try {
      const result = await revealInFolder(
        projectId,
        relativePathFromAssetUrl(version.asset_url),
      );
      setDownloadHint(`已在访达中定位：${result.path}`);
    } catch (error) {
      setDownloadHint(
        error instanceof Error ? error.message : "打开文件夹失败。",
      );
    }
  }

  if (versions.length === 0) {
    return <p className="mt-3 text-xs text-zinc-500">还没有资产版本。</p>;
  }

  return (
    <>
      <div className="mt-3 grid grid-cols-3 gap-3">
        {versions.map((version) => (
          <article
            key={version.id}
            className="min-w-0 border border-white/10 bg-black/12"
          >
            <button
              type="button"
              onClick={() => setPreview(version)}
              className="block w-full cursor-zoom-in border-b border-white/10"
              title="点击放大预览"
            >
              <img
                src={assetImageUrl(version.asset_url)}
                alt={`资产版本 ${versionLabel(version)}`}
                className="aspect-video w-full object-cover"
              />
            </button>
            <div className="p-3">
              <div className="flex items-center justify-between gap-3">
                <p className="text-xs font-medium text-orange-300">
                  {versionLabel(version)}
                </p>
                <p className="text-[11px] text-zinc-500">
                  {statusText[version.status]}
                </p>
              </div>
              <div className="mt-3 flex flex-wrap gap-2">
                {version.status !== "locked" &&
                  version.status !== "confirmed_current" && (
                    <button
                      type="button"
                      onClick={() => onTransition(kind, version.id, "confirm")}
                      className="flex items-center gap-1 border border-white/15 px-2 py-1 text-[11px] text-zinc-300 hover:border-orange-400/60"
                    >
                      <Check size={12} /> 确认为当前
                    </button>
                  )}
                {version.status === "confirmed_current" && (
                  <button
                    type="button"
                    onClick={() => onTransition(kind, version.id, "lock")}
                    className="flex items-center gap-1 border border-white/15 px-2 py-1 text-[11px] text-zinc-300 hover:border-orange-400/60"
                  >
                    <LockKeyhole size={12} /> 锁定
                  </button>
                )}
                {version.status === "locked" && (
                  <button
                    type="button"
                    onClick={() => onTransition(kind, version.id, "unlock")}
                    className="flex items-center gap-1 border border-white/15 px-2 py-1 text-[11px] text-zinc-300 hover:border-orange-400/60"
                  >
                    <UnlockKeyhole size={12} /> 解锁
                  </button>
                )}
                {version.status === "confirmed_history" && (
                  <button
                    type="button"
                    onClick={() => onTransition(kind, version.id, "rollback")}
                    className="flex items-center gap-1 border border-white/15 px-2 py-1 text-[11px] text-zinc-300 hover:border-orange-400/60"
                  >
                    <RotateCcw size={12} /> 回滚到此版
                  </button>
                )}
                <button
                  type="button"
                  onClick={() => void saveVersionToLocal(version)}
                  className="flex items-center gap-1 border border-white/15 px-2 py-1 text-[11px] text-zinc-300 hover:border-emerald-400/60"
                >
                  <Download size={12} /> 存到本地
                </button>
              </div>
            </div>
          </article>
        ))}
      </div>
      {downloadHint ? (
        <p className="mt-2 text-xs text-emerald-200/80">{downloadHint}</p>
      ) : null}
      {preview ? (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/85 px-8 py-8 backdrop-blur-sm"
          role="dialog"
          aria-modal="true"
          aria-label={`${assetName || "资产图"} ${versionLabel(preview)} 大图预览`}
          onClick={() => setPreview(null)}
        >
          <div
            className="flex max-h-[92vh] w-full max-w-6xl flex-col border border-orange-400/40 bg-[#11171c] shadow-2xl shadow-black/60"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="flex items-center justify-between border-b border-white/10 px-5 py-4">
              <div>
                <p className="text-xs tracking-[0.18em] text-orange-300">
                  资产图预览
                </p>
                <h2 className="mt-1 text-xl font-semibold text-zinc-100">
                  {assetName || "资产图"}｜{versionLabel(preview)}｜
                  {statusText[preview.status]}
                </h2>
              </div>
              <div className="flex items-center gap-2">
                {projectId ? (
                  <button
                    className="inline-flex items-center gap-2 border border-white/12 bg-white/[0.03] px-3 py-2 text-xs text-zinc-400 transition hover:border-orange-400/35 hover:bg-orange-400/7 hover:text-orange-200"
                    type="button"
                    onClick={() => void revealVersionInFolder(preview)}
                  >
                    <FolderOpen size={15} />
                    在文件夹中显示
                  </button>
                ) : null}
                <button
                  className="inline-flex items-center gap-2 border border-white/12 bg-white/[0.03] px-3 py-2 text-xs text-zinc-400 transition hover:border-orange-400/35 hover:bg-orange-400/7 hover:text-orange-200"
                  type="button"
                  onClick={() => void saveVersionToLocal(preview)}
                >
                  <Download size={15} />
                  存到本地
                </button>
                <button
                  className="inline-flex items-center gap-2 border border-white/12 bg-white/[0.03] px-3 py-2 text-xs text-zinc-400 transition hover:border-orange-400/35 hover:bg-orange-400/7 hover:text-orange-200"
                  type="button"
                  onClick={() => setPreview(null)}
                >
                  <X size={15} />
                  关闭
                </button>
              </div>
            </div>
            <div className="overflow-auto bg-[#0b0f12] p-4">
              <img
                src={assetImageUrl(preview.asset_url)}
                alt={`${assetName || "资产图"} ${versionLabel(preview)} 大图`}
                className="mx-auto max-h-[76vh] w-auto max-w-full object-contain"
              />
            </div>
          </div>
        </div>
      ) : null}
    </>
  );
}
