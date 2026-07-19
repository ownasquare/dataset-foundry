import { ChevronDown } from "lucide-react";
import type { ReactNode } from "react";

export function Disclosure({ summary, children }: { summary: string; children: ReactNode }) {
  return (
    <details className="disclosure">
      <summary>
        <span>{summary}</span>
        <ChevronDown size={16} aria-hidden="true" />
      </summary>
      <div className="disclosure__body">{children}</div>
    </details>
  );
}
