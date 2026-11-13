import React from "react";
import { createRoot } from "react-dom/client";

import App from "./App.jsx";
import "./styles.css";

const rootElement = document.getElementById("react-root");

if (rootElement) {
    const propsNode = rootElement.querySelector("#react-props");
    const props = rootElement.dataset.props
        ? JSON.parse(rootElement.dataset.props)
        : propsNode
          ? JSON.parse(propsNode.textContent)
          : {};
    createRoot(rootElement).render(
        <App
            csrfToken={rootElement.dataset.csrfToken}
            page={rootElement.dataset.page}
            {...props}
        />,
    );
}
