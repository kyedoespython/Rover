function initializeOllamaDrawer() {
    const drawer = document.getElementById("ollamaDrawer");
    const toggle = document.getElementById("ollamaDrawerToggle");
    const hideButton = document.getElementById("ollamaMinimize");
    const endSessionButton = document.getElementById("ollamaEndSession");
    const newSessionButton = document.getElementById("ollamaNewSession");
    const dragHandle = document.getElementById("ollamaDrawerDragHandle");
    const resizeHandle = document.getElementById("ollamaResizeHandle");
    const heightResizeHandle = document.getElementById("ollamaHeightResizeHandle");
    const inputResizeHandle = document.getElementById("ollamaInputResizeHandle");
    const statusPanel = document.getElementById("ollamaAssistantStatus");
    const statusText = document.getElementById("ollamaStatusText");
    const modelName = document.getElementById("ollamaModelName");
    const chatbotName = document.getElementById("ollamaChatbotName");
    const messagesPanel = document.getElementById("ollamaChatMessages");
    const form = document.getElementById("ollamaChatForm");
    const input = document.getElementById("ollamaChatInput");
    const sendButton = document.getElementById("ollamaChatSend");
    const modelTrigger = document.getElementById("roverModelTrigger");
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
    const folderStatus = document.getElementById("ollamaFolderStatus");
    const fileNameInput = document.getElementById("ollamaFileName");
    const writeFileButton = document.getElementById("ollamaWriteFile");
    const attachFolderFileButton = document.getElementById("ollamaAttachFolderFile");
    const fileInput = document.getElementById("ollamaFileInput");
    const fileList = document.getElementById("ollamaFileList");
    const fileStatus = document.getElementById("ollamaFileStatus");

    if (
        !(drawer instanceof HTMLElement) ||
        !(toggle instanceof HTMLButtonElement) ||
        !(hideButton instanceof HTMLButtonElement) ||
        !(endSessionButton instanceof HTMLButtonElement) ||
        !(newSessionButton instanceof HTMLButtonElement) ||
        !(dragHandle instanceof HTMLElement) ||
        !(resizeHandle instanceof HTMLElement) ||
        !(heightResizeHandle instanceof HTMLElement) ||
        !(inputResizeHandle instanceof HTMLElement) ||
        !(statusPanel instanceof HTMLElement) ||
        !(statusText instanceof HTMLElement) ||
        !(modelName instanceof HTMLElement) ||
        !(chatbotName instanceof HTMLElement) ||
        !(messagesPanel instanceof HTMLElement) ||
        !(form instanceof HTMLFormElement) ||
        !(input instanceof HTMLTextAreaElement) ||
        !(sendButton instanceof HTMLButtonElement) ||
        !(modelTrigger instanceof HTMLButtonElement) ||
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
        !(folderStatus instanceof HTMLElement) ||
        !(fileNameInput instanceof HTMLInputElement) ||
        !(writeFileButton instanceof HTMLButtonElement) ||
        !(attachFolderFileButton instanceof HTMLButtonElement) ||
        !(fileInput instanceof HTMLInputElement) ||
        !(fileList instanceof HTMLElement) ||
        !(fileStatus instanceof HTMLElement)
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
    let chatError = false;
    let activeProvider = "unselected";
    let isSelectingModel = false;
    let isSavingSettings = false;
    let statusRequestId = 0;
    let modelMenuRequestId = 0;
    let sessionActive = false;
    let directoryHandle = null;
    let latestAssistantReply = "";

    const modelMenu = document.createElement("div");
    modelMenu.id = "roverModelMenu";
    modelMenu.className = "ollama-model-menu";
    modelMenu.setAttribute("role", "dialog");
    modelMenu.setAttribute("aria-label", "Choose an AI model");
    modelMenu.tabIndex = -1;
    modelMenu.hidden = true;
    document.body.append(modelMenu);

    const closeModelMenu = (restoreFocus = false) => {
        modelMenu.hidden = true;
        modelMenuRequestId += 1;
        modelTrigger.setAttribute("aria-expanded", "false");
        if (restoreFocus && !modelTrigger.disabled) {
            modelTrigger.focus();
        }
    };

    const positionModelMenu = () => {
        const bounds = modelTrigger.getBoundingClientRect();
        const width = Math.min(320, window.innerWidth - 24);
        modelMenu.style.left = `${Math.max(12, Math.min(bounds.left, window.innerWidth - width - 12))}px`;
        modelMenu.style.bottom = `${Math.max(12, window.innerHeight - bounds.top + 6)}px`;
        modelMenu.style.maxHeight = `${Math.min(window.innerHeight * 0.55, Math.max(100, bounds.top - 20))}px`;
    };

    const setStatus = (state, message) => {
        statusPanel.dataset.state = state;
        statusPanel.hidden = state === "ready";
        statusText.textContent = message;
    };

    const addExpandButton = (message, messageContent) => {
        const expandButton = document.createElement("button");
        expandButton.className = "ollama-message-expand";
        expandButton.type = "button";
        expandButton.textContent = "Expand response";
        expandButton.addEventListener("click", () => {
            expandedResponse.textContent = messageContent.textContent;
            expandedDialog.showModal();
        });
        message.append(expandButton);
    };

    const appendMessage = (role, content, expandable = role === "assistant") => {
        document.getElementById("ollamaChatEmpty")?.remove();
        const message = document.createElement("div");
        message.className = "ollama-chat-message";
        message.dataset.role = role;
        const messageContent = document.createElement("span");
        messageContent.className = "ollama-chat-message-content";
        messageContent.textContent = content;
        message.append(messageContent);
        if (expandable && content) {
            addExpandButton(message, messageContent);
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
        input.disabled = !canChat || !active || isSending || isSelectingModel || isSavingSettings;
        sendButton.disabled = !canChat || !active || isSending || isSelectingModel || isSavingSettings || activeProvider === "unselected";
        modelTrigger.disabled = !canChat || !active || isSending || isSelectingModel || isSavingSettings;
        endSessionButton.disabled = !canChat || !active || isSending || isSelectingModel || isSavingSettings;
        newSessionButton.hidden = !canChat || active;
        settingsForm.querySelectorAll("input, select, button").forEach((control) => {
            control.disabled = !canChat || !active || isSending || isSelectingModel || isSavingSettings || activeProvider === "unselected";
        });
        apiKeyForm.querySelectorAll("select, button").forEach((control) => {
            control.disabled = !canChat || !active || isSending || isSelectingModel || isSavingSettings;
        });
        permissionsForm.querySelectorAll("input, button").forEach((control) => {
            control.disabled = !canChat || !active;
        });
        if (!active) {
            closeModelMenu();
        }
    };

    const setDrawerOpen = (open) => {
        drawer.classList.toggle("is-minimized", !open);
        toggle.setAttribute("aria-expanded", String(open));
        if (open && canChat) {
            window.setTimeout(() => input.focus(), 220);
            refreshStatus();
        } else if (!open) {
            closeModelMenu();
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

    let apiKeysRequestId = 0;
    let modelSources = [];
    const sourceValue = (source) => `${source.provider}:${source.key_id === null ? "local" : source.key_id}`;
    const loadApiKeys = async (preferActive = false) => {
        const requestId = ++apiKeysRequestId;
        try {
            const response = await fetch(drawer.dataset.modelSourcesUrl, {
                credentials: "same-origin",
                headers: { Accept: "application/json" },
                cache: "no-store",
            });
            const result = await response.json();
            if (requestId !== apiKeysRequestId) {
                return;
            }
            if (!response.ok) {
                throw new Error(result.error || "Could not load model providers.");
            }
            const previousValue = apiKeySelect.value;
            modelSources = result.sources;
            apiKeySelect.replaceChildren();
            const placeholder = document.createElement("option");
            placeholder.value = "";
            placeholder.textContent = "Choose a provider or API key";
            apiKeySelect.append(placeholder);
            modelSources.forEach((source) => {
                const option = document.createElement("option");
                option.value = sourceValue(source);
                const provider = source.provider === "gemini" ? "Google Gemini" : "Ollama";
                option.textContent = `${provider} · ${source.name}`;
                if (source.unavailable_reason) {
                    option.disabled = true;
                    option.textContent += " (requires Ollama Cloud)";
                }
                apiKeySelect.append(option);
            });
            const active = modelSources.find((source) => source.active);
            const previous = modelSources.find((source) => sourceValue(source) === previousValue && !source.unavailable_reason);
            apiKeySelect.value = sourceValueOrEmpty(preferActive ? active : previous || active);
        } catch (error) {
            if (requestId === apiKeysRequestId) {
                settingsStatus.textContent = error instanceof SyntaxError
                    ? "Could not load model providers. Please check your connection and sign-in."
                    : error.message || "Could not load model providers.";
            }
        }
    };
    const sourceValueOrEmpty = (source) => source ? sourceValue(source) : "";

    const getSourceModels = async (source) => {
        const sourceId = source.key_id === null ? "local" : String(source.key_id);
        const url = drawer.dataset.modelSourceUrl
            .replace("PROVIDER", encodeURIComponent(source.provider))
            .replace("SOURCE", encodeURIComponent(sourceId));
        const response = await fetch(url, {
            credentials: "same-origin", headers: { Accept: "application/json" }, cache: "no-store",
        });
        const data = await response.json();
        if (!response.ok) {
            throw new Error(data.error || "Could not load models.");
        }
        return data.models;
    };

    const saveModelSelection = (source, model) => requestJson(
        source.provider === "gemini" ? drawer.dataset.geminiPreferencesUrl : drawer.dataset.ollamaPreferencesUrl,
        { model, api_key_id: source.key_id },
    );

    const refreshStatus = async () => {
        const requestId = ++statusRequestId;
        try {
            const response = await fetch(drawer.dataset.statusUrl, {
                credentials: "same-origin",
                headers: { Accept: "application/json" },
            });
            const result = await response.json();
            if (requestId !== statusRequestId || isSelectingModel || isSavingSettings) {
                return null;
            }
            activeProvider = result.provider || activeProvider;
            modelName.textContent = result.model || "Not selected";
            setSessionActive(sessionActive);
            if (Array.isArray(result.available_models)) {
                updateModelOptions(result.available_models, result.model);
            } else {
                updateModelOptions([], result.model);
            }
            if (requestId === statusRequestId && !isSelectingModel && !isSavingSettings && !isSending && !chatError) {
                setStatus(
                    result.status || "offline",
                    result.message || "Unable to check Ollama status.",
                );
            }
            return result;
        } catch {
            if (requestId === statusRequestId && !isSelectingModel && !isSavingSettings && !isSending && !chatError) {
                setStatus("offline", "Could not reach Rover.");
            }
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

    const loadModelMenu = async () => {
        const requestId = ++modelMenuRequestId;
        modelMenu.replaceChildren();
        const title = document.createElement("strong");
        title.textContent = "Choose a model";
        const notice = document.createElement("p");
        notice.className = "ollama-model-menu-status";
        notice.textContent = "Chat history and checked files are sent to the selected provider.";
        const loading = document.createElement("p");
        loading.className = "ollama-model-menu-status";
        loading.textContent = "Loading integrations...";
        modelMenu.append(title, notice, loading);
        try {
            const response = await fetch(drawer.dataset.modelSourcesUrl, {
                credentials: "same-origin", headers: { Accept: "application/json" }, cache: "no-store",
            });
            const result = await response.json();
            if (!response.ok) {
                throw new Error(result.error || "Could not load integrations.");
            }
            if (requestId !== modelMenuRequestId) {
                return;
            }
            loading.remove();
            if (!result.sources.length) {
                const empty = document.createElement("p");
                empty.className = "ollama-model-menu-status";
                empty.textContent = "No integrations available. Add an API key in the design dashboard.";
                modelMenu.append(empty);
                return;
            }
            result.sources.forEach(async (source) => {
                const group = document.createElement("section");
                const heading = document.createElement("p");
                heading.className = "ollama-model-heading";
                heading.textContent = `${source.provider === "gemini" ? "Google Gemini" : "Ollama"} · ${source.name}`;
                const status = document.createElement("p");
                status.className = "ollama-model-menu-status";
                status.setAttribute("role", "status");
                status.textContent = "Loading models...";
                group.append(heading, status);
                modelMenu.append(group);
                if (source.unavailable_reason) {
                    status.textContent = source.unavailable_reason;
                    return;
                }
                try {
                    const models = await getSourceModels(source);
                    if (requestId !== modelMenuRequestId) {
                        return;
                    }
                    if (!models.length) {
                        status.textContent = "No models available.";
                        return;
                    }
                    status.remove();
                    models.forEach((name) => {
                        const button = document.createElement("button");
                        button.type = "button";
                        button.textContent = name;
                        if (source.active && name === modelName.textContent) {
                            button.setAttribute("aria-current", "true");
                            button.textContent += " ✓";
                        }
                        button.addEventListener("click", async () => {
                            if (isSelectingModel || isSending || isSavingSettings || !sessionActive) {
                                return;
                            }
                            isSelectingModel = true;
                            statusRequestId += 1;
                            setSessionActive(true);
                            group.append(status);
                            delete status.dataset.error;
                            status.textContent = "Selecting model...";
                            let selected = false;
                            try {
                                const result = await saveModelSelection(source, name);
                                activeProvider = source.provider;
                                chatError = false;
                                modelName.textContent = result.model;
                                settingsStatus.textContent = "";
                                closeModelMenu();
                                setStatus("ready", `${result.model} selected.`);
                                loadApiKeys(true);
                                selected = true;
                            } catch (error) {
                                status.dataset.error = "true";
                                status.textContent = error instanceof SyntaxError
                                    ? "Could not select the model. Please check your connection and sign-in."
                                    : error.message || "Could not select the model.";
                                if (modelMenu.hidden) {
                                    setStatus("error", status.textContent);
                                }
                            } finally {
                                isSelectingModel = false;
                                setSessionActive(sessionActive);
                                if (selected) {
                                    modelTrigger.focus();
                                    refreshStatus();
                                }
                            }
                        });
                        group.append(button);
                    });
                } catch (error) {
                    if (requestId === modelMenuRequestId) {
                        status.dataset.error = "true";
                        status.textContent = error instanceof SyntaxError
                            ? "Could not load models. Please check your connection and sign-in."
                            : error.message || "Could not load models.";
                    }
                }
            });
        } catch (error) {
            if (requestId === modelMenuRequestId) {
                loading.dataset.error = "true";
                loading.textContent = error instanceof SyntaxError
                    ? "Could not load integrations. Please check your connection and sign-in."
                    : error.message || "Could not load integrations.";
            }
        }
    };

    modelTrigger.addEventListener("click", () => {
        if (!modelMenu.hidden) {
            closeModelMenu();
            return;
        }
        positionModelMenu();
        modelMenu.hidden = false;
        modelTrigger.setAttribute("aria-expanded", "true");
        loadModelMenu();
        modelMenu.focus();
    });
    document.addEventListener("click", (event) => {
        if (!isSelectingModel && !modelMenu.hidden && !modelMenu.contains(event.target) && !modelTrigger.contains(event.target)) {
            closeModelMenu();
        }
    });
    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape" && !isSelectingModel && !modelMenu.hidden) {
            event.preventDefault();
            closeModelMenu(true);
        }
    });
    window.addEventListener("resize", () => {
        if (!modelMenu.hidden) {
            positionModelMenu();
        }
    });
    document.addEventListener("scroll", () => {
        if (!modelMenu.hidden) {
            positionModelMenu();
        }
    }, true);

    let filesRequestId = 0;
    const loadSavedFiles = async (newFileId = null) => {
        const requestId = ++filesRequestId;
        const response = await fetch(drawer.dataset.filesUrl, {
            credentials: "same-origin",
            headers: { Accept: "application/json" },
            cache: "no-store",
        });
        const result = await response.json();
        if (requestId !== filesRequestId) {
            return;
        }
        if (!response.ok) {
            throw new Error(result.error || "Could not load saved files.");
        }
        const selected = new Set(
            [...fileList.querySelectorAll('input[type="checkbox"]:checked')].map((item) => item.value),
        );
        if (newFileId) {
            selected.add(newFileId);
        }
        fileList.replaceChildren();
        result.files.forEach((file) => {
            const row = document.createElement("div");
            row.className = "ollama-file-item";
            const label = document.createElement("label");
            const checkbox = document.createElement("input");
            checkbox.type = "checkbox";
            checkbox.value = file.id;
            checkbox.checked = selected.has(file.id);
            label.append(checkbox, document.createTextNode(` ${file.name}`));
            const deleteButton = document.createElement("button");
            deleteButton.type = "button";
            deleteButton.className = "ollama-file-delete";
            deleteButton.textContent = "Delete";
            deleteButton.setAttribute("aria-label", `Delete ${file.name}`);
            deleteButton.addEventListener("click", async () => {
                if (!confirm(`Delete the encrypted copy of "${file.name}" from Rover?`)) {
                    return;
                }
                deleteButton.disabled = true;
                try {
                    const response = await fetch(`${drawer.dataset.filesUrl}/${encodeURIComponent(file.id)}`, {
                        method: "DELETE",
                        credentials: "same-origin",
                        headers: { "X-CSRFToken": csrfInput.value, Accept: "application/json" },
                    });
                    const result = await response.json();
                    if (!response.ok) {
                        throw new Error(result.error || "Could not delete the file.");
                    }
                    filesRequestId += 1;
                    row.remove();
                    fileStatus.textContent = "Encrypted file deleted.";
                } catch (error) {
                    fileStatus.textContent = error.message || "Could not delete the file.";
                    deleteButton.disabled = false;
                }
            });
            row.append(label, deleteButton);
            fileList.append(row);
        });
    };

    const uploadFile = async (file) => {
        if (file.size > 64 * 1024) {
            throw new Error("Files must be 64 KB or smaller.");
        }
        let content;
        try {
            content = new TextDecoder("utf-8", { fatal: true, ignoreBOM: true }).decode(await file.arrayBuffer());
        } catch (error) {
            if (error instanceof TypeError) {
                throw new Error("The file must contain valid UTF-8 text.");
            }
            throw error;
        }
        const result = await requestJson(drawer.dataset.filesUrl, { name: file.name, content });
        try {
            await loadSavedFiles(result.file.id);
        } catch (error) {
            throw new Error(`File saved, but the list could not be refreshed: ${error.message}`);
        }
    };

    let uploadingFiles = false;
    const uploadFiles = async (files, errors = []) => {
        if (!canChat) {
            fileStatus.textContent = "Verify your account to add files.";
            return;
        }
        if (uploadingFiles) {
            fileStatus.textContent = "Wait for the current files to finish saving.";
            return;
        }
        if (!files.length && !errors.length) {
            return;
        }
        uploadingFiles = true;
        fileInput.disabled = true;
        fileStatus.textContent = "Saving encrypted files...";
        let saved = 0;
        try {
            for (const file of files) {
                try {
                    await uploadFile(file);
                    saved += 1;
                } catch (error) {
                    errors.push(`${file.name}: ${error.message || "Could not save the file."}`);
                }
            }
            const summary = saved ? `${saved} file${saved === 1 ? "" : "s"} encrypted and saved.` : "";
            fileStatus.textContent = [summary, ...errors].filter(Boolean).join(" ");
        } finally {
            fileInput.value = "";
            fileInput.disabled = !canChat;
            uploadingFiles = false;
        }
    };

    fileInput.addEventListener("change", () => {
        uploadFiles([...fileInput.files]);
    });

    drawer.addEventListener("dragover", (event) => {
        if (!event.dataTransfer?.types.includes("Files")) {
            return;
        }
        event.preventDefault();
        event.dataTransfer.dropEffect = canChat && !uploadingFiles ? "copy" : "none";
        form.classList.add("is-drag-over");
    });
    drawer.addEventListener("dragleave", (event) => {
        if (!drawer.contains(event.relatedTarget)) {
            form.classList.remove("is-drag-over");
        }
    });
    drawer.addEventListener("drop", (event) => {
        if (!event.dataTransfer?.types.includes("Files")) {
            return;
        }
        event.preventDefault();
        form.classList.remove("is-drag-over");
        const files = [];
        const errors = [];
        const items = [...event.dataTransfer.items].filter((item) => item.kind === "file");
        if (items.length) {
            items.forEach((item) => {
                const entry = item.webkitGetAsEntry?.();
                if (entry?.isDirectory) {
                    errors.push(`${entry.name}: Drop individual files, not folders.`);
                    return;
                }
                const file = item.getAsFile();
                if (file) {
                    files.push(file);
                } else {
                    errors.push("Could not read one of the dropped files.");
                }
            });
        } else {
            files.push(...event.dataTransfer.files);
        }
        uploadFiles(files, errors);
    });

    const startSession = async () => {
        if (!canChat) {
            return;
        }
        newSessionButton.disabled = true;
        chatError = false;
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
            activeProvider = result.provider || "unselected";
            nameInput.value = result.chatbot_name;
            modelName.textContent = result.model || "Not selected";
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
            appendMessage("assistant", error.message, false);
            setSessionActive(false);
        } finally {
            newSessionButton.disabled = false;
        }
    };

    const resizeDrawer = (event) => {
        const width = drawer.getBoundingClientRect().right - event.clientX;
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

    const validFolderFileName = (name) =>
        name.length > 0 &&
        name.length <= 128 &&
        name !== "." &&
        name !== ".." &&
        !/[\\/]/.test(name) &&
        !name.includes("..");

    const validFileName = (name) => validFolderFileName(name) && /\.md$/i.test(name);

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

    attachFolderFileButton.addEventListener("click", async () => {
        const fileName = fileNameInput.value.trim();
        if (!sessionActive || !readPermission.checked || !directoryHandle) {
            folderStatus.textContent = "Enable folder reading and choose a working folder first.";
            return;
        }
        if (!validFolderFileName(fileName)) {
            folderStatus.textContent = "Enter a file name only; folder paths are not allowed.";
            return;
        }
        attachFolderFileButton.disabled = true;
        folderStatus.textContent = "Saving encrypted file...";
        try {
            await getDirectoryPermission("read");
            const fileHandle = await directoryHandle.getFileHandle(fileName);
            const file = await fileHandle.getFile();
            await uploadFile(file);
            folderStatus.textContent = `${fileName} encrypted and added to Rover AI.`;
        } catch (error) {
            folderStatus.textContent = error.message || "Could not add that file.";
        } finally {
            attachFolderFileButton.disabled = !sessionActive;
        }
    });

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

    const drawerHeightBounds = () => {
        const mobile = window.matchMedia("(max-width: 600px)").matches;
        const rect = drawer.getBoundingClientRect();
        const maximum = Math.max(0, window.innerHeight - (mobile ? 24 : rect.top + 12));
        const minimum = Math.min(320, maximum);
        return { minimum, maximum };
    };

    const updateHeightHandle = (height) => {
        const { minimum, maximum } = drawerHeightBounds();
        heightResizeHandle.setAttribute("aria-valuemin", String(Math.round(minimum)));
        heightResizeHandle.setAttribute("aria-valuemax", String(Math.round(maximum)));
        heightResizeHandle.setAttribute("aria-valuenow", String(Math.round(height)));
    };

    const setDrawerHeight = (height) => {
        const { minimum, maximum } = drawerHeightBounds();
        const nextHeight = Math.max(minimum, Math.min(maximum, height));
        drawer.style.height = `${nextHeight}px`;
        updateHeightHandle(nextHeight);
    };

    const resizeDrawerHeight = (event) => {
        const rect = drawer.getBoundingClientRect();
        const mobile = window.matchMedia("(max-width: 600px)").matches;
        setDrawerHeight(mobile ? rect.bottom - event.clientY : event.clientY - rect.top);
    };

    heightResizeHandle.addEventListener("pointerdown", (event) => {
        if (drawer.classList.contains("is-minimized")) {
            return;
        }
        event.preventDefault();
        heightResizeHandle.setPointerCapture(event.pointerId);
        resizeDrawerHeight(event);
    });
    heightResizeHandle.addEventListener("pointermove", (event) => {
        if (heightResizeHandle.hasPointerCapture(event.pointerId)) {
            resizeDrawerHeight(event);
        }
    });
    const stopHeightResizing = (event) => {
        if (heightResizeHandle.hasPointerCapture(event.pointerId)) {
            heightResizeHandle.releasePointerCapture(event.pointerId);
        }
    };
    heightResizeHandle.addEventListener("pointerup", stopHeightResizing);
    heightResizeHandle.addEventListener("pointercancel", stopHeightResizing);
    heightResizeHandle.addEventListener("keydown", (event) => {
        if (event.key !== "ArrowUp" && event.key !== "ArrowDown") {
            return;
        }
        event.preventDefault();
        const mobile = window.matchMedia("(max-width: 600px)").matches;
        const direction = event.key === "ArrowDown" ? 1 : -1;
        setDrawerHeight(drawer.getBoundingClientRect().height + direction * (mobile ? -20 : 20));
    });

    const updateInputResizeHandle = () => {
        const style = window.getComputedStyle(input);
        const minimum = parseFloat(style.minHeight);
        const maximum = Math.max(minimum, parseFloat(style.maxHeight));
        inputResizeHandle.setAttribute("aria-valuemin", String(Math.round(minimum)));
        inputResizeHandle.setAttribute("aria-valuemax", String(Math.round(maximum)));
        inputResizeHandle.setAttribute("aria-valuenow", String(Math.round(input.getBoundingClientRect().height)));
    };
    const setInputHeight = (height) => {
        const style = window.getComputedStyle(input);
        const minimum = parseFloat(style.minHeight);
        const maximum = Math.max(minimum, parseFloat(style.maxHeight));
        input.style.height = `${Math.max(minimum, Math.min(maximum, height))}px`;
        updateInputResizeHandle();
    };
    let inputResizeStart = null;
    inputResizeHandle.addEventListener("pointerdown", (event) => {
        event.preventDefault();
        inputResizeStart = { y: event.clientY, height: input.getBoundingClientRect().height };
        inputResizeHandle.setPointerCapture(event.pointerId);
    });
    inputResizeHandle.addEventListener("pointermove", (event) => {
        if (inputResizeStart && inputResizeHandle.hasPointerCapture(event.pointerId)) {
            setInputHeight(inputResizeStart.height + event.clientY - inputResizeStart.y);
        }
    });
    const stopInputResizing = (event) => {
        inputResizeStart = null;
        if (inputResizeHandle.hasPointerCapture(event.pointerId)) {
            inputResizeHandle.releasePointerCapture(event.pointerId);
        }
    };
    inputResizeHandle.addEventListener("pointerup", stopInputResizing);
    inputResizeHandle.addEventListener("pointercancel", stopInputResizing);
    inputResizeHandle.addEventListener("keydown", (event) => {
        if (event.key !== "ArrowUp" && event.key !== "ArrowDown") {
            return;
        }
        event.preventDefault();
        setInputHeight(input.getBoundingClientRect().height + (event.key === "ArrowDown" ? 20 : -20));
    });
    updateInputResizeHandle();
    updateHeightHandle(drawer.getBoundingClientRect().height);
    window.addEventListener("resize", () => {
        setInputHeight(input.getBoundingClientRect().height);
        const height = drawer.getBoundingClientRect().height;
        if (drawer.style.height) {
            setDrawerHeight(height);
        } else {
            updateHeightHandle(height);
        }
    });

    dragHandle.addEventListener("dblclick", () => {
        const currentWidth = drawer.getBoundingClientRect().width;
        const defaultWidth = window.innerWidth <= 600
            ? window.innerWidth - 24
            : Math.min(420, window.innerWidth - 24);
        drawer.style.setProperty(
            "--ollama-drawer-width",
            `${currentWidth > defaultWidth + 20 ? defaultWidth : Math.min(window.innerWidth * 0.94, window.innerWidth - 24)}px`,
        );
    });

    apiKeyForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        if (!sessionActive || isSavingSettings || isSending || isSelectingModel) {
            return;
        }
        isSavingSettings = true;
        closeModelMenu();
        setSessionActive(true);
        settingsStatus.textContent = "Loading models...";
        statusRequestId += 1;
        try {
            const source = modelSources.find((item) => sourceValue(item) === apiKeySelect.value);
            if (!source || source.unavailable_reason) {
                throw new Error("Choose an available provider or API key.");
            }
            const models = await getSourceModels(source);
            if (!models.length) {
                throw new Error("No models are available for this provider.");
            }
            const model = source.active && models.includes(modelName.textContent)
                ? modelName.textContent : models[0];
            const result = await saveModelSelection(source, model);
            activeProvider = source.provider;
            chatError = false;
            modelName.textContent = result.model;
            updateModelOptions(models, result.model);
            settingsStatus.textContent = `${source.name} loaded. ${result.model} is selected.`;
            setStatus("ready", "Models loaded.");
            loadApiKeys(true);
        } catch (error) {
            settingsStatus.textContent = error instanceof SyntaxError
                ? "Could not load models. Please check your connection and sign-in."
                : error.message || "Could not load models.";
        } finally {
            isSavingSettings = false;
            setSessionActive(sessionActive);
        }
    });

    settingsForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        if (!sessionActive || isSavingSettings || isSending || isSelectingModel) {
            return;
        }
        isSavingSettings = true;
        closeModelMenu();
        setSessionActive(true);
        settingsStatus.textContent = "Saving chatbot settings...";
        try {
            const result = await requestJson(drawer.dataset.chatbotSettingsUrl, {
                name: nameInput.value.trim(),
                model: modelSelect.value,
            });
            chatError = false;
            chatbotName.textContent = result.name;
            modelName.textContent = result.model;
            settingsStatus.textContent = "Chatbot settings saved.";
            window.dispatchEvent(new CustomEvent("ollama-preferences-updated"));
        } catch (error) {
            settingsStatus.textContent = error.message;
        } finally {
            isSavingSettings = false;
            setSessionActive(sessionActive);
        }
    });

    permissionsForm.addEventListener("change", async (event) => {
        if ((event.target !== readPermission && event.target !== writePermission) || !sessionActive) {
            return;
        }
        const newValue = event.target.checked;
        const previousValue = !newValue;
        const controls = [readPermission, writePermission, chooseFolderButton, attachFolderFileButton, writeFileButton];
        controls.forEach((control) => { control.disabled = true; });

        folderStatus.textContent = "Saving folder permissions...";
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
            }
            folderStatus.textContent = "Folder permissions saved.";
        } catch (error) {
            event.target.checked = previousValue;
            folderStatus.textContent = error.message || "Could not save folder permissions.";
        } finally {
            controls.forEach((control) => { control.disabled = !sessionActive; });
        }
    });

    chooseFolderButton.addEventListener("click", async () => {
        if (typeof window.showDirectoryPicker !== "function") {
            folderStatus.textContent = "Folder access requires a secure context (HTTPS or localhost) and a supported browser such as Chrome or Edge.";
            return;
        }
        try {
            const mode = writePermission.checked ? "readwrite" : "read";
            directoryHandle = await window.showDirectoryPicker({ mode });
            folderName.textContent = `Selected folder: ${directoryHandle.name} (available on this page only)`;
            folderStatus.textContent = readPermission.checked || writePermission.checked
                ? "Folder selected. Enter a file name to use it."
                : "Folder selected. Enable reading or writing to use it.";
        } catch (error) {
            if (error.name !== "AbortError") {
                folderStatus.textContent = error.message || "Could not select that folder.";
            }
        }
    });

    writeFileButton.addEventListener("click", async () => {
        const fileName = fileNameInput.value.trim();
        if (!sessionActive || !writePermission.checked) {
            folderStatus.textContent = "Enable selected-folder writing first.";
            return;
        }
        if (!validFileName(fileName)) {
            folderStatus.textContent = "Enter a file name only; folder paths are not allowed.";
            return;
        }
        if (!latestAssistantReply) {
            folderStatus.textContent = "There is no assistant reply to save yet.";
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
            folderStatus.textContent = `${fileName} saved in the selected folder.`;
        } catch (error) {
            folderStatus.textContent = error.message || "Could not write to the selected file.";
        }
    });

    const readChatStream = async (response, messageElement) => {
        if (!response.ok) {
            let result;
            try {
                result = await response.json();
            } catch {
                throw new Error(`Rover could not complete the request (HTTP ${response.status}).`);
            }
            throw new Error(
                typeof result?.error === "string" && result.error
                    ? result.error
                    : `Rover could not complete the request (HTTP ${response.status}).`,
            );
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
        if (!canChat || !sessionActive || !prompt || isSending || isSelectingModel || isSavingSettings || activeProvider === "unselected") {
            return;
        }
        isSending = true;
        closeModelMenu();
        chatError = false;
        setSessionActive(true);
        appendMessage("user", prompt);
        messages.push({ role: "user", content: prompt });
        input.value = "";
        setStatus("busy", `${activeProvider === "gemini" ? "Gemini" : "Ollama"} is generating a response...`);
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
                body: JSON.stringify({
                    message: prompt,
                    file_ids: [...fileList.querySelectorAll('input[type="checkbox"]:checked')].map((item) => item.value),
                }),
            });
            const assistantText = await readChatStream(response, assistantMessage);
            assistantMessage.classList.remove("is-streaming");
            addExpandButton(
                assistantMessage,
                assistantMessage.querySelector(".ollama-chat-message-content"),
            );
            messages.push({ role: "assistant", content: assistantText });
            latestAssistantReply = assistantText;
            setStatus("ready", "Response received.");
        } catch (error) {
            chatError = true;
            assistantMessage.classList.remove("is-streaming");
            assistantMessage.classList.add("is-error");
            assistantMessage.querySelector(".ollama-chat-message-content").textContent =
                error.message || "Ollama could not complete the request.";
            messages.pop();
            setStatus("error", error.message || "Ollama could not complete the request.");
        } finally {
            isSending = false;
            setSessionActive(sessionActive);
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
            folderStatus.textContent = "";
            chatError = false;
            appendMessage("assistant", "Session ended. Start a new session to continue.", false);
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
        appendMessage("assistant", "Verify your account to enable Rover AI chat.", false);
    } else {
        loadSavedFiles().catch((error) => {
            fileStatus.textContent = error.message || "Could not load saved files.";
        });
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
            if (!event.detail?.apiKeySaved) {
                await refreshStatus();
                return;
            }
            await loadApiKeys();
            if (!modelMenu.hidden) {
                loadModelMenu();
            }
        });
        window.addEventListener("focus", () => {
            if (sessionActive) {
                loadApiKeys();
                if (!isSending) {
                    refreshStatus();
                }
            }
        });
    }
}

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initializeOllamaDrawer, { once: true });
} else {
    initializeOllamaDrawer();
}
