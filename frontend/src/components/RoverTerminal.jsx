import React, { useEffect, useRef, useState } from "react";

import { executeTerminalCommand, TERMINAL_HELP } from "./terminalCommands.mjs";

export default function RoverTerminal({ open, onClose, ...context }) {
    const [lines, setLines] = useState([{ text: "Rover terminal. Type help for available commands." }]);
    const [input, setInput] = useState("");
    const [busy, setBusy] = useState(false);
    const [height, setHeight] = useState(280);
    const outputRef = useRef(null);
    const inputRef = useRef(null);
    const resizeRef = useRef(null);

    useEffect(() => {
        if (open) inputRef.current?.focus();
    }, [open]);

    useEffect(() => {
        if (outputRef.current) outputRef.current.scrollTop = outputRef.current.scrollHeight;
    }, [lines, open]);

    function resizeBy(delta) {
        setHeight((current) => Math.max(150, Math.min(window.innerHeight * 0.8, current + delta)));
    }

    async function run(event) {
        event.preventDefault();
        const command = input.trim();
        if (!command || busy) return;
        setInput("");
        if (command === "clear") {
            setLines([]);
            return;
        }
        setLines((current) => [...current, { text: `> ${command}` }]);
        setBusy(true);
        try {
            const result = command === "help" ? TERMINAL_HELP : await executeTerminalCommand(command, context);
            if (result) setLines((current) => [...current, { text: result }]);
        } catch (error) {
            setLines((current) => [...current, { text: `Error: ${error.message}`, error: true }]);
        } finally {
            setBusy(false);
            inputRef.current?.focus();
        }
    }

    return (
        <section
            aria-label="Rover terminal"
            className="rover-terminal"
            hidden={!open}
            id="rover-terminal"
            style={{ height: `min(${height}px, 80vh)` }}
        >
            <div
                aria-label="Resize terminal"
                aria-orientation="horizontal"
                aria-valuemax={Math.floor(window.innerHeight * 0.8)}
                aria-valuemin={150}
                aria-valuenow={height}
                className="rover-terminal-resize"
                onKeyDown={(event) => {
                    if (event.key === "ArrowUp" || event.key === "ArrowDown") {
                        event.preventDefault();
                        resizeBy(event.key === "ArrowUp" ? 20 : -20);
                    }
                }}
                onPointerDown={(event) => {
                    resizeRef.current = event.clientY;
                    event.currentTarget.setPointerCapture(event.pointerId);
                }}
                onPointerMove={(event) => {
                    if (resizeRef.current === null) return;
                    resizeBy(resizeRef.current - event.clientY);
                    resizeRef.current = event.clientY;
                }}
                onPointerUp={() => { resizeRef.current = null; }}
                onPointerCancel={() => { resizeRef.current = null; }}
                role="separator"
                tabIndex={0}
                title="Drag to resize"
            />
            <div className="rover-terminal-header">
                <strong>Rover terminal</strong>
                <span>{context.project ? `Project: ${context.project.name}` : "Select a project for file commands"}</span>
                <button aria-label="Close terminal" onClick={onClose} type="button">×</button>
            </div>
            <div aria-live="polite" className="rover-terminal-output" ref={outputRef}>
                {lines.map((line, index) => <pre className={line.error ? "is-error" : ""} key={index}>{line.text}</pre>)}
            </div>
            <form className="rover-terminal-input" onSubmit={run}>
                <span aria-hidden="true">&gt;</span>
                <input
                    aria-label="Terminal command"
                    autoComplete="off"
                    disabled={busy}
                    onChange={(event) => setInput(event.target.value)}
                    placeholder={busy ? "Running..." : "Type help for commands"}
                    ref={inputRef}
                    spellCheck="false"
                    value={input}
                />
                <button disabled={busy || !input.trim()} type="submit">Run</button>
            </form>
        </section>
    );
}
