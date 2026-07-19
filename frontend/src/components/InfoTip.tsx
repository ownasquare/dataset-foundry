import { CircleHelp } from "lucide-react";
import type { ReactNode } from "react";

export function InfoTip({ label, children }: { label: string; children: ReactNode }) {
  return (
    <details
      className="info-tip"
      onKeyDown={(event) => {
        if (event.key !== "Escape") return;
        event.currentTarget.open = false;
        event.currentTarget.querySelector("summary")?.focus();
      }}
    >
      <summary aria-label={`About ${label.toLowerCase()}`} tabIndex={0}>
        <CircleHelp size={15} aria-hidden="true" />
      </summary>
      <div className="info-tip__content" role="note">
        <strong>{label}</strong>
        <span>{children}</span>
      </div>
    </details>
  );
}
