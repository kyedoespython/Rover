import React, { useState } from "react";

function PageNavigation({ children }) {
    return (
        <nav className="app-navigation" aria-label="Main navigation">
            {children}
        </nav>
    );
}

function PageFrame({ children }) {
    return <div className="app-page">{children}</div>;
}

function PageCard({ title, children, className = "" }) {
    return (
        <section className={`app-card ${className}`}>
            <h1 className="app-title">{title}</h1>
            {children}
        </section>
    );
}

function Field({ id, label, children }) {
    return (
        <div className="app-field">
            <label htmlFor={id}>{label}</label>
            {children}
        </div>
    );
}

function PasswordField({ id = "password", label, name = "password", autocomplete }) {
    const [visible, setVisible] = useState(false);

    return (
        <Field id={id} label={label}>
            <div className="app-password-control">
                <input
                    autoComplete={autocomplete}
                    id={id}
                    maxLength={128}
                    minLength={8}
                    name={name}
                    required
                    type={visible ? "text" : "password"}
                />
                <button
                    aria-label={visible ? "Hide password" : "Show password"}
                    aria-pressed={visible}
                    className="app-password-toggle"
                    onClick={() => setVisible((value) => !value)}
                    type="button"
                >
                    {visible ? "Hide" : "Show"}
                </button>
            </div>
        </Field>
    );
}

function CsrfInput({ token }) {
    return <input name="csrf_token" type="hidden" value={token} />;
}

function FormButton({ children }) {
    return <button className="app-primary-button" type="submit">{children}</button>;
}

export function SignupPage({ csrfToken }) {
    return (
        <PageFrame>
            <PageNavigation>
                <a href="/">Home</a>
                <a href="/Rover/Login">Login</a>
                <a href="/Rover/Support">Contact support</a>
            </PageNavigation>
            <PageCard title="Create your account">
                <form action="/Handle_signup" className="app-form" method="post">
                    <CsrfInput token={csrfToken} />
                    <Field id="email" label="Email">
                        <input autoComplete="email" id="email" name="email" required type="email" />
                    </Field>
                    <Field id="username" label="Username">
                        <input autoComplete="username" id="username" name="username" required type="text" />
                    </Field>
                    <PasswordField autocomplete="new-password" label="Password" />
                    <Field id="telephone" label={<>Phone number <span>(optional)</span></>}>
                        <input autoComplete="tel" id="telephone" name="telephone" type="tel" />
                    </Field>
                    <Field id="signupCountry" label="Country">
                        <select defaultValue="" id="signupCountry" name="country" required>
                            <option disabled value="">Select a country</option>
                            <option value="United Kingdom">United Kingdom +44</option>
                            <option value="United States">United States +1</option>
                            <option value="Germany">Germany +49</option>
                            <option value="France">France +33</option>
                        </select>
                    </Field>
                    <FormButton>Sign up</FormButton>
                </form>
                <p className="app-card-footer">
                    Already have an account? <a href="/Rover/Login">Log in</a>
                </p>
            </PageCard>
        </PageFrame>
    );
}

export function LoginPage({ csrfToken }) {
    return (
        <PageFrame>
            <PageNavigation>
                <a href="/">Home</a>
                <a href="/Rover/Sign%20Up">Sign up</a>
                <a href="/Rover/Support">Contact support</a>
            </PageNavigation>
            <PageCard title="Log in">
                <form action="/Handle_Login" className="app-form" method="post">
                    <CsrfInput token={csrfToken} />
                    <Field id="username" label="Username">
                        <input autoComplete="username" id="username" name="username" required type="text" />
                    </Field>
                    <PasswordField autocomplete="current-password" label="Password" />
                    <label className="app-checkbox">
                        <input name="remember_me" type="checkbox" value="1" />
                        Remember me for 3 days
                    </label>
                    <FormButton>Log in</FormButton>
                </form>
                <p className="app-card-footer">
                    Don’t have an account? <a href="/Rover/Sign%20Up">Sign up</a>
                    <br />
                    <a href="/Rover/Forgot-Password">Forgot password?</a>
                </p>
            </PageCard>
        </PageFrame>
    );
}

export function AuthenticatePage({ csrfToken }) {
    return (
        <PageFrame>
            <PageNavigation>
                <a href="/">Home</a>
                <a href="/Rover/Support">Contact support</a>
            </PageNavigation>
            <PageCard title="Verify your account">
                <p className="app-intro">Enter the authentication code sent to your email.</p>
                <form action="/HandleAuth" className="app-form" method="post">
                    <CsrfInput token={csrfToken} />
                    <Field id="authCode" label="Authentication code">
                        <input autoComplete="one-time-code" id="authCode" name="authCode" required type="text" />
                    </Field>
                    <FormButton>Verify code</FormButton>
                </form>
                <form action="/Resend_Auth" className="app-form app-secondary-form" method="post">
                    <CsrfInput token={csrfToken} />
                    <button className="app-secondary-button" type="submit">Resend auth code</button>
                </form>
            </PageCard>
        </PageFrame>
    );
}

export function ForgotPasswordPage({ csrfToken }) {
    return (
        <PageFrame>
            <PageNavigation><a href="/">Home</a></PageNavigation>
            <PageCard title="Forgot password?">
                <p className="app-intro">
                    Enter your account email. If it matches an account, we will send a password reset link.
                </p>
                <form action="/Handle_Forgot_Password" className="app-form" method="post">
                    <CsrfInput token={csrfToken} />
                    <Field id="resetEmail" label="Email">
                        <input autoComplete="email" id="resetEmail" maxLength={254} name="email" required type="email" />
                    </Field>
                    <FormButton>Send reset link</FormButton>
                </form>
                <p className="app-card-footer"><a href="/Rover/Login">Back to log in</a></p>
            </PageCard>
        </PageFrame>
    );
}

export function ResetPasswordPage({ csrfToken, token }) {
    return (
        <PageFrame>
            <PageNavigation><a href="/">Home</a></PageNavigation>
            <PageCard title="Reset password">
                <p className="app-intro">
                    Choose a password with at least 8 characters, one uppercase letter, and one special character (!@#$%^&amp;*).
                </p>
                <form action="/Rover/Reset-Password" className="app-form" method="post">
                    <CsrfInput token={csrfToken} />
                    <input name="token" type="hidden" value={token} />
                    <PasswordField autocomplete="new-password" id="newPassword" label="New password" />
                    <PasswordField
                        autocomplete="new-password"
                        id="confirmPassword"
                        label="Confirm new password"
                        name="confirm_password"
                    />
                    <FormButton>Reset password</FormButton>
                </form>
            </PageCard>
        </PageFrame>
    );
}

export function SupportPage({ authenticated, csrfToken, ticketContent = "", ticketName = "", ticketType = "" }) {
    return (
        <PageFrame>
            <PageNavigation>
                <a href="/">Home</a>
                {authenticated && <a href="/Rover/Settings">Settings</a>}
            </PageNavigation>
            <header className="app-page-heading">
                <h1>Rover Support</h1>
            </header>
            <PageCard className="app-support-card" title="Create a ticket">
                {!authenticated && (
                    <p className="app-intro">
                        <a href="/Rover/Login">Sign in</a> before submitting a ticket.
                    </p>
                )}
                <form action="/Tickets/Rover" className="app-form" method="post">
                    <CsrfInput token={csrfToken} />
                    <Field id="ticketType" label="Ticket type">
                        <select defaultValue={ticketType} id="ticketType" name="ticketType" required>
                            <option disabled value="">Select a ticket type</option>
                            <option value="bug">Found a bug</option>
                            <option value="recommendation">Recommendation</option>
                            <option value="question">Question</option>
                        </select>
                    </Field>
                    <Field id="nameTicket" label="Ticket name">
                        <input
                            id="nameTicket"
                            maxLength={64}
                            name="ticketName"
                            placeholder="Ticket name"
                            required
                            type="text"
                            defaultValue={ticketName}
                        />
                    </Field>
                    <Field id="TicketContent" label="Description">
                        <textarea
                            id="TicketContent"
                            maxLength={512}
                            name="TicketContent"
                            placeholder="Describe the issue or suggestion"
                            required
                            defaultValue={ticketContent}
                            rows={4}
                        />
                    </Field>
                    <FormButton>Submit your ticket</FormButton>
                </form>
                <p className="app-card-footer">
                    More information about this site{" "}
                    <a href="https://github.com/kyedoespython/Rover.git">here</a>
                </p>
            </PageCard>
        </PageFrame>
    );
}

export function SettingsPage() {
    return (
        <PageFrame>
            <PageNavigation>
                <a href="/">Home</a>
                <a href="/Rover/Notes">Notes</a>
                <a href="/Rover/Support">Support</a>
            </PageNavigation>
            <section className="app-page-heading">
                <h1>Settings</h1>
                <p className="app-intro">No settings are available yet.</p>
            </section>
        </PageFrame>
    );
}
