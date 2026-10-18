import type { ReactNode, SyntheticEvent } from "react";
import { Link } from "react-router-dom";

type GuidePrimaryButtonProps = {
  children: ReactNode;
  disabled?: boolean;
  href?: string;
  loading?: boolean;
  loadingLabel?: string;
  onClick?: () => void;
  pulse?: boolean;
  type?: "button" | "submit";
};

type GuideSecondaryActionProps = {
  children: ReactNode;
  disabled?: boolean;
  href?: string;
  onClick?: () => void;
  type?: "button" | "submit";
};

export function GuidePrimaryButton({
  children,
  disabled = false,
  href,
  loading = false,
  loadingLabel = "正在处理…",
  onClick,
  pulse = true,
  type = "button",
}: GuidePrimaryButtonProps) {
  const isDisabled = disabled || loading;
  const className = `guide-primary-button ${pulse && !isDisabled ? "guide-primary-button--pulse" : ""} ${loading ? "guide-primary-button--loading" : ""}`;
  const content = loading ? (
    <>
      <span className="guide-spinner" aria-hidden="true" />
      <span>{loadingLabel}</span>
    </>
  ) : (
    children
  );
  if (href && !isDisabled) {
    return (
      <Link className={className} to={href}>
        {content}
      </Link>
    );
  }
  return (
    <button
      aria-busy={loading || undefined}
      className={className}
      disabled={isDisabled}
      onClick={onClick}
      type={type}
    >
      {content}
    </button>
  );
}

export function GuideSecondaryAction({
  children,
  disabled = false,
  href,
  onClick,
  type = "button",
}: GuideSecondaryActionProps) {
  const className = "guide-secondary-action";
  if (href && !disabled) {
    return (
      <Link className={className} to={href}>
        {children}
      </Link>
    );
  }
  return (
    <button
      className={className}
      disabled={disabled}
      onClick={onClick}
      type={type}
    >
      {children}
    </button>
  );
}

export function GuideActionCard({
  eyebrow = "当前主任务",
  title,
  description,
  children,
  progressLabel,
  tone = "current",
}: {
  eyebrow?: string;
  title: string;
  description: string;
  children?: ReactNode;
  progressLabel?: string;
  tone?: "current" | "done" | "blocked" | "info";
}) {
  const toneClass = {
    current: "guide-action-card--current",
    done: "guide-action-card--done",
    blocked: "guide-action-card--blocked",
    info: "guide-action-card--info",
  }[tone];
  return (
    <section className={`guide-action-card ${toneClass}`}>
      <p className="guide-eyebrow">{eyebrow}</p>
      <h2 className="guide-title">{title}</h2>
      <p className="guide-description">{description}</p>
      {children ? (
        <div className="guide-action-card__actions">{children}</div>
      ) : null}
      {progressLabel ? <GuideProgress label={progressLabel} /> : null}
    </section>
  );
}

export function GuideProgress({ label }: { label: string }) {
  return (
    <div className="guide-progress" role="status" aria-live="polite">
      <div className="guide-progress__label">
        <span className="guide-spinner" aria-hidden="true" />
        <span>{label}</span>
      </div>
      <div className="guide-progress__bar" aria-hidden="true">
        <span />
      </div>
      <p className="guide-progress__hint">
        请稍等，完成后页面会自动刷新结果，不需要重复点击。
      </p>
    </div>
  );
}

export function GuideProgressToast({ label }: { label: string }) {
  return (
    <div className="guide-progress-toast" role="status" aria-live="polite">
      <GuideProgress label={label} />
    </div>
  );
}

export function TechDetails({
  title = "更多设置（一般不用打开）",
  children,
  className = "",
  open,
  onToggle,
}: {
  title?: string;
  children: ReactNode;
  className?: string;
  open?: boolean;
  onToggle?: (event: SyntheticEvent<HTMLDetailsElement>) => void;
}) {
  return (
    <details
      className={`tech-details ${className}`}
      onToggle={onToggle}
      open={open}
    >
      <summary>{title}</summary>
      <div className="tech-details__body">{children}</div>
    </details>
  );
}

export function GuideMiniSteps({
  title = "小步骤",
  items,
  currentIndex = 0,
}: {
  title?: string;
  items: string[];
  currentIndex?: number;
}) {
  return (
    <section className="guide-mini-steps">
      <p className="guide-mini-steps__title">{title}</p>
      <div className="guide-mini-steps__list">
        {items.map((item, index) => (
          <span
            className={`guide-mini-step ${
              index < currentIndex
                ? "guide-mini-step--done"
                : index === currentIndex
                  ? "guide-mini-step--current"
                  : ""
            }`}
            key={item}
          >
            {index + 1}. {item}
          </span>
        ))}
      </div>
    </section>
  );
}

type DirectorStageStatus = "done" | "current" | "pending" | "blocked";

export type DirectorStageItem = {
  title: string;
  detail: string;
  status: DirectorStageStatus;
};

export function DirectorWorkbenchFrame({
  main,
  aside,
}: {
  main: ReactNode;
  aside: ReactNode;
}) {
  return (
    <div className="director-workbench-frame">
      <div className="director-workbench-frame__main">{main}</div>
      <aside className="director-workbench-frame__aside">{aside}</aside>
    </div>
  );
}

export function DirectorStageTimeline({
  title = "创作进度",
  items,
}: {
  title?: string;
  items: DirectorStageItem[];
}) {
  return (
    <section className="director-timeline" aria-label={title}>
      <p className="director-timeline__title">{title}</p>
      <div className="director-timeline__list">
        {items.map((item, index) => (
          <div
            className={`director-timeline__item director-timeline__item--${item.status}`}
            key={`${item.title}-${index}`}
          >
            <span className="director-timeline__dot" aria-hidden="true" />
            <div>
              <p className="director-timeline__item-title">{item.title}</p>
              <p className="director-timeline__item-detail">{item.detail}</p>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

export function DirectorStatusPanel({
  eyebrow = "当前状态",
  title,
  description,
  items,
}: {
  eyebrow?: string;
  title: string;
  description: string;
  items: DirectorStageItem[];
}) {
  return (
    <section className="director-status-panel">
      <p className="director-status-panel__eyebrow">{eyebrow}</p>
      <h2 className="director-status-panel__title">{title}</h2>
      <p className="director-status-panel__description">{description}</p>
      <div className="director-status-panel__items">
        {items.map((item, index) => (
          <div
            className={`director-status-pill director-status-pill--${item.status}`}
            key={`${item.title}-${index}`}
          >
            <span>{item.title}</span>
            <small>{item.detail}</small>
          </div>
        ))}
      </div>
    </section>
  );
}
