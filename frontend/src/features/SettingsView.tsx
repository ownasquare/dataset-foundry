import { Check, Cloud, KeyRound, LockKeyhole, MoonStar, ServerCog, ShieldCheck, Sun } from "lucide-react";

import { useProviders } from "../api/queries";
import { API_ROOT } from "../api/client";
import { PageHeader } from "../components/PageHeader";
import { StatePanel } from "../components/StatePanel";
import { StatusBadge } from "../components/StatusBadge";
import { useTheme, type ThemeChoice } from "../components/ThemeProvider";

export function SettingsView({ demoMode }: { demoMode: boolean }) {
  const providers = useProviders();
  const { theme, setTheme } = useTheme();

  return (
    <div className="view-stack">
      <PageHeader
        eyebrow="System"
        title="Settings"
        description="Review workspace appearance, API readiness, and provider boundaries. Credentials remain server-side and never appear here."
      />

      <div className="settings-grid">
        <section className="panel settings-section" aria-labelledby="appearance-title">
          <div className="settings-section__heading"><Sun size={18} /><div><h2 id="appearance-title">Appearance</h2><p>Choose how the local workbench looks on this device.</p></div></div>
          <div className="theme-options" role="radiogroup" aria-label="Color theme">
            {(["system", "light", "dark"] as ThemeChoice[]).map((choice) => (
              <button
                type="button"
                role="radio"
                aria-checked={theme === choice}
                className={theme === choice ? "theme-option is-selected" : "theme-option"}
                key={choice}
                onClick={() => setTheme(choice)}
              >
                {choice === "dark" ? <MoonStar size={18} /> : <Sun size={18} />}
                <span><strong>{choice[0]?.toUpperCase() + choice.slice(1)}</strong><small>{choice === "system" ? "Follow device preference" : `${choice} surfaces`}</small></span>
                {theme === choice ? <Check size={16} /> : null}
              </button>
            ))}
          </div>
        </section>

        <section className="panel settings-section" aria-labelledby="api-title">
          <div className="settings-section__heading"><ServerCog size={18} /><div><h2 id="api-title">API boundary</h2><p>The browser reads and changes data only through FastAPI.</p></div></div>
          <dl className="settings-facts">
            <div><dt>Base path</dt><dd><code>{API_ROOT}</code></dd></div>
            <div><dt>Mode</dt><dd>{demoMode ? "Deterministic demo adapter" : "Live local API"}</dd></div>
            <div><dt>Credential handling</dt><dd>Server-side only</dd></div>
          </dl>
          <div className="inline-success"><ShieldCheck size={16} /> Provider secrets are never sent to the browser.</div>
        </section>
      </div>

      <section className="panel settings-section" aria-labelledby="providers-title">
        <div className="settings-section__heading"><KeyRound size={18} /><div><h2 id="providers-title">Generation providers</h2><p>Readiness comes from the API. Configure credentials in the server environment, then refresh this view.</p></div></div>
        {providers.isPending ? <StatePanel kind="loading" /> : null}
        {providers.isError ? <StatePanel kind="error" message={providers.error.message} onRetry={() => void providers.refetch()} /> : null}
        {providers.data ? (
          <div className="provider-settings-grid">
            {providers.data.map((provider) => (
              <article className="provider-settings-card" key={provider.provider}>
                <span className="provider-settings-card__icon" aria-hidden="true">
                  {provider.provider === "offline" ? <LockKeyhole size={20} /> : <Cloud size={20} />}
                </span>
                <div><h3>{provider.label}</h3><p>{provider.description}</p></div>
                <StatusBadge status={provider.status} />
                <dl>
                  <div><dt>Default model</dt><dd>{provider.model}</dd></div>
                  <div><dt>Data transfer</dt><dd>{provider.dataLeavesEnvironment ? "External" : "Stays local"}</dd></div>
                </dl>
              </article>
            ))}
          </div>
        ) : null}
      </section>
    </div>
  );
}
