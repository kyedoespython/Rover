(() => {
    // Enhance same-origin navigation only; native browser behavior remains the fallback.
    const navigationScriptUrl = new URL(document.currentScript.src, window.location.href).href;
    const main = document.querySelector("main");
    if (!main) {
        return;
    }

    for (const script of document.head.querySelectorAll("script[src]")) {
        if (new URL(script.src, document.baseURI).href !== navigationScriptUrl) {
            script.dataset.roverPageScript = "true";
        }
    }

    let activeRequest;
    let navigationId = 0;

    // Keep only assets that belong to the currently rendered Flask template.
    const currentStylesheets = new Map(
        [...document.head.querySelectorAll('link[rel="stylesheet"]')].map((link) => {
            return [new URL(link.href, document.baseURI).href, link];
        })
    );

    function isSameOrigin(url) {
        return url.origin === window.location.origin;
    }

    function syncStylesheets(page, baseUrl) {
        const nextStylesheets = new Map(
            [...page.head.querySelectorAll('link[rel="stylesheet"][href]')]
                .map((link) => [new URL(link.getAttribute("href"), baseUrl), link])
                .filter(([url]) => isSameOrigin(url))
                .map(([url, link]) => [url.href, link])
        );

        for (const [href, link] of currentStylesheets) {
            if (!nextStylesheets.has(href)) {
                link.remove();
                currentStylesheets.delete(href);
            }
        }

        for (const [href, source] of nextStylesheets) {
            if (currentStylesheets.has(href)) {
                continue;
            }

            const link = document.createElement("link");
            for (const attribute of source.attributes) {
                link.setAttribute(attribute.name, attribute.value);
            }
            document.head.append(link);
            currentStylesheets.set(href, link);
        }
    }

    async function syncPageScripts(page, baseUrl) {
        for (const script of document.head.querySelectorAll("script[data-rover-page-script]")) {
            script.remove();
        }

        for (const source of page.head.querySelectorAll("script[src]")) {
            const src = new URL(source.getAttribute("src"), baseUrl).href;
            if (src === navigationScriptUrl || !isSameOrigin(new URL(src))) {
                continue;
            }

            const script = document.createElement("script");
            for (const attribute of source.attributes) {
                script.setAttribute(attribute.name, attribute.value);
            }
            script.dataset.roverPageScript = "true";
            script.async = false;

            await new Promise((resolve) => {
                script.addEventListener("load", resolve, { once: true });
                script.addEventListener("error", () => {
                    console.error(`Failed to load page script: ${src}`);
                    resolve();
                }, { once: true });
                document.head.append(script);
            });
        }
    }

    function syncFlashMessages(page) {
        const currentMessages = document.querySelector(".flash-message-stack");
        const nextMessages = page.querySelector(".flash-message-stack");

        if (currentMessages && nextMessages) {
            currentMessages.replaceWith(nextMessages);
        } else if (currentMessages) {
            currentMessages.remove();
        } else if (nextMessages) {
            document.body.append(nextMessages);
        }
    }

    function showNavigationError(message) {
        let stack = document.querySelector(".flash-message-stack");
        if (!stack) {
            stack = document.createElement("div");
            stack.className = "flash-message-stack";
            stack.setAttribute("aria-live", "assertive");
            document.body.append(stack);
        }

        const notice = document.createElement("div");
        notice.className = "flash-message";
        notice.setAttribute("role", "alert");
        notice.textContent = message;
        stack.append(notice);
    }

    async function navigate(url, options = {}) {
        const destination = new URL(url, window.location.href);
        if (!isSameOrigin(destination)) {
            showNavigationError("Navigation was blocked because the destination is outside this site.");
            return;
        }

        // A newer navigation wins if the user clicks again before this request finishes.
        if (activeRequest) {
            activeRequest.abort();
        }
        activeRequest = new AbortController();
        const requestId = ++navigationId;

        try {
            // Let Flask process the request and follow its redirects before swapping pages.
            const response = await fetch(destination.href, {
                method: options.method || "GET",
                body: options.body,
                credentials: "same-origin",
                cache: "no-store",
                headers: { "X-Requested-With": "XMLHttpRequest" },
                signal: activeRequest.signal,
            });

            if (requestId !== navigationId) {
                return;
            }

            const finalUrl = new URL(response.url, destination.href);
            if (!isSameOrigin(finalUrl)) {
                showNavigationError("The server redirected outside this site. Please continue using a regular page link.");
                return;
            }

            const contentType = response.headers.get("content-type") || "";
            if (!contentType.includes("text/html")) {
                showNavigationError(`The server returned a non-page response (HTTP ${response.status}).`);
                return;
            }

            const html = await response.text();
            const page = new DOMParser().parseFromString(html, "text/html");
            const nextMain = page.querySelector("main");
            if (!nextMain) {
                if (options.method !== "POST") {
                    window.history.pushState({}, "", finalUrl.href);
                }
                showNavigationError(`The server could not load this page (HTTP ${response.status}).`);
                return;
            }

            syncStylesheets(page, finalUrl.href);
            main.innerHTML = nextMain.innerHTML;
            document.body.className = page.body.className;
            document.title = page.title;
            syncFlashMessages(page);

            if (options.history !== false) {
                const historyMethod = options.replace ? "replaceState" : "pushState";
                window.history[historyMethod]({}, "", finalUrl.href);
            }

            window.scrollTo(0, 0);
            await syncPageScripts(page, finalUrl.href);
            document.dispatchEvent(new CustomEvent("rover:page-rendered", {
                detail: { url: finalUrl.href, method: options.method || "GET" },
            }));

            if (!response.ok) {
                console.error(`Page request failed with status ${response.status}: ${finalUrl.href}`);
            }
        } catch (error) {
            if (error.name === "AbortError") {
                return;
            }
            console.error("Client-side navigation failed; loading the page normally.", error);
            if (options.method === "POST") {
                window.location.reload();
            } else {
                window.location.assign(destination.href);
            }
        }
    }

    // Leave external, modified, and new-tab links to the browser.
    document.addEventListener("click", (event) => {
        if (
            event.defaultPrevented ||
            event.button !== 0 ||
            event.metaKey ||
            event.ctrlKey ||
            event.shiftKey ||
            event.altKey
        ) {
            return;
        }

        const link = event.target.closest("a[href]");
        if (
            !link ||
            link.hasAttribute("download") ||
            (link.target && link.target !== "_self")
        ) {
            return;
        }

        const destination = new URL(link.href, window.location.href);
        const isCurrentDocument =
            destination.pathname === window.location.pathname &&
            destination.search === window.location.search;
        if (!isSameOrigin(destination) || isCurrentDocument) {
            return;
        }

        event.preventDefault();
        navigate(destination.href);
    });

    document.addEventListener("submit", (event) => {
        if (event.defaultPrevented) {
            return;
        }

        const form = event.target;
        const submitter = event.submitter;
        const target =
            submitter?.getAttribute("formtarget") ??
            form.getAttribute("target") ??
            "";
        if (target && target !== "_self") {
            return;
        }

        const action =
            submitter?.getAttribute("formaction") ??
            form.getAttribute("action") ??
            window.location.href;
        const destination = new URL(action, window.location.href);
        const method = (
            submitter?.getAttribute("formmethod") ??
            form.getAttribute("method") ??
            "get"
        ).toUpperCase();
        const encoding = (
            submitter?.getAttribute("formenctype") ??
            form.getAttribute("enctype") ??
            "application/x-www-form-urlencoded"
        ).toLowerCase();
        if (
            !isSameOrigin(destination) ||
            !["GET", "POST"].includes(method) ||
            encoding === "text/plain"
        ) {
            return;
        }

        event.preventDefault();
        // FormData preserves hidden CSRF fields for Flask's normal validation.
        const data = new FormData(form, submitter);
        let body;
        if (method === "GET") {
            for (const [name, value] of data.entries()) {
                if (value instanceof File) {
                    continue;
                }
                destination.searchParams.append(name, value);
            }
        } else {
            body = data;
        }

        if (submitter) {
            submitter.disabled = true;
        }
        navigate(destination.href, { method, body }).finally(() => {
            if (submitter?.isConnected) {
                submitter.disabled = false;
            }
        });
    });

    window.addEventListener("popstate", () => {
        // Re-fetch the history entry without creating another entry.
        navigate(window.location.href, { history: false });
    });
})();
