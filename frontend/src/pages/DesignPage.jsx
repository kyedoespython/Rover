import React, { useEffect, useRef, useState } from "react";

const DATA_TYPES = [
    "AutoNumber",
    "Short Text",
    "Long Text",
    "Number",
    "Decimal",
    "Date/Time",
    "Yes/No",
    "Currency",
    "Attachment",
];
const LINE_COLORS = ["#2878b5", "#d64545", "#2b8a3e", "#9c36b5", "#e67700", "#00838f", "#343a40"];

async function requestJson(url, options = {}) {
    const response = await fetch(url, {
        credentials: "same-origin",
        headers: { Accept: "application/json", ...options.headers },
        ...options,
    });
    const result = await response.json();
    if (!response.ok) {
        throw new Error(result.error || "The request could not be completed.");
    }
    return result;
}

function createId() {
    return crypto.randomUUID();
}

export default function DesignPage({ csrfToken }) {
    const [databases, setDatabases] = useState([]);
    const [selected, setSelected] = useState(null);
    const [name, setName] = useState("");
    const [tables, setTables] = useState([]);
    const [relationships, setRelationships] = useState([]);
    const [relationshipSourceId, setRelationshipSourceId] = useState("");
    const [relationshipTargetId, setRelationshipTargetId] = useState("");
    const [activeView, setActiveView] = useState("tables");
    const [status, setStatus] = useState("Loading saved databases...");
    const [query, setQuery] = useState("SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name;");
    const [queryResult, setQueryResult] = useState(null);
    const [queryStatus, setQueryStatus] = useState("");
    const [demoOpen, setDemoOpen] = useState(false);
    const [demoActiveUsers, setDemoActiveUsers] = useState(0);
    const demoDialog = useRef(null);

    useEffect(() => {
        const dialog = demoDialog.current;
        if (!dialog) return;
        if (demoOpen && !dialog.open) dialog.showModal();
        if (!demoOpen && dialog.open) dialog.close();
    }, [demoOpen]);

    useEffect(() => {
        if (!demoOpen) return undefined;
        const timer = window.setInterval(() => {
            setDemoActiveUsers((count) => (count + 1) % 9);
        }, 850);
        return () => window.clearInterval(timer);
    }, [demoOpen]);

    async function loadDatabases() {
        const result = await requestJson("/api/schema");
        setDatabases(result.databases);
        setStatus(result.databases.length ? "" : "Create a database or load a SQLite file.");
    }

    useEffect(() => {
        loadDatabases().catch((error) => setStatus(error.message));
    }, []);

    async function selectDatabase(databaseId) {
        setStatus("Loading database...");
        try {
            const result = await requestJson(`/api/schema/${databaseId}`);
            setSelected(result.database);
            setName(result.database.name);
            setTables(result.schema.tables);
            setRelationships(result.schema.relationships);
            setQueryResult(null);
            setStatus(`Loaded ${result.database.name}.`);
        } catch (error) {
            setStatus(error.message);
        }
    }

    async function createDatabase(event) {
        event.preventDefault();
        const formData = new FormData(event.currentTarget);
        const databaseName = String(formData.get("name") || "").trim();
        if (!databaseName) {
            setStatus("Enter a name for the new database.");
            return;
        }
        try {
            const result = await requestJson("/api/schema", {
                method: "POST",
                headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken },
                body: JSON.stringify({ name: databaseName, schema: { tables: [], relationships: [] } }),
            });
            await loadDatabases();
            await selectDatabase(result.database.id);
        } catch (error) {
            setStatus(error.message);
        }
    }

    async function importDatabase(event) {
        const file = event.target.files?.[0];
        if (!file) return;
        const data = new FormData();
        data.append("file", file);
        try {
            const result = await requestJson("/api/schema/import", {
                method: "POST",
                headers: { "X-CSRFToken": csrfToken },
                body: data,
            });
            await loadDatabases();
            await selectDatabase(result.database.id);
        } catch (error) {
            setStatus(error.message);
        } finally {
            event.target.value = "";
        }
    }

    async function saveSchema() {
        if (!selected) return;
        setStatus("Saving schema...");
        try {
            const result = await requestJson(`/api/schema/${selected.id}`, {
                method: "PUT",
                headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken },
                body: JSON.stringify({ name, schema: { tables, relationships } }),
            });
            setSelected(result.database);
            setDatabases((items) => items.map((item) => item.id === result.database.id ? result.database : item));
            setStatus(`Saved ${result.metadata.table_count} tables and ${result.metadata.column_count} fields.`);
        } catch (error) {
            setStatus(error.message);
        }
    }

    async function deleteDatabase(database) {
        if (!window.confirm(`Delete "${database.name}"?`)) return;
        try {
            await requestJson(`/api/schema/${database.id}`, {
                method: "DELETE",
                headers: { "X-CSRFToken": csrfToken },
            });
            setDatabases((items) => items.filter((item) => item.id !== database.id));
            if (selected?.id === database.id) {
                setSelected(null);
                setName("");
                setTables([]);
                setRelationships([]);
            }
            setStatus("Database deleted.");
        } catch (error) {
            setStatus(error.message);
        }
    }

    function addTable() {
        const id = createId();
        setTables((items) => [...items, {
            id,
            name: `Table${items.length + 1}`,
            x: 24 + items.length * 24,
            y: 24 + items.length * 24,
            columns: [{ id: createId(), name: "id", type: "AutoNumber", primaryKey: true }],
        }]);
    }

    function updateTable(tableId, changes) {
        setTables((items) => items.map((table) => table.id === tableId ? { ...table, ...changes } : table));
    }

    function addColumn(tableId) {
        setTables((items) => items.map((table) => table.id === tableId ? {
            ...table,
            columns: [...table.columns, { id: createId(), name: `field${table.columns.length + 1}`, type: "Short Text", primaryKey: false }],
        } : table));
    }

    function updateColumn(tableId, columnId, changes) {
        setTables((items) => items.map((table) => table.id === tableId ? {
            ...table,
            columns: table.columns.map((column) => column.id === columnId ? { ...column, ...changes } : column),
        } : table));
    }

    function removeColumn(tableId, columnId) {
        setTables((items) => items.map((table) => table.id === tableId ? {
            ...table,
            columns: table.columns.filter((column) => column.id !== columnId),
        } : table));
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

    async function runQuery(event) {
        event.preventDefault();
        if (!selected) return;
        setQueryStatus("Running query...");
        try {
            const result = await requestJson(`/api/schema/${selected.id}/query`, {
                method: "POST",
                headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken },
                body: JSON.stringify({ query }),
            });
            setQueryResult(result);
            setQueryStatus(result.truncated ? "Showing the first 200 rows." : `${result.rows.length} rows returned.`);
        } catch (error) {
            setQueryResult(null);
            setQueryStatus(error.message);
        }
    }

    function addRelationship(event) {
        event.preventDefault();
        const data = new FormData(event.currentTarget);
        const sourceTableId = String(data.get("sourceTableId"));
        const targetTableId = String(data.get("targetTableId"));
        const relationship = {
            id: createId(),
            sourceTableId,
            targetTableId,
            sourceColumnId: String(data.get("sourceColumnId")),
            targetColumnId: String(data.get("targetColumnId")),
            color: String(data.get("color")),
        };
        setRelationships((items) => [...items, relationship]);
    }

    const sourceTable = tables.find((table) => table.id === relationshipSourceId) || tables[0];
    const targetTable = tables.find((table) => table.id === relationshipTargetId && table.id !== sourceTable?.id)
        || tables.find((table) => table.id !== sourceTable?.id);

    function openDemo() {
        if (!selected) {
            setStatus("Create or load a database before starting the traffic demo.");
            return;
        }
        setDemoActiveUsers(0);
        setDemoOpen(true);
    }

    return (
        <div className="design-react-page">
            <nav className="design-react-nav" aria-label="Main navigation">
                <div><a href="/">Home</a><a href="/Rover/Notes">Notes</a></div>
                <a href="/Rover/Support">Support</a>
            </nav>
            <h1>Your designs</h1>
            <div className="design-react-layout">
                <aside className="design-library">
                    <h2>SQLite databases</h2>
                    <form onSubmit={createDatabase}>
                        <label htmlFor="designDatabaseName">New database</label>
                        <input id="designDatabaseName" maxLength={128} name="name" placeholder="Database name" required />
                        <button type="submit">Create database</button>
                    </form>
                    <label className="design-file-button">
                        Load SQLite file
                        <input accept=".sqlite3,.sqlite,.db" onChange={importDatabase} type="file" />
                    </label>
                    <p className="design-status" role="status">{status}</p>
                    <ul className="design-database-list">
                        {databases.map((database) => (
                            <li key={database.id}>
                                <button
                                    className={selected?.id === database.id ? "is-selected" : ""}
                                    onClick={() => selectDatabase(database.id)}
                                    type="button"
                                >
                                    <strong>{database.name}</strong>
                                    <span>{database.table_count} tables · {database.file_name}</span>
                                </button>
                                <button aria-label={`Delete ${database.name}`} onClick={() => deleteDatabase(database)} type="button">×</button>
                            </li>
                        ))}
                    </ul>
                </aside>
                <section className="design-editor">
                    <div className="design-toolbar">
                        {["tables", "relationships", "query"].map((view) => (
                            <button
                                aria-pressed={activeView === view}
                                key={view}
                                onClick={() => setActiveView(view)}
                                type="button"
                            >
                                {view[0].toUpperCase() + view.slice(1)}
                            </button>
                        ))}
                        <button disabled={!selected} onClick={openDemo} type="button">Traffic demo</button>
                        <input
                            aria-label="Database name"
                            disabled={!selected}
                            maxLength={128}
                            onChange={(event) => setName(event.target.value)}
                            value={name}
                        />
                        <button disabled={!selected} onClick={saveSchema} type="button">Save changes</button>
                    </div>
                    {activeView === "tables" && (
                        <section className="design-table-view">
                            <button disabled={!selected} onClick={addTable} type="button">Add table</button>
                            <div className="design-table-grid">
                                {tables.map((table) => (
                                    <article className="design-table" key={table.id}>
                                        <header>
                                            <input aria-label="Table name" maxLength={64} onChange={(event) => updateTable(table.id, { name: event.target.value })} value={table.name} />
                                            <button aria-label={`Remove ${table.name}`} onClick={() => removeTable(table.id)} type="button">×</button>
                                        </header>
                                        {table.columns.map((column) => (
                                            <div className="design-column" key={column.id}>
                                                <input aria-label="Field name" maxLength={64} onChange={(event) => updateColumn(table.id, column.id, { name: event.target.value })} value={column.name} />
                                                <select aria-label="Field type" onChange={(event) => updateColumn(table.id, column.id, { type: event.target.value })} value={column.type}>
                                                    {DATA_TYPES.map((type) => <option key={type}>{type}</option>)}
                                                </select>
                                                <label>
                                                    <input checked={column.primaryKey} onChange={(event) => updateColumn(table.id, column.id, { primaryKey: event.target.checked })} type="checkbox" />
                                                    PK
                                                </label>
                                                <button aria-label={`Remove field ${column.name}`} onClick={() => removeColumn(table.id, column.id)} type="button">×</button>
                                            </div>
                                        ))}
                                        <button onClick={() => addColumn(table.id)} type="button">Add field</button>
                                    </article>
                                ))}
                                {!tables.length && <p className="design-empty">Create or load a database to begin designing its tables.</p>}
                            </div>
                        </section>
                    )}
                    {activeView === "relationships" && (
                        <section className="design-relationship-view">
                            {tables.length > 1 ? (
                                <form onSubmit={addRelationship}>
                                    <label>From table<select name="sourceTableId" onChange={(event) => setRelationshipSourceId(event.target.value)} required value={sourceTable?.id || ""}>{tables.map((table) => <option key={table.id} value={table.id}>{table.name}</option>)}</select></label>
                                    <label>From field<select key={sourceTable?.id} name="sourceColumnId" required>{(sourceTable?.columns || []).map((column) => <option key={column.id} value={column.id}>{column.name}</option>)}</select></label>
                                    <label>To table<select name="targetTableId" onChange={(event) => setRelationshipTargetId(event.target.value)} required value={targetTable?.id || ""}>{tables.filter((table) => table.id !== sourceTable?.id).map((table) => <option key={table.id} value={table.id}>{table.name}</option>)}</select></label>
                                    <label>To field<select key={targetTable?.id} name="targetColumnId" required>{(targetTable?.columns || []).map((column) => <option key={column.id} value={column.id}>{column.name}</option>)}</select></label>
                                    <label>Line color<select name="color">{LINE_COLORS.map((color) => <option key={color} value={color}>{color}</option>)}</select></label>
                                    <button type="submit">Add relationship</button>
                                </form>
                            ) : <p>Add two tables before creating a relationship.</p>}
                            <ul>{relationships.map((relationship) => {
                                const from = tables.find((table) => table.id === relationship.sourceTableId);
                                const to = tables.find((table) => table.id === relationship.targetTableId);
                                return <li key={relationship.id}>{from?.name} → {to?.name} <button onClick={() => setRelationships((items) => items.filter((item) => item.id !== relationship.id))} type="button">Remove</button></li>;
                            })}</ul>
                        </section>
                    )}
                    {activeView === "query" && (
                        <section className="design-query-view">
                            <form onSubmit={runQuery}>
                                <label htmlFor="schemaQuery">Read-only SQL query</label>
                                <textarea id="schemaQuery" maxLength={10000} onChange={(event) => setQuery(event.target.value)} value={query} />
                                <button disabled={!selected} type="submit">Run query</button>
                            </form>
                            <p role="status">{queryStatus}</p>
                            {queryResult && (
                                <div className="design-query-results">
                                    <table>
                                        <thead><tr>{queryResult.columns.map((column) => <th key={column}>{column}</th>)}</tr></thead>
                                        <tbody>{queryResult.rows.map((row, index) => <tr key={index}>{row.map((value, cell) => <td key={cell}>{value == null ? "NULL" : typeof value === "object" ? JSON.stringify(value) : String(value)}</td>)}</tr>)}</tbody>
                                    </table>
                                </div>
                            )}
                        </section>
                    )}
                </section>
            </div>
            <dialog className="design-demo-dialog" onClose={() => setDemoOpen(false)} ref={demoDialog}>
                <header>
                    <div>
                        <h2>Database traffic demo</h2>
                        <p>Simulated traffic passing through {selected?.name}.</p>
                    </div>
                    <button aria-label="Close traffic demo" onClick={() => setDemoOpen(false)} type="button">Close</button>
                </header>
                <div className="design-demo-track">
                    <div className="design-demo-nodes">
                        {tables.slice(0, 8).map((table, index) => (
                            <span className="design-demo-node" key={table.id} style={{ animationDelay: `${index * 0.12}s` }}>
                                {table.name}
                            </span>
                        ))}
                        {!tables.length && <span className="design-empty">No tables in this database yet.</span>}
                    </div>
                    <span aria-hidden="true" className="design-demo-packet" />
                </div>
                <footer>
                    <span role="status">Simulated active users: {demoActiveUsers}</span>
                    <span>{tables.length > 8 ? `Showing 8 of ${tables.length} tables.` : `${tables.length} table${tables.length === 1 ? "" : "s"} in this model.`}</span>
                </footer>
            </dialog>
        </div>
    );
}
