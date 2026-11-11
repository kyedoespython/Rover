function initializeSchemaEditor() {
    const dialog = document.getElementById("schemaEditorDialog");
    const openButton = document.getElementById("openSchemaEditor");
    const closeButton = document.getElementById("closeSchemaEditor");
    const demoButton = document.getElementById("openSchemaDemo");
    const databaseList = document.getElementById("schemaDatabaseList");
    const databaseCount = document.getElementById("schemaDatabaseCount");
    const libraryStatus = document.getElementById("schemaLibraryStatus");
    const createForm = document.getElementById("schemaCreateForm");
    const newNameInput = document.getElementById("schemaNewName");
    const fileInput = document.getElementById("schemaFileInput");
    const nameInput = document.getElementById("schemaNameInput");
    const canvas = document.getElementById("schemaCanvas");
    const inspector = document.getElementById("schemaInspector");
    const tableGrid = document.getElementById("schemaTableGrid");
    const emptyState = document.getElementById("schemaEmptyState");
    const connectionLayer = document.getElementById("schemaConnections");
    const saveButton = document.getElementById("saveSchemaButton");
    const saveStatus = document.getElementById("schemaSaveStatus");
    const queryButton = document.getElementById("openSchemaQuery");
    const queryPanel = document.getElementById("schemaQueryPanel");
    const workspace = document.getElementById("schemaWorkspace");
    const queryInput = document.getElementById("schemaQueryInput");
    const runQueryButton = document.getElementById("runSchemaQuery");
    const queryStatus = document.getElementById("schemaQueryStatus");
    const queryResults = document.getElementById("schemaQueryResults");
    const demoDialog = document.getElementById("schemaDemoDialog");
    const closeDemoButton = document.getElementById("closeSchemaDemo");
    const demoDatabaseName = document.getElementById("schemaDemoDatabaseName");
    const demoNodes = document.getElementById("schemaDemoNodes");
    const demoPackets = document.getElementById("schemaDemoPackets");
    const demoTrack = document.querySelector("#schemaDemoDialog .schema-demo-track");
    const demoActiveUsers = document.getElementById("schemaDemoActiveUsers");
    const demoStatus = document.getElementById("schemaDemoStatus");
    const viewButtons = document.querySelectorAll("[data-schema-view]");
    const csrfInput = document.querySelector('#apiKeyForm input[name="csrf_token"]');

    if (
        !(dialog instanceof HTMLDialogElement) ||
        !(openButton instanceof HTMLButtonElement) ||
        !(closeButton instanceof HTMLButtonElement) ||
        !(demoButton instanceof HTMLButtonElement) ||
        !(databaseList instanceof HTMLElement) ||
        !(databaseCount instanceof HTMLElement) ||
        !(libraryStatus instanceof HTMLElement) ||
        !(createForm instanceof HTMLFormElement) ||
        !(newNameInput instanceof HTMLInputElement) ||
        !(fileInput instanceof HTMLInputElement) ||
        !(nameInput instanceof HTMLInputElement) ||
        !(canvas instanceof HTMLElement) ||
        !(inspector instanceof HTMLElement) ||
        !(tableGrid instanceof HTMLElement) ||
        !(emptyState instanceof HTMLElement) ||
        !(connectionLayer instanceof SVGSVGElement) ||
        !(saveButton instanceof HTMLButtonElement) ||
        !(saveStatus instanceof HTMLElement) ||
        !(queryButton instanceof HTMLButtonElement) ||
        !(queryPanel instanceof HTMLElement) ||
        !(workspace instanceof HTMLElement) ||
        !(queryInput instanceof HTMLTextAreaElement) ||
        !(runQueryButton instanceof HTMLButtonElement) ||
        !(queryStatus instanceof HTMLElement) ||
        !(queryResults instanceof HTMLElement) ||
        !(demoDialog instanceof HTMLDialogElement) ||
        !(closeDemoButton instanceof HTMLButtonElement) ||
        !(demoDatabaseName instanceof HTMLElement) ||
        !(demoNodes instanceof HTMLElement) ||
        !(demoPackets instanceof HTMLElement) ||
        !(demoTrack instanceof HTMLElement) ||
        !(demoActiveUsers instanceof HTMLElement) ||
        !(demoStatus instanceof HTMLElement) ||
        !(csrfInput instanceof HTMLInputElement) ||
        viewButtons.length === 0
    ) {
        return;
    }

    const tables = [];
    const relationships = [];
    const databases = [];
    let activeView = "tables";
    let selectedTableId = null;
    let selectedDatabaseId = null;
    let relationshipSourceId = null;
    let relationshipTargetId = null;
    let selectedLineColor = "#2878b5";
    let nextId = 1;
    let dragState = null;
    let hasUnsavedChanges = false;
    let demoTrafficTimer = null;
    let activeDemoPacketCount = 0;
    let reloadAfterEditorClose = false;

    const lineColors = [
        { color: "#2878b5", name: "Blue line" },
        { color: "#d64545", name: "Red line" },
        { color: "#2b8a3e", name: "Green line" },
        { color: "#9c36b5", name: "Purple line" },
        { color: "#e67700", name: "Orange line" },
        { color: "#00838f", name: "Teal line" },
        { color: "#343a40", name: "Charcoal line" },
    ];

    const createElement = (tagName, className, text) => {
        const element = document.createElement(tagName);
        if (className) {
            element.className = className;
        }
        if (text !== undefined) {
            element.textContent = text;
        }
        return element;
    };

    const createField = (labelText, control) => {
        const wrapper = document.createElement("div");
        const label = createElement("label", "", labelText);
        if (control.id) {
            label.htmlFor = control.id;
        }
        wrapper.append(label, control);
        return wrapper;
    };

    const makeSelect = (options, selectedValue, className = "") => {
        const select = createElement("select", className);
        options.forEach(([value, label]) => {
            const option = createElement("option", "", label);
            option.value = value;
            select.append(option);
        });
        if (selectedValue) {
            select.value = selectedValue;
        }
        return select;
    };

    const databaseUrl = (databaseId, suffix = "") =>
        `${dialog.dataset.schemaUrl}/${encodeURIComponent(databaseId)}${suffix}`;

    const setLibraryStatus = (message) => {
        libraryStatus.textContent = message;
    };

    const renderDatabaseList = () => {
        databaseList.replaceChildren();
        databaseCount.textContent = String(databases.length);
        if (databases.length === 0) {
            databaseList.append(
                createElement("p", "schema-sidebar-help", "No saved databases yet."),
            );
            return;
        }

        databases.forEach((database) => {
            const item = createElement(
                "div",
                `schema-database-item${Number(database.id) === selectedDatabaseId ? " is-selected" : ""}`,
            );
            const select = createElement("button", "schema-database-select");
            select.type = "button";
            select.dataset.action = "select-database";
            select.dataset.databaseId = String(database.id);
            select.setAttribute("aria-current", String(Number(database.id) === selectedDatabaseId));
            const name = createElement("strong", "", database.name);
            const detail = createElement(
                "span",
                "",
                `${database.table_count} tables | ${database.file_name}`,
            );
            select.append(name, detail);

            const remove = createElement("button", "schema-database-delete", "Delete");
            remove.type = "button";
            remove.dataset.action = "delete-database";
            remove.dataset.databaseId = String(database.id);
            remove.setAttribute("aria-label", `Delete ${database.name}`);
            item.append(select, remove);
            databaseList.append(item);
        });
    };

    const selectedTable = () =>
        tables.find((table) => table.id === selectedTableId) || null;

    const drawConnections = () => {
        connectionLayer.replaceChildren();
        const width = Math.max(canvas.clientWidth, canvas.scrollWidth);
        const height = Math.max(canvas.clientHeight, canvas.scrollHeight);
        connectionLayer.setAttribute("width", String(width));
        connectionLayer.setAttribute("height", String(height));
        connectionLayer.setAttribute("viewBox", `0 0 ${width} ${height}`);

        relationships.forEach((relationship) => {
            const source = tableGrid.querySelector(
                `[data-table-id="${CSS.escape(relationship.sourceTableId)}"]`,
            );
            const target = tableGrid.querySelector(
                `[data-table-id="${CSS.escape(relationship.targetTableId)}"]`,
            );
            if (!(source instanceof HTMLElement) || !(target instanceof HTMLElement)) {
                return;
            }
            const canvasRect = canvas.getBoundingClientRect();
            const sourceRect = source.getBoundingClientRect();
            const targetRect = target.getBoundingClientRect();
            const sourceX = sourceRect.right - canvasRect.left + canvas.scrollLeft;
            const sourceY = sourceRect.top - canvasRect.top + canvas.scrollTop + sourceRect.height / 2;
            const targetX = targetRect.left - canvasRect.left + canvas.scrollLeft;
            const targetY = targetRect.top - canvasRect.top + canvas.scrollTop + targetRect.height / 2;
            const curve = Math.max(50, Math.abs(targetX - sourceX) * 0.45);
            const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
            path.classList.add("schema-connection-path");
            path.setAttribute(
                "d",
                `M ${sourceX} ${sourceY} C ${sourceX + curve} ${sourceY}, ${targetX - curve} ${targetY}, ${targetX} ${targetY}`,
            );
            path.setAttribute("stroke", relationship.color);
            path.setAttribute("data-relationship-id", relationship.id);
            const sourceTable = tables.find((table) => table.id === relationship.sourceTableId);
            const targetTable = tables.find((table) => table.id === relationship.targetTableId);
            const sourceColumn = sourceTable?.columns.find(
                (column) => column.id === relationship.sourceColumnId,
            );
            const targetColumn = targetTable?.columns.find(
                (column) => column.id === relationship.targetColumnId,
            );
            const colorName = lineColors.find(
                (lineColor) => lineColor.color === relationship.color,
            )?.name || "Colored line";
            const title = document.createElementNS("http://www.w3.org/2000/svg", "title");
            title.textContent =
                `${colorName}: ${sourceTable?.name}.${sourceColumn?.name} → ` +
                `${targetTable?.name}.${targetColumn?.name}. Drag a table onto another ` +
                "table or edit this relationship in the Relationships panel.";
            path.append(title);
            connectionLayer.append(path);
        });
    };

    const renderTables = () => {
        tableGrid.replaceChildren();
        emptyState.hidden = tables.length > 0;
        tables.forEach((table) => {
            const card = createElement(
                "article",
                `schema-table-card${table.id === selectedTableId ? " is-selected" : ""}`,
            );
            card.dataset.tableId = table.id;
            card.style.left = `${table.x}px`;
            card.style.top = `${table.y}px`;
            const selectTable = createElement("button", "schema-table-select");
            selectTable.type = "button";
            selectTable.dataset.action = "select-table";
            selectTable.dataset.tableId = table.id;
            selectTable.title = "Drag this table onto another table to create a relationship.";
            const tableName = createElement("span", "", table.name || "Untitled table");
            const rowCount = createElement("span", "", `${table.columns.length} fields`);
            selectTable.append(tableName, rowCount);
            card.append(selectTable);

            table.columns.forEach((column) => {
                const row = createElement("div", "schema-table-row");
                const name = createElement(
                    "span",
                    "",
                    `${column.primaryKey ? "🔑 " : ""}${column.name || "Untitled field"}`,
                );
                const type = createElement("span", "schema-table-type", column.type);
                row.append(name, type);
                card.append(row);
            });
            tableGrid.append(card);
        });
        drawConnections();
    };

    const renderTablesView = () => {
        inspector.replaceChildren(
            createElement("h3", "", "Tables"),
        );
        if (!selectedDatabaseId) {
            inspector.append(
                createElement("p", "", "Create a database or load a SQLite file to edit its schema."),
            );
            return;
        }
        inspector.append(
            createElement(
                "p",
                "",
                "Add a table to the diagram. Select a table card to customize its fields.",
            ),
        );
        const addButton = createElement("button", "schema-action", "Add table");
        addButton.type = "button";
        addButton.dataset.action = "add-table";
        inspector.append(addButton);
        if (tables.length > 0) {
            const configureButton = createElement(
                "button",
                "schema-action schema-secondary-action",
                "Customize selected table",
            );
            configureButton.type = "button";
            configureButton.dataset.action = "show-configure";
            inspector.append(configureButton);
        }
    };

    const renderConfigureView = () => {
        const table = selectedTable();
        inspector.replaceChildren(createElement("h3", "", "Configure table"));
        if (!selectedDatabaseId) {
            inspector.append(createElement("p", "", "Create or load a database first."));
            return;
        }
        if (!table) {
            inspector.append(
                createElement("p", "", "Add and select a table before configuring it."),
            );
            const addButton = createElement("button", "schema-action", "Add table");
            addButton.type = "button";
            addButton.dataset.action = "add-table";
            inspector.append(addButton);
            return;
        }

        const nameInput = createElement("input");
        nameInput.type = "text";
        nameInput.maxLength = 64;
        nameInput.value = table.name;
        nameInput.dataset.field = "table-name";
        inspector.append(createField("Table name", nameInput));

        inspector.append(createElement("h3", "", "Fields"));
        table.columns.forEach((column, index) => {
            const row = createElement("div", "schema-column-editor");
            const nameInput = createElement("input");
            nameInput.type = "text";
            nameInput.maxLength = 64;
            nameInput.value = column.name;
            nameInput.setAttribute("aria-label", `Field ${index + 1} name`);
            nameInput.dataset.field = "column-name";
            nameInput.dataset.columnIndex = String(index);

            const typeSelect = makeSelect(
                [
                    ["AutoNumber", "AutoNumber"],
                    ["Short Text", "Short Text"],
                    ["Long Text", "Long Text"],
                    ["Number", "Number"],
                    ["Decimal", "Decimal"],
                    ["Date/Time", "Date/Time"],
                    ["Yes/No", "Yes/No"],
                    ["Currency", "Currency"],
                    ["Attachment", "Attachment"],
                ],
                column.type,
            );
            typeSelect.setAttribute("aria-label", `Field ${index + 1} data type`);
            typeSelect.dataset.field = "column-type";
            typeSelect.dataset.columnIndex = String(index);

            const keyLabel = createElement("label");
            const keyInput = createElement("input");
            keyInput.type = "checkbox";
            keyInput.checked = column.primaryKey;
            keyInput.setAttribute("aria-label", `Field ${index + 1} primary key`);
            keyInput.dataset.field = "column-primary";
            keyInput.dataset.columnIndex = String(index);
            keyLabel.append(keyInput, document.createTextNode("PK"));

            const removeButton = createElement("button", "schema-remove-column", "×");
            removeButton.type = "button";
            removeButton.dataset.action = "remove-column";
            removeButton.dataset.columnIndex = String(index);
            removeButton.setAttribute("aria-label", `Remove field ${index + 1}`);
            row.append(nameInput, typeSelect, keyLabel, removeButton);
            inspector.append(row);
        });

        const addColumnButton = createElement(
            "button",
            "schema-action schema-secondary-action",
            "Add field",
        );
        addColumnButton.type = "button";
        addColumnButton.dataset.action = "add-column";
        inspector.append(addColumnButton);

        const doneButton = createElement("button", "schema-action", "Apply table changes");
        doneButton.type = "button";
        doneButton.dataset.action = "apply-table";
        inspector.append(doneButton);

        const removeTableButton = createElement(
            "button",
            "schema-action schema-secondary-action schema-danger-action",
            "Delete table",
        );
        removeTableButton.type = "button";
        removeTableButton.dataset.action = "remove-table";
        inspector.append(removeTableButton);
    };

    const renderRelationshipsView = () => {
        inspector.replaceChildren(
            createElement("h3", "", "Relationships"),
            createElement(
                "p",
                "",
                "Drag one table onto another to connect them, or define the relationship below.",
            ),
        );
        if (!selectedDatabaseId) {
            inspector.replaceChildren(
                createElement("h3", "", "Relationships"),
                createElement("p", "", "Create or load a database first."),
            );
            return;
        }
        const loadButton = createElement("button", "schema-action", "Reload database");
        loadButton.type = "button";
        loadButton.dataset.action = "load-schema";
        inspector.append(loadButton);

        const appendLinePalette = () => {
            inspector.append(createElement("h3", "", "Line colors"));
            const palette = createElement("div", "schema-line-palette");
            lineColors.forEach(({ color, name }) => {
                const swatch = createElement("button", "schema-line-swatch", name);
                swatch.type = "button";
                swatch.dataset.action = "choose-line-color";
                swatch.dataset.color = color;
                swatch.title = `${name}. Select this color for new relationship lines.`;
                swatch.setAttribute("aria-label", `${name}, select for new relationship lines`);
                swatch.setAttribute(
                    "aria-pressed",
                    String(selectedLineColor === color),
                );
                const line = createElement("span", "schema-line-color");
                line.style.backgroundColor = color;
                line.setAttribute("aria-hidden", "true");
                swatch.prepend(line);
                palette.append(swatch);
            });
            inspector.append(palette);
            inspector.append(
                createElement(
                    "p",
                    "schema-line-help",
                    "Hover over a color or connection line to see its name and use. Each color has a generic line name.",
                ),
            );
        };
        if (tables.length < 2) {
            inspector.append(
                createElement("p", "", "Load or add at least two tables to create a relationship."),
            );
            appendLinePalette();
            return;
        }

        const tableOptions = tables.map((table) => [table.id, table.name || "Untitled table"]);
        const source = makeSelect(
            tableOptions,
            relationshipSourceId || selectedTableId || tableOptions[0][0],
        );
        source.id = "schemaRelationshipSource";
        source.dataset.field = "relationship-source";
        inspector.append(createField("From table", source));

        const defaultTarget = tables.find((table) => table.id !== source.value)?.id;
        const target = makeSelect(
            tableOptions.filter(([id]) => id !== source.value),
            relationshipTargetId && relationshipTargetId !== source.value
                ? relationshipTargetId
                : defaultTarget,
        );
        target.id = "schemaRelationshipTarget";
        target.dataset.field = "relationship-target";
        inspector.append(createField("To table", target));
        relationshipSourceId = source.value;
        relationshipTargetId = target.value;

        const addColumns = () => {
            const oldSourceColumn = inspector.querySelector('[data-field="relationship-source-column"]')?.value;
            const oldTargetColumn = inspector.querySelector('[data-field="relationship-target-column"]')?.value;
            const fromTable = tables.find((table) => table.id === source.value);
            const toTable = tables.find((table) => table.id === target.value);
            const sourceColumn = makeSelect(
                (fromTable?.columns || []).map((column) => [column.id, column.name]),
                oldSourceColumn,
            );
            sourceColumn.dataset.field = "relationship-source-column";
            sourceColumn.id = "schemaRelationshipSourceColumn";
            const targetColumn = makeSelect(
                (toTable?.columns || []).map((column) => [column.id, column.name]),
                oldTargetColumn,
            );
            targetColumn.dataset.field = "relationship-target-column";
            targetColumn.id = "schemaRelationshipTargetColumn";
            let sourceField = inspector.querySelector("#schemaRelationshipSourceColumnField");
            let targetField = inspector.querySelector("#schemaRelationshipTargetColumnField");
            if (!sourceField) {
                sourceField = createElement("div");
                sourceField.id = "schemaRelationshipSourceColumnField";
                inspector.append(sourceField);
            }
            if (!targetField) {
                targetField = createElement("div");
                targetField.id = "schemaRelationshipTargetColumnField";
                inspector.append(targetField);
            }
            sourceField.replaceChildren(createField("From field", sourceColumn));
            targetField.replaceChildren(createField("To field", targetColumn));
        };
        source.addEventListener("change", () => {
            relationshipSourceId = source.value;
            relationshipTargetId = tables.find(
                (table) => table.id !== source.value,
            )?.id;
            addColumns();
        });
        target.addEventListener("change", () => {
            relationshipTargetId = target.value;
            addColumns();
        });
        addColumns();

        const applyButton = createElement("button", "schema-action", "Apply relationship");
        applyButton.type = "button";
        applyButton.dataset.action = "add-relationship";
        inspector.append(applyButton);

        if (relationships.length > 0) {
            inspector.append(createElement("h3", "", "Applied relationships"));
            relationships.forEach((relationship, index) => {
                const fromTable = tables.find((table) => table.id === relationship.sourceTableId);
                const toTable = tables.find((table) => table.id === relationship.targetTableId);
                const fromColumn = fromTable?.columns.find(
                    (column) => column.id === relationship.sourceColumnId,
                );
                const toColumn = toTable?.columns.find(
                    (column) => column.id === relationship.targetColumnId,
                );
                const row = createElement(
                    "div",
                    "schema-relationship",
                    `${fromTable?.name}.${fromColumn?.name} → ${toTable?.name}.${toColumn?.name}`,
                );
                const removeButton = createElement(
                    "button",
                    "schema-remove-column",
                    "Remove",
                );
                removeButton.type = "button";
                removeButton.dataset.action = "remove-relationship";
                removeButton.dataset.relationshipIndex = String(index);
                row.append(removeButton);
                inspector.append(row);
            });
        }
        appendLinePalette();
    };

    const renderInspector = () => {
        if (activeView === "configure") {
            renderConfigureView();
        } else if (activeView === "relationships") {
            renderRelationshipsView();
        } else {
            renderTablesView();
        }
    };

    const markDirty = () => {
        hasUnsavedChanges = true;
        saveButton.disabled = !selectedDatabaseId;
        saveStatus.textContent = "Unsaved changes";
    };

    const createRelationship = (sourceTable, targetTable) => {
        if (!sourceTable || !targetTable || sourceTable.id === targetTable.id) {
            return;
        }
        const sourceColumn =
            sourceTable.columns.find((column) => column.primaryKey) || sourceTable.columns[0];
        const targetColumn =
            targetTable.columns.find((column) => column.primaryKey) || targetTable.columns[0];
        const exists = relationships.some((relationship) =>
            relationship.sourceTableId === sourceTable.id &&
            relationship.targetTableId === targetTable.id &&
            relationship.sourceColumnId === sourceColumn.id &&
            relationship.targetColumnId === targetColumn.id,
        );
        if (exists) {
            return;
        }
        relationships.push({
            id: String(nextId++),
            sourceTableId: sourceTable.id,
            targetTableId: targetTable.id,
            sourceColumnId: sourceColumn.id,
            targetColumnId: targetColumn.id,
            color: selectedLineColor,
        });
        markDirty();
    };

    const clearSelectedDatabase = () => {
        selectedDatabaseId = null;
        nameInput.value = "";
        nameInput.disabled = true;
        saveButton.disabled = true;
        queryButton.disabled = true;
        runQueryButton.disabled = true;
        hasUnsavedChanges = false;
        tables.splice(0, tables.length);
        relationships.splice(0, relationships.length);
        selectedTableId = null;
        queryPanel.hidden = true;
        workspace.hidden = false;
        queryButton.setAttribute("aria-pressed", "false");
        queryStatus.textContent = "";
        queryResults.replaceChildren();
        renderDatabaseList();
        render();
    };

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
            selectedDatabaseId = Number(result.database.id);
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
            selectedTableId = tables[0]?.id || null;
            const numericIds = [
                ...tables.map((table) => Number(table.id)),
                ...tables.flatMap((table) => table.columns.map((column) => Number(column.id))),
                ...relationships.map((relationship) => Number(relationship.id)),
            ].filter(Number.isSafeInteger);
            nextId = Math.max(0, ...numericIds) + 1;
            relationshipSourceId = null;
            relationshipTargetId = null;
            hasUnsavedChanges = false;
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
            if (selectedDatabaseId && !databases.some(
                (database) => Number(database.id) === selectedDatabaseId,
            )) {
                clearSelectedDatabase();
            }
            if (
                selectFirst &&
                databases.length > 0 &&
                (!selectedDatabaseId || !databases.some(
                    (database) => Number(database.id) === selectedDatabaseId,
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

    const saveSchema = async () => {
        if (!selectedDatabaseId) {
            saveStatus.textContent = "Create or load a database first.";
            return;
        }
        saveButton.disabled = true;
        saveStatus.textContent = "Saving schema...";
        try {
            const response = await fetch(databaseUrl(selectedDatabaseId), {
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
                    Number(database.id) === selectedDatabaseId
                        ? result.database
                        : database,
                ),
            );
            hasUnsavedChanges = false;
            renderDatabaseList();
            saveStatus.textContent =
                `Saved ${result.metadata.table_count} tables, ` +
                `${result.metadata.column_count} fields, and ` +
                `${result.metadata.relationship_count} relationships`;
        } catch (error) {
            saveStatus.textContent = error.message || "Could not save the schema.";
        } finally {
            saveButton.disabled = !selectedDatabaseId;
        }
    };

    const render = () => {
        viewButtons.forEach((button) => {
            button.setAttribute(
                "aria-pressed",
                String(button.dataset.schemaView === activeView),
            );
        });
        renderTables();
        renderInspector();
    };

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
            if (Number(databaseId) === selectedDatabaseId) {
                clearSelectedDatabase();
            }
            await loadDatabaseList();
            setLibraryStatus("Database deleted.");
        } catch (error) {
            setLibraryStatus(error.message || "Could not delete the database.");
        }
    };

    const renderQueryResults = (columns, rows, truncated) => {
        queryResults.replaceChildren();
        if (columns.length === 0) {
            queryResults.append(
                createElement("p", "schema-sidebar-help", "No result columns were returned."),
            );
            return;
        }
        const table = createElement("table");
        const head = createElement("thead");
        const headerRow = createElement("tr");
        columns.forEach((column) => {
            const cell = createElement("th", "", column);
            cell.scope = "col";
            headerRow.append(cell);
        });
        head.append(headerRow);
        const body = createElement("tbody");
        if (rows.length === 0) {
            const row = createElement("tr");
            const cell = createElement("td", "", "No rows returned.");
            cell.colSpan = columns.length;
            row.append(cell);
            body.append(row);
        } else {
            rows.forEach((values) => {
                const row = createElement("tr");
                values.forEach((value) => {
                    let text = value === null ? "NULL" : String(value);
                    if (value && typeof value === "object" && "blob_hex" in value) {
                        text = `BLOB ${value.blob_hex}${value.truncated ? "..." : ""}`;
                    }
                    row.append(createElement("td", "", text));
                });
                body.append(row);
            });
        }
        table.append(head, body);
        queryResults.append(table);
        if (truncated) {
            queryResults.append(
                createElement("p", "schema-sidebar-help", "Showing the first 200 rows."),
            );
        }
    };

    const runSchemaQuery = async () => {
        if (!selectedDatabaseId) {
            queryStatus.textContent = "Load a database first.";
            return;
        }
        runQueryButton.disabled = true;
        queryStatus.textContent = "Running read-only query...";
        queryResults.replaceChildren();
        try {
            const response = await fetch(databaseUrl(selectedDatabaseId, "/query"), {
                method: "POST",
                credentials: "same-origin",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": csrfInput.value,
                    Accept: "application/json",
                },
                body: JSON.stringify({ query: queryInput.value }),
            });
            const result = await response.json();
            if (!response.ok) {
                throw new Error(result.error || "The query could not be completed.");
            }
            renderQueryResults(result.columns, result.rows, result.truncated);
            queryStatus.textContent =
                `${result.rows.length} row${result.rows.length === 1 ? "" : "s"} returned` +
                (result.truncated ? " (limited)" : "");
        } catch (error) {
            queryStatus.textContent = error.message || "The query could not be completed.";
        } finally {
            runQueryButton.disabled = !selectedDatabaseId;
        }
    };

    const toggleQueryPanel = () => {
        if (!selectedDatabaseId) {
            saveStatus.textContent = "Create or load a database before querying.";
            return;
        }
        const showingQuery = queryPanel.hidden;
        queryPanel.hidden = !showingQuery;
        workspace.hidden = showingQuery;
        queryButton.setAttribute("aria-pressed", String(showingQuery));
        if (showingQuery) {
            queryInput.focus();
        } else {
            queryButton.focus();
        }
    };

    const renderDemo = () => {
        demoNodes.replaceChildren();
        demoPackets.replaceChildren();
        const database = databases.find(
            (item) => Number(item.id) === selectedDatabaseId,
        );
        demoDatabaseName.textContent = database
            ? `Simulated traffic passing through ${database.name}.`
            : "Simulated requests passing through your schema.";
        const visibleTables = tables.slice(0, 8);
        visibleTables.forEach((table) => {
            demoNodes.append(
                createElement("div", "schema-demo-node", table.name),
            );
        });
        demoStatus.textContent = tables.length > visibleTables.length
            ? `Showing 8 of ${tables.length} tables.`
            : `${tables.length} table${tables.length === 1 ? "" : "s"} in this model.`;
        activeDemoPacketCount = 0;
        demoActiveUsers.textContent = "Simulated active users: 0";
    };

    const stopDemoTraffic = () => {
        if (demoTrafficTimer !== null) {
            window.clearInterval(demoTrafficTimer);
            demoTrafficTimer = null;
        }
        demoPackets.replaceChildren();
        activeDemoPacketCount = 0;
        demoActiveUsers.textContent = "Simulated active users: 0";
    };

    const startDemoTraffic = () => {
        stopDemoTraffic();
        const spawnPacket = () => {
            if (!demoDialog.open || tables.length === 0) {
                return;
            }
            const packet = createElement("span", "schema-demo-packet");
            packet.style.top = `${35 + Math.random() * 30}%`;
            packet.style.setProperty(
                "--travel",
                `${Math.max(0, demoTrack.clientWidth - 12)}px`,
            );
            packet.style.animationDuration = `${2.4 + Math.random() * 1.2}s`;
            packet.addEventListener("animationend", () => {
                packet.remove();
                activeDemoPacketCount = Math.max(0, activeDemoPacketCount - 1);
                demoActiveUsers.textContent =
                    `Simulated active users: ${activeDemoPacketCount}`;
            }, { once: true });
            demoPackets.append(packet);
            activeDemoPacketCount += 1;
            demoActiveUsers.textContent =
                `Simulated active users: ${activeDemoPacketCount}`;
        };
        spawnPacket();
        demoTrafficTimer = window.setInterval(spawnPacket, 850);
    };

    const openDemo = async () => {
        if (!dialog.open) {
            dialog.showModal();
        }
        if (!await loadDatabaseList(true)) {
            return;
        }
        if (!selectedDatabaseId) {
            setLibraryStatus("Create a database or load a SQLite file before starting the demo.");
            newNameInput.focus();
            return;
        }
        if (dialog.open) {
            dialog.close();
        }
        renderDemo();
        demoDialog.showModal();
        startDemoTraffic();
    };

    const addTable = () => {
        if (!selectedDatabaseId) {
            return;
        }
        const id = String(nextId++);
        const tableIndex = tables.length;
        const table = {
            id,
            name: `Table${tableIndex + 1}`,
            x: 24 + (tableIndex % 3) * 340,
            y: 24 + Math.floor(tableIndex / 3) * 280,
            columns: [
                {
                    id: String(nextId++),
                    name: "ID",
                    type: "AutoNumber",
                    primaryKey: true,
                },
            ],
        };
        tables.push(table);
        selectedTableId = id;
        activeView = "configure";
        markDirty();
        render();
    };

    viewButtons.forEach((button) => {
        button.addEventListener("click", () => {
            activeView = button.dataset.schemaView;
            render();
        });
    });

    inspector.addEventListener("input", (event) => {
        const target = event.target;
        if (!(target instanceof HTMLInputElement)) {
            return;
        }
        const table = selectedTable();
        if (!table) {
            return;
        }
        if (target.dataset.field === "table-name") {
            table.name = target.value.trim() || "Untitled table";
            markDirty();
            renderTables();
        } else if (target.dataset.field === "column-name") {
            table.columns[Number(target.dataset.columnIndex)].name =
                target.value.trim() || "Untitled field";
            markDirty();
            renderTables();
        }
    });

    inspector.addEventListener("change", (event) => {
        const target = event.target;
        if (!(target instanceof HTMLInputElement || target instanceof HTMLSelectElement)) {
            return;
        }
        if (target.dataset.field === "relationship-source" ||
            target.dataset.field === "relationship-target") {
            relationshipSourceId = document.getElementById(
                "schemaRelationshipSource",
            )?.value;
            relationshipTargetId = document.getElementById(
                "schemaRelationshipTarget",
            )?.value;
            renderRelationshipsView();
            return;
        }
        const table = selectedTable();
        const index = Number(target.dataset.columnIndex);
        const column = table?.columns[index];
        if (!column) {
            return;
        }
        if (target.dataset.field === "column-type") {
            column.type = target.value;
        } else if (target.dataset.field === "column-primary") {
            column.primaryKey = target.checked;
        }
        markDirty();
        renderTables();
    });

    tableGrid.addEventListener("click", (event) => {
        const target = event.target;
        if (!(target instanceof Element)) {
            return;
        }
        const button = target.closest('button[data-action="select-table"]');
        if (!(button instanceof HTMLButtonElement) || dragState?.moved) {
            return;
        }
        selectedTableId = button.dataset.tableId;
        activeView = "configure";
        render();
    });

    tableGrid.addEventListener("pointerdown", (event) => {
        const target = event.target;
        if (!(target instanceof Element) || !(event.target instanceof HTMLElement)) {
            return;
        }
        const handle = target.closest(".schema-table-select");
        if (!(handle instanceof HTMLButtonElement)) {
            return;
        }
        const table = tables.find((item) => item.id === handle.dataset.tableId);
        const card = handle.closest(".schema-table-card");
        if (!table || !(card instanceof HTMLElement)) {
            return;
        }
        dragState = {
            pointerId: event.pointerId,
            handle,
            card,
            table,
            startX: event.clientX,
            startY: event.clientY,
            initialX: table.x,
            initialY: table.y,
            moved: false,
        };
        handle.setPointerCapture(event.pointerId);
    });

    tableGrid.addEventListener("pointermove", (event) => {
        if (!dragState || dragState.pointerId !== event.pointerId || !(event.buttons & 1)) {
            return;
        }
        const deltaX = event.clientX - dragState.startX;
        const deltaY = event.clientY - dragState.startY;
        if (Math.abs(deltaX) + Math.abs(deltaY) > 5) {
            dragState.moved = true;
        }
        if (!dragState.moved) {
            return;
        }
        dragState.table.x = Math.max(0, Math.round(dragState.initialX + deltaX));
        dragState.table.y = Math.max(0, Math.round(dragState.initialY + deltaY));
        dragState.card.style.left = `${dragState.table.x}px`;
        dragState.card.style.top = `${dragState.table.y}px`;
        drawConnections();
    });

    const finishTableDrag = (event) => {
        if (!dragState || dragState.pointerId !== event.pointerId) {
            return;
        }
        const completedDrag = dragState;
        dragState = null;
        if (completedDrag.handle.hasPointerCapture(event.pointerId)) {
            completedDrag.handle.releasePointerCapture(event.pointerId);
        }
        if (!completedDrag.moved) {
            return;
        }
        const targetTable = tables.find((table) => {
            if (table.id === completedDrag.table.id) {
                return false;
            }
            const card = tableGrid.querySelector(
                `[data-table-id="${CSS.escape(table.id)}"]`,
            );
            if (!(card instanceof HTMLElement)) {
                return false;
            }
            const rect = card.getBoundingClientRect();
            return (
                event.clientX >= rect.left &&
                event.clientX <= rect.right &&
                event.clientY >= rect.top &&
                event.clientY <= rect.bottom
            );
        });
        createRelationship(completedDrag.table, targetTable);
        markDirty();
        render();
    };
    tableGrid.addEventListener("pointerup", finishTableDrag);
    tableGrid.addEventListener("pointercancel", finishTableDrag);
    canvas.addEventListener("scroll", drawConnections);

    inspector.addEventListener("click", (event) => {
        const target = event.target;
        if (!(target instanceof Element)) {
            return;
        }
        const button = target.closest("button[data-action]");
        if (!(button instanceof HTMLButtonElement)) {
            return;
        }
        const table = selectedTable();
        switch (button.dataset.action) {
            case "add-table":
                addTable();
                break;
            case "load-schema":
                if (
                    selectedDatabaseId &&
                    (!hasUnsavedChanges ||
                        window.confirm("Discard unsaved changes and reload this database?"))
                ) {
                    loadDatabase(selectedDatabaseId);
                }
                break;
            case "choose-line-color":
                selectedLineColor = button.dataset.color;
                renderRelationshipsView();
                break;
            case "select-table":
                selectedTableId = button.dataset.tableId;
                activeView = "configure";
                render();
                break;
            case "show-configure":
                activeView = "configure";
                render();
                break;
            case "add-column":
                if (table) {
                    table.columns.push({
                        id: String(nextId++),
                        name: `Field${table.columns.length + 1}`,
                        type: "Short Text",
                        primaryKey: false,
                    });
                    markDirty();
                    render();
                }
                break;
            case "remove-column":
                if (table && table.columns.length > 1) {
                    const [removedColumn] = table.columns.splice(
                        Number(button.dataset.columnIndex),
                        1,
                    );
                    for (let index = relationships.length - 1; index >= 0; index -= 1) {
                        if (
                            (relationships[index].sourceTableId === table.id &&
                                relationships[index].sourceColumnId === removedColumn.id) ||
                            (relationships[index].targetTableId === table.id &&
                                relationships[index].targetColumnId === removedColumn.id)
                        ) {
                            relationships.splice(index, 1);
                        }
                    }
                    markDirty();
                    render();
                }
                break;
            case "remove-table":
                if (
                    table &&
                    window.confirm(
                        `Delete table "${table.name}" from the database schema?`,
                    )
                ) {
                    tables.splice(tables.indexOf(table), 1);
                    for (let index = relationships.length - 1; index >= 0; index -= 1) {
                        if (
                            relationships[index].sourceTableId === table.id ||
                            relationships[index].targetTableId === table.id
                        ) {
                            relationships.splice(index, 1);
                        }
                    }
                    selectedTableId = tables[0]?.id || null;
                    markDirty();
                    render();
                }
                break;
            case "apply-table":
                markDirty();
                renderTables();
                inspector.insertBefore(
                    createElement("p", "", "Table changes applied to the diagram."),
                    inspector.querySelector(".schema-action"),
                );
                break;
            case "add-relationship": {
                const sourceTable = document.getElementById("schemaRelationshipSource");
                const targetTable = document.getElementById("schemaRelationshipTarget");
                const sourceColumn = document.getElementById("schemaRelationshipSourceColumn");
                const targetColumn = document.getElementById("schemaRelationshipTargetColumn");
                if (
                    !(sourceTable instanceof HTMLSelectElement) ||
                    !(targetTable instanceof HTMLSelectElement) ||
                    !(sourceColumn instanceof HTMLSelectElement) ||
                    !(targetColumn instanceof HTMLSelectElement) ||
                    sourceTable.value === targetTable.value
                ) {
                    return;
                }
                const source = tables.find((table) => table.id === sourceTable.value);
                const target = tables.find((table) => table.id === targetTable.value);
                const existing = relationships.some((relationship) =>
                    relationship.sourceTableId === sourceTable.value &&
                    relationship.targetTableId === targetTable.value &&
                    relationship.sourceColumnId === sourceColumn.value &&
                    relationship.targetColumnId === targetColumn.value,
                );
                if (!existing) {
                    relationships.push({
                        id: String(nextId++),
                        sourceTableId: sourceTable.value,
                        targetTableId: targetTable.value,
                        sourceColumnId: sourceColumn.value,
                        targetColumnId: targetColumn.value,
                        color: selectedLineColor,
                    });
                    markDirty();
                }
                render();
                break;
            }
            case "remove-relationship":
                relationships.splice(Number(button.dataset.relationshipIndex), 1);
                markDirty();
                render();
                break;
        }
    });

    createForm.addEventListener("submit", (event) => {
        if (
            hasUnsavedChanges &&
            !window.confirm("Discard unsaved changes before creating another database?")
        ) {
            event.preventDefault();
            return;
        }
        createDatabase(event);
    });

    fileInput.addEventListener("change", () => {
        if (
            hasUnsavedChanges &&
            !window.confirm("Discard unsaved changes before loading another database?")
        ) {
            fileInput.value = "";
            return;
        }
        importDatabase();
    });

    databaseList.addEventListener("click", (event) => {
        const target = event.target;
        if (!(target instanceof Element)) {
            return;
        }
        const button = target.closest("button[data-action]");
        if (!(button instanceof HTMLButtonElement)) {
            return;
        }
        const databaseId = Number(button.dataset.databaseId);
        const database = databases.find((item) => Number(item.id) === databaseId);
        if (!database) {
            return;
        }
        if (button.dataset.action === "delete-database") {
            if (
                databaseId === selectedDatabaseId &&
                hasUnsavedChanges &&
                !window.confirm("Discard unsaved changes before deleting this database?")
            ) {
                return;
            }
            deleteDatabase(databaseId, database.name);
            return;
        }
        if (button.dataset.action === "select-database") {
            if (
                databaseId === selectedDatabaseId ||
                !hasUnsavedChanges ||
                window.confirm("Discard unsaved changes and load another database?")
            ) {
                loadDatabase(databaseId);
            }
        }
    });

    nameInput.addEventListener("input", markDirty);
    queryButton.addEventListener("click", toggleQueryPanel);
    runQueryButton.addEventListener("click", runSchemaQuery);
    saveButton.addEventListener("click", saveSchema);

    openButton.addEventListener("click", async () => {
        if (!dialog.open) {
            dialog.showModal();
        }
        render();
        await loadDatabaseList(true);
        dialog.querySelector('[data-schema-view="tables"]').focus();
    });
    closeButton.addEventListener("click", () => {
        if (
            hasUnsavedChanges &&
            !window.confirm("Close without saving the schema changes?")
        ) {
            return;
        }
        reloadAfterEditorClose = hasUnsavedChanges;
        dialog.close();
        openButton.focus();
    });
    dialog.addEventListener("click", (event) => {
        if (event.target === dialog) {
            if (
                hasUnsavedChanges &&
                !window.confirm("Close without saving the schema changes?")
            ) {
                return;
            }
            reloadAfterEditorClose = hasUnsavedChanges;
            dialog.close();
            openButton.focus();
        }
    });
    dialog.addEventListener("cancel", (event) => {
        if (
            hasUnsavedChanges &&
            !window.confirm("Close without saving the schema changes?")
        ) {
            event.preventDefault();
        } else {
            reloadAfterEditorClose = hasUnsavedChanges;
        }
    });
    dialog.addEventListener("close", () => {
        if (reloadAfterEditorClose && selectedDatabaseId) {
            reloadAfterEditorClose = false;
            loadDatabase(selectedDatabaseId);
        }
    });
    demoButton.addEventListener("click", openDemo);
    closeDemoButton.addEventListener("click", () => {
        demoDialog.close();
        demoButton.focus();
    });
    demoDialog.addEventListener("close", stopDemoTraffic);
    demoDialog.addEventListener("cancel", stopDemoTraffic);
}

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initializeSchemaEditor, { once: true });
} else {
    initializeSchemaEditor();
}
