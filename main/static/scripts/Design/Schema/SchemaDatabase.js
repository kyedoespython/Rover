// Load and save schemas and manage the user's SQLite database library.
export function createSchemaDatabase(context) {
    const {
        state, tables, relationships, databases, dialog, nameInput, saveButton,
        saveStatus, queryButton, runQueryButton, queryPanel, workspace, queryStatus,
        queryResults, csrfInput, createForm, newNameInput, fileInput, databaseUrl,
        setLibraryStatus, renderDatabaseList, render,
    } = context;

    // Clear the workspace when the selected database is no longer available.
    const clearSelectedDatabase = () => {
        state.selectedDatabaseId = null;
        nameInput.value = "";
        nameInput.disabled = true;
        saveButton.disabled = true;
        queryButton.disabled = true;
        runQueryButton.disabled = true;
        state.hasUnsavedChanges = false;
        tables.splice(0, tables.length);
        relationships.splice(0, relationships.length);
        state.selectedTableId = null;
        queryPanel.hidden = true;
        workspace.hidden = false;
        queryButton.setAttribute("aria-pressed", "false");
        queryStatus.textContent = "";
        queryResults.replaceChildren();
        renderDatabaseList();
        render();
    };

    // Load the schema and refresh the library without replacing shared arrays.
    const loadDatabase = async (databaseId) => {
        saveStatus.textContent = "Loading database...";
        try {
            const response = await fetch(databaseUrl(databaseId), {
                credentials: "same-origin",
                headers: { Accept: "application/json" },
            });
            const result = await response.json();
            if (!response.ok) {
                throw new Error(result.error || "Could not load the database.");
            }
            state.selectedDatabaseId = Number(result.database.id);
            nameInput.value = result.database.name;
            nameInput.disabled = false;
            saveButton.disabled = false;
            queryButton.disabled = false;
            runQueryButton.disabled = false;
            tables.splice(0, tables.length, ...result.schema.tables);
            relationships.splice(
                0,
                relationships.length,
                ...result.schema.relationships,
            );
            state.selectedTableId = tables[0]?.id || null;
            const numericIds = [
                ...tables.map((table) => Number(table.id)),
                ...tables.flatMap((table) => table.columns.map((column) => Number(column.id))),
                ...relationships.map((relationship) => Number(relationship.id)),
            ].filter(Number.isSafeInteger);
            state.nextId = Math.max(0, ...numericIds) + 1;
            state.relationshipSourceId = null;
            state.relationshipTargetId = null;
            state.hasUnsavedChanges = false;
            renderDatabaseList();
            render();
            saveStatus.textContent =
                `Loaded ${result.database.name} (${result.database.table_count} tables)`;
            return true;
        } catch (error) {
            saveStatus.textContent = error.message || "Could not load the saved schema.";
            return false;
        }
    };

    const loadDatabaseList = async (selectFirst = false) => {
        setLibraryStatus("Loading saved databases...");
        try {
            const response = await fetch(dialog.dataset.schemaUrl, {
                credentials: "same-origin",
                headers: { Accept: "application/json" },
            });
            const result = await response.json();
            if (!response.ok) {
                throw new Error(result.error || "Could not load saved databases.");
            }
            databases.splice(0, databases.length, ...result.databases);
            renderDatabaseList();
            setLibraryStatus(
                databases.length ? "" : "Create a database or load a SQLite file.",
            );
            if (state.selectedDatabaseId && !databases.some(
                (database) => Number(database.id) === state.selectedDatabaseId,
            )) {
                clearSelectedDatabase();
            }
            if (
                selectFirst &&
                databases.length > 0 &&
                (!state.selectedDatabaseId || !databases.some(
                    (database) => Number(database.id) === state.selectedDatabaseId,
                ))
            ) {
                await loadDatabase(databases[0].id);
            }
            return true;
        } catch (error) {
            setLibraryStatus(error.message || "Could not load saved databases.");
            return false;
        }
    };

    // Persist the currently edited tables and relationships.
    const saveSchema = async () => {
        if (!state.selectedDatabaseId) {
            saveStatus.textContent = "Create or load a database first.";
            return;
        }
        saveButton.disabled = true;
        saveStatus.textContent = "Saving schema...";
        try {
            const response = await fetch(databaseUrl(state.selectedDatabaseId), {
                method: "PUT",
                credentials: "same-origin",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": csrfInput.value,
                    Accept: "application/json",
                },
                body: JSON.stringify({
                    name: nameInput.value,
                    schema: { tables, relationships },
                }),
            });
            const result = await response.json();
            if (!response.ok) {
                throw new Error(result.error || "Could not save the schema.");
            }
            databases.splice(
                0,
                databases.length,
                ...databases.map((database) =>
                    Number(database.id) === state.selectedDatabaseId
                        ? result.database
                        : database,
                ),
            );
            state.hasUnsavedChanges = false;
            renderDatabaseList();
            saveStatus.textContent =
                `Saved ${result.metadata.table_count} tables, ` +
                `${result.metadata.column_count} fields, and ` +
                `${result.metadata.relationship_count} relationships`;
        } catch (error) {
            saveStatus.textContent = error.message || "Could not save the schema.";
        } finally {
            saveButton.disabled = !state.selectedDatabaseId;
        }
    };

    // Create, import, and delete entries in the SQLite database library.
    const createDatabase = async (event) => {
        event.preventDefault();
        const name = newNameInput.value.trim();
        if (!name) {
            setLibraryStatus("Enter a name for the new database.");
            newNameInput.focus();
            return;
        }
        const submitButton = createForm.querySelector('button[type="submit"]');
        if (submitButton instanceof HTMLButtonElement) {
            submitButton.disabled = true;
        }
        setLibraryStatus("Creating SQLite database...");
        try {
            const response = await fetch(dialog.dataset.schemaUrl, {
                method: "POST",
                credentials: "same-origin",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": csrfInput.value,
                    Accept: "application/json",
                },
                body: JSON.stringify({
                    name,
                    schema: { tables: [], relationships: [] },
                }),
            });
            const result = await response.json();
            if (!response.ok) {
                throw new Error(result.error || "Could not create the database.");
            }
            newNameInput.value = "";
            await loadDatabaseList();
            await loadDatabase(result.database.id);
            setLibraryStatus("Database created.");
        } catch (error) {
            setLibraryStatus(error.message || "Could not create the database.");
        } finally {
            if (submitButton instanceof HTMLButtonElement) {
                submitButton.disabled = false;
            }
        }
    };

    const importDatabase = async () => {
        const file = fileInput.files?.[0];
        if (!file) {
            return;
        }
        const extension = file.name.split(".").pop()?.toLowerCase();
        if (!["db", "sqlite", "sqlite3"].includes(extension)) {
            setLibraryStatus("Only .sqlite3, .sqlite, and .db files are accepted.");
            fileInput.value = "";
            return;
        }
        const formData = new FormData();
        formData.append("file", file);
        setLibraryStatus("Validating and loading SQLite file...");
        fileInput.disabled = true;
        try {
            const response = await fetch(dialog.dataset.schemaImportUrl, {
                method: "POST",
                credentials: "same-origin",
                headers: {
                    "X-CSRFToken": csrfInput.value,
                    Accept: "application/json",
                },
                body: formData,
            });
            const result = await response.json();
            if (!response.ok) {
                throw new Error(result.error || "Could not load the SQLite file.");
            }
            await loadDatabaseList();
            await loadDatabase(result.database.id);
            setLibraryStatus("SQLite database loaded.");
        } catch (error) {
            setLibraryStatus(error.message || "Could not load the SQLite file.");
        } finally {
            fileInput.disabled = false;
            fileInput.value = "";
        }
    };

    const deleteDatabase = async (databaseId, databaseName) => {
        if (!window.confirm(`Permanently delete "${databaseName}" and its stored SQLite file?`)) {
            return;
        }
        setLibraryStatus(`Deleting ${databaseName}...`);
        try {
            const response = await fetch(databaseUrl(databaseId), {
                method: "DELETE",
                credentials: "same-origin",
                headers: {
                    "X-CSRFToken": csrfInput.value,
                    Accept: "application/json",
                },
            });
            const result = await response.json();
            if (!response.ok) {
                throw new Error(result.error || "Could not delete the database.");
            }
            if (Number(databaseId) === state.selectedDatabaseId) {
                clearSelectedDatabase();
            }
            await loadDatabaseList();
            setLibraryStatus("Database deleted.");
        } catch (error) {
            setLibraryStatus(error.message || "Could not delete the database.");
        }
    };


    return { loadDatabase, loadDatabaseList, saveSchema, createDatabase, importDatabase, deleteDatabase };
}
