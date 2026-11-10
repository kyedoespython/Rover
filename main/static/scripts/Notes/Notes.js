function initializeNotesPage() {
    const notesList = document.querySelector("#notesPage .notes-list-panel");
    const content = document.getElementById("noteContent");
    const headingMenu = document.getElementById("noteHeadingMenu");

    if (!(notesList instanceof HTMLElement)) {
        return;
    }

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

    if (
        !(content instanceof HTMLTextAreaElement) ||
        !(headingMenu instanceof HTMLElement)
    ) {
        return;
    }

    let selectedLine = null;
    content.addEventListener("dblclick", () => {
        const start = content.selectionStart;
        const end = content.selectionEnd;
        const lineStart = content.value.lastIndexOf("\n", start - 1) + 1;
        let lineEnd = content.value.indexOf("\n", Math.max(start, end));
        if (lineEnd === -1) {
            lineEnd = content.value.length;
        }

        selectedLine = { start: lineStart, end: lineEnd };
        headingMenu.hidden = false;
        headingMenu.querySelector("button")?.focus();
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
        if (selectedLine === null || level < 1 || level > 4) {
            headingMenu.hidden = true;
            content.focus();
            return;
        }

        const line = content.value.slice(selectedLine.start, selectedLine.end);
        const headingText = line.replace(/^#{1,6}\s*/, "");
        const replacement = `${"#".repeat(level)} ${headingText}`;
        content.setRangeText(
            replacement,
            selectedLine.start,
            selectedLine.end,
            "select",
        );
        selectedLine = null;
        headingMenu.hidden = true;
        content.focus();
    });

    headingMenu.addEventListener("keydown", (event) => {
        if (event.key === "Escape") {
            headingMenu.hidden = true;
            selectedLine = null;
            content.focus();
        }
    });
}

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initializeNotesPage, { once: true });
} else {
    initializeNotesPage();
}
