function initializeOllamaDrawer() {
    const drawer = document.getElementById("ollamaDrawer");
    const toggle = document.getElementById("ollamaDrawerToggle");
    const hideButton = document.getElementById("ollamaMinimize");
    const endSessionButton = document.getElementById("ollamaEndSession");
    const newSessionButton = document.getElementById("ollamaNewSession");
    const dragHandle = document.getElementById("ollamaDrawerDragHandle");
    const resizeHandle = document.getElementById("ollamaResizeHandle");
    const statusPanel = document.getElementById("ollamaAssistantStatus");
    const statusText = document.getElementById("ollamaStatusText");
    const modelName = document.getElementById("ollamaModelName");
    const chatbotName = document.getElementById("ollamaChatbotName");
    const messagesPanel = document.getElementById("ollamaChatMessages");
    const form = document.getElementById("ollamaChatForm");
    const input = document.getElementById("ollamaChatInput");
    const sendButton = document.getElementById("ollamaChatSend");
    const settingsForm = document.getElementById("ollamaChatbotSettingsForm");
    const nameInput = document.getElementById("ollamaChatbotNameInput");
    const modelSelect = document.getElementById("ollamaChatbotModelSelect");
    const apiKeyForm = document.getElementById("ollamaApiKeyForm");
    const apiKeySelect = document.getElementById("ollamaApiKeySelect");
    const loadApiKeyButton = document.getElementById("ollamaLoadApiKey");
    const settingsStatus = document.getElementById("ollamaSettingsStatus");
    const permissionsForm = document.getElementById("ollamaPermissionsForm");
    const readPermission = document.getElementById("ollamaAllowFolderRead");
    const writePermission = document.getElementById("ollamaAllowFolderWrite");
    const chooseFolderButton = document.getElementById("ollamaChooseFolder");
    const folderName = document.getElementById("ollamaFolderName");
    const fileNameInput = document.getElementById("ollamaFileName");
    const writeFileButton = document.getElementById("ollamaWriteFile");

    if (
        !(drawer instanceof HTMLElement) ||
        !(toggle instanceof HTMLButtonElement) ||
        !(hideButton instanceof HTMLButtonElement) ||
        !(endSessionButton instanceof HTMLButtonElement) ||
        !(newSessionButton instanceof HTMLButtonElement) ||
        !(dragHandle instanceof HTMLElement) ||
        !(resizeHandle instanceof HTMLElement) ||
        !(statusPanel instanceof HTMLElement) ||
        !(statusText instanceof HTMLElement) ||
        !(modelName instanceof HTMLElement) ||
        !(chatbotName instanceof HTMLElement) ||
        !(messagesPanel instanceof HTMLElement) ||
        !(form instanceof HTMLFormElement) ||
        !(input instanceof HTMLTextAreaElement) ||
        !(sendButton instanceof HTMLButtonElement) ||
        !(settingsForm instanceof HTMLFormElement) ||
        !(nameInput instanceof HTMLInputElement) ||
        !(modelSelect instanceof HTMLSelectElement) ||
        !(apiKeyForm instanceof HTMLFormElement) ||
        !(apiKeySelect instanceof HTMLSelectElement) ||
        !(loadApiKeyButton instanceof HTMLButtonElement) ||
        !(settingsStatus instanceof HTMLElement) ||
        !(permissionsForm instanceof HTMLFormElement) ||
        !(readPermission instanceof HTMLInputElement) ||
        !(writePermission instanceof HTMLInputElement) ||
        !(chooseFolderButton instanceof HTMLButtonElement) ||
        !(folderName instanceof HTMLElement) ||
        !(fileNameInput instanceof HTMLInputElement) ||
        !(writeFileButton instanceof HTMLButtonElement)
    ) {
        return;
    }

    const csrfInput = form.querySelector('input[name="csrf_token"]');
    if (!(csrfInput instanceof HTMLInputElement)) {
        return;
    }

    const canChat = drawer.dataset.verified === "true";
    const messages = [];
    let isSending = false;
    let sessionActive = false;
    let directoryHandle = null;
    let latestAssistantReply = "";
    let fileLoadTimer;
    let fileLoadGeneration = 0;
    let loadedFileContext = "";

    const setStatus = (state, message) => {
        statusPanel.dataset.state = state;
        statusText.textContent = message;
    };

    const appendMessage = (role, content) => {
        document.getElementById("ollamaChatEmpty")?.remove();
        const message = document.createElement("div");
        message.className = "ollama-chat-message";
        message.dataset.role = role;
        const messageContent = document.createElement("span");
        messageContent.className = "ollama-chat-message-content";
        messageContent.textContent = content;
        message.append(messageContent);
        if (role === "assistant") {
            const expandButton = document.createElement("button");
            expandButton.className = "ollama-message-expand";
            expandButton.type = "button";
            expandButton.textContent = "Expand response";
            expandButton.addEventListener("click", () => {
                expandedResponse.textContent = messageContent.textContent;
                expandedDialog.showModal();
            });
            message.append(expandButton);
        }
        messagesPanel.append(message);
        messagesPanel.scrollTop = messagesPanel.scrollHeight;
        return message;
    };

    const expandedDialog = document.createElement("dialog");
    expandedDialog.className = "ollama-expanded-response";
    const expandedCloseButton = document.createElement("button");
    expandedCloseButton.className = "ollama-expanded-response-close";
    expandedCloseButton.type = "button";
    expandedCloseButton.textContent = "Close";
    expandedCloseButton.addEventListener("click", () => expandedDialog.close());
    const expandedResponse = document.createElement("div");
    expandedResponse.className = "ollama-expanded-response-content";
    expandedDialog.append(expandedCloseButton, expandedResponse);
    document.body.append(expandedDialog);

    const clearMessages = () => {
        messages.length = 0;
        latestAssistantReply = "";
        messagesPanel.replaceChildren();
        const emptyState = document.createElement("p");
        emptyState.className = "ollama-chat-empty";
        emptyState.id = "ollamaChatEmpty";
        emptyState.textContent = "Ask Rover AI a question to get started.";
        messagesPanel.append(emptyState);
    };

    const setSessionActive = (active) => {
        sessionActive = active;
        input.disabled = !canChat || !active;
        sendButton.disabled = !canChat || !active;
        endSessionButton.disabled = !canChat || !active;
        newSessionButton.hidden = !canChat || active;
        settingsForm.querySelectorAll("input, select, button").forEach((control) => {
            control.disabled = !canChat || !active;
        });
        apiKeyForm.querySelectorAll("select, button").forEach((control) => {
            control.disabled = !canChat || !active;
        });
        permissionsForm.querySelectorAll("input, button").forEach((control) => {
            control.disabled = !canChat || !active;
        });
    };

    const setDrawerOpen = (open) => {
        drawer.classList.toggle("is-minimized", !open);
        toggle.setAttribute("aria-expanded", String(open));
        if (open && canChat) {
            window.setTimeout(() => input.focus(), 220);
            refreshStatus();
        } else if (!open) {
            toggle.focus();
        }
    };

    const updateModelOptions = (availableModels, preferredModel) => {
        const models = [...new Set(
            availableModels.filter((model) => typeof model === "string" && model),
        )];
        const previousModel = modelSelect.value;
        modelSelect.replaceChildren();

        if (models.length === 0) {
            const option = document.createElement("option");
            option.value = "";
            option.textContent = "No models currently available";
            option.disabled = true;
            option.selected = true;
            modelSelect.append(option);
            return "";
        }

        models.forEach((model) => {
            const option = document.createElement("option");
            option.value = model;
            option.textContent = model;
            modelSelect.append(option);
        });

        const selectedModel = models.includes(preferredModel)
            ? preferredModel
            : models.includes(previousModel)
                ? previousModel
                : models[0];
        modelSelect.value = selectedModel;
        return selectedModel;
    };

    const loadApiKeys = async () => {
        try {
            const response = await fetch(drawer.dataset.keysUrl, {
                credentials: "same-origin",
                headers: { Accept: "application/json" },
            });
            const result = await response.json();
            if (!response.ok) {
                throw new Error(result.error || "Could not load saved Ollama API keys.");
            }
            apiKeySelect.replaceChildren();
            const localOption = document.createElement("option");
            localOption.value = "";
            localOption.textContent = "No API key (local Ollama)";
            apiKeySelect.append(localOption);
            result.keys.forEach((key) => {
                const option = document.createElement("option");
                option.value = String(key.id);
                option.textContent = key.name;
                apiKeySelect.append(option);
            });
            apiKeySelect.value = result.active_api_key_id === null
                ? ""
                : String(result.active_api_key_id);
        } catch (error) {
            settingsStatus.textContent = error.message || "Could not load saved Ollama API keys.";
        }
    };

    const refreshStatus = async () => {
        try {
            const response = await fetch(drawer.dataset.statusUrl, {
                credentials: "same-origin",
                headers: { Accept: "application/json" },
            });
            const result = await response.json();
            modelName.textContent = result.model || "Not configured";
            if (Array.isArray(result.available_models)) {
                updateModelOptions(result.available_models, result.model);
            } else {
                updateModelOptions([], result.model);
            }
            setStatus(
                result.status || "offline",
                result.message || "Unable to check Ollama status.",
            );
            return result;
        } catch {
            setStatus("offline", "Could not reach Rover.");
            return null;
        }
    };

    const requestJson = async (url, body) => {
        const response = await fetch(url, {
            method: "POST",
            credentials: "same-origin",
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": csrfInput.value,
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

    const startSession = async () => {
        if (!canChat) {
            return;
        }
        newSessionButton.disabled = true;
        setStatus("checking", "Loading Rover AI session...");
        try {
            const response = await fetch(drawer.dataset.sessionUrl, {
                credentials: "same-origin",
                headers: { Accept: "application/json" },
            });
            const result = await response.json();
            if (!response.ok) {
                throw new Error(result.error || "Unable to start a Rover AI session.");
            }

            clearMessages();
            chatbotName.textContent = result.chatbot_name;
            nameInput.value = result.chatbot_name;
            modelName.textContent = result.model;
            modelSelect.value = result.model;
            readPermission.checked = result.permissions.read_folder;
            writePermission.checked = result.permissions.write_folder;
            result.messages.forEach((message) => {
                messages.push(message);
                appendMessage(message.role, message.content);
                if (message.role === "assistant") {
                    latestAssistantReply = message.content;
                }
            });
            setSessionActive(true);
            setStatus("ready", "Rover AI session is active.");
            loadApiKeys();
            refreshStatus();
        } catch (error) {
            setStatus("error", error.message);
            appendMessage("assistant", error.message);
            setSessionActive(false);
        } finally {
            newSessionButton.disabled = false;
        }
    };

    const resizeDrawer = (event) => {
        const width = window.innerWidth - event.clientX;
        if (width < 180) {
            setDrawerOpen(false);
            return;
        }

        const maximum = Math.min(window.innerWidth * 0.94, window.innerWidth - 24);
        drawer.style.setProperty(
            "--ollama-drawer-width",
            `${Math.max(300, Math.min(maximum, width))}px`,
        );
    };

    const validFileName = (name) =>
        name.length > 0 &&
        name.length <= 128 &&
        name !== "." &&
        name !== ".." &&
        !/[\\/]/.test(name) &&
        !name.includes("..") &&
        /\.md$/i.test(name);

    const getDirectoryPermission = async (mode) => {
        if (!directoryHandle) {
            throw new Error("Choose a folder for this page first.");
        }
        let permission = await directoryHandle.queryPermission({ mode });
        if (permission !== "granted") {
            permission = await directoryHandle.requestPermission({ mode });
        }
        if (permission !== "granted") {
            throw new Error("Folder permission was not granted.");
        }
    };

    const loadMarkdownFile = async () => {
        const generation = ++fileLoadGeneration;
        const fileName = fileNameInput.value.trim();
        if (!sessionActive || !readPermission.checked || !directoryHandle) {
            return;
        }
        if (!validFileName(fileName)) {
            settingsStatus.textContent = fileName
                ? "Enter a Markdown file name ending in .md."
                : "Choose a Markdown file name to load it automatically.";
            return;
        }

        try {
            await getDirectoryPermission("read");
            const fileHandle = await directoryHandle.getFileHandle(fileName);
            const file = await fileHandle.getFile();
            if (generation !== fileLoadGeneration || fileNameInput.value.trim() !== fileName) {
                return;
            }
            if (file.size > 64 * 1024) {
                throw new Error("Markdown files larger than 64 KB cannot be added to chat.");
            }

            const content = await file.text();
            if (generation !== fileLoadGeneration || fileNameInput.value.trim() !== fileName) {
                return;
            }
            if (loadedFileContext) {
                const contextStart = input.value.indexOf(loadedFileContext);
                if (contextStart !== -1) {
                    input.value =
                        input.value.slice(0, contextStart) +
                        input.value.slice(contextStart + loadedFileContext.length);
                }
            }
            const context = `\n\n[File context: ${fileName}]\n${content}`;
            if (input.value.length + context.length > 20_000) {
                throw new Error("That file would exceed the message size limit.");
            }
            input.value += context;
            loadedFileContext = context;
            settingsStatus.textContent = `${fileName} loaded into your draft. Review it before sending.`;
        } catch (error) {
            if (generation === fileLoadGeneration) {
                settingsStatus.textContent = error.message || `Could not load ${fileName}.`;
            }
        }
    };

    const scheduleMarkdownFileLoad = () => {
        window.clearTimeout(fileLoadTimer);
        if (!fileNameInput.value.trim()) {
            return;
        }
        fileLoadTimer = window.setTimeout(loadMarkdownFile, 600);
    };

    toggle.addEventListener("click", () => setDrawerOpen(true));
    hideButton.addEventListener("click", () => setDrawerOpen(false));
    newSessionButton.addEventListener("click", startSession);

    let dragStartX = null;
    dragHandle.addEventListener("pointerdown", (event) => {
        if (event.target instanceof HTMLButtonElement) {
            return;
        }
        dragStartX = event.clientX;
        dragHandle.setPointerCapture(event.pointerId);
    });

    dragHandle.addEventListener("pointermove", (event) => {
        if (dragStartX === null || !dragHandle.hasPointerCapture(event.pointerId)) {
            return;
        }
        const dragDistance = event.clientX - dragStartX;
        if (dragDistance > 80) {
            dragStartX = null;
            setDrawerOpen(false);
        } else if (dragDistance < -80) {
            const currentWidth = drawer.getBoundingClientRect().width;
            drawer.style.setProperty(
                "--ollama-drawer-width",
                `${Math.min(window.innerWidth * 0.94, currentWidth + Math.abs(dragDistance))}px`,
            );
            dragStartX = event.clientX;
        }
    });

    const stopDragging = (event) => {
        dragStartX = null;
        if (dragHandle.hasPointerCapture(event.pointerId)) {
            dragHandle.releasePointerCapture(event.pointerId);
        }
    };
    dragHandle.addEventListener("pointerup", stopDragging);
    dragHandle.addEventListener("pointercancel", stopDragging);

    resizeHandle.addEventListener("pointerdown", (event) => {
        if (drawer.classList.contains("is-minimized")) {
            return;
        }
        event.preventDefault();
        resizeHandle.setPointerCapture(event.pointerId);
        resizeDrawer(event);
    });
    resizeHandle.addEventListener("pointermove", (event) => {
        if (resizeHandle.hasPointerCapture(event.pointerId)) {
            resizeDrawer(event);
        }
    });

    const stopResizing = (event) => {
        if (resizeHandle.hasPointerCapture(event.pointerId)) {
            resizeHandle.releasePointerCapture(event.pointerId);
        }
    };
    resizeHandle.addEventListener("pointerup", stopResizing);
    resizeHandle.addEventListener("pointercancel", stopResizing);

    dragHandle.addEventListener("dblclick", () => {
        const currentWidth = drawer.getBoundingClientRect().width;
        const defaultWidth = Math.min(window.innerWidth * 0.84, window.innerWidth - 24);
        drawer.style.setProperty(
            "--ollama-drawer-width",
            `${currentWidth > defaultWidth + 20 ? defaultWidth : Math.min(window.innerWidth * 0.94, window.innerWidth - 24)}px`,
        );
    });

    apiKeyForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        if (!sessionActive) {
            return;
        }
        loadApiKeyButton.disabled = true;
        settingsStatus.textContent = "Loading saved Ollama API key...";
        const rawKeyId = apiKeySelect.value;
        try {
            const result = await requestJson(drawer.dataset.selectKeyUrl, {
                api_key_id: rawKeyId ? Number(rawKeyId) : null,
            });
            modelName.textContent = result.model;
            updateModelOptions(result.available_models, result.model);
            settingsStatus.textContent = result.api_key_name
                ? `${result.api_key_name} loaded into Rover AI.`
                : "Local Ollama selected.";
            setStatus("ready", "Ollama key and models loaded.");
        } catch (error) {
            settingsStatus.textContent = error.message;
        } finally {
            loadApiKeyButton.disabled = !sessionActive;
        }
    });

    settingsForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        if (!sessionActive) {
            return;
        }
        settingsStatus.textContent = "Saving chatbot settings...";
        try {
            const result = await requestJson(drawer.dataset.chatbotSettingsUrl, {
                name: nameInput.value.trim(),
                model: modelSelect.value,
            });
            chatbotName.textContent = result.name;
            modelName.textContent = result.model;
            settingsStatus.textContent = "Chatbot settings saved.";
            window.dispatchEvent(new CustomEvent("ollama-preferences-updated"));
        } catch (error) {
            settingsStatus.textContent = error.message;
        }
    });

    permissionsForm.addEventListener("change", async (event) => {
        if (!(event.target instanceof HTMLInputElement) || !sessionActive) {
            return;
        }
        const newValue = event.target.checked;
        const previousValue = !newValue;

        settingsStatus.textContent = "Saving folder permissions...";
        try {
            const result = await requestJson(drawer.dataset.permissionsUrl, {
                read_folder: readPermission.checked,
                write_folder: writePermission.checked,
            });
            readPermission.checked = result.read_folder;
            writePermission.checked = result.write_folder;
            if (!result.read_folder && !result.write_folder) {
                directoryHandle = null;
                folderName.textContent = "No folder selected for this page.";
            } else if (directoryHandle && previousValue !== newValue) {
                directoryHandle = null;
                folderName.textContent = "Choose the folder again to apply the updated permissions.";
            }
            settingsStatus.textContent = "Folder permissions saved.";
        } catch (error) {
            event.target.checked = previousValue;
            settingsStatus.textContent = error.message;
        }
    });

    chooseFolderButton.addEventListener("click", async () => {
        if (!readPermission.checked && !writePermission.checked) {
            settingsStatus.textContent = "Enable a folder permission before choosing a folder.";
            return;
        }
        if (typeof window.showDirectoryPicker !== "function") {
            settingsStatus.textContent = "Folder access requires a supported browser such as Chrome or Edge.";
            return;
        }
        try {
            const mode = writePermission.checked ? "readwrite" : "read";
            directoryHandle = await window.showDirectoryPicker({ mode });
            folderName.textContent = `Selected folder: ${directoryHandle.name} (available on this page only)`;
            settingsStatus.textContent = "Folder selected. Enter a .md file name to load it into your draft automatically.";
            await loadMarkdownFile();
        } catch (error) {
            if (error.name !== "AbortError") {
                settingsStatus.textContent = error.message || "Could not select that folder.";
            }
        }
    });

    fileNameInput.addEventListener("input", scheduleMarkdownFileLoad);

    writeFileButton.addEventListener("click", async () => {
        const fileName = fileNameInput.value.trim();
        if (!sessionActive || !writePermission.checked) {
            settingsStatus.textContent = "Enable selected-folder writing first.";
            return;
        }
        if (!validFileName(fileName)) {
            settingsStatus.textContent = "Enter a file name only; folder paths are not allowed.";
            return;
        }
        if (!latestAssistantReply) {
            settingsStatus.textContent = "There is no assistant reply to save yet.";
            return;
        }
        try {
            await getDirectoryPermission("readwrite");
            let exists = true;
            try {
                await directoryHandle.getFileHandle(fileName);
            } catch (error) {
                if (error.name !== "NotFoundError") {
                    throw error;
                }
                exists = false;
            }
            const action = exists ? "Overwrite" : "Create";
            if (!confirm(`${action} "${fileName}" in the selected folder with the latest Rover AI reply?`)) {
                return;
            }
            const fileHandle = await directoryHandle.getFileHandle(fileName, { create: true });
            const writable = await fileHandle.createWritable();
            await writable.write(latestAssistantReply);
            await writable.close();
            settingsStatus.textContent = `${fileName} saved in the selected folder.`;
        } catch (error) {
            settingsStatus.textContent = error.message || "Could not write to the selected file.";
        }
    });

    const readChatStream = async (response, messageElement) => {
        if (!response.ok) {
            const result = await response.json();
            throw new Error(result.error || "Ollama could not complete the request.");
        }
        if (!response.body) {
            throw new Error("The Rover response stream is unavailable.");
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";
        let fullMessage = "";
        let completed = false;

        const processLine = async (line) => {
            if (!line.trim()) {
                return;
            }
            let event;
            try {
                event = JSON.parse(line);
            } catch {
                throw new Error("Rover returned an invalid response stream.");
            }
            if (event.error) {
                throw new Error(event.error);
            }
            if (typeof event.token === "string") {
                fullMessage += event.token;
                for (const character of event.token) {
                    const content = messageElement.querySelector(
                        ".ollama-chat-message-content",
                    );
                    content.textContent += character;
                    messagesPanel.scrollTop = messagesPanel.scrollHeight;
                    await new Promise((resolve) => window.setTimeout(resolve, 6));
                }
            }
            if (event.done === true) {
                completed = true;
            }
        };

        while (true) {
            const { value, done } = await reader.read();
            buffer += decoder.decode(value || new Uint8Array(), { stream: !done });
            const lines = buffer.split("\n");
            buffer = lines.pop();
            for (const line of lines) {
                await processLine(line);
            }
            if (done) {
                break;
            }
        }
        if (buffer.trim()) {
            await processLine(buffer);
        }
        if (!completed || !fullMessage) {
            throw new Error("The response stream ended before Rover finished replying.");
        }
        return fullMessage;
    };

    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        const prompt = input.value.trim();
        if (!canChat || !sessionActive || !prompt || isSending) {
            return;
        }
        isSending = true;
        sendButton.disabled = true;
        input.disabled = true;
        appendMessage("user", prompt);
        messages.push({ role: "user", content: prompt });
        input.value = "";
        loadedFileContext = "";
        setStatus("busy", "Ollama is generating a response...");
        const assistantMessage = appendMessage("assistant", "");
        assistantMessage.classList.add("is-streaming");

        try {
            const response = await fetch(drawer.dataset.chatUrl, {
                method: "POST",
                credentials: "same-origin",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": csrfInput.value,
                    Accept: "application/x-ndjson",
                },
                body: JSON.stringify({ message: prompt }),
            });
            const assistantText = await readChatStream(response, assistantMessage);
            assistantMessage.classList.remove("is-streaming");
            messages.push({ role: "assistant", content: assistantText });
            latestAssistantReply = assistantText;
            setStatus("ready", "Model is ready.");
        } catch (error) {
            assistantMessage.classList.remove("is-streaming");
            messages.pop();
            appendMessage("assistant", error.message);
            setStatus("error", error.message);
        } finally {
            isSending = false;
            input.disabled = !sessionActive;
            sendButton.disabled = !sessionActive;
            input.focus();
        }
    });

    endSessionButton.addEventListener("click", async () => {
        if (!sessionActive || !confirm("End this session and permanently delete its chat history?")) {
            return;
        }
        endSessionButton.disabled = true;
        try {
            await requestJson(drawer.dataset.endSessionUrl, {});
            clearMessages();
            directoryHandle = null;
            folderName.textContent = "No folder selected for this page.";
            settingsStatus.textContent = "";
            appendMessage("assistant", "Session ended. Start a new session to continue.");
            setSessionActive(false);
            setStatus("ready", "Session ended.");
        } catch (error) {
            settingsStatus.textContent = error.message;
            endSessionButton.disabled = false;
        }
    });

    if (!canChat) {
        modelName.textContent = "Unavailable";
        setStatus("error", "Verify your account to use Rover AI.");
        setSessionActive(false);
        appendMessage("assistant", "Verify your account to enable Rover AI chat.");
    } else {
        setSessionActive(false);
        startSession();
        const statusPoll = window.setInterval(() => {
            if (!drawer.classList.contains("is-minimized") && !isSending) {
                refreshStatus();
            }
        }, 30_000);
        window.addEventListener(
            "beforeunload",
            () => window.clearInterval(statusPoll),
            { once: true },
        );
        window.addEventListener("ollama-preferences-updated", async (event) => {
            const result = await refreshStatus();
            if (!event.detail?.apiKeySaved || !result?.available_models?.length) {
                return;
            }

            if (modelSelect.value === result.model) {
                settingsStatus.textContent = "Ollama API key connected to Rover AI.";
                return;
            }

            try {
                const saved = await requestJson(drawer.dataset.chatbotSettingsUrl, {
                    name: nameInput.value.trim() || "Rover AI",
                    model: modelSelect.value,
                });
                chatbotName.textContent = saved.name;
                modelName.textContent = saved.model;
                settingsStatus.textContent = `Ollama API key connected. ${saved.model} is ready.`;
            } catch (error) {
                settingsStatus.textContent = error.message;
            }
        });
    }
}

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initializeOllamaDrawer, { once: true });
} else {
    initializeOllamaDrawer();
}
