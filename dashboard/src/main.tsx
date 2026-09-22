import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import { loadDashboardConfig } from "./config";
import "./styles.css";

const config = await loadDashboardConfig();

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App config={config} />
  </StrictMode>,
);
