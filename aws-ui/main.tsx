import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import ReliabilityDashboard from "../app/reliability-dashboard";
import "../app/globals.css";
import "../app/operations-theme.css";

const root = document.getElementById("root");

if (!root) {
  throw new Error("Reliability Memory root element was not found");
}

createRoot(root).render(
  <StrictMode>
    <ReliabilityDashboard />
  </StrictMode>,
);
