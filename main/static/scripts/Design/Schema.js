function initializeSchemaEditor() {
    const dialog = document.getElementById("schemaEditorDialog");
    const openButton = document.getElementById("openSchemaEditor");
    const closeButton = document.getElementById("closeSchemaEditor");
    const inspector = document.getElementById("schemaInspector");
    const tableGrid = document.getElementById("schemaTableGrid");
    const emptyState = document.getElementById("schemaEmptyState");
    const viewButtons = document.querySelectorAll("[data-schema-view]");

    if (
        !(dialog instanceof HTMLDialogElement) ||
        !(openButton instanceof HTMLButtonElement) ||
        !(closeButton instanceof HTMLButtonElement) ||
        !(inspector instanceof HTMLElement) ||
        !(tableGrid instanceof HTMLElement) ||
        !(emptyState instanceof HTMLElement) ||
        viewButtons.length === 0
    ) {
        return;
    }

    const tables = [];
    const relationships = [];
    let activeView = "tables";
    let selectedTableId = null;
    let relationshipSourceId = null;
    let relationshipTargetId = null;
    let nextId = 1;

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

    const selectedTable = () =>
        tables.find((table) => table.id === selectedTableId) || null;

    const renderTables = () => {
        tableGrid.replaceChildren();
        emptyState.hidden = tables.length > 0;
        tables.forEach((table) => {
            const card = createElement(
                "article",
                `schema-table-card${table.id === selectedTableId ? " is-selected" : ""}`,
            );
            const selectTable = createElement("button", "schema-table-select");
            selectTable.type = "button";
            selectTable.dataset.action = "select-table";
            selectTable.dataset.tableId = table.id;
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
    };

    const renderTablesView = () => {
        inspector.replaceChildren(
            createElement("h3", "", "Tables"),
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
    };

    const renderRelationshipsView = () => {
        inspector.replaceChildren(
            createElement("h3", "", "Relationships"),
            createElement(
                "p",
                "",
                "Connect fields between two different tables. A relationship is applied to this schema diagram.",
            ),
        );
        if (tables.length < 2) {
            inspector.append(
                createElement("p", "", "Add at least two tables to create a relationship."),
            );
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

    const addTable = () => {
        const id = String(nextId++);
        const table = {
            id,
            name: `Table${tables.length + 1}`,
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
            renderTables();
        } else if (target.dataset.field === "column-name") {
            table.columns[Number(target.dataset.columnIndex)].name =
                target.value.trim() || "Untitled field";
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
        renderTables();
    });

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
                    render();
                }
                break;
            case "remove-column":
                if (table && table.columns.length > 1) {
                    table.columns.splice(Number(button.dataset.columnIndex), 1);
                    render();
                }
                break;
            case "apply-table":
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
                relationships.push({
                    sourceTableId: sourceTable.value,
                    targetTableId: targetTable.value,
                    sourceColumnId: sourceColumn.value,
                    targetColumnId: targetColumn.value,
                });
                render();
                break;
            }
            case "remove-relationship":
                relationships.splice(Number(button.dataset.relationshipIndex), 1);
                render();
                break;
        }
    });

    openButton.addEventListener("click", () => {
        dialog.showModal();
        render();
        dialog.querySelector('[data-schema-view="tables"]').focus();
    });
    closeButton.addEventListener("click", () => {
        dialog.close();
        openButton.focus();
    });
    dialog.addEventListener("click", (event) => {
        if (event.target === dialog) {
            dialog.close();
            openButton.focus();
        }
    });
}

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initializeSchemaEditor, { once: true });
} else {
    initializeSchemaEditor();
}
