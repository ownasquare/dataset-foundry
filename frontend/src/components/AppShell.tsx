import {
  Archive,
  BarChart3,
  DatabaseZap,
  FileCheck2,
  FolderKanban,
  Menu,
  MoonStar,
  PlaySquare,
  Settings,
  Sparkles,
  Sun,
  X,
} from "lucide-react";
import { useState, type ReactNode } from "react";

import type { ViewKey } from "../api/types";
import { useTheme } from "./ThemeProvider";

interface AppShellProps {
  activeView: ViewKey;
  onNavigate: (view: ViewKey) => void;
  children: ReactNode;
  demoMode: boolean;
}

const NAVIGATION = [
  { id: "overview", label: "Overview", icon: BarChart3, group: "Workspace" },
  { id: "projects", label: "Projects", icon: FolderKanban, group: "Workspace" },
  { id: "generate", label: "Generate", icon: Sparkles, group: "Create" },
  { id: "runs", label: "Runs", icon: PlaySquare, group: "Create" },
  { id: "review", label: "Review", icon: FileCheck2, group: "Prepare" },
  { id: "exports", label: "Exports", icon: Archive, group: "Prepare" },
  { id: "settings", label: "Settings", icon: Settings, group: "System" },
] as const;

export function AppShell({ activeView, onNavigate, children, demoMode }: AppShellProps) {
  const [mobileOpen, setMobileOpen] = useState(false);
  const { theme, setTheme } = useTheme();

  const navigate = (view: ViewKey) => {
    onNavigate(view);
    setMobileOpen(false);
    window.requestAnimationFrame(() => document.querySelector<HTMLElement>("#main-content")?.focus());
  };

  const cycleTheme = () => {
    setTheme(theme === "light" ? "dark" : theme === "dark" ? "system" : "light");
  };

  const grouped = NAVIGATION.reduce<Record<string, typeof NAVIGATION[number][]>>((groups, item) => {
    (groups[item.group] ??= []).push(item);
    return groups;
  }, {});

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
          <span>
            <strong>Dataset Foundry</strong>
            <small>Training data workbench</small>
          </span>
        </div>

        <button className="button button--primary sidebar-cta" type="button" onClick={() => navigate("generate")}>
          <Sparkles size={17} aria-hidden="true" /> New generation
        </button>

        <nav className="sidebar-nav">
          {Object.entries(grouped).map(([group, items]) => (
            <section key={group} aria-labelledby={`nav-${group.toLowerCase()}`}>
              <p id={`nav-${group.toLowerCase()}`} className="sidebar-nav__group">
                {group}
              </p>
              <ul>
                {items.map(({ id, label, icon: Icon }) => (
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
          ))}
        </nav>

        <div className="sidebar-footer">
          <div className="connection-chip">
            <span aria-hidden="true" />
            {demoMode ? "Demo workspace" : "API connected"}
          </div>
          <button className="theme-control" type="button" onClick={cycleTheme}>
            {theme === "dark" ? <MoonStar size={16} /> : <Sun size={16} />}
            <span>Theme: {theme}</span>
          </button>
          <p>Local-first · API boundary `/api/v1`</p>
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
