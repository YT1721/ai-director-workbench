import { Construction } from "lucide-react";

import { workbenchPageClass } from "../styles/layout";

type PlaceholderPageProps = {
  title: string;
};

export function PlaceholderPage({ title }: PlaceholderPageProps) {
  return (
    <div className={workbenchPageClass}>
      <p className="text-xs tracking-[0.18em] text-orange-400">UCODE-9</p>
      <h1 className="mt-2 text-4xl font-semibold tracking-wide text-zinc-100">
        {title}
      </h1>
      <section className="mt-7 border border-white/15 bg-[#151b21]/85 p-7">
        <Construction size={32} className="text-orange-400" />
        <h2 className="mt-5 text-xl font-semibold text-zinc-100">
          当前页面将在后续里程碑开放
        </h2>
        <p className="mt-3 max-w-2xl text-sm leading-6 text-zinc-400">
          当前已开放项目、素材、黑白故事板、分镜提示词、批量视频、真实文本分析配置和受控单镜测试。
          其余能力会在后续里程碑按顺序开放。
        </p>
      </section>
    </div>
  );
}
