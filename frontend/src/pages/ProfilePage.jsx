import React, { useEffect, useState } from "react";

import UserAvatar from "../components/UserAvatar.jsx";

async function requestJson(url) {
    const response = await fetch(url, {
        credentials: "same-origin",
        headers: { Accept: "application/json" },
    });
    const result = await response.json();
    if (!response.ok) {
        throw new Error(result.error || "Your learning progress could not be loaded.");
    }
    return result;
}

export default function ProfilePage({ username }) {
    const [data, setData] = useState(null);
    const [status, setStatus] = useState("Loading your learning progress...");

    useEffect(() => {
        let cancelled = false;
        requestJson("/api/fastquery")
            .then((result) => {
                if (cancelled) return;
                setData(result);
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
    const completedSections = data?.progress.completedSections || [];
    const currentSection = sections.find(
        (section) => section.slug === data?.progress.currentSection,
    );
    const percent = sections.length
        ? Math.round((completedSections.length / sections.length) * 100)
        : 0;

    return (
        <div className="profile-page">
            <header className="fastquery-header">
                <a className="fastquery-brand" href="/">Rover</a>
                <nav aria-label="Profile navigation" className="fastquery-links">
                    <a href="/Rover/FastQuery">FastQuery</a>
                    <a href="/DesignDashboard">Schema workspace</a>
                </nav>
            </header>
            <main className="profile-content">
                <section className="profile-card" aria-labelledby="profile-title">
                    <UserAvatar large />
                    <p className="fastquery-eyebrow">Your Rover account</p>
                    <h1 id="profile-title">{username}</h1>
                    <p>Track your SQL learning and continue from your last lesson.</p>
                </section>

                <section className="profile-progress-card" aria-labelledby="profile-progress-title">
                    <div className="profile-progress-heading">
                        <div>
                            <p className="fastquery-eyebrow">FastQuery</p>
                            <h2 id="profile-progress-title">SQL learning progress</h2>
                        </div>
                        <span>{completedSections.length} / {sections.length} complete</span>
                    </div>
                    <div
                        aria-label={`${percent}% of lessons completed`}
                        className="fastquery-progress-track"
                        role="progressbar"
                        aria-valuemin={0}
                        aria-valuemax={100}
                        aria-valuenow={percent}
                    >
                        <span style={{ width: `${percent}%` }} />
                    </div>
                    {currentSection && (
                        <p className="profile-current-stage">
                            Current stage: <strong>{currentSection.title}</strong>
                        </p>
                    )}
                    <ol className="profile-section-list">
                        {sections.map((section) => (
                            <li key={section.slug}>
                                <span>{section.title}</span>
                                <strong>
                                    {completedSections.includes(section.slug) ? "Complete" : "Not complete"}
                                </strong>
                            </li>
                        ))}
                    </ol>
                    <a className="profile-continue-button" href="/Rover/FastQuery">
                        Continue learning
                    </a>
                    {status && <p className="fastquery-status" role="status">{status}</p>}
                </section>
            </main>
        </div>
    );
}
