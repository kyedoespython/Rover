function initializeNotesPage() {
    const notesList = document.querySelector("#notesPage .notes-list-panel");
    const content = document.getElementById("noteContent");
    const headingSelect = document.getElementById("noteHeadingSelect");

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
        !(headingSelect instanceof HTMLSelectElement)
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
        headingSelect.hidden = false;
        headingSelect.value = "";
        headingSelect.focus();
    });

    headingSelect.addEventListener("change", () => {
        const level = Number(headingSelect.value);
        if (selectedLine === null || level < 1 || level > 4) {
            headingSelect.hidden = true;
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
        headingSelect.hidden = true;
        headingSelect.value = "";
        content.focus();
    });
}

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initializeNotesPage, { once: true });
} else {
    initializeNotesPage();
}
