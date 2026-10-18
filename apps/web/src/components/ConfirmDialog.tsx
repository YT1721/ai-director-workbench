import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
} from "react";

type ConfirmTone = "normal" | "cost" | "danger";

export type ConfirmOptions = {
  title: string;
  message?: string;
  details?: string[];
  confirmLabel?: string;
  cancelLabel?: string;
  tone?: ConfirmTone;
};

type PendingConfirm = {
  options: ConfirmOptions;
  resolve: (confirmed: boolean) => void;
};

const ConfirmContext = createContext<
  ((options: ConfirmOptions) => Promise<boolean>) | null
>(null);

export function ConfirmProvider({ children }: { children: React.ReactNode }) {
  const [pending, setPending] = useState<PendingConfirm | null>(null);

  const confirm = useCallback((options: ConfirmOptions) => {
    return new Promise<boolean>((resolve) => {
      setPending({ options, resolve });
    });
  }, []);

  const close = useCallback((confirmed: boolean) => {
    setPending((current) => {
      current?.resolve(confirmed);
      return null;
    });
  }, []);

  const value = useMemo(() => confirm, [confirm]);
  const tone = pending?.options.tone ?? "normal";
  const toneClass = {
    normal: "border-orange-400/35 bg-[#12181e]",
    cost: "border-amber-300/38 bg-[#191713]",
    danger: "border-red-300/38 bg-[#1a1416]",
  }[tone];
  const confirmClass =
    tone === "danger"
      ? "border-red-300/45 bg-red-400/16 text-red-100 hover:bg-red-400/22"
      : tone === "cost"
        ? "border-amber-300/45 bg-amber-300/18 text-amber-50 hover:bg-amber-300/24"
        : "border-orange-300/45 bg-orange-400/16 text-orange-100 hover:bg-orange-400/22";
  const eyebrow =
    tone === "danger"
      ? "危险操作，需要你确认"
      : tone === "cost"
        ? "可能产生费用，需要你确认"
        : "继续前，请确认";

  return (
    <ConfirmContext.Provider value={value}>
      {children}
      {pending ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/74 px-6 backdrop-blur-md">
          <section
            aria-modal="true"
            className={`w-full max-w-2xl border p-7 shadow-2xl shadow-black/50 ${toneClass}`}
            role="dialog"
          >
            <p className="text-xs font-semibold tracking-[0.18em] text-orange-200">
              {eyebrow}
            </p>
            <h2 className="mt-3 text-2xl font-semibold leading-tight text-zinc-50">
              {pending.options.title}
            </h2>
            {pending.options.message ? (
              <p className="mt-4 whitespace-pre-wrap text-sm leading-7 text-zinc-300">
                {pending.options.message}
              </p>
            ) : null}
            {pending.options.details?.length ? (
              <div className="mt-5 space-y-2 border border-white/10 bg-black/18 p-4">
                {pending.options.details.map((item) => (
                  <p key={item} className="text-sm leading-6 text-zinc-300">
                    <span className="mr-2 text-orange-300">·</span>
                    {item}
                  </p>
                ))}
              </div>
            ) : null}
            <p className="mt-5 border border-white/10 bg-white/[0.03] px-4 py-3 text-xs leading-5 text-zinc-400">
              系统不会自动重复执行。取消后可以继续检查页面内容，确认后才会进入本次操作。
            </p>
            <div className="mt-6 flex justify-end gap-3">
              <button
                className="min-w-28 border border-white/15 px-4 py-2.5 text-sm font-semibold text-zinc-300 transition hover:bg-white/5"
                onClick={() => close(false)}
                type="button"
              >
                {pending.options.cancelLabel ?? "取消"}
              </button>
              <button
                className={`min-w-32 border px-4 py-2.5 text-sm font-extrabold transition ${confirmClass}`}
                onClick={() => close(true)}
                type="button"
              >
                {pending.options.confirmLabel ?? "确认执行"}
              </button>
            </div>
          </section>
        </div>
      ) : null}
    </ConfirmContext.Provider>
  );
}

export function useConfirmAction() {
  const confirm = useContext(ConfirmContext);
  if (!confirm) {
    throw new Error("useConfirmAction must be used inside ConfirmProvider");
  }
  return confirm;
}
