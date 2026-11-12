function initializePasswordToggles() {
    document.querySelectorAll(".password-toggle").forEach((button) => {
        const input = document.getElementById(button.getAttribute("aria-controls"));
        if (!(button instanceof HTMLButtonElement) || !(input instanceof HTMLInputElement)) {
            return;
        }

        button.hidden = false;
        button.addEventListener("click", () => {
            const showingPassword = input.type === "password";
            input.type = showingPassword ? "text" : "password";
            button.setAttribute("aria-pressed", String(showingPassword));
            button.title = showingPassword ? "Hide password" : "Show password";
        });
    });
}

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initializePasswordToggles, { once: true });
} else {
    initializePasswordToggles();
}
