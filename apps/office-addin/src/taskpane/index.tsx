import React from "react";
import { createRoot } from "react-dom/client";
import { FluentProvider, webLightTheme } from "@fluentui/react-components";

import { App } from "./App";

// Office.js dispatches `Office.onReady` once the host (Word) has
// finished loading the add-in's runtime. Mount React inside that
// callback so the Office object is fully available to child components.
Office.onReady(({ host }) => {
  if (host !== Office.HostType.Word) {
    document.body.innerText = "Anchor Quality Gate runs in Word only.";
    return;
  }
  const root = createRoot(document.getElementById("root")!);
  root.render(
    <React.StrictMode>
      <FluentProvider theme={webLightTheme}>
        <App />
      </FluentProvider>
    </React.StrictMode>
  );
});
