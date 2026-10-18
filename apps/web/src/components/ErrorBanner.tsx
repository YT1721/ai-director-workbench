import { AlertTriangle, X } from "lucide-react";

import { humanizeCopy } from "../utils/humanCopy";

type ErrorBannerProps = {
  message: string | null;
  onClose: () => void;
};

export function ErrorBanner({ message, onClose }: ErrorBannerProps) {
  if (!message) return null;
  return (
    <div className="mb-5 flex items-start justify-between gap-4 border border-amber-400/35 bg-amber-400/8 px-4 py-3 text-sm text-amber-100">
      <div className="flex items-start gap-3">
        <AlertTriangle size={18} className="mt-0.5 shrink-0 text-amber-300" />
        <p>{humanizeCopy(message)}</p>
      </div>
      <button type="button" aria-label="关闭错误提示" onClick={onClose}>
        <X size={16} />
      </button>
    </div>
  );
}
