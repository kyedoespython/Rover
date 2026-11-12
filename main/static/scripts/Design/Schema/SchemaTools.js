// Run read-only queries and animate the schema traffic demo.
export function createSchemaTools(context) {
    const {
        state, tables, databases, dialog, newNameInput, queryResults, queryStatus,
        runQueryButton, queryInput, csrfInput, queryPanel, workspace, queryButton,
        saveStatus, demoNodes, demoPackets, demoDatabaseName, demoStatus,
        demoActiveUsers, demoDialog, demoTrack, createElement, databaseUrl,
        setLibraryStatus, loadDatabaseList,
    } = context;
    let demoTrafficTimer = null;
    let activeDemoPacketCount = 0;

    // Render read-only query results, including NULL and BLOB values.
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
        if (!state.selectedDatabaseId) {
            queryStatus.textContent = "Load a database first.";
            return;
        }
        runQueryButton.disabled = true;
        queryStatus.textContent = "Running read-only query...";
        queryResults.replaceChildren();
        try {
            const response = await fetch(databaseUrl(state.selectedDatabaseId, "/query"), {
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
            runQueryButton.disabled = !state.selectedDatabaseId;
        }
    };

    const toggleQueryPanel = () => {
        if (!state.selectedDatabaseId) {
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

    // Display simulated traffic for the currently loaded schema.
    const renderDemo = () => {
        demoNodes.replaceChildren();
        demoPackets.replaceChildren();
        const database = databases.find(
            (item) => Number(item.id) === state.selectedDatabaseId,
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
        if (!state.selectedDatabaseId) {
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

    return { runSchemaQuery, toggleQueryPanel, openDemo, stopDemoTraffic };
}
