function initializeDesignDashboard() {
    const modeSelect = document.getElementById("roverModeSelect");
    if (modeSelect instanceof HTMLSelectElement) {
        modeSelect.addEventListener("change", () => {
            if (modeSelect.value !== "triple") {
                return;
            }
            if (window.confirm("Open Triple Rover Mode? Three agents can chat independently at the same time.")) {
                window.location.assign(modeSelect.dataset.tripleUrl);
            } else {
                modeSelect.value = "single";
            }
        });
    }

    const openButton = document.getElementById("openApiKeyDialog");
    const backdrop = document.getElementById("apiKeyDialog");
    const dialog = backdrop?.querySelector('[role="dialog"]');

    if (
        !(openButton instanceof HTMLButtonElement) ||
        !(backdrop instanceof HTMLElement) ||
        !(dialog instanceof HTMLElement)
    ) {
        console.error("API key dialog controls are missing from the design dashboard.");
        return;
    }

    const closeButton = document.getElementById("closeApiKeyDialog");
    const cancelButton = document.getElementById("cancelApiKeyDialog");
    const nameInput = document.getElementById("apiKeyName");

    const closeDialog = () => {
        backdrop.hidden = true;
        const apiKeyInput = document.getElementById("apiKeyValue");
        if (apiKeyInput instanceof HTMLInputElement) {
            apiKeyInput.value = "";
        }
        openButton.focus();
    };

    openButton.addEventListener("click", () => {
        backdrop.hidden = false;
        if (nameInput instanceof HTMLInputElement) {
            nameInput.focus();
        }
    });

    closeButton?.addEventListener("click", closeDialog);
    cancelButton?.addEventListener("click", closeDialog);

    backdrop.addEventListener("click", (event) => {
        if (event.target === backdrop) {
            closeDialog();
        }
    });

    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape" && !backdrop.hidden) {
            closeDialog();
        }
    });

    const form = document.getElementById("apiKeyForm");
    const status = document.getElementById("apiKeyStatus");
    const apiKeyInput = document.getElementById("apiKeyValue");
    const typeInput = document.getElementById("apiKeyType");
    const savedKeysList = document.getElementById("savedApiKeysList");
    const saveButton = document.getElementById("saveApiKey");
    const csrfInput = form?.querySelector('input[name="csrf_token"]');

    if (
        !(form instanceof HTMLFormElement) ||
        !(status instanceof HTMLElement) ||
        !(nameInput instanceof HTMLInputElement) ||
        !(apiKeyInput instanceof HTMLInputElement) ||
        !(typeInput instanceof HTMLSelectElement) ||
        !(savedKeysList instanceof HTMLElement) ||
        !(saveButton instanceof HTMLButtonElement) ||
        !(csrfInput instanceof HTMLInputElement)
    ) {
        console.error("API key form controls are missing from the design dashboard.");
        return;
    }

    const setStatus = (message, state = "") => {
        status.textContent = message;
        if (state) {
            status.dataset.state = state;
        } else {
            delete status.dataset.state;
        }
    };

    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        setStatus("");
        saveButton.disabled = true;

        try {
            const response = await fetch(form.action, {
                method: "POST",
                credentials: "same-origin",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": csrfInput.value,
                },
                body: JSON.stringify({
                    name: nameInput.value,
                    type: typeInput.value,
                    api_key: apiKeyInput.value,
                }),
            });
            const result = await response.json();

            if (!response.ok) {
                setStatus(result.error || "The API key could not be saved.", "error");
                return;
            }

            document.getElementById("noSavedApiKeys")?.remove();

            const entry = document.createElement("article");
            entry.className = "saved-api-key";

            const name = document.createElement("p");
            name.className = "saved-api-key-name";
            name.textContent = result.api_key.name;

            const type = document.createElement("p");
            type.className = "saved-api-key-type";
            type.textContent = result.api_key.type === "ollama"
                ? "Ollama API Key"
                : result.api_key.type;

            const created = document.createElement("p");
            created.className = "api-key-row-meta";
            created.textContent = `Added ${new Date(result.api_key.created_at).toLocaleDateString()}`;

            entry.append(name, type, created);
            savedKeysList.prepend(entry);
            form.reset();
            setStatus("API key saved. The secret cannot be viewed again.", "success");
            window.dispatchEvent(new CustomEvent("ollama-preferences-updated", {
                detail: { apiKeySaved: true },
            }));
        } catch {
            setStatus("Could not reach the server. Please try again.", "error");
        } finally {
            saveButton.disabled = false;
        }
    });
}

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initializeDesignDashboard, { once: true });
} else {
    initializeDesignDashboard();
}
