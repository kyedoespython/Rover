import React, { useEffect, useRef, useState } from "react";

const explanation = "This example maps a sign-up journey to a schema: an account has a unique ID, and a session refers back to that ID. Validation and password hashing happen before storage; the authentication checkpoint represents the rules required before access. Use relationships and checkpoints like these to plan a production schema, then implement and test the actual security rules for your application.";

const steps = [
    { number: "01", title: "Sign-up request", detail: "A user submits a username and password." },
    { number: "02", title: "Validate", detail: "Check the username and password against your rules." },
    { number: "03", title: "Store securely", detail: "Hash the password and create an account record." },
];

function DemoTable({ title, subtitle, rows }) {
    return (
        <div className="home-demo-table">
            <div className="home-demo-table-heading">
                <div>
                    <strong>{title}</strong>
                    <span>{subtitle}</span>
                </div>
                <span className="home-demo-table-tag">TABLE</span>
            </div>
            <table>
                <thead>
                    <tr><th scope="col">Field</th><th scope="col">Type</th><th scope="col">Example</th></tr>
                </thead>
                <tbody>
                    {rows.map(([field, type, value]) => (
                        <tr key={field}><th scope="row">{field}</th><td>{type}</td><td>{value}</td></tr>
                    ))}
                </tbody>
            </table>
        </div>
    );
}

export default function HomeDemo() {
    const flowRef = useRef(null);
    const [step, setStep] = useState(-1);
    const [run, setRun] = useState(0);
    const [typedLength, setTypedLength] = useState(0);
    const [reducedMotion, setReducedMotion] = useState(false);

    useEffect(() => {
        const preference = window.matchMedia("(prefers-reduced-motion: reduce)");
        const updatePreference = () => setReducedMotion(preference.matches);
        updatePreference();
        preference.addEventListener("change", updatePreference);
        return () => preference.removeEventListener("change", updatePreference);
    }, []);

    useEffect(() => {
        const flow = flowRef.current;
        if (!flow) return undefined;
        if (!("IntersectionObserver" in window)) {
            setStep(0);
            return undefined;
        }
        const observer = new IntersectionObserver((entries) => {
            if (entries.some((entry) => entry.isIntersecting)) {
                setStep(0);
                observer.disconnect();
            }
        }, { threshold: 0.1 });
        observer.observe(flow);
        return () => observer.disconnect();
    }, []);

    useEffect(() => {
        if (step < 0 || step >= 3) return undefined;
        if (reducedMotion) {
            setStep(3);
            return undefined;
        }
        const timer = window.setTimeout(() => setStep((current) => current + 1), 1100);
        return () => window.clearTimeout(timer);
    }, [step, reducedMotion, run]);

    useEffect(() => {
        if (step !== 3) return undefined;
        if (reducedMotion) {
            setTypedLength(explanation.length);
            return undefined;
        }
        const timer = window.setInterval(() => {
            setTypedLength((length) => {
                if (length >= explanation.length) {
                    window.clearInterval(timer);
                    return length;
                }
                return length + 1;
            });
        }, 18);
        return () => window.clearInterval(timer);
    }, [step, reducedMotion]);

    function replay() {
        setTypedLength(0);
        setStep(0);
        setRun((current) => current + 1);
    }

    return (
        <section className="home-demo" aria-labelledby="home-demo-title">
            <div className="home-demo-intro">
                <div>
                    <p className="home-demo-eyebrow">From idea to architecture</p>
                    <h2 id="home-demo-title">See the connections before you build.</h2>
                </div>
                <p>Explore a sample schema and follow a sign-up request from input to an authentication checkpoint.</p>
            </div>

            <div className="home-demo-panel">
                <div className="home-demo-section-heading">
                    <div><span>01 / SCHEMA</span><h3>A connected database</h3></div>
                    <p>Example data only · one account can have many sessions</p>
                </div>
                <div className="home-demo-schema">
                    <DemoTable title="accounts" subtitle="User records" rows={[
                        ["id · PK", "INTEGER", "101"],
                        ["username", "TEXT", "alex"],
                        ["password_hash", "TEXT", "[hashed]"],
                    ]} />
                    <div className="home-demo-relationship" aria-label="One account can have many sessions">
                        <span>1</span><div aria-hidden="true" /><span>∞</span>
                    </div>
                    <DemoTable title="sessions" subtitle="Account sessions" rows={[
                        ["id · PK", "INTEGER", "201"],
                        ["account_id · FK", "INTEGER", "101"],
                        ["created_at", "DATETIME", "2026-01-01"],
                    ]} />
                </div>
                <p className="home-demo-caption">PK = primary key &nbsp;·&nbsp; FK = foreign key referencing accounts.id</p>
            </div>

            <div className="home-demo-panel home-demo-flow-panel" ref={flowRef}>
                <div className="home-demo-section-heading">
                    <div><span>02 / REQUEST FLOW</span><h3>Follow a sign-up</h3></div>
                    <button className="home-demo-replay" type="button" onClick={replay}>Replay demo <span aria-hidden="true">↻</span></button>
                </div>
                <p className="home-demo-flow-note">An illustrative flow, not a live account or production request.</p>
                <div className="home-demo-flow">
                    {steps.map((item, index) => (
                        <div key={item.number} className={`home-demo-step${step === index ? " is-active" : ""}${step > index ? " is-complete" : ""}`}>
                            <span className="home-demo-step-number">{item.number}</span>
                            <h4>{item.title}</h4>
                            <p>{item.detail}</p>
                        </div>
                    ))}
                    <div className={`home-demo-target${step === 3 ? " is-reached" : ""}`}>
                        <div className="home-demo-target-icon" aria-hidden="true"><span /></div>
                        <div><span>04 / TARGET</span><h4>Authentication checkpoint</h4><p>Apply access and verification rules before granting a session.</p></div>
                        <strong>{step === 3 ? "Reached" : "Waiting"}</strong>
                    </div>
                </div>
                <div className="home-demo-response">
                    <div className="home-demo-response-label"><span /> SCHEMA NOTES</div>
                    <p aria-hidden="true">{step === 3 ? explanation.slice(0, typedLength) : "The walkthrough will appear here when the target is reached."}<span className={step === 3 && typedLength < explanation.length ? "home-demo-cursor" : ""} /></p>
                    <p className="home-demo-sr-only" role="status">{step === 3 && typedLength === explanation.length ? explanation : ""}</p>
                </div>
            </div>
        </section>
    );
}
