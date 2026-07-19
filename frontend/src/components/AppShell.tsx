import {
  Archive,
  BarChart3,
  DatabaseZap,
  FileCheck2,
  FolderKanban,
  Menu,
  MoonStar,
  MoreHorizontal,
  PlaySquare,
  Settings,
  Sparkles,
  Sun,
  X,
} from "lucide-react";
import { useState, type ReactNode } from "react";

import { useSystemStatus } from "../api/queries";
import type { ViewKey } from "../api/types";
import { useTheme } from "./ThemeProvider";

interface AppShellProps {
  activeView: ViewKey;
  onNavigate: (view: ViewKey) => void;
  children: ReactNode;
  demoMode: boolean;
}

const PRIMARY_NAVIGATION = [
  { id: "overview", label: "Overview", icon: BarChart3 },
  { id: "generate", label: "Generate", icon: Sparkles },
  { id: "review", label: "Review", icon: FileCheck2 },
  { id: "exports", label: "Exports", icon: Archive },
] as const;

const SECONDARY_NAVIGATION = [
  { id: "projects", label: "Projects", icon: FolderKanban },
  { id: "runs", label: "Runs", icon: PlaySquare },
  { id: "settings", label: "Settings", icon: Settings },
] as const;

export function AppShell({ activeView, onNavigate, children, demoMode }: AppShellProps) {
  const [mobileOpen, setMobileOpen] = useState(false);
  const [moreOpen, setMoreOpen] = useState(false);
  const { theme, setTheme } = useTheme();
  const systemStatus = useSystemStatus();
  const serviceWarning = systemStatus.isError || systemStatus.data?.workerReady === false;

  const navigate = (view: ViewKey) => {
    onNavigate(view);
    setMobileOpen(false);
    if (!SECONDARY_NAVIGATION.some((item) => item.id === view)) setMoreOpen(false);
    window.requestAnimationFrame(() => {
      window.scrollTo({ top: 0, behavior: "auto" });
      document.querySelector<HTMLElement>("#main-content")?.focus({ preventScroll: true });
    });
  };

  const cycleTheme = () => {
    setTheme(theme === "light" ? "dark" : theme === "dark" ? "system" : "light");
  };

  const secondaryActive = SECONDARY_NAVIGATION.some((item) => item.id === activeView);
  const showSecondary = moreOpen || secondaryActive;

  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">
        Skip to content
      </a>
      <header className="mobile-header">
        <button
          className="icon-button"
          type="button"
          aria-label={mobileOpen ? "Close navigation" : "Open navigation"}
          aria-expanded={mobileOpen}
          onClick={() => setMobileOpen((open) => !open)}
        >
          {mobileOpen ? <X size={20} /> : <Menu size={20} />}
        </button>
        <span className="mobile-brand">
          <DatabaseZap size={19} aria-hidden="true" /> Dataset Foundry
        </span>
        <button className="icon-button" type="button" aria-label="Change color theme" onClick={cycleTheme}>
          {theme === "dark" ? <MoonStar size={18} /> : <Sun size={18} />}
        </button>
      </header>

      <aside className={`sidebar${mobileOpen ? " is-open" : ""}`} aria-label="Primary navigation">
        <div className="brand-lockup">
          <span className="brand-mark" aria-hidden="true">
            <DatabaseZap size={22} />
          </span>
          <span className="brand-lockup__copy">
            <strong>Dataset Foundry</strong>
            <small>Training data workbench</small>
          </span>
          <button
            className="icon-button sidebar-close"
            type="button"
            aria-label="Close navigation"
            onClick={() => setMobileOpen(false)}
          >
            <X size={19} />
          </button>
        </div>

        <button className="button button--primary sidebar-cta" type="button" onClick={() => navigate("generate")}>
          <Sparkles size={17} aria-hidden="true" /> New generation
        </button>

        <nav className="sidebar-nav">
          <section aria-labelledby="nav-core-workflow">
            <p id="nav-core-workflow" className="sidebar-nav__group">Core workflow</p>
            <ul>
              {PRIMARY_NAVIGATION.map(({ id, label, icon: Icon }) => (
                <li key={id}>
                  <button
                    className={activeView === id ? "is-active" : undefined}
                    type="button"
                    aria-current={activeView === id ? "page" : undefined}
                    onClick={() => navigate(id)}
                  >
                    <Icon size={17} aria-hidden="true" />
                    <span>{label}</span>
                  </button>
                </li>
              ))}
            </ul>
          </section>
          <section aria-labelledby="nav-supporting-tools">
            <p id="nav-supporting-tools" className="sidebar-nav__group">Supporting tools</p>
            <button
              className={`secondary-nav-toggle${secondaryActive ? " is-active" : ""}`}
              type="button"
              aria-expanded={showSecondary}
              onClick={() => setMoreOpen((open) => !open)}
            >
              <MoreHorizontal size={17} aria-hidden="true" />
              <span>More</span>
            </button>
            {showSecondary ? (
              <ul className="secondary-nav-list">
                {SECONDARY_NAVIGATION.map(({ id, label, icon: Icon }) => (
                  <li key={id}>
                    <button
                      className={activeView === id ? "is-active" : undefined}
                      type="button"
                      aria-current={activeView === id ? "page" : undefined}
                      onClick={() => navigate(id)}
                    >
                      <Icon size={17} aria-hidden="true" />
                      <span>{label}</span>
                    </button>
                  </li>
                ))}
              </ul>
            ) : null}
          </section>
        </nav>

        <div className="sidebar-footer">
          <div className={`connection-chip${serviceWarning ? " is-warning" : ""}`}>
            <span aria-hidden="true" />
            {demoMode
              ? "Demo services ready"
              : systemStatus.isPending
                ? "Checking services"
                : systemStatus.isError
                  ? "Service status unavailable"
                  : systemStatus.data?.workerReady
                    ? "API + worker ready"
                    : "API ready · worker offline"}
          </div>
          {!demoMode && systemStatus.data && !systemStatus.data.workerReady ? (
            <p className="service-hint">Start: <code>uv run dataset-foundry worker</code></p>
          ) : null}
          <button className="theme-control" type="button" onClick={cycleTheme}>
            {theme === "dark" ? <MoonStar size={16} /> : <Sun size={16} />}
            <span>Theme: {theme}</span>
          </button>
          <p>Local-first · API boundary <code>/api/v1</code></p>
        </div>
      </aside>

      {mobileOpen ? (
        <button
          className="mobile-scrim"
          type="button"
          aria-label="Close navigation"
          onClick={() => setMobileOpen(false)}
        />
      ) : null}

      <main id="main-content" className="main-content" tabIndex={-1}>
        {demoMode ? (
          <div className="demo-banner" role="status">
            <DatabaseZap size={15} aria-hidden="true" />
            <span>
              <strong>Demo data</strong> · Deterministic examples; no provider request or billable usage.
            </span>
          </div>
        ) : null}
        {children}
      </main>
    </div>
  );
}
