import React from "react";

import UserAvatar from "../components/UserAvatar.jsx";

export default function Home({ loggedIn, logoUrl, username = "" }) {
    return (
        <div className="home-page">
            <section className="landing-shell" id="about">
                <nav className="landing-nav" aria-label="Main navigation">
                    <a className="landing-brand" href="/" aria-label="Rover home">
                        <img src={logoUrl} alt="" />
                        <span>Rover</span>
                    </a>

                    <div className="landing-links">
                        <a href="/">Home</a>
                        <a href="/Rover/Support">Contact</a>
                    </div>

                    <div className="landing-actions">
                        {loggedIn ? (
                            <>
                                <span className="landing-username">{username}</span>
                                <UserAvatar href="/Rover/Profile" label="Open your profile" />
                            </>
                        ) : (
                            <>
                                <a href="/Rover/Login">Log in</a>
                                <a className="landing-signup" href="/Rover/Sign%20Up">
                                    Get started
                                </a>
                            </>
                        )}
                    </div>
                </nav>

                <section className="landing-copy" aria-labelledby="landing-title">
                    <p className="landing-eyebrow">Ideas into intelligent software</p>
                    <h1 className="landing-title" id="landing-title">
                        Backend design choices made easy with Flask
                    </h1>
                    <div className="landing-footer">
                        <p className="landing-description">
                            Import a database, inspect your data, and build your project in one focused workspace.
                        </p>
                        <a className="landing-cta" href="/DesignDashboard">
                            Start building <span aria-hidden="true">→</span>
                        </a>
                    </div>
                </section>
            </section>
        </div>
    );
}
