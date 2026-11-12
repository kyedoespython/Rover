document.addEventListener("DOMContentLoaded", () => {
    const container = document.getElementById("ollamaPreferences");
    const form = document.getElementById("ollamaPreferencesForm");
    const modelSelect = document.getElementById("ollamaModelSelect");
    const apiKeySelect = document.getElementById("ollamaApiKeySelect");
    const status = document.getElementById("ollamaPreferencesStatus");
    const currentModel = document.getElementById("currentOllamaModel");
    const saveButton = document.getElementById("saveOllamaPreferences");
    const activateButton = document.getElementById("activateOllamaApiKey");
    const deactivateButton = document.getElementById("deactivateOllamaApiKey");
    const activeKey = document.getElementById("activeOllamaApiKey");
    const connectionStatus = document.getElementById("ollamaConnectionStatus");
    const csrfInput = form?.querySelector('input[name="csrf_token"]');
    const geminiForm = document.getElementById("geminiPreferencesForm");
    const geminiKey = document.getElementById("geminiApiKeySelect");
    const geminiModel = document.getElementById("geminiModelSelect");
    const geminiStatus = document.getElementById("geminiPreferencesStatus");
    const geminiSave = document.getElementById("saveGeminiModel");
    const useOllama = document.getElementById("useOllamaProvider");
    const activeProvider = document.getElementById("activeRoverProvider");

    if (
        !(container instanceof HTMLElement) ||
        !(form instanceof HTMLFormElement) ||
        !(modelSelect instanceof HTMLSelectElement) ||
        !(apiKeySelect instanceof HTMLSelectElement) ||
        !(status instanceof HTMLElement) ||
        !(currentModel instanceof HTMLElement) ||
        !(saveButton instanceof HTMLButtonElement) ||
        !(activateButton instanceof HTMLButtonElement) ||
        !(deactivateButton instanceof HTMLButtonElement) ||
        !(activeKey instanceof HTMLElement) ||
        !(connectionStatus instanceof HTMLElement) ||
        !(csrfInput instanceof HTMLInputElement) ||
        !(geminiForm instanceof HTMLFormElement) ||
        !(geminiKey instanceof HTMLSelectElement) ||
        !(geminiModel instanceof HTMLSelectElement) ||
        !(geminiStatus instanceof HTMLElement) ||
        !(geminiSave instanceof HTMLButtonElement) ||
        !(useOllama instanceof HTMLButtonElement) ||
        !(activeProvider instanceof HTMLElement)
    ) {
        return;
    }

    const setActiveApiKey = async (apiKeyId) => {
        status.textContent = "Updating Ollama API key...";
        status.dataset.state = "";
        activateButton.disabled = true;
        deactivateButton.disabled = true;
        saveButton.disabled = true;

        try {
            const response = await fetch(container.dataset.keyUrl, {
                method: "POST",
                credentials: "same-origin",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": csrfInput.value,
                    Accept: "application/json",
                },
                body: JSON.stringify({ api_key_id: apiKeyId }),
            });
            const result = await response.json();
            if (!response.ok) {
                throw new Error(result.error || "API key could not be updated.");
            }

            apiKeySelect.value = result.api_key_id === null ? "" : String(result.api_key_id);
            activeKey.textContent = `Active API key: ${result.api_key_name || "None"}`;
            connectionStatus.textContent = result.api_key_id === null
                ? "API key deactivated. Connection status has not been checked."
                : "Connected to Ollama.";
            if (result.available_models.length) {
                currentModel.textContent = result.model;
                modelSelect.replaceChildren();
                result.available_models.forEach((model) => {
                    const option = document.createElement("option");
                    option.value = model;
                    option.textContent = model;
                    modelSelect.append(option);
                });
                modelSelect.value = result.model;
                modelSelect.disabled = false;
            }
            status.textContent = result.api_key_id === null
                ? "Ollama API key deactivated."
                : "Ollama API key activated.";
            status.dataset.state = "success";
            if (result.api_key_id !== null) {
                activeProvider.textContent = "Ollama";
            }
            window.dispatchEvent(new CustomEvent("ollama-preferences-updated", {
                detail: { model: result.model },
            }));
        } catch (error) {
            status.textContent = error.message || "Could not reach Rover. Please try again.";
            status.dataset.state = "error";
        } finally {
            activateButton.disabled = false;
            deactivateButton.disabled = false;
            saveButton.disabled = modelSelect.disabled;
        }
    };

    activateButton.addEventListener("click", () => {
        if (!apiKeySelect.value) {
            status.textContent = "Select a saved API key first.";
            status.dataset.state = "error";
            return;
        }
        setActiveApiKey(Number(apiKeySelect.value));
    });
    deactivateButton.addEventListener("click", () => setActiveApiKey(null));

    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        status.textContent = "Connecting to Ollama...";
        status.dataset.state = "";
        saveButton.disabled = true;
        activateButton.disabled = true;
        deactivateButton.disabled = true;

        const selectedKey = apiKeySelect.value;
        try {
            const response = await fetch(container.dataset.preferencesUrl, {
                method: "POST",
                credentials: "same-origin",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": csrfInput.value,
                    Accept: "application/json",
                },
                body: JSON.stringify({
                    model: modelSelect.value,
                    api_key_id: selectedKey ? Number(selectedKey) : null,
                }),
            });
            const result = await response.json();

            if (!response.ok) {
                status.textContent = result.error || "Integration settings could not be saved.";
                status.dataset.state = "error";
                return;
            }

            currentModel.textContent = result.model;
            document.getElementById("ollamaModelName")?.replaceChildren(
                document.createTextNode(result.model),
            );
            activeKey.textContent = `Active API key: ${result.api_key_name || "None"}`;
            connectionStatus.textContent = "Connected to Ollama.";
            status.textContent = "Ollama settings saved.";
            status.dataset.state = "success";
            activeProvider.textContent = "Ollama";
            window.dispatchEvent(new CustomEvent("ollama-preferences-updated", {
                detail: { model: result.model },
            }));
        } catch {
            status.textContent = "Could not reach Rover. Please try again.";
            status.dataset.state = "error";
        } finally {
            saveButton.disabled = false;
            activateButton.disabled = false;
            deactivateButton.disabled = false;
        }
    });

    const updateGemini = async (payload) => {
        geminiForm.querySelectorAll("button, select").forEach((control) => { control.disabled = true; });
        geminiStatus.textContent = "Updating AI provider...";
        geminiStatus.dataset.state = "";
        try {
            const response = await fetch(container.dataset.geminiUrl, {
                method: "POST",
                credentials: "same-origin",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": csrfInput.value,
                    Accept: "application/json",
                },
                body: JSON.stringify(payload),
            });
            const result = await response.json();
            if (!response.ok) {
                throw new Error(result.error || "Could not update the AI provider.");
            }
            activeProvider.textContent = result.provider === "gemini" ? "Google Gemini" : "Ollama";
            if (result.provider === "gemini") {
                geminiModel.replaceChildren();
                result.available_models.forEach((name) => {
                    const option = document.createElement("option");
                    option.value = name;
                    option.textContent = name;
                    geminiModel.append(option);
                });
                geminiModel.value = result.model;
            }
            geminiStatus.textContent = result.provider === "gemini"
                ? `Gemini activated with ${result.model}.`
                : "Ollama selected for Rover AI.";
            geminiStatus.dataset.state = "success";
        } catch (error) {
            geminiStatus.textContent = error.message || "Could not update the AI provider.";
            geminiStatus.dataset.state = "error";
        } finally {
            geminiForm.querySelectorAll("button, select").forEach((control) => { control.disabled = false; });
        }
    };

    geminiForm.addEventListener("submit", (event) => {
        event.preventDefault();
        if (!geminiKey.value) {
            geminiStatus.textContent = "Select a saved Gemini key first.";
            geminiStatus.dataset.state = "error";
            return;
        }
        updateGemini({ api_key_id: Number(geminiKey.value) });
    });
    geminiSave.addEventListener("click", () => {
        if (!geminiKey.value || !geminiModel.value) {
            geminiStatus.textContent = "Activate a Gemini key and choose a model first.";
            geminiStatus.dataset.state = "error";
            return;
        }
        updateGemini({ api_key_id: Number(geminiKey.value), model: geminiModel.value });
    });
    useOllama.addEventListener("click", () => updateGemini({ provider: "ollama" }));
});
