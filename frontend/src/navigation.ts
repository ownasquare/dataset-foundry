import { useCallback, useEffect, useState } from "react";

import type { ViewKey } from "./api/types";

export const DEFAULT_VIEW: ViewKey = "overview";

export const VIEW_HASHES = {
  overview: "#overview",
  generate: "#generate",
  review: "#review",
  exports: "#exports",
  projects: "#projects",
  runs: "#runs",
  settings: "#settings",
} as const satisfies Record<ViewKey, `#${string}`>;

const HASH_VIEWS = new Map<string, ViewKey>(
  Object.entries(VIEW_HASHES).map(([view, hash]) => [hash, view as ViewKey]),
);

export function hashForView(view: ViewKey): (typeof VIEW_HASHES)[ViewKey] {
  return VIEW_HASHES[view];
}

export function parseViewHash(hash: string): ViewKey | null {
  return HASH_VIEWS.get(hash) ?? null;
}

function replaceViewHash(view: ViewKey) {
  window.history.replaceState(window.history.state, "", hashForView(view));
}

export function useViewNavigation(initialView?: ViewKey) {
  const [activeView, setActiveView] = useState<ViewKey>(
    () => initialView ?? parseViewHash(window.location.hash) ?? DEFAULT_VIEW,
  );

  useEffect(() => {
    const startingView = initialView ?? parseViewHash(window.location.hash) ?? DEFAULT_VIEW;
    if (window.location.hash !== hashForView(startingView)) replaceViewHash(startingView);
    setActiveView(startingView);

    const syncFromLocation = () => {
      const nextView = parseViewHash(window.location.hash);
      if (nextView) {
        setActiveView(nextView);
        return;
      }
      replaceViewHash(DEFAULT_VIEW);
      setActiveView(DEFAULT_VIEW);
    };

    window.addEventListener("popstate", syncFromLocation);
    window.addEventListener("hashchange", syncFromLocation);
    return () => {
      window.removeEventListener("popstate", syncFromLocation);
      window.removeEventListener("hashchange", syncFromLocation);
    };
  }, [initialView]);

  const navigateTo = useCallback((view: ViewKey) => {
    const nextHash = hashForView(view);
    if (window.location.hash !== nextHash) {
      window.history.pushState(window.history.state, "", nextHash);
    }
    setActiveView(view);
  }, []);

  return { activeView, navigateTo };
}
