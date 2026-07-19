import { Component, type ErrorInfo, type ReactNode } from "react";
import { AlertTriangle } from "lucide-react";

interface State {
  failed: boolean;
}

export class AppErrorBoundary extends Component<{ children: ReactNode }, State> {
  state: State = { failed: false };

  static getDerivedStateFromError(): State {
    return { failed: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    if (import.meta.env.DEV) {
      console.error("Dataset Foundry view failed", error, info.componentStack);
    }
  }

  render() {
    if (!this.state.failed) return this.props.children;
    return (
      <main className="fatal-state" role="alert">
        <AlertTriangle size={30} aria-hidden="true" />
        <h1>The workbench could not finish loading</h1>
        <p>Your data has not been changed. Reload the page to open a fresh session.</p>
        <button className="button button--primary" type="button" onClick={() => window.location.reload()}>
          Reload workbench
        </button>
      </main>
    );
  }
}
