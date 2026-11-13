import React, { useRef, useState } from "react";

function CsrfInput({ token }) {
    return <input name="csrf_token" type="hidden" value={token} />;
}

function MarkdownEditor({ initialContent }) {
    const [content, setContent] = useState(initialContent);
    const editor = useRef(null);

    function setHeading(level) {
        const element = editor.current;
        if (!element) {
            return;
        }

        const value = element.value;
        const selectionStart = element.selectionStart;
        const selectionEnd = element.selectionEnd;
        const start = value.lastIndexOf("\n", Math.max(0, selectionStart - 1)) + 1;
        const endOfLine = value.indexOf("\n", selectionEnd);
        const end = endOfLine === -1 ? value.length : endOfLine;
        const lines = value.slice(start, end).split("\n").map((line) => {
            const text = line.replace(/^#{1,6}\s*/, "");
            return level ? `${"#".repeat(level)} ${text}` : text;
        });
        const nextContent = value.slice(0, start) + lines.join("\n") + value.slice(end);

        setContent(nextContent);
        requestAnimationFrame(() => {
            element.focus();
            element.setSelectionRange(start, start + lines.join("\n").length);
        });
    }

    return (
        <div className="notes-markdown-editor">
            <div className="notes-format-toolbar" role="group" aria-label="Markdown headings">
                {[1, 2, 3].map((level) => (
                    <button key={level} onClick={() => setHeading(level)} type="button">
                        H{level}
                    </button>
                ))}
                <button onClick={() => setHeading(0)} type="button">Paragraph</button>
            </div>
            <textarea
                aria-label="Note body in Markdown"
                maxLength={4096}
                name="note_content"
                onChange={(event) => setContent(event.target.value)}
                placeholder="Write your note in Markdown..."
                ref={editor}
                value={content}
            />
        </div>
    );
}

export default function NotesPage({
    csrfToken,
    hasNext,
    hasPrev,
    nextPage,
    notes,
    page,
    pages,
    prevPage,
    selectedContent,
    selectedNote,
}) {
    return (
        <div className="notes-react-page">
            <nav className="notes-react-nav" aria-label="Main navigation">
                <a className="notes-nav-link" href="/">Home</a>
                <h1>Notes</h1>
                <a className="notes-nav-link" href="/Rover/Support">Support</a>
            </nav>
            <div className="notes-react-workspace">
                <aside className="notes-react-sidebar" aria-labelledby="notes-list-heading">
                    <h2 id="notes-list-heading">Your notes</h2>
                    <form action="/Rover/Notes" className="notes-create-form" method="post">
                        <CsrfInput token={csrfToken} />
                        <input
                            aria-label="New note name"
                            maxLength={128}
                            name="note_name"
                            placeholder="New note name"
                            required
                        />
                        <button type="submit">Create</button>
                    </form>
                    <div className="notes-react-list">
                        {notes.length ? notes.map((note) => (
                            <article className="notes-react-row" key={note.id}>
                                <a
                                    aria-current={selectedNote?.id === note.id ? "page" : undefined}
                                    className={selectedNote?.id === note.id ? "is-selected" : ""}
                                    href={`/Rover/Notes?load_id=${note.id}`}
                                >
                                    <strong>{note.name}</strong>
                                    <span>{note.description || "No description"}</span>
                                </a>
                                <details>
                                    <summary>Edit description</summary>
                                    <form action={`/Rover/Notes/${note.id}/description`} method="post">
                                        <CsrfInput token={csrfToken} />
                                        <input
                                            aria-label={`${note.name} description`}
                                            maxLength={512}
                                            name="note_description"
                                            defaultValue={note.description}
                                        />
                                        <button type="submit">Save</button>
                                    </form>
                                </details>
                                <form
                                    action={`/Rover/Notes/${note.id}/delete`}
                                    method="post"
                                    onSubmit={(event) => {
                                        if (!window.confirm(`Delete "${note.name}"?`)) {
                                            event.preventDefault();
                                        }
                                    }}
                                >
                                    <CsrfInput token={csrfToken} />
                                    <button className="notes-delete-button" type="submit">Delete</button>
                                </form>
                            </article>
                        )) : <p className="notes-empty-state">No notes yet. Create one to get started.</p>}
                    </div>
                    {pages > 1 && (
                        <nav className="notes-react-pagination" aria-label="Notes pages">
                            {hasPrev ? <a href={`/Rover/Notes?page=${prevPage}`}>Previous</a> : <span />}
                            <span>Page {page} of {pages}</span>
                            {hasNext ? <a href={`/Rover/Notes?page=${nextPage}`}>Next</a> : <span />}
                        </nav>
                    )}
                </aside>
                <section className="notes-react-editor" aria-label="Note editor">
                    {selectedNote ? (
                        <form action={`/Rover/Notes/${selectedNote.id}/update`} method="post">
                            <CsrfInput token={csrfToken} />
                            <label className="notes-editor-name">
                                <span className="visually-hidden">Note name</span>
                                <input
                                    aria-label="Note name"
                                    maxLength={128}
                                    name="note_name"
                                    defaultValue={selectedNote.name}
                                    required
                                />
                            </label>
                            <MarkdownEditor initialContent={selectedContent} />
                            <button className="notes-save-button" type="submit">Save note</button>
                        </form>
                    ) : (
                        <div className="notes-empty-editor">
                            <h2>Open a note</h2>
                            <p>Select a note from Your notes, or enter a name to create one.</p>
                        </div>
                    )}
                </section>
            </div>
        </div>
    );
}
