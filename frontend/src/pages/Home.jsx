import React from "react";

export default function Home({ authenticated, logoUrl }) {
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
                        <a href="/DesignDashboard">Workspace</a>
                        <a href="/Rover/Support">Contact</a>
                    </div>

                    <div className="landing-actions">
                        {authenticated ? (
                            <a href="/DesignDashboard">Open workspace</a>
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

                <div className="landing-art" aria-hidden="true">
                    {Array.from({ length: 8 }, (_, index) => (
                        <span className="metal-tile" key={index} />
                    ))}
                </div>

                <section className="landing-copy" aria-labelledby="landing-title">
                    <p className="landing-eyebrow">Ideas into intelligent software</p>
                    <h1 className="landing-title" id="landing-title">
                        Backend design choices made easy with Flask
                    </h1>
                    <div className="landing-footer">
                        <p className="landing-description">
                            Design, explore, and build with a workspace that keeps your tools and ideas together.
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
