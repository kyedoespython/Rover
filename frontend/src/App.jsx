import React from "react";

import Home from "./pages/Home.jsx";
import NotesPage from "./pages/NotesPage.jsx";
import DesignPage from "./pages/DesignPage.jsx";
import FastQueryPage from "./pages/FastQueryPage.jsx";
import ProfilePage from "./pages/ProfilePage.jsx";
import {
    AuthenticatePage,
    ForgotPasswordPage,
    LoginPage,
    ResetPasswordPage,
    SettingsPage,
    SignupPage,
    SupportPage,
} from "./pages/AuthPages.jsx";

const pages = {
    auth: AuthenticatePage,
    "forgot-password": ForgotPasswordPage,
    design: DesignPage,
    fastquery: FastQueryPage,
    home: Home,
    login: LoginPage,
    notes: NotesPage,
    profile: ProfilePage,
    "reset-password": ResetPasswordPage,
    settings: SettingsPage,
    signup: SignupPage,
    support: SupportPage,
};

export default function App({ page, ...props }) {
    const Page = pages[page];

    if (!Page) {
        throw new Error(`Unknown React page: ${page}`);
    }

    return <Page {...props} />;
}
