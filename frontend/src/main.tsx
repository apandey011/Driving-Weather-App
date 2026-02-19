import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import "./App.css";

const sentryDsn = import.meta.env.VITE_SENTRY_DSN;
if (sentryDsn) {
  const sentryModuleName = "@sentry/react";
  void import(sentryModuleName)
    .then((Sentry) => {
      Sentry.init({
        dsn: sentryDsn,
        environment: import.meta.env.VITE_SENTRY_ENVIRONMENT || "development",
        release: import.meta.env.VITE_SENTRY_RELEASE || undefined,
        tracesSampleRate: 0,
      });
    })
    .catch(() => {
      // Keep app booting even if optional monitoring dependency is unavailable.
    });
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>
);
