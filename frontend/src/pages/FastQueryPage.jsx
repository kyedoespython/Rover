import React, { useEffect, useState } from "react";

import UserAvatar from "../components/UserAvatar.jsx";

async function requestJson(url, options = {}) {
    const response = await fetch(url, {
        credentials: "same-origin",
        headers: { Accept: "application/json", ...options.headers },
        ...options,
    });
    const result = await response.json();
    if (!response.ok) {
        throw new Error(result.error || "The request could not be completed.");
    }
    return result;
}

function displayValue(value) {
    if (value == null) return "NULL";
    return typeof value === "object" ? JSON.stringify(value) : String(value);
}

export default function FastQueryPage({ csrfToken }) {
    const [data, setData] = useState(null);
    const [currentSlug, setCurrentSlug] = useState("");
    const [query, setQuery] = useState("");
    const [queryResult, setQueryResult] = useState(null);
    const [status, setStatus] = useState("Loading your SQL lessons...");
    const [saving, setSaving] = useState(false);

    useEffect(() => {
        let cancelled = false;
        requestJson("/api/fastquery")
            .then((result) => {
                if (cancelled) return;
                setData(result);
                const section = result.sections.find(
                    (item) => item.slug === result.progress.currentSection,
                ) || result.sections[0];
                setCurrentSlug(section.slug);
                setQuery(section.lesson.examples[0]?.query || "");
                setStatus("");
            })
            .catch((error) => {
                if (!cancelled) setStatus(error.message);
            });
        return () => {
            cancelled = true;
        };
    }, []);

    const sections = data?.sections || [];
    const currentIndex = sections.findIndex((section) => section.slug === currentSlug);
    const currentSection = sections[currentIndex];
    const completedSections = data?.progress.completedSections || [];
    const progressPercent = sections.length
        ? Math.round((completedSections.length / sections.length) * 100)
        : 0;

    async function saveProgress(sectionSlug, complete = false) {
        const result = await requestJson("/api/fastquery/progress", {
            method: "PUT",
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": csrfToken,
            },
            body: JSON.stringify({ section: sectionSlug, complete }),
        });
        setData(result);
        return result;
    }

    async function selectSection(section) {
        setCurrentSlug(section.slug);
        setQuery(section.lesson.examples[0]?.query || "");
        setQueryResult(null);
        setStatus("Saving your place...");
        try {
            await saveProgress(section.slug);
            setStatus("");
        } catch (error) {
            setStatus(error.message);
        }
    }

    async function runQuery(event) {
        event.preventDefault();
        if (!data?.demoDatabase?.id) return;
        setStatus("Running the read-only example...");
        try {
            const result = await requestJson(
                `/api/schema/${data.demoDatabase.id}/query`,
                {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json",
                        "X-CSRFToken": csrfToken,
                    },
                    body: JSON.stringify({ query }),
                },
            );
            setQueryResult(result);
            setStatus(
                result.truncated
                    ? "Showing the first 200 rows."
                    : `${result.rows.length} rows returned.`,
            );
        } catch (error) {
            setQueryResult(null);
            setStatus(error.message);
        }
    }

    async function completeLesson() {
        if (!currentSection || saving) return;
        setSaving(true);
        setStatus("Saving your progress...");
        try {
            await saveProgress(currentSection.slug, true);
            const nextSection = sections[currentIndex + 1];
            if (nextSection) {
                setCurrentSlug(nextSection.slug);
                setQuery(nextSection.lesson.examples[0]?.query || "");
                setQueryResult(null);
                await saveProgress(nextSection.slug);
                setStatus("Lesson complete. The next lesson is ready.");
            } else {
                setStatus("You completed every FastQuery lesson. Great work!");
            }
        } catch (error) {
            setStatus(error.message);
        } finally {
            setSaving(false);
        }
    }

    return (
        <div className="fastquery-page">
            <header className="fastquery-header">
                <a className="fastquery-brand" href="/">FastQuery</a>
                <nav aria-label="FastQuery navigation" className="fastquery-links">
                    <a href="/DesignDashboard">Schema workspace</a>
                    <UserAvatar href="/Rover/Profile" label="Open your profile" />
                </nav>
            </header>

            <main className="fastquery-layout">
                <aside aria-label="SQL learning stages" className="fastquery-sidebar">
                    <div className="fastquery-database-badge">
                        <span>Practice database</span>
                        <strong>{data?.demoDatabase?.fileName || "user.db"}</strong>
                    </div>
                    <div
                        aria-label={`${progressPercent}% of lessons completed`}
                        className="fastquery-progress-track"
                        role="progressbar"
                        aria-valuemin={0}
                        aria-valuemax={100}
                        aria-valuenow={progressPercent}
                    >
                        <span style={{ width: `${progressPercent}%` }} />
                    </div>
                    <p className="fastquery-progress-label">
                        {completedSections.length} of {sections.length} lessons complete
                    </p>
                    <ol className="fastquery-section-list">
                        {sections.map((section, index) => {
                            const completed = completedSections.includes(section.slug);
                            return (
                                <li key={section.slug}>
                                    <button
                                        aria-current={currentSlug === section.slug ? "step" : undefined}
                                        className={currentSlug === section.slug ? "is-current" : ""}
                                        onClick={() => selectSection(section)}
                                        type="button"
                                    >
                                        <span className="fastquery-section-number">
                                            {completed ? "Done" : String(index + 1).padStart(2, "0")}
                                        </span>
                                        <span>{section.title.replace(/^\d+\.\s*/, "")}</span>
                                    </button>
                                </li>
                            );
                        })}
                    </ol>
                </aside>

                <section aria-labelledby="fastquery-title" className="fastquery-lesson">
                    {currentSection ? (
                        <>
                            <p className="fastquery-eyebrow">
                                Lesson {currentIndex + 1} of {sections.length}
                            </p>
                            <h1 id="fastquery-title">{currentSection.title}</h1>
                            <p className="fastquery-summary">{currentSection.summary}</p>
                            <p className="fastquery-intro">{currentSection.lesson.intro}</p>

                            <div className="fastquery-concepts">
                                {currentSection.lesson.steps.map((step) => (
                                    <article key={step.heading}>
                                        <h2>{step.heading}</h2>
                                        <p>{step.text}</p>
                                    </article>
                                ))}
                            </div>

                            <section aria-label="SQL examples" className="fastquery-examples">
                                <h2>Examples to try</h2>
                                <div className="fastquery-example-list">
                                    {currentSection.lesson.examples.map((example) => (
                                        <article className="fastquery-example" key={example.title}>
                                            <h3>{example.title}</h3>
                                            <p>{example.description}</p>
                                            <pre><code>{example.query}</code></pre>
                                            <button
                                                onClick={() => {
                                                    setQuery(example.query);
                                                    setQueryResult(null);
                                                }}
                                                type="button"
                                            >
                                                Load example
                                            </button>
                                        </article>
                                    ))}
                                </div>
                            </section>

                            <form className="fastquery-runner" onSubmit={runQuery}>
                                <label htmlFor="fastquery-sql">Try it on your user.db</label>
                                <textarea
                                    id="fastquery-sql"
                                    maxLength={10000}
                                    onChange={(event) => setQuery(event.target.value)}
                                    value={query}
                                />
                                <button disabled={!query.trim()} type="submit">Run read-only query</button>
                                {queryResult && (
                                    <div className="fastquery-results">
                                        <table>
                                            <thead>
                                                <tr>
                                                    {queryResult.columns.map((column) => (
                                                        <th key={column}>{column}</th>
                                                    ))}
                                                </tr>
                                            </thead>
                                            <tbody>
                                                {queryResult.rows.map((row, rowIndex) => (
                                                    <tr key={rowIndex}>
                                                        {row.map((value, columnIndex) => (
                                                            <td key={columnIndex}>{displayValue(value)}</td>
                                                        ))}
                                                    </tr>
                                                ))}
                                            </tbody>
                                        </table>
                                    </div>
                                )}
                            </form>

                            <p className="fastquery-tip"><strong>Tip:</strong> {currentSection.lesson.tip}</p>
                            <div className="fastquery-pager">
                                <button
                                    disabled={currentIndex <= 0 || saving}
                                    onClick={() => selectSection(sections[currentIndex - 1])}
                                    type="button"
                                >
                                    Previous lesson
                                </button>
                                <button
                                    disabled={saving}
                                    onClick={completeLesson}
                                    type="button"
                                >
                                    {currentIndex === sections.length - 1
                                        ? "Complete course"
                                        : "Complete and continue"}
                                </button>
                            </div>
                        </>
                    ) : !status ? (
                        <p role="status">{status || "Loading your lesson..."}</p>
                    ) : null}
                    {status && <p className="fastquery-status" role="status">{status}</p>}
                </section>
            </main>
        </div>
    );
}
