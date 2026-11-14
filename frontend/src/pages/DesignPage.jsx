import React, { useEffect, useState } from "react";

import UserAvatar from "../components/UserAvatar.jsx";

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

function ProjectTree({ items, parentId = null, depth = 0, selectedId, onSelect, onRename, onDelete }) {
    const children = items.filter((item) => item.parentId === parentId);
    if (!children.length) return null;

    return (
        <ul className="project-tree">
            {children.map((item) => (
                <li key={item.id}>
                    <div className="project-tree-row" style={{ "--tree-depth": depth }}>
                        <button
                            aria-pressed={selectedId === item.id}
                            className="project-tree-item"
                            onClick={() => onSelect(item)}
                            type="button"
                        >
                            <span aria-hidden="true">{item.kind === "folder" ? "▸" : "·"}</span>
                            <span>{item.name}</span>
                        </button>
                        <button aria-label={`Rename ${item.name}`} onClick={() => onRename(item)} type="button">···</button>
                        <button aria-label={`Delete ${item.name}`} onClick={() => onDelete(item)} type="button">×</button>
                    </div>
                    {item.kind === "folder" && (
                        <ProjectTree
                            depth={depth + 1}
                            items={items}
                            onDelete={onDelete}
                            onRename={onRename}
                            onSelect={onSelect}
                            parentId={item.id}
                            selectedId={selectedId}
                        />
                    )}
                </li>
            ))}
        </ul>
    );
}

export default function DesignPage({ csrfToken, username = "" }) {
    const [databases, setDatabases] = useState([]);
    const [selected, setSelected] = useState(null);
    const [name, setName] = useState("");
    const [tables, setTables] = useState([]);
    const [relationships, setRelationships] = useState([]);
    const [relationshipSourceId, setRelationshipSourceId] = useState("");
    const [relationshipTargetId, setRelationshipTargetId] = useState("");
    const [activeView, setActiveView] = useState("project");
    const [status, setStatus] = useState("Loading saved databases...");
    const [query, setQuery] = useState("SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name;");
    const [queryResult, setQueryResult] = useState(null);
    const [queryStatus, setQueryStatus] = useState("");
    const [projects, setProjects] = useState([]);
    const [selectedProject, setSelectedProject] = useState(null);
    const [projectItems, setProjectItems] = useState([]);
    const [selectedItemId, setSelectedItemId] = useState(null);
    const [fileContent, setFileContent] = useState("");
    const [projectDraft, setProjectDraft] = useState("");
    const [projectStatus, setProjectStatus] = useState("Loading projects...");
    const [newItemName, setNewItemName] = useState("");
    const [newItemKind, setNewItemKind] = useState("file");
    const [browseTable, setBrowseTable] = useState("");
    const [browseOffset, setBrowseOffset] = useState(0);
    const [browseResult, setBrowseResult] = useState(null);
    const [browseStatus, setBrowseStatus] = useState("");

    async function loadDatabases() {
        const result = await requestJson("/api/schema");
        setDatabases(result.databases);
        setStatus(result.databases.length ? "" : "Create a database or load a SQLite file.");
    }

    useEffect(() => {
        loadDatabases().catch((error) => setStatus(error.message));
        loadProjects().catch((error) => setProjectStatus(error.message));
    }, []);

    async function loadBrowseData(databaseId, tableName, offset = 0) {
        if (!databaseId || !tableName) {
            setBrowseResult(null);
            setBrowseStatus("Choose a database table to browse its rows.");
            return;
        }
        setBrowseTable(tableName);
        setBrowseOffset(offset);
        setBrowseStatus("Loading rows...");
        try {
            const escapedName = tableName.replaceAll('"', '""');
            const result = await requestJson(`/api/schema/${databaseId}/query`, {
                method: "POST",
                headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken },
                body: JSON.stringify({ query: `SELECT * FROM "${escapedName}" LIMIT 200 OFFSET ${offset}` }),
            });
            setBrowseResult(result);
            setBrowseStatus(`${result.rows.length} rows shown${result.rows.length === 200 ? " · more may be available" : ""}.`);
        } catch (error) {
            setBrowseResult(null);
            setBrowseStatus(error.message);
        }
    }

    async function selectDatabase(databaseId) {
        setStatus("Loading database...");
        try {
            const result = await requestJson(`/api/schema/${databaseId}`);
            setSelected(result.database);
            setName(result.database.name);
            setTables(result.schema.tables);
            setRelationships(result.schema.relationships);
            setQueryResult(null);
            setActiveView("data");
            setStatus(`Loaded ${result.database.name}.`);
            const firstTable = result.schema.tables[0]?.name || "";
            await loadBrowseData(databaseId, firstTable);
        } catch (error) {
            setStatus(error.message);
        }
    }

    async function loadProjects() {
        const result = await requestJson("/api/projects");
        setProjects(result.projects);
        setProjectStatus(result.projects.length ? "" : "Create a project to get started.");
    }

    async function selectProject(projectId) {
        setProjectStatus("Loading project...");
        try {
            const result = await requestJson(`/api/projects/${projectId}`);
            setSelectedProject(result.project);
            setProjectItems(result.items);
            setSelectedItemId(null);
            setFileContent("");
            setActiveView("project");
            setProjectStatus("");
        } catch (error) {
            setProjectStatus(error.message);
        }
    }

    async function createProject(event) {
        event.preventDefault();
        const projectName = projectDraft.trim();
        if (!projectName) return;
        try {
            const result = await requestJson("/api/projects", {
                method: "POST",
                headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken },
                body: JSON.stringify({ name: projectName }),
            });
            setProjects((items) => [result.project, ...items]);
            setProjectDraft("");
            setSelectedProject(result.project);
            setProjectItems(result.items);
            setSelectedItemId(null);
            setFileContent("");
            setActiveView("project");
            setProjectStatus("");
        } catch (error) {
            setProjectStatus(error.message);
        }
    }

    async function renameProject() {
        if (!selectedProject) return;
        const projectName = window.prompt("Project name", selectedProject.name);
        if (projectName === null || !projectName.trim()) return;
        try {
            const result = await requestJson(`/api/projects/${selectedProject.id}`, {
                method: "PUT",
                headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken },
                body: JSON.stringify({ name: projectName }),
            });
            setSelectedProject(result.project);
            setProjects((items) => items.map((item) => item.id === result.project.id ? result.project : item));
            setProjectStatus("Project renamed.");
        } catch (error) {
            setProjectStatus(error.message);
        }
    }

    async function deleteProject() {
        if (!selectedProject || !window.confirm(`Delete project "${selectedProject.name}" and all its files?`)) return;
        try {
            await requestJson(`/api/projects/${selectedProject.id}`, {
                method: "DELETE",
                headers: { "X-CSRFToken": csrfToken },
            });
            setProjects((items) => items.filter((item) => item.id !== selectedProject.id));
            setSelectedProject(null);
            setProjectItems([]);
            setSelectedItemId(null);
            setFileContent("");
            setProjectStatus("Project deleted.");
        } catch (error) {
            setProjectStatus(error.message);
        }
    }

    async function createProjectItem(event) {
        event.preventDefault();
        if (!selectedProject || !newItemName.trim()) return;
        const selectedItem = projectItems.find((item) => item.id === selectedItemId);
        const parentId = selectedItem?.kind === "folder" ? selectedItem.id : selectedItem?.parentId || null;
        try {
            const result = await requestJson(`/api/projects/${selectedProject.id}/items`, {
                method: "POST",
                headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken },
                body: JSON.stringify({
                    name: newItemName,
                    kind: newItemKind,
                    parentId,
                    content: "",
                }),
            });
            setProjectItems(result.items);
            setNewItemName("");
            if (result.item.kind === "file") {
                setSelectedItemId(result.item.id);
                setFileContent("");
            }
            setActiveView("project");
            setProjectStatus(`${newItemKind === "folder" ? "Folder" : "File"} created.`);
        } catch (error) {
            setProjectStatus(error.message);
        }
    }

    async function renameProjectItem(item) {
        const itemName = window.prompt("Name", item.name);
        if (itemName === null || !itemName.trim()) return;
        try {
            const result = await requestJson(`/api/projects/${selectedProject.id}/items/${item.id}`, {
                method: "PATCH",
                headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken },
                body: JSON.stringify({ name: itemName }),
            });
            setProjectItems(result.items);
            setProjectStatus("Item renamed.");
        } catch (error) {
            setProjectStatus(error.message);
        }
    }

    async function deleteProjectItem(item) {
        if (item.kind === "folder" && !window.confirm(`Delete "${item.name}" and everything inside it?`)) return;
        try {
            const result = await requestJson(`/api/projects/${selectedProject.id}/items/${item.id}`, {
                method: "DELETE",
                headers: { "X-CSRFToken": csrfToken },
            });
            setProjectItems(result.items);
            if (result.items.every((entry) => entry.id !== selectedItemId)) {
                setSelectedItemId(null);
                setFileContent("");
            }
            setProjectStatus("Item deleted.");
        } catch (error) {
            setProjectStatus(error.message);
        }
    }

    async function saveFile() {
        const item = projectItems.find((entry) => entry.id === selectedItemId);
        if (!selectedProject || !item || item.kind !== "file") return;
        try {
            const result = await requestJson(`/api/projects/${selectedProject.id}/items/${item.id}`, {
                method: "PATCH",
                headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken },
                body: JSON.stringify({ content: fileContent }),
            });
            setProjectItems(result.items);
            setProjectStatus("File saved.");
        } catch (error) {
            setProjectStatus(error.message);
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
                setBrowseTable("");
                setBrowseResult(null);
                setBrowseStatus("");
                setQueryResult(null);
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
    const selectedProjectItem = projectItems.find((item) => item.id === selectedItemId);

    return (
        <div className="design-react-page builder-page">
            <header className="builder-header">
                <a className="builder-brand" href="/">Rover</a>
                <span className="builder-header-title">Workspace</span>
                <nav aria-label="Workspace navigation" className="builder-header-actions">
                    <a href="/">Home</a>
                    <span>{username}</span>
                    <UserAvatar href="/Rover/Profile" label="Open your profile" />
                </nav>
            </header>
            <div className="builder-layout">
                <aside aria-label="Project and database explorer" className="builder-sidebar">
                    <section className="builder-sidebar-section">
                        <div className="builder-section-heading"><h2>Projects</h2><span>{projects.length}</span></div>
                        <form className="builder-create-project" onSubmit={createProject}>
                            <input aria-label="New project name" maxLength={128} onChange={(event) => setProjectDraft(event.target.value)} placeholder="New project" value={projectDraft} />
                            <button aria-label="Create project" disabled={!projectDraft.trim()} type="submit">+</button>
                        </form>
                        <div className="builder-project-list">
                            {projects.map((project) => (
                                <button
                                    aria-current={selectedProject?.id === project.id ? "page" : undefined}
                                    className={selectedProject?.id === project.id ? "is-selected" : ""}
                                    key={project.id}
                                    onClick={() => selectProject(project.id)}
                                    type="button"
                                >
                                    <span aria-hidden="true">▰</span>{project.name}
                                </button>
                            ))}
                        </div>
                        {selectedProject && (
                            <>
                                <div className="builder-section-heading builder-files-heading">
                                    <h3>{selectedProject.name}</h3>
                                    <div>
                                        <button aria-label="Rename project" onClick={renameProject} type="button">···</button>
                                        <button aria-label="Delete project" onClick={deleteProject} type="button">×</button>
                                    </div>
                                </div>
                                <form className="builder-create-item" onSubmit={createProjectItem}>
                                    <select aria-label="Item type" onChange={(event) => setNewItemKind(event.target.value)} value={newItemKind}>
                                        <option value="file">File</option>
                                        <option value="folder">Folder</option>
                                    </select>
                                    <input aria-label={`New ${newItemKind} name`} maxLength={128} onChange={(event) => setNewItemName(event.target.value)} placeholder={newItemKind === "folder" ? "Folder name" : "File name"} value={newItemName} />
                                    <button aria-label={`Create ${newItemKind}`} disabled={!newItemName.trim()} type="submit">+</button>
                                </form>
                                <ProjectTree
                                    items={projectItems}
                                    onDelete={deleteProjectItem}
                                    onRename={renameProjectItem}
                                    onSelect={(item) => {
                                        setSelectedItemId(item.id);
                                        setFileContent(item.kind === "file" ? item.content : "");
                                        setActiveView("project");
                                    }}
                                    selectedId={selectedItemId}
                                />
                            </>
                        )}
                        {projectStatus && <p className="builder-status" role="status">{projectStatus}</p>}
                    </section>
                    <section className="builder-sidebar-section builder-databases">
                        <div className="builder-section-heading"><h2>Databases</h2><span>{databases.length}</span></div>
                        <form className="builder-create-database" onSubmit={createDatabase}>
                            <input aria-label="New database name" maxLength={128} name="name" placeholder="New database" required />
                            <button type="submit">Create</button>
                        </form>
                        <label className="builder-import-button">
                            Import SQLite
                            <input accept=".sqlite3,.sqlite,.db" onChange={importDatabase} type="file" />
                        </label>
                        <ul className="builder-database-list">
                            {databases.map((database) => (
                                <li key={database.id}>
                                    <button
                                        aria-current={selected?.id === database.id ? "true" : undefined}
                                        className={selected?.id === database.id ? "is-selected" : ""}
                                        onClick={() => selectDatabase(database.id)}
                                        type="button"
                                    >
                                        <span>{database.name}</span><small>{database.table_count} tables</small>
                                    </button>
                                    <button aria-label={`Delete ${database.name}`} onClick={() => deleteDatabase(database)} type="button">×</button>
                                </li>
                            ))}
                        </ul>
                        {status && <p className="builder-status" role="status">{status}</p>}
                    </section>
                </aside>
                <main className="builder-main">
                    <nav aria-label="Workspace views" className="builder-tabs">
                        {[
                            ["project", "Project"],
                            ["data", "Browse data"],
                            ["tables", "Schema"],
                            ["relationships", "Relations"],
                            ["query", "SQL"],
                        ].map(([view, label]) => (
                            <button
                                aria-pressed={activeView === view}
                                className={activeView === view ? "is-active" : ""}
                                key={view}
                                onClick={() => setActiveView(view)}
                                type="button"
                            >
                                {label}
                            </button>
                        ))}
                        <span className="builder-current-database">{selected?.name || "No database selected"}</span>
                    </nav>
                    <section className="design-editor">
                    {activeView === "project" && (
                        <section aria-label="Project editor" className="builder-workspace-panel">
                            {selectedProject ? (
                                selectedProjectItem?.kind === "file" ? (
                                    <div className="builder-file-editor">
                                        <div className="builder-panel-heading">
                                            <div><p className="builder-eyebrow">{selectedProject.name}</p><h1>{selectedProjectItem.name}</h1></div>
                                            <button className="builder-primary-button" onClick={saveFile} type="button">Save file</button>
                                        </div>
                                        <textarea aria-label={`${selectedProjectItem.name} contents`} onChange={(event) => setFileContent(event.target.value)} spellCheck="false" value={fileContent} />
                                        <p className="builder-status" role="status">{projectStatus || "Save your edits to update this file."}</p>
                                    </div>
                                ) : selectedProjectItem?.kind === "folder" ? (
                                    <div className="builder-empty-state"><span aria-hidden="true">▱</span><h1>{selectedProjectItem.name}</h1><p>Create a file or folder in this directory using the explorer.</p></div>
                                ) : (
                                    <div className="builder-empty-state"><span aria-hidden="true">⌘</span><h1>{selectedProject.name}</h1><p>Create files and folders from the explorer, then open a file to edit it.</p></div>
                                )
                            ) : (
                                <div className="builder-empty-state"><span aria-hidden="true">⌘</span><h1>Your project workspace</h1><p>Create or select a project in the explorer to start adding files.</p></div>
                            )}
                        </section>
                    )}
                    {activeView === "data" && (
                        <section aria-label="Database table data" className="builder-workspace-panel builder-data-panel">
                            <div className="builder-panel-heading">
                                <div><p className="builder-eyebrow">{selected?.file_name || "SQLite viewer"}</p><h1>Browse data</h1></div>
                                <label>Table
                                    <select disabled={!selected || !tables.length} onChange={(event) => loadBrowseData(selected?.id, event.target.value, 0)} value={browseTable}>
                                        {tables.map((table) => <option key={table.id} value={table.name}>{table.name}</option>)}
                                    </select>
                                </label>
                            </div>
                            <p className="builder-status" role="status">{browseStatus}</p>
                            {browseResult && (
                                <>
                                    <div className="builder-data-grid">
                                        <table>
                                            <thead><tr>{browseResult.columns.map((column) => <th key={column}>{column}</th>)}</tr></thead>
                                            <tbody>
                                                {browseResult.rows.map((row, rowIndex) => (
                                                    <tr key={rowIndex}>{row.map((value, cellIndex) => <td key={cellIndex}>{value == null ? <span className="builder-null">NULL</span> : typeof value === "object" ? JSON.stringify(value) : String(value)}</td>)}</tr>
                                                ))}
                                                {!browseResult.rows.length && <tr><td className="builder-empty-cell" colSpan={browseResult.columns.length}>This table has no rows.</td></tr>}
                                            </tbody>
                                        </table>
                                    </div>
                                    <div className="builder-pagination">
                                        <span>Rows {browseOffset + 1}{browseResult.rows.length ? `–${browseOffset + browseResult.rows.length}` : ""}</span>
                                        <button disabled={browseOffset === 0} onClick={() => loadBrowseData(selected.id, browseTable, Math.max(0, browseOffset - 200))} type="button">Previous</button>
                                        <button disabled={browseResult.rows.length < 200} onClick={() => loadBrowseData(selected.id, browseTable, browseOffset + 200)} type="button">Next</button>
                                    </div>
                                </>
                            )}
                            {!selected && <div className="builder-empty-state"><h1>No database selected</h1><p>Create or import a SQLite database from the explorer.</p></div>}
                        </section>
                    )}
                    {activeView === "tables" && (
                        <div className="builder-toolbar">
                            <input aria-label="Database name" disabled={!selected} maxLength={128} onChange={(event) => setName(event.target.value)} value={name} />
                            <button disabled={!selected} onClick={saveSchema} type="button">Save schema</button>
                            <button disabled={!selected} onClick={addTable} type="button">Add table</button>
                        </div>
                    )}
                    {activeView === "tables" && (
                        <section className="builder-workspace-panel builder-schema-panel design-table-view">
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
                </main>
            </div>
        </div>
    );
}
