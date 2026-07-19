import { AlertTriangle, ArrowRight, Inbox, RefreshCw } from "lucide-react";

interface StatePanelProps {
  kind: "loading" | "empty" | "error";
  title?: string;
  message?: string;
  onRetry?: () => void;
  actionLabel?: string;
  onAction?: () => void;
}

export function StatePanel({
  kind,
  title,
  message,
  onRetry,
  actionLabel,
  onAction,
}: StatePanelProps) {
  if (kind === "loading") {
    return (
      <div className="state-panel state-panel--loading" aria-busy="true" aria-label="Loading data">
        <div className="skeleton skeleton--title" />
        <div className="skeleton" />
        <div className="skeleton skeleton--short" />
      </div>
    );
  }

  const isError = kind === "error";
  const Icon = isError ? AlertTriangle : Inbox;
  return (
    <div className={`state-panel state-panel--${kind}`} role={isError ? "alert" : undefined}>
      <span className="state-panel__icon" aria-hidden="true">
        <Icon size={22} />
      </span>
      <div>
        <h2>{title ?? (isError ? "This view could not be loaded" : "Nothing here yet")}</h2>
        <p>
          {message ??
            (isError
              ? "The API did not return this data. Your existing work has not been changed."
              : "Create the first item to get started.")}
        </p>
      </div>
      {onRetry ? (
        <button className="button button--secondary" type="button" onClick={onRetry}>
          <RefreshCw size={16} aria-hidden="true" /> Retry
        </button>
      ) : null}
      {actionLabel && onAction ? (
        <button className="button button--primary" type="button" onClick={onAction}>
          {actionLabel} <ArrowRight size={16} aria-hidden="true" />
        </button>
      ) : null}
    </div>
  );
}
