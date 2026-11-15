import React, { useEffect, useRef, useState } from "react";

const PYSCRIPT_CORE_URL = "https://pyscript.net/releases/2026.1.1/core.js";
const STARTUP_TIMEOUT_MS = 60000;

export default function PythonTerminal({ active }) {
    const outputRef = useRef(null);
    const scriptRef = useRef(null);
    const generationRef = useRef(0);
    const timeoutRef = useRef(null);
    const [status, setStatus] = useState("idle");
    const [message, setMessage] = useState("");

    function dispose(script) {
        script?.xworker?.terminate();
        script?.terminal?.dispose();
        script?.remove();
    }

    function stop() {
        generationRef.current += 1;
        window.clearTimeout(timeoutRef.current);
        dispose(scriptRef.current);
        scriptRef.current = null;
        outputRef.current?.replaceChildren();
        setStatus("idle");
        setMessage("Python session stopped. Its variables and temporary files were cleared.");
    }

    function fitTerminal() {
        const output = outputRef.current;
        const terminal = scriptRef.current?.terminal;
        const screen = output?.querySelector(".xterm-screen");
        if (!output || !terminal || !screen || !output.clientWidth || !output.clientHeight) return;
        const charWidth = screen.getBoundingClientRect().width / terminal.cols;
        const charHeight = screen.getBoundingClientRect().height / terminal.rows;
        if (!charWidth || !charHeight) return;
        const columns = Math.max(10, Math.floor(output.clientWidth / charWidth));
        const rows = Math.max(1, Math.floor(output.clientHeight / charHeight));
        if (columns !== terminal.cols || rows !== terminal.rows) terminal.resize(columns, rows);
    }

    async function start() {
        if (!window.crossOriginIsolated) {
            setStatus("error");
            setMessage("Python requires a secure, cross-origin isolated workspace. Check the workspace response headers and reload.");
            return;
        }
        dispose(scriptRef.current);
        scriptRef.current = null;
        outputRef.current?.replaceChildren();
        const generation = ++generationRef.current;
        setStatus("loading");
        setMessage("Loading Python in your browser. The first download may take a moment.");
        timeoutRef.current = window.setTimeout(() => {
            if (generationRef.current !== generation) return;
            generationRef.current += 1;
            dispose(scriptRef.current);
            scriptRef.current = null;
            outputRef.current?.replaceChildren();
            setStatus("error");
            setMessage("Python did not start in time. Check your connection and reload or try again.");
        }, STARTUP_TIMEOUT_MS);

        try {
            await import(/* @vite-ignore */ PYSCRIPT_CORE_URL);
            if (generationRef.current !== generation) return;
            const script = document.createElement("script");
            script.type = "py";
            script.setAttribute("worker", "");
            script.setAttribute("terminal", "");
            script.setAttribute("target", "#rover-python-output");
            script.setAttribute("config", '{"interpreter":"0.29.1"}');
            script.textContent = 'import code\ncode.interact(banner="Rover Python (browser session)")';
            script.addEventListener("py:ready", () => {
                if (generationRef.current !== generation) {
                    dispose(script);
                    return;
                }
                window.clearTimeout(timeoutRef.current);
                setStatus("ready");
                setMessage("");
                fitTerminal();
                if (outputRef.current?.offsetParent) script.terminal?.focus();
            }, { once: true });
            script.addEventListener("py:done", () => {
                if (generationRef.current !== generation) return;
                setStatus("ended");
                setMessage("Python session ended. Start a new session to continue.");
            }, { once: true });
            scriptRef.current = script;
            document.body.appendChild(script);
        } catch (error) {
            if (generationRef.current !== generation) return;
            window.clearTimeout(timeoutRef.current);
            setStatus("error");
            setMessage(`Unable to load Python: ${error.message}. Check your connection and reload.`);
        }
    }

    useEffect(() => {
        if (active && status === "idle" && !message) start();
    }, [active, status, message]);

    useEffect(() => {
        const output = outputRef.current;
        if (!output) return undefined;
        const observer = new ResizeObserver(fitTerminal);
        observer.observe(output);
        if (active && status === "ready") {
            fitTerminal();
            scriptRef.current?.terminal?.focus();
        }
        return () => observer.disconnect();
    }, [active, status]);

    useEffect(() => () => {
        generationRef.current += 1;
        window.clearTimeout(timeoutRef.current);
        dispose(scriptRef.current);
    }, []);

    return (
        <div className="rover-python" hidden={!active}>
            <div className="rover-python-toolbar">
                <span>Browser Python · temporary session</span>
                {(status === "loading" || status === "ready") ? (
                    <button onClick={stop} type="button">Stop &amp; reset</button>
                ) : (
                    <button onClick={start} type="button">Start Python</button>
                )}
            </div>
            {message && <p className="rover-python-status" role={status === "error" ? "alert" : "status"}>{message}</p>}
            <div aria-label="Python shell" className="rover-python-output" id="rover-python-output" ref={outputRef} />
        </div>
    );
}
