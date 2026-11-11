function initializeNotesPage() {
    const notesList = document.querySelector("#notesPage .notes-list-panel");
    const content = document.getElementById("noteContent");
    const editor = document.getElementById("noteContentEditor");
    const headingMenu = document.getElementById("noteHeadingMenu");
    const headingToggle = document.getElementById("headingSelectToggle");
    const editForm = document.querySelector("#notesPage .note-edit-form");

    if (notesList instanceof HTMLElement) {
        notesList.addEventListener("contextmenu", (event) => {
            const target = event.target;
            if (!(target instanceof Element)) {
                return;
            }

            const noteButton = target.closest(".note-open-button");
            if (!(noteButton instanceof HTMLAnchorElement)) {
                return;
            }

            const noteRow = noteButton.closest(".note-row");
            const descriptionForm = noteRow?.querySelector(".note-description-form");
            if (!(descriptionForm instanceof HTMLFormElement)) {
                return;
            }

            event.preventDefault();
            notesList.querySelectorAll(".note-description-form").forEach((form) => {
                form.hidden = true;
            });
            descriptionForm.hidden = false;
            descriptionForm.querySelector("input[name='note_description']")?.focus();
        });

        notesList.addEventListener("click", (event) => {
            const target = event.target;
            if (!(target instanceof Element) || target.closest(".note-description-form")) {
                return;
            }

            notesList.querySelectorAll(".note-description-form").forEach((form) => {
                form.hidden = true;
            });
        });
    }

    if (
        !(content instanceof HTMLTextAreaElement) ||
        !(editor instanceof HTMLElement) ||
        !(headingMenu instanceof HTMLElement) ||
        !(headingToggle instanceof HTMLButtonElement) ||
        !(editForm instanceof HTMLFormElement)
    ) {
        return;
    }

    const makeBlock = (line) => {
        const heading = line.match(/^(#{1,6})\s+(.*)$/);
        const block = document.createElement(heading ? `h${heading[1].length}` : "div");
        block.textContent = heading ? heading[2] : line;
        if (line === "") {
            block.append(document.createElement("br"));
        }
        return block;
    };

    const parseMarkdown = (markdown) => {
        editor.replaceChildren();
        markdown.split("\n").forEach((line) => editor.append(makeBlock(line)));
        if (!editor.firstChild) {
            editor.append(makeBlock(""));
        }
    };

    const serializeMarkdown = () => Array.from(editor.children, (block) => {
        const text = block.textContent ?? "";
        const heading = block.tagName.match(/^H([1-6])$/);
        return heading ? `${"#".repeat(Number(heading[1]))} ${text}` : text;
    }).join("\n");

    parseMarkdown(content.value);

    let savedRange = null;
    const rememberSelection = () => {
        const selection = window.getSelection();
        if (
            selection?.rangeCount &&
            editor.contains(selection.anchorNode) &&
            editor.contains(selection.focusNode)
        ) {
            savedRange = selection.getRangeAt(0).cloneRange();
        }
    };

    document.addEventListener("selectionchange", rememberSelection);
    editor.addEventListener("keyup", rememberSelection);
    editor.addEventListener("mouseup", rememberSelection);
    editor.addEventListener("input", () => {
        content.value = serializeMarkdown();
        editor.removeAttribute("aria-invalid");
        rememberSelection();
    });

    editor.addEventListener("paste", (event) => {
        event.preventDefault();
        const text = event.clipboardData?.getData("text/plain");
        if (text) {
            document.execCommand("insertText", false, text);
        }
    });

    headingToggle.addEventListener("click", () => {
        const isOpen = !headingMenu.hidden;
        headingMenu.hidden = isOpen;
        headingToggle.setAttribute("aria-expanded", String(!isOpen));
    });

    headingMenu.addEventListener("mousedown", (event) => {
        if (event.target instanceof Element && event.target.closest("button")) {
            event.preventDefault();
        }
    });

    headingMenu.addEventListener("click", (event) => {
        const target = event.target;
        if (!(target instanceof Element)) {
            return;
        }

        const button = target.closest("button[data-heading-level]");
        if (!(button instanceof HTMLButtonElement)) {
            return;
        }

        const level = Number(button.dataset.headingLevel);
        if (!Number.isInteger(level) || level < 0 || level > 6) {
            return;
        }

        if (savedRange && editor.contains(savedRange.startContainer)) {
            const blocks = Array.from(editor.children).filter((block) => {
                try {
                    return savedRange.intersectsNode(block);
                } catch {
                    return false;
                }
            });
            blocks.forEach((block) => {
                const replacement = document.createElement(level ? `h${level}` : "div");
                while (block.firstChild) {
                    replacement.append(block.firstChild);
                }
                if (!replacement.firstChild) {
                    replacement.append(document.createElement("br"));
                }
                block.replaceWith(replacement);
            });
        }

        content.value = serializeMarkdown();
        headingMenu.hidden = true;
        headingToggle.setAttribute("aria-expanded", "false");
        editor.focus();
    });

    document.addEventListener("click", (event) => {
        const target = event.target;
        if (
            target instanceof Node &&
            !headingMenu.contains(target) &&
            !headingToggle.contains(target)
        ) {
            headingMenu.hidden = true;
            headingToggle.setAttribute("aria-expanded", "false");
        }
    });

    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape" && !headingMenu.hidden) {
            headingMenu.hidden = true;
            headingToggle.setAttribute("aria-expanded", "false");
            editor.focus();
        }
    });

    editForm.addEventListener("submit", (event) => {
        const markdown = serializeMarkdown();
        if (markdown.length > 4096) {
            event.preventDefault();
            editor.setAttribute("aria-invalid", "true");
            editor.focus();
            return;
        }

        content.value = markdown;
    });
}

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initializeNotesPage, { once: true });
} else {
    initializeNotesPage();
}
