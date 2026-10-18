import type { LucideIcon } from "lucide-react";

import type { UcodeAction } from "../data/actions";

type ActionCardProps = {
  action: UcodeAction;
  icon: LucideIcon;
  selected: boolean;
  statusLabel?: string;
  statusLevel?: "done" | "current" | "blocked" | "pending" | "optional";
  disabledReason?: string;
  onSelect: (action: UcodeAction) => void;
};

export function ActionCard({
  action,
  icon: Icon,
  selected,
  statusLabel,
  statusLevel,
  disabledReason,
  onSelect,
}: ActionCardProps) {
  const statusClass = {
    done: "border-emerald-400/40 text-emerald-300",
    current: "border-orange-400/50 text-orange-300",
    blocked: "border-red-400/45 text-red-300",
    pending: "border-white/15 text-zinc-500",
    optional: "border-sky-400/40 text-sky-300",
  }[statusLevel ?? "pending"];

  return (
    <button
      type="button"
      data-testid="ucode-action-card"
      data-action={action.code}
      aria-pressed={selected}
      onClick={() => onSelect(action)}
      className={`group min-h-[172px] border p-5 text-left transition duration-200 hover:-translate-y-0.5 hover:border-orange-400/60 hover:bg-orange-400/5 ${
        selected
          ? "border-orange-400/75 bg-orange-400/8 shadow-lg shadow-orange-950/20"
          : "border-white/15 bg-[#171d23]/80"
      }`}
    >
      <div className="flex items-start gap-5">
        <div className="grid size-14 shrink-0 place-items-center border border-orange-400/80 text-orange-400 transition group-hover:bg-orange-400/10">
          <Icon size={30} strokeWidth={1.65} />
        </div>
        <div>
          <h2 className="text-2xl font-semibold tracking-wide text-zinc-100">
            {action.label}
          </h2>
          <p className="mt-3 text-sm leading-6 text-zinc-400">
            {action.description}
          </p>
          {statusLabel ? (
            <p
              className={`mt-4 inline-flex border px-2 py-1 text-xs ${statusClass}`}
            >
              {statusLabel}
            </p>
          ) : null}
          {disabledReason ? (
            <p className="mt-3 text-xs leading-5 text-red-300">
              {disabledReason}
            </p>
          ) : null}
        </div>
      </div>
    </button>
  );
}
