// Render the database list, diagram, and inspector from the shared editor state.
export function createSchemaViews(context) {
    const {
        state, tables, relationships, databases, lineColors, dialog, databaseList,
        databaseCount, libraryStatus, canvas, tableGrid, emptyState, connectionLayer,
        inspector,
    } = context;

    // Build DOM controls with text content rather than inserting HTML.
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

    // Show the saved database library and its current selection.
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
                `schema-database-item${Number(database.id) === state.selectedDatabaseId ? " is-selected" : ""}`,
            );
            const select = createElement("button", "schema-database-select");
            select.type = "button";
            select.dataset.action = "select-database";
            select.dataset.databaseId = String(database.id);
            select.setAttribute("aria-current", String(Number(database.id) === state.selectedDatabaseId));
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
        tables.find((table) => table.id === state.selectedTableId) || null;

    // Draw relationship paths between the current table card positions.
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
                `schema-table-card${table.id === state.selectedTableId ? " is-selected" : ""}`,
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

    // Render the inspector controls for tables, fields, and relationships.
    const renderTablesView = () => {
        inspector.replaceChildren(
            createElement("h3", "", "Tables"),
        );
        if (!state.selectedDatabaseId) {
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
        if (!state.selectedDatabaseId) {
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
        if (!state.selectedDatabaseId) {
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
                    String(state.selectedLineColor === color),
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
            state.relationshipSourceId || state.selectedTableId || tableOptions[0][0],
        );
        source.id = "schemaRelationshipSource";
        source.dataset.field = "relationship-source";
        inspector.append(createField("From table", source));

        const defaultTarget = tables.find((table) => table.id !== source.value)?.id;
        const target = makeSelect(
            tableOptions.filter(([id]) => id !== source.value),
            state.relationshipTargetId && state.relationshipTargetId !== source.value
                ? state.relationshipTargetId
                : defaultTarget,
        );
        target.id = "schemaRelationshipTarget";
        target.dataset.field = "relationship-target";
        inspector.append(createField("To table", target));
        state.relationshipSourceId = source.value;
        state.relationshipTargetId = target.value;

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
            state.relationshipSourceId = source.value;
            state.relationshipTargetId = tables.find(
                (table) => table.id !== source.value,
            )?.id;
            addColumns();
        });
        target.addEventListener("change", () => {
            state.relationshipTargetId = target.value;
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

    // Select the inspector panel matching the active view.
    const renderInspector = () => {
        if (state.activeView === "configure") {
            renderConfigureView();
        } else if (state.activeView === "relationships") {
            renderRelationshipsView();
        } else {
            renderTablesView();
        }
    };


    return {
        createElement, databaseUrl, setLibraryStatus, renderDatabaseList,
        selectedTable, drawConnections, renderTables, renderRelationshipsView,
        renderInspector,
    };
}
