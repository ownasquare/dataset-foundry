import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { App } from "./App";
import "./styles/index.css";

const query = new URLSearchParams(window.location.search);
const demoMode = query.get("demo") === "1" || import.meta.env.VITE_DEMO_MODE === "true";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App demoMode={demoMode} />
  </StrictMode>,
);
