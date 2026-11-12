import { createSchemaViews } from "./SchemaViews.js?v=2";
import { createSchemaDatabase } from "./SchemaDatabase.js?v=1";
import { createSchemaTools } from "./SchemaTools.js?v=1";

// Connect the schema editor's shared state, modules, and user interactions.
function initializeSchemaEditor() {
    // Collect the editor controls before wiring up any interactions.
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
    // Keep the editor's selection and unsaved state shared across its modules.
    const state = {
        activeView: "tables",
        selectedTableId: null,
        selectedDatabaseId: null,
        relationshipSourceId: null,
        relationshipTargetId: null,
        selectedLineColor: "#2878b5",
        nextId: 1,
        dragState: null,
        hasUnsavedChanges: false,
        reloadAfterEditorClose: false,
    };

    const lineColors = [
        { color: "#2878b5", name: "Blue line" },
        { color: "#d64545", name: "Red line" },
        { color: "#2b8a3e", name: "Green line" },
        { color: "#9c36b5", name: "Purple line" },
        { color: "#e67700", name: "Orange line" },
        { color: "#00838f", name: "Teal line" },
        { color: "#343a40", name: "Charcoal line" },
    ];


    // Connect rendering, persistence, and auxiliary tools to the same state.
    const views = createSchemaViews({
        state, tables, relationships, databases, lineColors, dialog, databaseList,
        databaseCount, libraryStatus, canvas, tableGrid, emptyState, connectionLayer,
        inspector,
    });
    const {
        createElement, databaseUrl, setLibraryStatus, renderDatabaseList,
        selectedTable, drawConnections, renderTables, renderRelationshipsView,
        renderInspector,
    } = views;

    // Track edits and create relationships between existing table fields.
    const markDirty = () => {
        state.hasUnsavedChanges = true;
        saveButton.disabled = !state.selectedDatabaseId;
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
            id: String(state.nextId++),
            sourceTableId: sourceTable.id,
            targetTableId: targetTable.id,
            sourceColumnId: sourceColumn.id,
            targetColumnId: targetColumn.id,
            color: state.selectedLineColor,
        });
        markDirty();
    };

    const render = () => {
        viewButtons.forEach((button) => {
            button.setAttribute(
                "aria-pressed",
                String(button.dataset.schemaView === state.activeView),
            );
        });
        renderTables();
        renderInspector();
    };

    const {
        loadDatabase, loadDatabaseList, saveSchema, createDatabase, importDatabase,
        deleteDatabase,
    } = createSchemaDatabase({
        state, tables, relationships, databases, dialog, nameInput, saveButton,
        saveStatus, queryButton, runQueryButton, queryPanel, workspace, queryStatus,
        queryResults, csrfInput, createForm, newNameInput, fileInput, databaseUrl,
        setLibraryStatus, renderDatabaseList, render,
    });
    const { runSchemaQuery, toggleQueryPanel, openDemo, stopDemoTraffic } = createSchemaTools({
        state, tables, databases, dialog, newNameInput, queryResults, queryStatus,
        runQueryButton, queryInput, csrfInput, queryPanel, workspace, queryButton,
        saveStatus, demoNodes, demoPackets, demoDatabaseName, demoStatus,
        demoActiveUsers, demoDialog, demoTrack, createElement, databaseUrl,
        setLibraryStatus, loadDatabaseList,
    });

    // New tables start with a primary-key field and a position on the canvas.
    const addTable = () => {
        if (!state.selectedDatabaseId) {
            return;
        }
        const id = String(state.nextId++);
        const tableIndex = tables.length;
        const table = {
            id,
            name: `Table${tableIndex + 1}`,
            x: 24 + (tableIndex % 3) * 340,
            y: 24 + Math.floor(tableIndex / 3) * 280,
            columns: [
                {
                    id: String(state.nextId++),
                    name: "ID",
                    type: "AutoNumber",
                    primaryKey: true,
                },
            ],
        };
        tables.push(table);
        state.selectedTableId = id;
        state.activeView = "configure";
        markDirty();
        render();
    };

    // Route inspector changes to the current table and relationship state.
    viewButtons.forEach((button) => {
        button.addEventListener("click", () => {
            state.activeView = button.dataset.schemaView;
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
            state.relationshipSourceId = document.getElementById(
                "schemaRelationshipSource",
            )?.value;
            state.relationshipTargetId = document.getElementById(
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

    // Select and drag table cards; dropping one onto another creates a link.
    tableGrid.addEventListener("click", (event) => {
        const target = event.target;
        if (!(target instanceof Element)) {
            return;
        }
        const button = target.closest('button[data-action="select-table"]');
        if (!(button instanceof HTMLButtonElement) || state.dragState?.moved) {
            return;
        }
        state.selectedTableId = button.dataset.tableId;
        state.activeView = "configure";
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
        state.dragState = {
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
        if (!state.dragState || state.dragState.pointerId !== event.pointerId || !(event.buttons & 1)) {
            return;
        }
        const deltaX = event.clientX - state.dragState.startX;
        const deltaY = event.clientY - state.dragState.startY;
        if (Math.abs(deltaX) + Math.abs(deltaY) > 5) {
            state.dragState.moved = true;
        }
        if (!state.dragState.moved) {
            return;
        }
        state.dragState.table.x = Math.max(0, Math.round(state.dragState.initialX + deltaX));
        state.dragState.table.y = Math.max(0, Math.round(state.dragState.initialY + deltaY));
        state.dragState.card.style.left = `${state.dragState.table.x}px`;
        state.dragState.card.style.top = `${state.dragState.table.y}px`;
        drawConnections();
    });

    const finishTableDrag = (event) => {
        if (!state.dragState || state.dragState.pointerId !== event.pointerId) {
            return;
        }
        const completedDrag = state.dragState;
        state.dragState = null;
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

    // Handle table and relationship actions from the inspector.
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
                    state.selectedDatabaseId &&
                    (!state.hasUnsavedChanges ||
                        window.confirm("Discard unsaved changes and reload this database?"))
                ) {
                    loadDatabase(state.selectedDatabaseId);
                }
                break;
            case "choose-line-color":
                state.selectedLineColor = button.dataset.color;
                renderRelationshipsView();
                break;
            case "select-table":
                state.selectedTableId = button.dataset.tableId;
                state.activeView = "configure";
                render();
                break;
            case "show-configure":
                state.activeView = "configure";
                render();
                break;
            case "add-column":
                if (table) {
                    table.columns.push({
                        id: String(state.nextId++),
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
                    state.selectedTableId = tables[0]?.id || null;
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
                        id: String(state.nextId++),
                        sourceTableId: sourceTable.value,
                        targetTableId: targetTable.value,
                        sourceColumnId: sourceColumn.value,
                        targetColumnId: targetColumn.value,
                        color: state.selectedLineColor,
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

    // Protect unsaved edits when switching, importing, or deleting databases.
    createForm.addEventListener("submit", (event) => {
        if (
            state.hasUnsavedChanges &&
            !window.confirm("Discard unsaved changes before creating another database?")
        ) {
            event.preventDefault();
            return;
        }
        createDatabase(event);
    });

    fileInput.addEventListener("change", () => {
        if (
            state.hasUnsavedChanges &&
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
                databaseId === state.selectedDatabaseId &&
                state.hasUnsavedChanges &&
                !window.confirm("Discard unsaved changes before deleting this database?")
            ) {
                return;
            }
            deleteDatabase(databaseId, database.name);
            return;
        }
        if (button.dataset.action === "select-database") {
            if (
                databaseId === state.selectedDatabaseId ||
                !state.hasUnsavedChanges ||
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

    // Open and close the editor and traffic demo, restoring focus as needed.
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
            state.hasUnsavedChanges &&
            !window.confirm("Close without saving the schema changes?")
        ) {
            return;
        }
        state.reloadAfterEditorClose = state.hasUnsavedChanges;
        dialog.close();
        openButton.focus();
    });
    dialog.addEventListener("click", (event) => {
        if (event.target === dialog) {
            if (
                state.hasUnsavedChanges &&
                !window.confirm("Close without saving the schema changes?")
            ) {
                return;
            }
            state.reloadAfterEditorClose = state.hasUnsavedChanges;
            dialog.close();
            openButton.focus();
        }
    });
    dialog.addEventListener("cancel", (event) => {
        if (
            state.hasUnsavedChanges &&
            !window.confirm("Close without saving the schema changes?")
        ) {
            event.preventDefault();
        } else {
            state.reloadAfterEditorClose = state.hasUnsavedChanges;
        }
    });
    dialog.addEventListener("close", () => {
        if (state.reloadAfterEditorClose && state.selectedDatabaseId) {
            state.reloadAfterEditorClose = false;
            loadDatabase(state.selectedDatabaseId);
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
