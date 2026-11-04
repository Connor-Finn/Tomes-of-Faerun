import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import "@fontsource/im-fell-english-sc/400.css";
import "@fontsource/im-fell-english/400.css";
import "@fontsource/im-fell-english/400-italic.css";
import "@fontsource/eb-garamond/400.css";
import "@fontsource/eb-garamond/500.css";
import "@fontsource/eb-garamond/600.css";
import "@fontsource/eb-garamond/400-italic.css";
import { App } from "./App";
import { AuthProvider } from "./lib/auth";
import { FlashProvider } from "./lib/flash";
import "./styles.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <BrowserRouter>
      <AuthProvider>
        <FlashProvider>
          <App />
        </FlashProvider>
      </AuthProvider>
    </BrowserRouter>
  </React.StrictMode>,
);
