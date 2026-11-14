import React, { useEffect, useRef, useState } from "react";

import UserAvatar from "../components/UserAvatar.jsx";

const DATA_TYPES = ["AutoNumber", "Short Text", "Long Text", "Number", "Decimal", "Date/Time", "Yes/No", "Currency", "Attachment"];
const RELATIONSHIP_COLORS = [
    { name: "Blue", value: "#2563eb" },
    { name: "Red", value: "#dc2626" },
    { name: "Green", value: "#16a34a" },
    { name: "Violet", value: "#9333ea" },
    { name: "Amber", value: "#d97706" },
    { name: "Teal", value: "#0891b2" },
    { name: "Black", value: "#111827" },
];
const FIELD_DRAG_TYPE = "application/x-rover-schema-column";

async function requestJson(url, options = {}) {
    const response = await fetch(url, {
        credentials: "same-origin",
        headers: { Accept: "application/json", ...options.headers },
        ...options,
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "The request could not be completed.");
    return result;
}

function createId() {
    return crypto.randomUUID();
}

function createTable(index, name) {
    return {
        id: createId(),
        name: name || `Table${index + 1}`,
        x: 24 + (index % 3) * 340,
        y: 24 + (Math.floor(index / 3) % 35) * 280,
        columns: [{ id: createId(), name: "id", type: "AutoNumber", primaryKey: true }],
    };
}

export default function DatabaseConfigurationsPage({ csrfToken, username = "" }) {
    const [databases, setDatabases] = useState([]);
    const [selected, setSelected] = useState(null);
    const [databaseName, setDatabaseName] = useState("");
    const [newDatabaseName, setNewDatabaseName] = useState("");
    const [tables, setTables] = useState([]);
    const [relationships, setRelationships] = useState([]);
    const [activeSection, setActiveSection] = useState("schema");
    const [activeColor, setActiveColor] = useState(RELATIONSHIP_COLORS[0].value);
    const [dropTarget, setDropTarget] = useState("");
    const [status, setStatus] = useState("Loading databases...");
    const tableGridRef = useRef(null);
    const fieldRefs = useRef(new Map());
    const [relationshipLines, setRelationshipLines] = useState([]);
    const [lineCanvasSize, setLineCanvasSize] = useState({ width: 0, height: 0 });

    useEffect(() => {
        requestJson("/api/schema")
            .then((result) => {
                setDatabases(result.databases);
                setStatus(result.databases.length ? "Select a database to configure." : "Create or import a database to begin.");
            })
            .catch((error) => setStatus(error.message));
    }, []);

    useEffect(() => {
        const grid = tableGridRef.current;
        if (!grid) {
            setRelationshipLines([]);
            return undefined;
        }

        const updateLines = () => {
            const gridRect = grid.getBoundingClientRect();
            setLineCanvasSize({ width: gridRect.width, height: gridRect.height });
            setRelationshipLines(relationships.flatMap((relationship) => {
                const source = fieldRefs.current.get(`${relationship.sourceTableId}:${relationship.sourceColumnId}`);
                const target = fieldRefs.current.get(`${relationship.targetTableId}:${relationship.targetColumnId}`);
                if (!source || !target) return [];

                const sourceRect = source.getBoundingClientRect();
                const targetRect = target.getBoundingClientRect();
                const sourceIsLeft = sourceRect.left <= targetRect.left;
                const startX = (sourceIsLeft ? sourceRect.right : sourceRect.left) - gridRect.left;
                const endX = (sourceIsLeft ? targetRect.left : targetRect.right) - gridRect.left;
                const startY = sourceRect.top + sourceRect.height / 2 - gridRect.top;
                const endY = targetRect.top + targetRect.height / 2 - gridRect.top;
                const bend = (endX - startX) / 2;
                return [{
                    id: relationship.id,
                    color: relationship.color,
                    path: `M ${startX} ${startY} C ${startX + bend} ${startY}, ${endX - bend} ${endY}, ${endX} ${endY}`,
                }];
            }));
        };

        const frame = requestAnimationFrame(updateLines);
        window.addEventListener("resize", updateLines);
        return () => {
            cancelAnimationFrame(frame);
            window.removeEventListener("resize", updateLines);
        };
    }, [activeSection, relationships, tables]);

    async function selectDatabase(databaseId) {
        setStatus("Loading database...");
        try {
            const result = await requestJson(`/api/schema/${databaseId}`);
            setSelected(result.database);
            setDatabaseName(result.database.name);
            setTables(result.schema.tables);
            setRelationships(result.schema.relationships);
            setActiveSection("schema");
            setStatus(`Loaded ${result.database.name}.`);
        } catch (error) {
            setStatus(error.message);
        }
    }

    async function createDatabase(event) {
        event.preventDefault();
        const name = newDatabaseName.trim();
        if (!name) return;
        try {
            const result = await requestJson("/api/schema", {
                method: "POST",
                headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken },
                body: JSON.stringify({ name, schema: { tables: [], relationships: [] } }),
            });
            setDatabases((items) => [result.database, ...items]);
            setSelected(result.database);
            setDatabaseName(result.database.name);
            setNewDatabaseName("");
            setTables([]);
            setRelationships([]);
            setStatus(`Created ${result.database.name}. Add a table to begin.`);
        } catch (error) {
            setStatus(error.message);
        }
    }

    async function importDatabase(event) {
        const file = event.target.files?.[0];
        if (!file) return;
        const formData = new FormData();
        formData.append("file", file);
        try {
            const result = await requestJson("/api/schema/import", {
                method: "POST",
                headers: { "X-CSRFToken": csrfToken },
                body: formData,
            });
            setDatabases((items) => [result.database, ...items]);
            await selectDatabase(result.database.id);
        } catch (error) {
            setStatus(error.message);
        } finally {
            event.target.value = "";
        }
    }

    async function saveSchema() {
        if (!selected) return;
        setStatus("Saving configuration...");
        try {
            const result = await requestJson(`/api/schema/${selected.id}`, {
                method: "PUT",
                headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken },
                body: JSON.stringify({
                    name: databaseName,
                    schema: { tables, relationships },
                }),
            });
            setSelected(result.database);
            setDatabases((items) => items.map((item) => item.id === result.database.id ? result.database : item));
            setStatus(`Saved ${result.metadata.table_count} tables and ${result.metadata.relationship_count} relationships.`);
        } catch (error) {
            setStatus(error.message);
        }
    }

    async function deleteDatabase() {
        if (!selected || !window.confirm(`Delete "${selected.name}"?`)) return;
        try {
            await requestJson(`/api/schema/${selected.id}`, {
                method: "DELETE",
                headers: { "X-CSRFToken": csrfToken },
            });
            setDatabases((items) => items.filter((item) => item.id !== selected.id));
            setSelected(null);
            setDatabaseName("");
            setTables([]);
            setRelationships([]);
            setStatus("Database deleted.");
        } catch (error) {
            setStatus(error.message);
        }
    }

    function addTable() {
        if (tables.length >= 200) {
            setStatus("A database can contain up to 200 tables.");
            return;
        }
        const names = new Set(tables.map((table) => table.name.toLocaleLowerCase()));
        let nextNumber = tables.length + 1;
        while (names.has(`table${nextNumber}`.toLocaleLowerCase())) nextNumber += 1;
        setTables((items) => [...items, createTable(items.length, `Table${nextNumber}`)]);
    }

    function updateTable(tableId, changes) {
        setTables((items) => items.map((table) => table.id === tableId ? { ...table, ...changes } : table));
    }

    function addColumn(tableId) {
        const target = tables.find((table) => table.id === tableId);
        if (!target || target.columns.length >= 100) {
            setStatus("A table can contain up to 100 fields.");
            return;
        }
        const names = new Set(target.columns.map((column) => column.name.toLocaleLowerCase()));
        let nextNumber = target.columns.length + 1;
        while (names.has(`field${nextNumber}`.toLocaleLowerCase())) nextNumber += 1;
        setTables((items) => items.map((table) => table.id === tableId
            ? {
                ...table,
                columns: [...table.columns, {
                    id: createId(),
                    name: `field${nextNumber}`,
                    type: "Short Text",
                    primaryKey: false,
                }],
            }
            : table));
    }

    function updateColumn(tableId, columnId, changes) {
        setTables((items) => items.map((table) => table.id === tableId
            ? {
                ...table,
                columns: table.columns.map((column) => column.id === columnId ? { ...column, ...changes } : column),
            }
            : table));
    }

    function removeColumn(tableId, columnId) {
        const table = tables.find((item) => item.id === tableId);
        if (!table || table.columns.length <= 1) return;
        setTables((items) => items.map((item) => item.id === tableId
            ? { ...item, columns: item.columns.filter((column) => column.id !== columnId) }
            : item));
        setRelationships((items) => items.filter((relationship) => !(
            (relationship.sourceTableId === tableId && relationship.sourceColumnId === columnId)
            || (relationship.targetTableId === tableId && relationship.targetColumnId === columnId)
        )));
    }

    function removeTable(tableId) {
        setTables((items) => items.filter((table) => table.id !== tableId));
        setRelationships((items) => items.filter((relationship) => (
            relationship.sourceTableId !== tableId && relationship.targetTableId !== tableId
        )));
    }

    function handleFieldDrop(event, targetTableId, targetColumnId) {
        event.preventDefault();
        event.stopPropagation();
        setDropTarget("");
        const rawSource = event.dataTransfer.getData(FIELD_DRAG_TYPE)
            || event.dataTransfer.getData("text/plain");
        if (!rawSource) return;

        try {
            const source = JSON.parse(rawSource);
            if (source.tableId === targetTableId) {
                setStatus("Drag a field onto a field in a different table.");
                return;
            }
            if (relationships.some((relationship) => (
                relationship.sourceTableId === source.tableId
                && relationship.sourceColumnId === source.columnId
                && relationship.targetTableId === targetTableId
                && relationship.targetColumnId === targetColumnId
            ))) {
                setStatus("That relationship already exists.");
                return;
            }
            setRelationships((items) => [...items, {
                id: createId(),
                sourceTableId: source.tableId,
                sourceColumnId: source.columnId,
                targetTableId,
                targetColumnId,
                color: activeColor,
            }]);
            setStatus("Relationship added. Save the schema to apply it.");
        } catch {
            setStatus("The dragged field could not be read.");
        }
    }

    function getRelationshipLabel(relationship) {
        const sourceTable = tables.find((table) => table.id === relationship.sourceTableId);
        const targetTable = tables.find((table) => table.id === relationship.targetTableId);
        const sourceColumn = sourceTable?.columns.find((column) => column.id === relationship.sourceColumnId);
        const targetColumn = targetTable?.columns.find((column) => column.id === relationship.targetColumnId);
        return {
            source: `${sourceTable?.name || "Unknown"}.${sourceColumn?.name || "field"}`,
            target: `${targetTable?.name || "Unknown"}.${targetColumn?.name || "field"}`,
        };
    }

    return (
        <div className="configuration-page">
            <header className="configuration-header">
                <a className="configuration-brand" href="/">Rover</a>
                <span>Database configurations</span>
                <nav aria-label="Main navigation">
                    <a href="/DesignDashboard">Workspace</a>
                    <span>{username}</span>
                    <UserAvatar href="/Rover/Profile" label="Open your profile" />
                </nav>
            </header>
            <div className="configuration-layout">
                <aside aria-label="Database navigation" className="configuration-sidebar">
                    <div className="configuration-sidebar-heading">
                        <h2>Databases</h2><span>{databases.length}</span>
                    </div>
                    <form className="configuration-create-form" onSubmit={createDatabase}>
                        <input
                            aria-label="Database name"
                            maxLength={128}
                            onChange={(event) => setNewDatabaseName(event.target.value)}
                            placeholder="New database"
                            required
                            value={newDatabaseName}
                        />
                        <button disabled={!newDatabaseName.trim()} type="submit">Create</button>
                    </form>
                    <label className="configuration-import-button">
                        Import SQLite
                        <input accept=".sqlite3,.sqlite,.db" onChange={importDatabase} type="file" />
                    </label>
                    <nav aria-label="Saved databases" className="configuration-database-list">
                        {databases.map((database) => (
                            <button
                                aria-current={selected?.id === database.id ? "page" : undefined}
                                className={selected?.id === database.id ? "is-selected" : ""}
                                key={database.id}
                                onClick={() => selectDatabase(database.id)}
                                type="button"
                            >
                                <span>{database.name}</span><small>{database.table_count} tables</small>
                            </button>
                        ))}
                    </nav>
                    <p className="configuration-status" role="status">{status}</p>
                </aside>
                <main className="configuration-main">
                    <div className="configuration-toolbar">
                        <div>
                            <p className="configuration-eyebrow">Schema editor</p>
                            <h1>{selected ? selected.name : "Database configurations"}</h1>
                        </div>
                        <div className="configuration-actions">
                            {selected && (
                                <>
                                    <input
                                        aria-label="Database name"
                                        maxLength={128}
                                        onChange={(event) => setDatabaseName(event.target.value)}
                                        value={databaseName}
                                    />
                                    <button onClick={deleteDatabase} type="button">Delete</button>
                                    <button className="configuration-primary" onClick={saveSchema} type="button">Save</button>
                                </>
                            )}
                        </div>
                    </div>
                    <nav aria-label="Schema tools" className="configuration-nav">
                        <div className="configuration-nav-tabs">
                            <button
                                aria-pressed={activeSection === "schema"}
                                className={activeSection === "schema" ? "is-active" : ""}
                                onClick={() => setActiveSection("schema")}
                                type="button"
                            >
                                Schema
                            </button>
                            <button
                                aria-pressed={activeSection === "relationships"}
                                className={activeSection === "relationships" ? "is-active" : ""}
                                onClick={() => setActiveSection("relationships")}
                                type="button"
                            >
                                Relationships <span>{relationships.length}</span>
                            </button>
                        </div>
                        <div aria-label="Relationship line colors" className="configuration-color-nav" role="group">
                            <span>Line color</span>
                            {RELATIONSHIP_COLORS.map((color) => (
                                <button
                                    aria-label={`${color.name} relationship line`}
                                    aria-pressed={activeColor === color.value}
                                    className={activeColor === color.value ? "is-selected" : ""}
                                    key={color.value}
                                    onClick={() => setActiveColor(color.value)}
                                    style={{ "--relationship-color": color.value }}
                                    title={color.name}
                                    type="button"
                                />
                            ))}
                        </div>
                    </nav>
                    {activeSection === "schema" ? (
                        <section aria-label="Schema tables" className="configuration-canvas">
                            {selected ? (
                                <>
                                    <div className="configuration-canvas-heading">
                                        <p>Drag a field handle onto a field in another table to create a relationship.</p>
                                        <button disabled={tables.length >= 200} onClick={addTable} type="button">Add table</button>
                                    </div>
                                    <div className="configuration-table-grid" ref={tableGridRef}>
                                        <svg
                                            aria-hidden="true"
                                            className="configuration-relationship-lines"
                                            preserveAspectRatio="none"
                                            viewBox={`0 0 ${lineCanvasSize.width} ${lineCanvasSize.height}`}
                                        >
                                            {relationshipLines.map((line) => (
                                                <path d={line.path} key={line.id} stroke={line.color} strokeWidth="2" fill="none" />
                                            ))}
                                        </svg>
                                        {tables.map((table) => (
                                            <article className="configuration-table" key={table.id}>
                                                <header>
                                                    <input
                                                        aria-label="Table name"
                                                        maxLength={64}
                                                        onChange={(event) => updateTable(table.id, { name: event.target.value })}
                                                        value={table.name}
                                                    />
                                                    <button aria-label={`Delete ${table.name}`} onClick={() => removeTable(table.id)} type="button">×</button>
                                                </header>
                                                <div className="configuration-fields">
                                                    {table.columns.map((column) => {
                                                        const fieldKey = `${table.id}:${column.id}`;
                                                        return (
                                                            <div
                                                                className={`configuration-field${dropTarget === fieldKey ? " is-drop-target" : ""}`}
                                                                key={column.id}
                                                                ref={(element) => {
                                                                    if (element) fieldRefs.current.set(fieldKey, element);
                                                                    else fieldRefs.current.delete(fieldKey);
                                                                }}
                                                                onDragLeave={() => setDropTarget("")}
                                                                onDragOver={(event) => {
                                                                    const types = Array.from(event.dataTransfer.types);
                                                                    if (!types.includes(FIELD_DRAG_TYPE) && !types.includes("text/plain")) return;
                                                                    event.preventDefault();
                                                                    event.dataTransfer.dropEffect = "link";
                                                                    setDropTarget(fieldKey);
                                                                }}
                                                                onDrop={(event) => handleFieldDrop(event, table.id, column.id)}
                                                            >
                                                                <button
                                                                    aria-label={`Drag ${table.name}.${column.name} to create a relationship`}
                                                                    className="configuration-drag-handle"
                                                                    draggable
                                                                    onDragEnd={() => setDropTarget("")}
                                                                    onDragStart={(event) => {
                                                                        const source = JSON.stringify({ tableId: table.id, columnId: column.id });
                                                                        event.dataTransfer.effectAllowed = "link";
                                                                        event.dataTransfer.setData(FIELD_DRAG_TYPE, source);
                                                                        event.dataTransfer.setData("text/plain", source);
                                                                    }}
                                                                    title="Drag to another table field"
                                                                    type="button"
                                                                >
                                                                    ⠿
                                                                </button>
                                                                <input
                                                                    aria-label="Field name"
                                                                    maxLength={64}
                                                                    onChange={(event) => updateColumn(table.id, column.id, { name: event.target.value })}
                                                                    value={column.name}
                                                                />
                                                                <select
                                                                    aria-label="Field type"
                                                                    onChange={(event) => updateColumn(table.id, column.id, { type: event.target.value })}
                                                                    value={column.type}
                                                                >
                                                                    {DATA_TYPES.map((type) => <option key={type}>{type}</option>)}
                                                                </select>
                                                                <label title="Primary key">
                                                                    <input
                                                                        checked={column.primaryKey}
                                                                        onChange={(event) => updateColumn(table.id, column.id, { primaryKey: event.target.checked })}
                                                                        type="checkbox"
                                                                    />
                                                                    PK
                                                                </label>
                                                                <button
                                                                    aria-label={`Delete field ${column.name}`}
                                                                    disabled={table.columns.length <= 1}
                                                                    onClick={() => removeColumn(table.id, column.id)}
                                                                    type="button"
                                                                >
                                                                    ×
                                                                </button>
                                                            </div>
                                                        );
                                                    })}
                                                </div>
                                                <button className="configuration-add-field" onClick={() => addColumn(table.id)} type="button">Add field</button>
                                            </article>
                                        ))}
                                        {!tables.length && (
                                            <div className="configuration-empty">
                                                <h2>Start with a blank schema</h2>
                                                <p>Add a table, then define its fields. Drag field handles between tables to connect them.</p>
                                                <button onClick={addTable} type="button">Add first table</button>
                                            </div>
                                        )}
                                    </div>
                                </>
                            ) : (
                                <div className="configuration-empty">
                                    <h2>No database selected</h2>
                                    <p>Create a database or import a SQLite file from the navigation panel.</p>
                                </div>
                            )}
                        </section>
                    ) : (
                        <section aria-label="Database relationships" className="configuration-relationships">
                            <div>
                                <h2>Relationships</h2>
                                <p>Choose a line color, then drag a field handle between tables in the Schema view.</p>
                            </div>
                            {relationships.length ? (
                                <ul>
                                    {relationships.map((relationship) => {
                                        const label = getRelationshipLabel(relationship);
                                        return (
                                            <li key={relationship.id}>
                                                <span aria-hidden="true" className="configuration-line-preview" style={{ backgroundColor: relationship.color }} />
                                                <span>{label.source} <span aria-hidden="true">→</span> {label.target}</span>
                                                <button
                                                    aria-label={`Remove relationship from ${label.source} to ${label.target}`}
                                                    onClick={() => setRelationships((items) => items.filter((item) => item.id !== relationship.id))}
                                                    type="button"
                                                >
                                                    Remove
                                                </button>
                                            </li>
                                        );
                                    })}
                                </ul>
                            ) : <p className="configuration-empty-message">No relationships yet.</p>}
                        </section>
                    )}
                </main>
            </div>
        </div>
    );
}
