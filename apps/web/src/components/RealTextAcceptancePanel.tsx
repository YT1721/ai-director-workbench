import { CheckCircle2, Circle, Sparkles } from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { fetchRealTextAcceptance } from "../services/api";
import type { RealTextAcceptance } from "../types/workflows";
import { humanizeCopy } from "../utils/humanCopy";

type RealTextAcceptancePanelProps = {
  projectId?: string | null;
};

function statusClass(status: string) {
  if (status === "done")
    return "border-emerald-400/30 bg-emerald-400/7 text-emerald-100";
  if (status === "current")
    return "border-orange-400/45 bg-orange-400/10 text-orange-100";
  return "border-white/10 bg-black/12 text-zinc-500";
}

function statusIcon(status: string) {
  if (status === "done") return <CheckCircle2 size={15} />;
  if (status === "current") return <Sparkles size={15} />;
  return <Circle size={15} />;
}

export function RealTextAcceptancePanel({
  projectId,
}: RealTextAcceptancePanelProps) {
  const [data, setData] = useState<RealTextAcceptance | null>(null);

  useEffect(() => {
    if (!projectId) {
      setData(null);
      return;
    }
    void fetchRealTextAcceptance(projectId)
      .then(setData)
      .catch(() => setData(null));
  }, [projectId]);

  if (!projectId || !data) return null;

  return (
    <section className="mt-5 border border-emerald-400/25 bg-emerald-400/5 p-5">
      <div className="flex items-start justify-between gap-5">
        <div>
          <p className="text-xs tracking-[0.18em] text-emerald-300">
            真实文本跑通验收
          </p>
          <h2 className="mt-2 text-xl font-semibold text-zinc-100">
            {data.ready
              ? "文本主链已有真实 AI 证据"
              : `下一步：${data.current_label}`}
          </h2>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-zinc-400">
            {data.summary} 这里只读取已保存的真实 AI
            运行记录，不会调用模型、不产生费用。
          </p>
          <p className="mt-2 max-w-3xl text-xs leading-5 text-emerald-100/80">
            每条真实结果都会显示三类证据：真实模型结果、完整系统文件、调用与费用线索。没有这些证据，就不算正式跑通。
          </p>
        </div>
        <Link
          className="shrink-0 border border-emerald-300/45 px-4 py-2 text-sm text-emerald-100 transition hover:bg-emerald-300/10"
          to={data.primary_action_href}
        >
          {data.primary_action_label}
        </Link>
      </div>
      <div className="mt-4 grid grid-cols-3 gap-3">
        {data.items.map((item) => (
          <article
            className={`min-h-32 border p-3 text-xs ${statusClass(item.status)}`}
            key={item.key}
          >
            <p className="flex items-center gap-2 font-semibold">
              {statusIcon(item.status)}
              {item.label}
            </p>
            <p className="mt-2 leading-5 text-zinc-400">
              {humanizeCopy(item.evidence)}
            </p>
            {item.provider ? (
              <p className="mt-2 leading-5 text-zinc-500">
                {humanizeCopy(item.provider)}｜{item.model_name}｜已生成
              </p>
            ) : (
              <Link
                className="mt-3 inline-block text-orange-200 underline decoration-orange-400/60 underline-offset-4"
                to={item.action_href}
              >
                {item.action_label}
              </Link>
            )}
          </article>
        ))}
      </div>
    </section>
  );
}
