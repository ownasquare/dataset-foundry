import type { LucideIcon } from "lucide-react";

interface MetricCardProps {
  label: string;
  value: string;
  detail: string;
  icon: LucideIcon;
  tone?: "default" | "positive" | "attention";
}

export function MetricCard({
  label,
  value,
  detail,
  icon: Icon,
  tone = "default",
}: MetricCardProps) {
  return (
    <article className={`metric-card metric-card--${tone}`}>
      <div className="metric-card__topline">
        <span>{label}</span>
        <span className="metric-card__icon" aria-hidden="true">
          <Icon size={17} />
        </span>
      </div>
      <strong>{value}</strong>
      <p>{detail}</p>
    </article>
  );
}
