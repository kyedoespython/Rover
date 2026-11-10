document.addEventListener("DOMContentLoaded", () => {
    const container = document.getElementById("ollamaPreferences");
    const form = document.getElementById("ollamaPreferencesForm");
    const modelSelect = document.getElementById("ollamaModelSelect");
    const apiKeySelect = document.getElementById("ollamaApiKeySelect");
    const status = document.getElementById("ollamaPreferencesStatus");
    const currentModel = document.getElementById("currentOllamaModel");
    const saveButton = document.getElementById("saveOllamaPreferences");
    const csrfInput = form?.querySelector('input[name="csrf_token"]');

    if (
        !(container instanceof HTMLElement) ||
        !(form instanceof HTMLFormElement) ||
        !(modelSelect instanceof HTMLSelectElement) ||
        !(apiKeySelect instanceof HTMLSelectElement) ||
        !(status instanceof HTMLElement) ||
        !(currentModel instanceof HTMLElement) ||
        !(saveButton instanceof HTMLButtonElement) ||
        !(csrfInput instanceof HTMLInputElement)
    ) {
        return;
    }

    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        status.textContent = "Connecting to Ollama...";
        status.dataset.state = "";
        saveButton.disabled = true;

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
            status.textContent = "Ollama settings saved.";
            status.dataset.state = "success";
            window.dispatchEvent(new CustomEvent("ollama-preferences-updated", {
                detail: { model: result.model },
            }));
        } catch {
            status.textContent = "Could not reach Rover. Please try again.";
            status.dataset.state = "error";
        } finally {
            saveButton.disabled = false;
        }
    });
});
