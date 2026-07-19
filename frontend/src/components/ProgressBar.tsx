interface ProgressBarProps {
  value: number;
  max?: number;
  label: string;
  showValue?: boolean;
  tone?: "accent" | "success" | "warning";
}

export function ProgressBar({
  value,
  max = 100,
  label,
  showValue = true,
  tone = "accent",
}: ProgressBarProps) {
  const safeMax = max > 0 ? max : 1;
  const percent = Math.max(0, Math.min(100, (value / safeMax) * 100));
  return (
    <div className="progress-block">
      <div className="progress-block__label">
        <span>{label}</span>
        {showValue ? <strong>{Math.round(percent)}%</strong> : null}
      </div>
      <div
        className="progress-track"
        role="progressbar"
        aria-label={label}
        aria-valuemin={0}
        aria-valuemax={safeMax}
        aria-valuenow={Math.min(value, safeMax)}
      >
        <span
          className={`progress-track__fill progress-track__fill--${tone}`}
          style={{ width: `${percent}%` }}
        />
      </div>
    </div>
  );
}
