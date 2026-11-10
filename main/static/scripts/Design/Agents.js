document.addEventListener("DOMContentLoaded", () => {
    const page = document.getElementById("agentsPage");
    const grid = document.getElementById("roverAgentsGrid");
    const pageStatus = document.getElementById("agentsPageStatus");
    const modeSelect = document.getElementById("roverModeSelect");

    if (
        !(page instanceof HTMLElement) ||
        !(grid instanceof HTMLElement) ||
        !(pageStatus instanceof HTMLElement) ||
        !(modeSelect instanceof HTMLSelectElement)
    ) {
        console.error("Triple Rover page controls are missing.");
        return;
    }

    modeSelect.addEventListener("change", () => {
        if (modeSelect.value === "single") {
            window.location.assign(modeSelect.dataset.singleUrl);
        }
    });

    const csrfToken = page.dataset.csrfToken;
    const requestJson = async (url, body) => {
        const response = await fetch(url, {
            method: "POST",
            credentials: "same-origin",
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": csrfToken,
                Accept: "application/json",
            },
            body: JSON.stringify(body),
        });
        const result = await response.json();
        if (!response.ok) {
            throw new Error(result.error || "The request could not be completed.");
        }
        return result;
    };

    const addMessage = (messages, role, content) => {
        messages.querySelector(".rover-agent-empty")?.remove();
        const message = document.createElement("p");
        message.className = "rover-agent-message";
        message.dataset.role = role;
        message.textContent = content;
        messages.append(message);
        messages.scrollTop = messages.scrollHeight;
    };

    const createLabelledInput = (form, labelText, inputType, name, value) => {
        const label = document.createElement("label");
        label.textContent = labelText;
        const input = document.createElement("input");
        input.name = name;
        input.type = inputType;
        input.value = value;
        input.required = true;
        label.append(input);
        form.append(label);
        return input;
    };

    const renderAgent = (agent) => {
        const card = document.createElement("article");
        card.className = "rover-agent-card";

        const header = document.createElement("header");
        header.className = "rover-agent-header";
        const identity = document.createElement("div");
        const title = document.createElement("h2");
        title.className = "rover-agent-title";
        title.textContent = agent.name;
        const model = document.createElement("p");
        model.className = "rover-agent-model";
        model.textContent = `Model: ${agent.model}`;
        identity.append(title, model);
        const status = document.createElement("span");
        status.className = "rover-agent-status";
        status.dataset.state = "idle";
        status.textContent = agent.messages.length > 0
            ? `Ready · history since ${new Date(agent.first_message_at).toLocaleDateString()}`
            : agent.first_message_at
                ? `Idle · history started ${new Date(agent.first_message_at).toLocaleDateString()}`
                : "Idle · history starts on first chat";
        header.append(identity, status);

        const settings = document.createElement("details");
        settings.className = "rover-agent-settings";
        const summary = document.createElement("summary");
        summary.textContent = "Agent settings";
        settings.append(summary);
        const settingsForm = document.createElement("form");
        settingsForm.noValidate = false;
        const nameInput = createLabelledInput(
            settingsForm,
            "Agent name",
            "text",
            "name",
            agent.name,
        );
        nameInput.maxLength = 64;
        const modelInput = createLabelledInput(
            settingsForm,
            "Ollama model",
            "text",
            "model",
            agent.model,
        );
        modelInput.maxLength = 128;
        const promptLabel = document.createElement("label");
        promptLabel.textContent = "System instructions";
        const promptInput = document.createElement("textarea");
        promptInput.name = "system_prompt";
        promptInput.maxLength = 2000;
        promptInput.value = agent.system_prompt;
        promptLabel.append(promptInput);
        settingsForm.append(promptLabel);
        const temperatureInput = createLabelledInput(
            settingsForm,
            "Temperature (0–2)",
            "number",
            "temperature",
            agent.temperature,
        );
        temperatureInput.min = "0";
        temperatureInput.max = "2";
        temperatureInput.step = "0.1";
        const saveButton = document.createElement("button");
        saveButton.className = "rover-agent-save";
        saveButton.type = "submit";
        saveButton.textContent = "Save settings";
        const settingsStatus = document.createElement("p");
        settingsStatus.className = "rover-agent-settings-status";
        settingsStatus.setAttribute("role", "status");
        settingsForm.append(saveButton, settingsStatus);
        settings.append(settingsForm);

        const messages = document.createElement("div");
        messages.className = "rover-agent-messages";
        messages.setAttribute("role", "log");
        messages.setAttribute("aria-live", "polite");
        if (agent.messages.length === 0) {
            const empty = document.createElement("p");
            empty.className = "rover-agent-empty";
            empty.textContent = "Start a conversation with this agent.";
            messages.append(empty);
        } else {
            agent.messages.forEach((message) => {
                addMessage(messages, message.role, message.content);
            });
        }

        const chatForm = document.createElement("form");
        chatForm.className = "rover-agent-chat-form";
        const chatInput = document.createElement("textarea");
        chatInput.className = "rover-agent-input";
        chatInput.name = "message";
        chatInput.rows = 2;
        chatInput.maxLength = 20000;
        chatInput.placeholder = `Message ${agent.name}...`;
        chatInput.setAttribute("aria-label", `Message ${agent.name}`);
        chatInput.required = true;
        const sendButton = document.createElement("button");
        sendButton.className = "rover-agent-send";
        sendButton.type = "submit";
        sendButton.textContent = "Send";
        chatForm.append(chatInput, sendButton);

        settingsForm.addEventListener("submit", async (event) => {
            event.preventDefault();
            settingsStatus.textContent = "Saving settings...";
            saveButton.disabled = true;
            try {
                const result = await requestJson(
                    `${page.dataset.agentsUrl}/${agent.id}/settings`,
                    {
                        name: nameInput.value.trim(),
                        model: modelInput.value.trim(),
                        system_prompt: promptInput.value,
                        temperature: Number(temperatureInput.value),
                    },
                );
                title.textContent = result.name;
                model.textContent = `Model: ${result.model}`;
                chatInput.placeholder = `Message ${result.name}...`;
                chatInput.setAttribute("aria-label", `Message ${result.name}`);
                settingsStatus.textContent = "Settings saved.";
            } catch (error) {
                settingsStatus.textContent = error.message;
            } finally {
                saveButton.disabled = false;
            }
        });

        chatForm.addEventListener("submit", async (event) => {
            event.preventDefault();
            const content = chatInput.value.trim();
            if (!content || sendButton.disabled) {
                return;
            }
            sendButton.disabled = true;
            status.dataset.state = "busy";
            status.textContent = "Thinking...";
            try {
                const result = await requestJson(
                    `${page.dataset.agentsUrl}/${agent.id}/chat`,
                    { message: content },
                );
                addMessage(messages, "user", content);
                addMessage(messages, "assistant", result.message);
                chatInput.value = "";
                agent.first_message_at ||= result.first_message_at;
                status.dataset.state = "ready";
                status.textContent = `Ready · history since ${new Date(agent.first_message_at).toLocaleDateString()}`;
            } catch (error) {
                status.dataset.state = "error";
                status.textContent = error.message;
            } finally {
                sendButton.disabled = false;
            }
        });

        card.append(header, settings, messages, chatForm);
        grid.append(card);
    };

    const loadAgents = async () => {
        try {
            const response = await fetch(page.dataset.agentsUrl, {
                credentials: "same-origin",
                headers: { Accept: "application/json" },
            });
            const result = await response.json();
            if (!response.ok) {
                throw new Error(result.error || "Could not load Triple Rover agents.");
            }
            pageStatus.remove();
            result.agents.forEach(renderAgent);
        } catch (error) {
            pageStatus.textContent = error.message;
        }
    };

    loadAgents();
});
