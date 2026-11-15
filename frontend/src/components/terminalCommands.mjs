export const TERMINAL_HELP = `Project commands (paths start at the selected project's root):
  ls [folder]                  List files and folders
  mkdir <path>                 Create a folder
  touch <path>                 Create an empty file
  cat <path>                   Read a file
  write <path> <text>          Replace file content
  mv <path> <destination>      Move or rename an item
  rm <path>                    Delete a file or folder (with confirmation)
Database commands:
  db list                      List databases
  db create <name>             Create an empty database
  db show <name>               Read database tables and fields
  db rename <name> <new-name>  Rename a database
  db delete <name>             Delete a database (with confirmation)
  db query <name> <sql>        Run a read-only SQL query
Use quotes around names or text containing spaces. Type clear to clear the terminal.
Select Python for a separate in-browser Python session.
Rover commands manage Rover data; they do not run operating-system commands.`;

export function parseCommand(line) {
    const words = [];
    let word = "";
    let quote = null;
    let started = false;
    let escaped = false;
    for (const char of line) {
        if (escaped) {
            word += char;
            escaped = false;
            started = true;
        } else if (char === "\\" && quote !== "'") {
            escaped = true;
            started = true;
        } else if (quote) {
            if (char === quote) quote = null;
            else word += char;
        } else if (char === '"' || char === "'") {
            quote = char;
            started = true;
        } else if (/\s/.test(char)) {
            if (started) words.push(word);
            word = "";
            started = false;
        } else {
            word += char;
            started = true;
        }
    }
    if (quote || escaped) throw new Error("Unterminated quote or escape.");
    if (started) words.push(word);
    return words;
}

function pathParts(path) {
    const parts = [];
    for (const part of path.split("/")) {
        if (!part || part === ".") continue;
        if (part === "..") {
            if (!parts.length) throw new Error("Cannot go above the project root.");
            parts.pop();
        } else {
            parts.push(part);
        }
    }
    return parts;
}

function findPath(items, parts) {
    let parentId = null;
    let item = null;
    for (const part of parts) {
        item = items.find((entry) => entry.parentId === parentId && entry.name.toLowerCase() === part.toLowerCase());
        if (!item) throw new Error(`Path not found: ${parts.join("/")}`);
        parentId = item.id;
    }
    return item;
}

function folderAt(items, parts) {
    const folder = findPath(items, parts);
    if (folder && folder.kind !== "folder") throw new Error("Destination is not a folder.");
    return folder;
}

function requireArgs(args, min, max, usage) {
    if (args.length < min || args.length > max) throw new Error(`Usage: ${usage}`);
}

export async function executeTerminalCommand(line, context) {
    const [command, ...args] = parseCommand(line);
    if (!command) return "";
    if (command === "help") {
        requireArgs(args, 0, 0, "help");
        return TERMINAL_HELP;
    }
    const { request, csrfToken, project, items, databases, confirm, onItemsChanged, onDatabasesChanged, dirtyItemId, dirtyDatabaseId } = context;
    const jsonOptions = (method, body) => ({
        method,
        headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken },
        body: JSON.stringify(body),
    });
    const deleteOptions = { method: "DELETE", headers: { "X-CSRFToken": csrfToken } };

    if (command === "db") {
        const [action, ...values] = args;
        if (action === "list") {
            requireArgs(values, 0, 0, "db list");
            const result = await request("/api/schema");
            return result.databases.map((database) => database.name).join("\n") || "No databases.";
        }
        if (action === "create") {
            requireArgs(values, 1, 1, "db create <name>");
            const result = await request("/api/schema", jsonOptions("POST", {
                name: values[0], schema: { tables: [], relationships: [] },
            }));
            await onDatabasesChanged(result.database);
            return `Created database "${result.database.name}".`;
        }
        const counts = { show: [1, 1], rename: [2, 2], delete: [1, 1], query: [2, 2] };
        if (!Object.hasOwn(counts, action)) throw new Error("Unknown database command. Type help for commands.");
        requireArgs(values, ...counts[action], `db ${action} ${action === "rename" ? "<name> <new-name>" : action === "query" ? "<name> <sql>" : "<name>"}`);
        const database = databases.find((entry) => entry.name.toLowerCase() === values[0].toLowerCase());
        if (!database) throw new Error(`Database not found: ${values[0]}`);
        if ((action === "rename" || action === "delete") && database.id === dirtyDatabaseId) {
            throw new Error("Save or discard the selected database's unsaved schema edits first.");
        }
        const url = `/api/schema/${database.id}`;
        if (action === "delete") {
            if (!confirm(`Delete database "${database.name}"?`)) return "Deletion cancelled.";
            await request(url, deleteOptions);
            await onDatabasesChanged(null, database.id);
            return `Deleted database "${database.name}".`;
        }
        if (action === "query") {
            const result = await request(`${url}/query`, jsonOptions("POST", { query: values[1] }));
            return [result.columns.join("\t"), ...result.rows.map((row) => row.map((value) => value == null ? "NULL" : typeof value === "object" ? JSON.stringify(value) : String(value)).join("\t")), result.truncated ? "Showing the first 200 rows." : `${result.rows.length} rows.`].join("\n");
        }
        const loaded = await request(url);
        if (action === "show") {
            return [`Database: ${loaded.database.name}`, ...loaded.schema.tables.map((table) => `${table.name}: ${table.columns.map((column) => `${column.name} (${column.type})`).join(", ")}`)].join("\n");
        }
        const result = await request(url, jsonOptions("PUT", { name: values[1], schema: loaded.schema }));
        await onDatabasesChanged(result.database);
        return `Renamed database "${database.name}" to "${result.database.name}".`;
    }

    const commands = ["ls", "mkdir", "touch", "cat", "write", "mv", "rm"];
    if (!commands.includes(command)) throw new Error("Unknown command. Type help for commands.");
    if (!project) throw new Error("Select a project in the explorer first.");
    const base = `/api/projects/${project.id}/items`;
    if (command === "ls") {
        requireArgs(args, 0, 1, "ls [folder]");
        const folder = folderAt(items, pathParts(args[0] || "/"));
        return items.filter((item) => item.parentId === (folder?.id || null))
            .map((item) => `${item.kind === "folder" ? "folder" : "file  "}  ${item.name}`).join("\n") || "Folder is empty.";
    }
    if (command === "mkdir" || command === "touch") {
        requireArgs(args, 1, 1, `${command} <path>`);
        const parts = pathParts(args[0]);
        const name = parts.pop();
        if (!name) throw new Error("Enter an item name.");
        const parent = folderAt(items, parts);
        const result = await request(base, jsonOptions("POST", { name, kind: command === "mkdir" ? "folder" : "file", parentId: parent?.id || null, content: "" }));
        onItemsChanged(project.id, result.items);
        return `Created ${result.item.kind} "${args[0]}".`;
    }
    requireArgs(args, command === "write" || command === "mv" ? 2 : 1, command === "write" || command === "mv" ? 2 : 1, `${command} <path>${command === "write" ? " <text>" : command === "mv" ? " <destination>" : ""}`);
    const source = findPath(items, pathParts(args[0]));
    if (!source) throw new Error("The project root cannot be modified.");
    const url = `${base}/${source.id}`;
    if (command === "cat") {
        if (source.kind !== "file") throw new Error("Only files can be read.");
        return source.content || "(empty file)";
    }
    if (command === "write") {
        if (source.kind !== "file") throw new Error("Only files can contain text.");
        if (source.id === dirtyItemId) throw new Error("Save or discard the open file's unsaved edits before writing it.");
        const result = await request(url, jsonOptions("PATCH", { content: args[1] }));
        onItemsChanged(project.id, result.items);
        return `Updated "${args[0]}".`;
    }
    if (command === "rm") {
        let dirty = items.find((item) => item.id === dirtyItemId);
        while (dirty) {
            if (dirty.id === source.id) throw new Error("Save or discard the open file's unsaved edits before deleting it.");
            dirty = items.find((item) => item.id === dirty.parentId);
        }
        if (!confirm(`Delete "${args[0]}"${source.kind === "folder" ? " and everything inside it" : ""}?`)) return "Deletion cancelled.";
        const result = await request(url, deleteOptions);
        onItemsChanged(project.id, result.items);
        return `Deleted "${args[0]}".`;
    }
    const parts = pathParts(args[1]);
    if (!parts.length) {
        const result = await request(url, jsonOptions("PATCH", { parentId: null }));
        onItemsChanged(project.id, result.items);
        return `Moved "${args[0]}" to the project root.`;
    }
    const destinationName = parts.pop();
    const parent = folderAt(items, parts);
    const existing = items.find((item) => item.parentId === (parent?.id || null) && item.name.toLowerCase() === destinationName.toLowerCase());
    const changes = existing?.kind === "folder" ? { parentId: existing.id } : { parentId: parent?.id || null, name: destinationName };
    const result = await request(url, jsonOptions("PATCH", changes));
    onItemsChanged(project.id, result.items);
    return `Moved "${args[0]}" to "${args[1]}".`;
}
