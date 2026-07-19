import { AlertCircle, Check, CircleDashed, Clock3, LoaderCircle, X } from "lucide-react";

type BadgeTone = "success" | "warning" | "danger" | "info" | "neutral";

const STATUS_PRESENTATION: Record<string, { label: string; tone: BadgeTone; icon: typeof Check }> = {
  accepted: { label: "Accepted", tone: "success", icon: Check },
  ready: { label: "Ready", tone: "success", icon: Check },
  completed: { label: "Complete", tone: "success", icon: Check },
  completed_with_review: { label: "Review ready", tone: "warning", icon: AlertCircle },
  needs_review: { label: "Needs review", tone: "warning", icon: AlertCircle },
  setup_needed: { label: "Setup needed", tone: "warning", icon: AlertCircle },
  running: { label: "Generating", tone: "info", icon: LoaderCircle },
  building: { label: "Building", tone: "info", icon: LoaderCircle },
  queued: { label: "Queued", tone: "neutral", icon: Clock3 },
  rejected: { label: "Rejected", tone: "danger", icon: X },
  failed: { label: "Failed", tone: "danger", icon: AlertCircle },
  unavailable: { label: "Unavailable", tone: "danger", icon: AlertCircle },
  cancelled: { label: "Cancelled", tone: "neutral", icon: CircleDashed },
};

function humanize(value: string): string {
  return value
    .replaceAll("_", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

export function StatusBadge({ status, label }: { status: string; label?: string }) {
  const presentation = STATUS_PRESENTATION[status] ?? {
    label: humanize(status),
    tone: "neutral" as const,
    icon: CircleDashed,
  };
  const Icon = presentation.icon;
  return (
    <span className={`status-badge status-badge--${presentation.tone}`}>
      <Icon
        size={13}
        aria-hidden="true"
        className={status === "running" || status === "building" ? "spin" : undefined}
      />
      {label ?? presentation.label}
    </span>
  );
}
