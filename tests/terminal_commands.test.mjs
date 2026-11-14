import test from "node:test";
import assert from "node:assert/strict";

import { executeTerminalCommand, parseCommand } from "../frontend/src/components/terminalCommands.mjs";

function fixture() {
    const calls = [];
    const itemUpdates = [];
    const databaseUpdates = [];
    const items = [
        { id: "folder", name: "src", kind: "folder", parentId: null, content: "" },
        { id: "file", name: "app.js", kind: "file", parentId: "folder", content: "old" },
    ];
    const database = { id: 1, name: "My DB" };
    const schema = { tables: [{ name: "users", columns: [{ name: "id", type: "Number" }] }], relationships: [] };
    const context = {
        csrfToken: "token",
        project: { id: 7, name: "Demo" },
        items,
        databases: [database],
        dirtyItemId: null,
        confirm: () => true,
        onItemsChanged: (...args) => itemUpdates.push(args),
        onDatabasesChanged: (...args) => databaseUpdates.push(args),
        request: async (url, options = {}) => {
            calls.push([url, options]);
            if (url === "/api/schema" && !options.method) return { databases: [database] };
            if (url === "/api/schema" && options.method === "POST") return { database: { id: 2, name: "New DB" } };
            if (url === "/api/schema/1" && !options.method) return { database, schema };
            if (url === "/api/schema/1" && options.method === "PUT") return { database: { id: 1, name: "Renamed" } };
            if (url === "/api/schema/1/query") return { columns: ["id"], rows: [[1]], truncated: false };
            if (url === "/api/schema/1") return { deleted: true };
            return { items, item: { kind: "file" } };
        },
    };
    return { context, calls, itemUpdates, databaseUpdates, schema };
}

test("parses quoted arguments and rejects malformed input", () => {
    assert.deepEqual(parseCommand(`write "src/my file" "hello world"`), ["write", "src/my file", "hello world"]);
    assert.deepEqual(parseCommand("write file ''"), ["write", "file", ""]);
    assert.throws(() => parseCommand(`cat "unfinished`), /Unterminated/);
});

test("reads and modifies project items through the workspace API", async () => {
    const { context, calls, itemUpdates } = fixture();
    assert.match(await executeTerminalCommand("ls src", context), /app.js/);
    assert.equal(await executeTerminalCommand("cat src/app.js", context), "old");
    await executeTerminalCommand('write src/app.js "new content"', context);
    assert.equal(calls[0][0], "/api/projects/7/items/file");
    assert.deepEqual(JSON.parse(calls[0][1].body), { content: "new content" });
    await executeTerminalCommand("mkdir src/assets", context);
    assert.deepEqual(JSON.parse(calls[1][1].body), { name: "assets", kind: "folder", parentId: "folder", content: "" });
    await executeTerminalCommand("mv src/app.js /", context);
    assert.deepEqual(JSON.parse(calls[2][1].body), { parentId: null });
    assert.equal(itemUpdates.length, 3);
    await assert.rejects(() => executeTerminalCommand("touch ../escape", context), /above the project root/);
});

test("protects unsaved edits and asks before deleting", async () => {
    const { context, calls } = fixture();
    context.dirtyItemId = "file";
    await assert.rejects(() => executeTerminalCommand("write src/app.js replacement", context), /unsaved/);
    await assert.rejects(() => executeTerminalCommand("rm src", context), /unsaved/);
    context.dirtyItemId = null;
    context.confirm = () => false;
    assert.equal(await executeTerminalCommand("rm src", context), "Deletion cancelled.");
    assert.equal(calls.length, 0);
    context.confirm = () => true;
    await executeTerminalCommand("rm src", context);
    assert.equal(calls[0][1].method, "DELETE");
});

test("database commands use persisted schema and report errors", async () => {
    const { context, calls, databaseUpdates, schema } = fixture();
    assert.equal(await executeTerminalCommand("db list", context), "My DB");
    assert.match(await executeTerminalCommand('db show "My DB"', context), /users: id \(Number\)/);
    assert.match(await executeTerminalCommand('db query "My DB" "SELECT id FROM users"', context), /id\n1\n1 rows/);
    await executeTerminalCommand('db create "New DB"', context);
    await executeTerminalCommand('db rename "My DB" Renamed', context);
    const rename = calls.find(([url, options]) => url === "/api/schema/1" && options.method === "PUT");
    assert.deepEqual(JSON.parse(rename[1].body), { name: "Renamed", schema });
    await executeTerminalCommand('db delete "My DB"', context);
    assert.equal(databaseUpdates.length, 3);
    await assert.rejects(() => executeTerminalCommand("db show missing", context), /Database not found/);
    await assert.rejects(() => executeTerminalCommand("whoami", context), /Unknown command/);
});

test("database mutations do not discard unsaved schema edits", async () => {
    const { context, calls } = fixture();
    context.dirtyDatabaseId = 1;
    await assert.rejects(() => executeTerminalCommand('db rename "My DB" other', context), /unsaved schema/);
    await assert.rejects(() => executeTerminalCommand('db delete "My DB"', context), /unsaved schema/);
    assert.equal(calls.length, 0);
});
