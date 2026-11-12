import io
import json
import re
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import pytest
import requests
from flask import Flask
from werkzeug.security import check_password_hash, generate_password_hash

from main.blueprints.auth import auth_bp
from main.blueprints.home import home_bp
from main.blueprints.Integrations.Ollama import ollama_bp
from main.extensions import csrf, db, limiter, login_manager
from main.models.user import (
    Accounts,
    Authentication,
    Chatbot,
    ChatbotFile,
    ChatbotMessage,
    ChatbotSession,
    Notes,
    PasswordResetToken,
    RoverAgent,
    RoverAgentMessage,
    RoverAgentSession,
    SchemaMetadata,
    UserApiKey,
    UserSchemaDatabase,
    UserSchema,
)
from main.services import notes_service
from main.services.agent_history_cleanup import cleanup_expired_agent_history
from main.services.auth_service import AUTH_CODE_MAX_ATTEMPTS, Create_Auth_Code
from main.services.notes_service import create_note
from main.services.ollama_service import decrypt_api_key


@pytest.fixture
def notes_client(tmp_path):
    template_folder = Path(__file__).parent.parent / "main" / "templates"
    app = Flask(
        __name__,
        template_folder=str(template_folder),
        static_folder=str(template_folder.parent / "static"),
    )
    app.config.update(
        TESTING=True,
        SECRET_KEY="notes-test-secret",
        SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        NOTE_STORAGE_DIR=str(tmp_path / "note-files"),
        PUBLIC_BASE_URL="https://rover.test",
        OLLAMA_BASE_URL="http://ollama.test",
        OLLAMA_MODEL="llama3.2",
        OLLAMA_API_KEY_ENCRYPTION_KEY="test-ollama-encryption-key",
        WTF_CSRF_ENABLED=False,
        RATELIMIT_ENABLED=False,
    )
    db.init_app(app)
    csrf.init_app(app)
    login_manager.init_app(app)
    limiter.init_app(app)
    app.register_blueprint(auth_bp)
    app.register_blueprint(home_bp)
    app.register_blueprint(ollama_bp)

    with app.app_context():
        db.create_all()
        account = Accounts(
            email="route-notes@example.com",
            username="RouteNotes",
            password="hashed-password",
            country_of_origin="United States",
            rover_ai_provider="ollama",
        )
        db.session.add(account)
        db.session.flush()
        db.session.add(Authentication(user_id=account.user_id, authenticated=True))
        db.session.commit()
        user_id = account.user_id

    with app.test_client() as client:
        with client.session_transaction() as session:
            session["_user_id"] = str(user_id)
            session["_fresh"] = True
        yield client

    with app.app_context():
        db.session.remove()
        db.drop_all()


def test_notes_route_create_load_edit_and_delete(notes_client):
    response = notes_client.post(
        "/Rover/Notes",
        data={
            "note_name": "Route plan",
            "note_description": "Route test",
            "note_content": "# Route note\nInitial content",
        },
    )
    assert response.status_code == 302

    with notes_client.application.app_context():
        note = Notes.query.filter_by(note_name="Route plan").one()
        note_id = note.note_id
        file_path = (
            Path(notes_client.application.config["NOTE_STORAGE_DIR"])
            / note.file_metadata.relative_path
        )

    response = notes_client.get(f"/Rover/Notes?load_id={note_id}")
    assert response.status_code == 200
    assert b"# Route note\nInitial content" in response.data
    assert b"Save note" in response.data
    assert b'id="noteHeadingMenu"' in response.data
    assert b'id="headingSelectToggle"' in response.data
    assert b'id="headingSelect" hidden' in response.data
    assert b'id="noteContentEditor"' in response.data
    assert b'data-heading-level="6"' in response.data
    notes_heading = response.data.index(b">Notes</h1>")
    heading_button = response.data.index(b">Heading select</button>")
    support_button = response.data.index(b">Support</a>")
    assert notes_heading < heading_button < support_button
    assert b'id="notePreview"' not in response.data
    assert b"Preview" not in response.data

    response = notes_client.post(
        f"/Rover/Notes/{note_id}/update",
        data={
            "note_name": "Updated route plan",
            "note_description": "Edited through route",
            "note_content": "# Updated route note",
        },
    )
    assert response.status_code == 302

    with notes_client.application.app_context():
        note = db.session.get(Notes, note_id)
        assert note.note_name == "Updated route plan"
        assert note.file_metadata.relative_path
        assert not file_path.exists()

    response = notes_client.get(f"/Rover/Notes?load_id={note_id}")
    assert response.status_code == 200
    assert b'id="noteName"' in response.data
    assert b'name="note_name"' in response.data
    assert b'value="Updated route plan"' in response.data
    assert b'id="noteHeadingMenu"' in response.data
    assert b'data-heading-level="1"' in response.data

    response = notes_client.post(
        f"/Rover/Notes/{note_id}/description",
        data={"note_description": "Updated from the sidebar"},
    )
    assert response.status_code == 302
    with notes_client.application.app_context():
        note = db.session.get(Notes, note_id)
        assert note.note_description == "Updated from the sidebar"

    response = notes_client.post(f"/Rover/Notes/{note_id}/delete")
    assert response.status_code == 302

    with notes_client.application.app_context():
        assert db.session.get(Notes, note_id) is None


def test_authenticated_routes_reject_anonymous_clients(notes_client):
    anonymous_client = notes_client.application.test_client()

    assert anonymous_client.get("/Rover/Notes").status_code == 401
    assert anonymous_client.get("/DesignDashboard").status_code == 401
    assert anonymous_client.get("/api/ollama/session").status_code == 401


def test_notes_routes_reject_access_to_another_users_note(notes_client):
    with notes_client.application.app_context():
        other_account = Accounts(
            email="private-note-owner@example.com",
            username="PrivateNoteOwner",
            password=generate_password_hash("test-password"),
            country_of_origin="United States",
        )
        db.session.add(other_account)
        db.session.flush()
        other_note = create_note(
            other_account.user_id,
            "Private note",
            "",
            "Only the owner should see this content.",
        )
        note_id = other_note.note_id
        note_file_path = (
            Path(notes_client.application.config["NOTE_STORAGE_DIR"])
            / other_note.file_metadata.relative_path
        )
        original_file_content = note_file_path.read_text(encoding="utf-8")

    loaded = notes_client.get(f"/Rover/Notes?load_id={note_id}")
    updated = notes_client.post(
        f"/Rover/Notes/{note_id}/update",
        data={"note_content": "Changed by another user"},
    )
    deleted = notes_client.post(f"/Rover/Notes/{note_id}/delete")

    assert loaded.status_code == 404
    assert b"Only the owner should see this content." not in loaded.data
    assert updated.status_code == 404
    assert deleted.status_code == 404

    with notes_client.application.app_context():
        note = db.session.get(Notes, note_id)
        assert note is not None
        assert note.note_content is None
        assert note_file_path.read_text(encoding="utf-8") == original_file_content


def test_notes_write_rejects_missing_csrf_token(notes_client):
    notes_client.application.config["WTF_CSRF_ENABLED"] = True

    response = notes_client.post(
        "/Rover/Notes",
        data={
            "note_name": "CSRF attempt",
            "note_description": "",
            "note_content": "Must not be stored",
        },
    )

    assert response.status_code == 400
    with notes_client.application.app_context():
        assert Notes.query.filter_by(note_name="CSRF attempt").first() is None


def test_auth_code_attempt_limit_is_per_account_across_ips(notes_client):
    with notes_client.application.app_context():
        account = Accounts(
            email="pending-verification@example.com",
            username="PendingVerification",
            password=generate_password_hash("test-password"),
            country_of_origin="United States",
        )
        db.session.add(account)
        db.session.flush()
        authentication = Authentication(
            user_id=account.user_id,
            auth_code=generate_password_hash("1234567"),
            auth_code_expires=datetime.now(timezone.utc) + timedelta(minutes=10),
        )
        db.session.add(authentication)
        db.session.commit()
        user_id = account.user_id
        auth_id = authentication.auth_id

    with notes_client.session_transaction() as session:
        session["pending_auth_email"] = "pending-verification@example.com"

    for attempt in range(AUTH_CODE_MAX_ATTEMPTS):
        response = notes_client.post(
            "/HandleAuth",
            data={"authCode": "0000000"},
            environ_overrides={"REMOTE_ADDR": f"198.51.100.{attempt + 1}"},
        )
        assert response.status_code == 302

    with notes_client.application.app_context():
        authentication = db.session.get(Authentication, auth_id)
        account = db.session.get(Accounts, user_id)
        assert authentication.failed_attempts == AUTH_CODE_MAX_ATTEMPTS
        assert authentication.auth_code is None
        assert authentication.auth_code_expires is None
        assert not authentication.authenticated

    notes_client.post("/HandleAuth", data={"authCode": "1234567"})
    with notes_client.application.app_context():
        assert not db.session.get(Authentication, auth_id).authenticated


def test_duplicate_signup_cannot_bind_session_to_pending_account(notes_client):
    email = "pending-owner@example.com"
    with notes_client.application.app_context():
        account = Accounts(
            email=email,
            username="PendingOwner",
            password=generate_password_hash("original-password"),
            country_of_origin="United States",
        )
        db.session.add(account)
        db.session.flush()
        db.session.add(
            Authentication(
                user_id=account.user_id,
                auth_code=generate_password_hash("7654321"),
                auth_code_expires=datetime.now(timezone.utc) + timedelta(minutes=10),
            )
        )
        db.session.commit()

    with notes_client.session_transaction() as session:
        session["pending_auth_email"] = "previous-pending@example.com"

    with patch("main.blueprints.auth.routes.SignupAttemptMail") as signup_attempt:
        response = notes_client.post(
            "/Handle_signup",
            data={
                "email": email,
                "username": "NewPendingOwner",
                "password": "Strong!Password",
                "telephone": "",
                "country": "United States",
            },
        )

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/Rover/Auth")
    signup_attempt.assert_called_once_with(email)
    with notes_client.session_transaction() as session:
        assert "pending_auth_email" not in session


def test_issuing_new_auth_code_resets_failed_attempts(notes_client):
    with notes_client.application.app_context():
        account = Accounts(
            email="auth-code-reset@example.com",
            username="AuthCodeReset",
            password=generate_password_hash("test-password"),
            country_of_origin="United States",
        )
        db.session.add(account)
        db.session.flush()
        authentication = Authentication(
            user_id=account.user_id,
            failed_attempts=AUTH_CODE_MAX_ATTEMPTS,
        )
        db.session.add(authentication)
        db.session.commit()
        db.session.expire(account, ["authentication_data"])

        with patch(
            "main.services.auth_service.SendAuthCode_EMAIL",
            return_value=(True, "Auth code sent to your email."),
        ):
            success, _ = Create_Auth_Code(account)

        db.session.refresh(authentication)
        assert success
        assert authentication.failed_attempts == 0
        assert authentication.auth_code
        assert authentication.auth_code_expires


def test_home_uses_metallic_dark_hero(notes_client):
    response = notes_client.get("/")

    assert response.status_code == 200
    assert b"WorldImage.jpg" not in response.data
    assert b"Rover_backgroundVideo" not in response.data
    assert b'class="landing-title"' in response.data
    assert b'class="metal-tile"' in response.data
    assert b"One workspace.<br>Clear direction.<br>Complete execution." in response.data
    assert b"Rover_Logo.png" in response.data


@pytest.mark.parametrize(
    "path",
    [
        "/",
        "/Rover/Notes",
        "/DesignDashboard",
        "/Rover/Support",
        "/Rover/Settings",
        "/Rover/Login",
        "/Rover/Sign%20Up",
    ],
)
def test_site_pages_share_silver_theme_and_responsive_viewport(notes_client, path):
    response = notes_client.get(path, follow_redirects=True)

    assert response.status_code == 200
    assert b'content="width=device-width, initial-scale=1.0"' in response.data
    assert b"--rover-accent: #bcc6ca" in response.data
    assert b"WorldImage.jpg" not in response.data
    assert b"RoverBackground" not in response.data


def test_signup_phone_country_mismatch_flashes_red_error(notes_client):
    response = notes_client.post(
        "/Handle_signup",
        data={
            "email": "signup-mismatch@example.com",
            "username": "SignupMismatch",
            "password": "Strong!Password",
            "telephone": "+442083661177",
            "country": "France",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b'class="flash-message flash-message-error"' in response.data
    assert b"phone number and country doesnt match" in response.data
    assert b"scripts/Signup.js?v=1" in response.data
    assert b'data-calling-code="44"' in response.data
    with notes_client.application.app_context():
        assert (
            Accounts.query.filter_by(email="signup-mismatch@example.com").first()
            is None
        )


def test_password_reset_request_is_generic_and_reset_token_is_single_use(notes_client):
    notes_client.application.config["RESEND_API_KEY"] = "test-resend-key"
    account_email = "route-notes@example.com"

    with patch("main.services.auth_service.resend.Emails.send") as send:
        known_response = notes_client.post(
            "/Handle_Forgot_Password",
            data={"email": account_email},
            follow_redirects=True,
        )
        unknown_response = notes_client.post(
            "/Handle_Forgot_Password",
            data={"email": "not-an-account@example.com"},
            follow_redirects=True,
        )

    assert known_response.status_code == 200
    assert known_response.data == unknown_response.data
    assert (
        b"If an account exists for that email, password reset instructions will be sent."
        in known_response.data
    )
    send.assert_called_once()

    email_payload = send.call_args.args[0]
    assert email_payload["to"] == [account_email]
    match = re.search(
        r"https://rover\.test/Rover/Reset-Password\?token=([A-Za-z0-9_-]+)",
        email_payload["text"],
    )
    assert match is not None
    token = match.group(1)

    with notes_client.application.app_context():
        reset_record = PasswordResetToken.query.one()
        account = Accounts.query.filter_by(email=account_email).one()
        assert reset_record.token_hash != token
        assert reset_record.user_id == account.user_id

    reset_page = notes_client.get(f"/Rover/Reset-Password?token={token}")
    assert reset_page.status_code == 200
    assert reset_page.headers["Cache-Control"] == "no-store"
    assert reset_page.headers["Referrer-Policy"] == "no-referrer"

    changed = notes_client.post(
        "/Rover/Reset-Password",
        data={
            "token": token,
            "password": "NewStrong!Password",
            "confirm_password": "NewStrong!Password",
        },
        follow_redirects=True,
    )
    assert changed.status_code == 200
    assert b"Your password has been reset. Please log in." in changed.data
    assert b"Login" in changed.data
    assert notes_client.get("/DesignDashboard").status_code == 401

    reused = notes_client.post(
        "/Rover/Reset-Password",
        data={
            "token": token,
            "password": "AnotherStrong!Password",
            "confirm_password": "AnotherStrong!Password",
        },
        follow_redirects=True,
    )
    assert b"That password reset link is invalid or expired." in reused.data

    with notes_client.application.app_context():
        account = Accounts.query.filter_by(email=account_email).one()
        assert check_password_hash(account.password, "NewStrong!Password")
        assert not check_password_hash(account.password, "AnotherStrong!Password")
        assert account.session_version == 1
        assert PasswordResetToken.query.one().used_at is not None


def test_notes_page_creates_default_note_and_sidebar_creates_named_notes(notes_client):
    page = notes_client.get("/Rover/Notes")
    assert page.status_code == 200
    assert b"Empty note" in page.data
    assert b"New note name" in page.data
    assert b"Your notes" in page.data
    assert b"scripts/Notes/Notes.js?v=5" in page.data
    assert b"notePreview" not in page.data
    assert b"Preview" not in page.data

    with notes_client.application.app_context():
        default_note = Notes.query.filter_by(note_name="Empty note").one()
        assert default_note.note_content is None
        assert default_note.file_metadata is not None
        default_note_id = default_note.note_id

    created = notes_client.post(
        "/Rover/Notes",
        data={"note_name": "A note from the sidebar"},
    )
    assert created.status_code == 302
    assert created.headers["Location"].endswith("/Rover/Notes")

    with notes_client.application.app_context():
        created_note = Notes.query.filter_by(note_name="A note from the sidebar").one()
        assert created_note.note_content is None
        assert created_note.file_metadata is not None

    opened = notes_client.get(f"/Rover/Notes?load_id={default_note_id}")
    assert opened.status_code == 200
    assert b'id="noteContent"' in opened.data
    assert b"Double-click text to show the Heading select menu" in opened.data
    assert b'id="noteContentEditor"' in opened.data


def test_notes_page_remains_usable_when_markdown_storage_is_unavailable(
    notes_client, monkeypatch
):
    def fail_file_write(*args, **kwargs):
        raise PermissionError("note storage is read-only")

    monkeypatch.setattr(notes_service, "_write_markdown_file", fail_file_write)

    page = notes_client.get("/Rover/Notes")
    assert page.status_code == 200
    assert b"Empty note" in page.data
    assert b"Your default note could not be created" not in page.data

    response = notes_client.post(
        "/Rover/Notes",
        data={
            "note_name": "Saved in database",
            "note_description": "Fallback note",
            "note_content": "This note is still saved",
        },
    )
    assert response.status_code == 302
    with notes_client.application.app_context():
        note = Notes.query.filter_by(note_name="Saved in database").one()
        assert note.note_content == "This note is still saved"
        assert note.file_metadata is None


def test_note_names_are_unique_per_user(notes_client):
    with notes_client.application.app_context():
        other_account = Accounts(
            email="another-notes-user@example.com",
            username="AnotherNotesUser",
            password=generate_password_hash("test-password"),
            country_of_origin="United States",
        )
        db.session.add(other_account)
        db.session.commit()
        other_user_id = other_account.user_id

        first_user_id = (
            Accounts.query.filter_by(email="route-notes@example.com").one().user_id
        )
        create_note(first_user_id, "Shared name", "", "")
        create_note(other_user_id, "Shared name", "", "")

        assert Notes.query.filter_by(note_name="Shared name").count() == 2


def test_api_key_is_saved_as_hash_and_returned_without_secret(notes_client):
    secret = "ollama-secret-test-value"
    response = notes_client.post(
        "/Rover/Design/API-Keys",
        json={"name": "Local Ollama", "type": "ollama", "api_key": secret},
    )

    assert response.status_code == 201
    result = response.get_json()["api_key"]
    assert result["name"] == "Local Ollama"
    assert result["type"] == "ollama"
    assert secret not in response.get_data(as_text=True)

    with notes_client.application.app_context():
        stored_key = db.session.get(UserApiKey, result["id"])
        account = db.session.get(Accounts, stored_key.user_id)
        assert stored_key is not None
        assert stored_key.key_name == "Local Ollama"
        assert stored_key.key_type == "ollama"
        assert stored_key.key_hash != secret
        assert check_password_hash(stored_key.key_hash, secret)
        assert stored_key.key_ciphertext
        assert (
            decrypt_api_key(
                stored_key.key_ciphertext,
                stored_key.user_id,
                stored_key.api_key_id,
            )
            == secret
        )
        assert account.active_ollama_api_key_id == stored_key.api_key_id

    dashboard = notes_client.get("/DesignDashboard")
    assert dashboard.status_code == 200
    assert b"Saved API keys" not in dashboard.data
    assert b"Local Ollama" not in dashboard.data
    assert secret.encode() not in dashboard.data

    settings = notes_client.get("/Rover/Settings")
    assert settings.status_code == 200
    assert b"Saved API keys" in settings.data
    assert b"Local Ollama" in settings.data
    assert b"Active" in settings.data
    assert secret.encode() not in settings.data


def test_rover_ai_panel_is_design_page_only_and_labels_are_black(notes_client):
    with notes_client.application.app_context():
        account = Accounts.query.filter_by(email="route-notes@example.com").one()
        account.authentication_data.authenticated = False
        db.session.commit()

    response = notes_client.get("/DesignDashboard")

    assert response.status_code == 200
    assert b'id="ollamaDrawer"' in response.data
    assert b'id="roverModeSelect"' in response.data
    assert b'class="ollama-mode-section"' in response.data
    assert b'id="ollamaMinimize"' in response.data
    assert b'id="ollamaEndSession"' in response.data
    assert b"scripts/Integrations/Ollama.js?v=18" in response.data
    assert response.data.count(b'id="ollamaDrawer"') == 1
    assert (
        b'class="button is-outlined design-side-button rover-ai-nav-button"'
        in response.data
    )
    assert b"ollama-drawer-toggle" not in response.data
    assert response.data.index(b">Demo</button>") < response.data.index(
        b">Rover AI</button>"
    )
    assert b'aria-expanded="false"' in response.data
    assert b'class="ollama-drawer is-minimized"' in response.data
    assert b"Rover AI" in response.data
    assert b'id="ollamaReadFile"' not in response.data
    assert b"Add folder file to Rover AI" in response.data
    assert b"Encrypted at rest; checked files are sent to the active AI provider" in response.data
    assert b"Drop text files here or" in response.data
    assert (
        b'id="ollamaFileInput" type="file" multiple aria-label="Browse text files" disabled'
        in response.data
    )
    assert b'id="ollamaAddFile"' not in response.data
    assert b"Verify your account to enable Rover AI chat." in response.data
    assert b"#designPage .api-key-dialog .label" in response.data
    assert (
        b'id="ollamaChatInput"' in response.data
        and b" disabled required" in response.data
    )
    assert b'id="ollamaChatbotModelSelect"' in response.data
    assert b'id="ollamaChatbotModelInput"' not in response.data
    assert b'id="ollamaApiKeySelect"' in response.data
    assert b'id="ollamaLoadApiKey"' in response.data
    assert b'type="module" src="/static/scripts/Design/Schema/Schema.js?v=1"' in response.data
    assert b'id="openSchemaEditor"' in response.data
    assert b'id="schemaEditorDialog"' in response.data
    assert b'data-schema-url="/api/schema"' in response.data
    assert b'id="schemaFileInput"' in response.data
    assert b'id="schemaDatabaseList"' in response.data
    assert b'id="openSchemaQuery"' in response.data
    assert b'id="openSchemaDemo"' in response.data
    assert b"Browser simulation only" in response.data
    assert b'id="saveSchemaButton"' in response.data
    assert b'data-schema-view="tables"' in response.data
    assert b'data-schema-view="configure"' in response.data
    assert b'data-schema-view="relationships"' in response.data
    assert response.data.count(b">Relationships</button>") == 1

    other_page = notes_client.get("/Rover/Settings", follow_redirects=True)
    assert other_page.status_code == 200
    assert b'id="ollamaDrawer"' not in other_page.data
    home_page = notes_client.get("/")
    assert home_page.status_code == 200
    assert b'id="ollamaDrawer"' not in home_page.data
    assert b"scripts/Integrations/Ollama.js?v=8" not in home_page.data


def test_schema_editor_module_imports_are_served(notes_client):
    response = notes_client.get("/DesignDashboard")
    entry = re.search(
        rb'type="module" src="([^"]*scripts/Design/Schema/Schema\.js[^"]*)"',
        response.data,
    )
    assert entry is not None
    entry_url = entry.group(1).decode()
    script = notes_client.get(entry_url)
    assert script.status_code == 200
    assert script.mimetype in ("text/javascript", "application/javascript")

    imports = re.findall(rb'from "\./([^"]+)"', script.data)
    assert imports
    module_directory = entry_url.rsplit("/", 1)[0]
    for imported in imports:
        module = notes_client.get(f"{module_directory}/{imported.decode()}")
        assert module.status_code == 200
        assert module.mimetype in ("text/javascript", "application/javascript")


def test_user_schema_saves_connections_and_derived_metadata(notes_client):
    schema = {
        "tables": [
            {
                "id": "1",
                "name": "Accounts",
                "x": 40,
                "y": 60,
                "columns": [
                    {
                        "id": "11",
                        "name": "id",
                        "type": "AutoNumber",
                        "primaryKey": True,
                    }
                ],
            },
            {
                "id": "2",
                "name": "Orders",
                "x": 420,
                "y": 60,
                "columns": [
                    {
                        "id": "21",
                        "name": "id",
                        "type": "AutoNumber",
                        "primaryKey": True,
                    },
                    {
                        "id": "22",
                        "name": "account_id",
                        "type": "Number",
                        "primaryKey": False,
                    },
                ],
            },
        ],
        "relationships": [
            {
                "id": "31",
                "sourceTableId": "1",
                "targetTableId": "2",
                "sourceColumnId": "11",
                "targetColumnId": "22",
                "color": "#2878b5",
            }
        ],
    }

    empty = notes_client.get("/api/schema")
    assert empty.status_code == 200
    assert empty.get_json()["databases"] == []

    saved = notes_client.post(
        "/api/schema",
        json={"name": "Orders database", "schema": schema},
    )
    assert saved.status_code == 201
    database = saved.get_json()["database"]
    assert database["name"] == "Orders database"
    assert database["file_name"] == "Orders-database.sqlite3"
    assert database["table_count"] == 2
    assert database["column_count"] == 3
    assert database["relationship_count"] == 1

    loaded = notes_client.get(f"/api/schema/{database['id']}")
    assert loaded.status_code == 200
    assert loaded.get_json()["schema"] == schema
    with notes_client.application.app_context():
        stored_database = UserSchemaDatabase.query.one()
        assert stored_database.schema_data == schema
        assert stored_database.database_data.startswith(b"SQLite format 3\x00")
        sqlite_file = sqlite3.connect(":memory:")
        sqlite_file.deserialize(stored_database.database_data)
        assert sqlite_file.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        ).fetchall() == [("Accounts",), ("Orders",)]
        sqlite_file.close()

    invalid = {
        **schema,
        "relationships": [
            {
                **schema["relationships"][0],
                "targetTableId": "missing-table",
            }
        ],
    }
    rejected = notes_client.put(
        f"/api/schema/{database['id']}",
        json={"name": "Orders database", "schema": invalid},
    )
    assert rejected.status_code == 400
    assert notes_client.get(f"/api/schema/{database['id']}").get_json()["schema"] == schema

    query = notes_client.post(
        f"/api/schema/{database['id']}/query",
        json={
            "query": "SELECT name FROM sqlite_master "
            "WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        },
    )
    assert query.status_code == 200
    assert query.get_json()["rows"] == [["Accounts"], ["Orders"]]

    write_query = notes_client.post(
        f"/api/schema/{database['id']}/query",
        json={"query": "DELETE FROM Accounts"},
    )
    assert write_query.status_code == 400

    deleted = notes_client.delete(f"/api/schema/{database['id']}")
    assert deleted.status_code == 200
    assert notes_client.get("/api/schema").get_json()["databases"] == []


def test_sqlite_upload_preserves_data_and_rejects_writes(notes_client):
    source = sqlite3.connect(":memory:")
    source.execute("CREATE TABLE Sample (id INTEGER PRIMARY KEY, value TEXT)")
    source.execute("INSERT INTO Sample (id, value) VALUES (1, 'stored')")
    database_file = source.serialize()
    source.close()

    unsupported = notes_client.post(
        "/api/schema/import",
        data={"file": (io.BytesIO(database_file), "sample.txt")},
        content_type="multipart/form-data",
    )
    assert unsupported.status_code == 415

    imported = notes_client.post(
        "/api/schema/import",
        data={"file": (io.BytesIO(database_file), "sample.db")},
        content_type="multipart/form-data",
    )
    assert imported.status_code == 201
    database = imported.get_json()["database"]
    assert database["name"] == "sample"

    loaded = notes_client.get(f"/api/schema/{database['id']}")
    schema = loaded.get_json()["schema"]
    schema["tables"][0]["columns"].append(
        {
            "id": "new-column",
            "name": "notes",
            "type": "Short Text",
            "primaryKey": False,
        }
    )
    updated = notes_client.put(
        f"/api/schema/{database['id']}",
        json={"name": "sample", "schema": schema},
    )
    assert updated.status_code == 200
    rows = notes_client.post(
        f"/api/schema/{database['id']}/query",
        json={"query": "SELECT id, value, notes FROM Sample"},
    )
    assert rows.status_code == 200
    assert rows.get_json()["rows"] == [[1, "stored", None]]

    rejected_write = notes_client.post(
        f"/api/schema/{database['id']}/query",
        json={"query": "DELETE FROM Sample"},
    )
    assert rejected_write.status_code == 400
    assert notes_client.post(
        f"/api/schema/{database['id']}/query",
        json={"query": "SELECT id, value FROM Sample"},
    ).get_json()["rows"] == [[1, "stored"]]


@pytest.mark.parametrize("filename", ["schema.sqlite3", "schema.sqlite", "schema.db"])
def test_sqlite_import_accepts_supported_extensions(notes_client, filename):
    source = sqlite3.connect(":memory:")
    database_file = source.serialize()
    source.close()

    response = notes_client.post(
        "/api/schema/import",
        data={"file": (io.BytesIO(database_file), filename)},
        content_type="multipart/form-data",
    )

    assert response.status_code == 201
    assert response.get_json()["database"]["file_name"] == filename


def test_legacy_user_schema_is_migrated_to_sqlite_storage(notes_client):
    with notes_client.application.app_context():
        account = Accounts.query.filter_by(email="route-notes@example.com").one()
        legacy = UserSchema(
            user_id=account.user_id,
            schema_data={"tables": [], "relationships": []},
        )
        legacy.details = SchemaMetadata(
            table_count=0,
            column_count=0,
            relationship_count=0,
            table_names=[],
            data_types=[],
        )
        db.session.add(legacy)
        db.session.commit()

    response = notes_client.get("/api/schema")
    assert response.status_code == 200
    database = response.get_json()["databases"][0]
    assert database["name"] == "My Database"
    with notes_client.application.app_context():
        assert UserSchema.query.count() == 0
        stored_database = UserSchemaDatabase.query.one()
        assert stored_database.database_data.startswith(b"SQLite format 3\x00")


def test_schema_database_crud_is_scoped_to_the_owner(notes_client):
    source = sqlite3.connect(":memory:")
    database_file = source.serialize()
    source.close()
    with notes_client.application.app_context():
        other_account = Accounts(
            email="other-schema@example.com",
            username="OtherSchema",
            password="hashed-password",
            country_of_origin="United States",
        )
        db.session.add(other_account)
        db.session.flush()
        other_database = UserSchemaDatabase(
            user_id=other_account.user_id,
            schema_name="Private database",
            file_name="private.db",
            database_data=database_file,
            schema_data={"tables": [], "relationships": []},
        )
        db.session.add(other_database)
        db.session.commit()
        database_id = other_database.schema_database_id

    url = f"/api/schema/{database_id}"
    assert notes_client.get(url).status_code == 404
    assert notes_client.put(
        url,
        json={"name": "Changed", "schema": {"tables": [], "relationships": []}},
    ).status_code == 404
    assert notes_client.delete(url).status_code == 404
    assert (
        notes_client.post(f"{url}/query", json={"query": "SELECT 1"}).status_code
        == 404
    )


def test_triple_rover_page_keeps_only_the_navigation_and_three_agent_slots(
    notes_client,
):
    response = notes_client.get("/DesignDashboard/Agents")

    assert response.status_code == 200
    assert b'id="roverAgentsGrid"' in response.data
    assert b"scripts/Design/Agents.js?v=1" in response.data
    assert b"Triple Rover Mode" in response.data
    assert b"<title>Rover Triple Rover Mode</title>" in response.data
    assert b'id="ollamaDrawer"' not in response.data
    assert b'id="dashboardHeading"' not in response.data
    assert b'id="openApiKeyDialog"' not in response.data
    assert b"Your designs" not in response.data
    assert b">Home</a>" in response.data and b">Notes</a>" in response.data
    assert b">Support</a>" not in response.data
    assert b"text-decoration: none" in response.data
    assert b"padding: 0.5rem 1rem" in response.data
    assert b"gap: 1rem" in response.data
    assert b"white-space: nowrap" in response.data
    assert b"text-overflow: ellipsis" in response.data


def test_triple_rover_initializes_three_owned_agent_slots(notes_client):
    response = notes_client.get("/api/ollama/agents")

    assert response.status_code == 200
    agents = response.get_json()["agents"]
    assert len(agents) == 3
    assert [agent["slot"] for agent in agents] == [1, 2, 3]
    assert [agent["name"] for agent in agents] == [
        "Rover Agent 1",
        "Rover Agent 2",
        "Rover Agent 3",
    ]

    with notes_client.application.app_context():
        assert RoverAgent.query.count() == 3
        assert RoverAgentSession.query.count() == 3
        assert {agent["id"] for agent in agents} == {
            agent.agent_id for agent in RoverAgent.query.all()
        }


@patch("main.blueprints.Integrations.Ollama.routes.requests.post")
@patch("main.blueprints.Integrations.Ollama.routes.requests.get")
def test_triple_rover_agent_settings_and_chats_are_independent(
    mock_get,
    mock_post,
    notes_client,
):
    agents = notes_client.get("/api/ollama/agents").get_json()["agents"]
    mock_get.return_value.json.return_value = {
        "models": [{"name": "qwen3:latest"}, {"name": "llama3.2"}]
    }
    mock_get.return_value.raise_for_status.return_value = None

    saved = notes_client.post(
        f"/api/ollama/agents/{agents[0]['id']}/settings",
        json={
            "name": "Planner",
            "model": "qwen3:latest",
            "system_prompt": "Plan before answering.",
            "temperature": 0.2,
        },
    )
    assert saved.status_code == 200
    assert saved.get_json()["name"] == "Planner"

    mock_post.return_value.json.side_effect = [
        {"message": {"role": "assistant", "content": "Plan ready."}},
        {"message": {"role": "assistant", "content": "Hello."}},
    ]
    mock_post.return_value.raise_for_status.return_value = None
    first_chat = notes_client.post(
        f"/api/ollama/agents/{agents[0]['id']}/chat",
        json={"message": "Plan a task"},
    )
    second_chat = notes_client.post(
        f"/api/ollama/agents/{agents[1]['id']}/chat",
        json={"message": "Say hello"},
    )

    assert first_chat.status_code == 200
    assert second_chat.status_code == 200
    first_request = mock_post.call_args_list[0].kwargs["json"]
    second_request = mock_post.call_args_list[1].kwargs["json"]
    assert first_request["model"] == "qwen3:latest"
    assert first_request["messages"][0] == {
        "role": "system",
        "content": "Plan before answering.",
    }
    assert first_request["options"]["temperature"] == 0.2
    assert second_request["model"] == "llama3.2"
    assert second_request["messages"] == [{"role": "user", "content": "Say hello"}]

    with notes_client.application.app_context():
        saved_agents = RoverAgent.query.order_by(RoverAgent.slot_number).all()
        assert saved_agents[0].chat_session.first_message_at is not None
        assert saved_agents[1].chat_session.first_message_at is not None
        assert saved_agents[2].chat_session.first_message_at is None
        assert saved_agents[0].configuration.system_prompt == "Plan before answering."
        assert saved_agents[1].configuration.system_prompt == ""


def test_scheduled_agent_history_cleanup_uses_first_chat_timestamp(notes_client):
    agents = notes_client.get("/api/ollama/agents").get_json()["agents"]
    now = datetime.now(timezone.utc)
    with notes_client.application.app_context():
        sessions = RoverAgentSession.query.order_by(RoverAgentSession.agent_id).all()
        sessions[0].first_message_at = now - timedelta(days=7)
        sessions[1].first_message_at = now - timedelta(days=6)
        db.session.add(
            RoverAgentMessage(
                session_id=sessions[0].session_id,
                role="user",
                content="This history has expired.",
            )
        )
        db.session.commit()
        expired_session_id = sessions[0].session_id
        retained_session_id = sessions[1].session_id

        deleted_count = cleanup_expired_agent_history(now)

        assert deleted_count == 1
        assert db.session.get(RoverAgentSession, expired_session_id) is None
        assert db.session.get(RoverAgentSession, retained_session_id) is not None
        assert (
            RoverAgentMessage.query.filter_by(session_id=expired_session_id).count()
            == 0
        )
        assert RoverAgent.query.count() == len(agents)


def test_settings_navigation_is_only_on_support_page(notes_client):
    support_page = notes_client.get("/Rover/Support")
    assert support_page.status_code == 200
    assert b"justify-content: space-between" in support_page.data
    assert b'href="/Rover/Settings"' in support_page.data

    notes_page = notes_client.get("/Rover/Notes")
    assert notes_page.status_code == 200
    assert b'href="/Rover/Settings"' not in notes_page.data


def test_api_key_type_is_required_and_names_must_be_unique(notes_client):
    incomplete = notes_client.post(
        "/Rover/Design/API-Keys",
        json={"name": "Missing type", "type": "", "api_key": "secret"},
    )
    assert incomplete.status_code == 400

    payload = {"name": "One key", "type": "ollama", "api_key": "secret"}
    assert notes_client.post("/Rover/Design/API-Keys", json=payload).status_code == 201
    duplicate = notes_client.post("/Rover/Design/API-Keys", json=payload)
    assert duplicate.status_code == 409


def test_hash_only_api_key_can_be_reentered_and_encrypted(notes_client):
    with notes_client.application.app_context():
        account = Accounts.query.filter_by(email="route-notes@example.com").one()
        old_key = UserApiKey(
            user_id=account.user_id,
            key_name="Legacy Ollama",
            key_type="ollama",
            key_hash=generate_password_hash("unrecoverable"),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db.session.add(old_key)
        db.session.commit()
        old_key_id = old_key.api_key_id

    replacement = notes_client.post(
        "/Rover/Design/API-Keys",
        json={
            "name": "Legacy Ollama",
            "type": "ollama",
            "api_key": "new-usable-secret",
        },
    )
    assert replacement.status_code == 201
    assert replacement.get_json()["api_key"]["id"] == old_key_id

    with notes_client.application.app_context():
        key = db.session.get(UserApiKey, old_key_id)
        assert decrypt_api_key(key.key_ciphertext, key.user_id, key.api_key_id) == (
            "new-usable-secret"
        )


@patch("main.blueprints.Integrations.Ollama.routes.requests.get")
def test_ollama_status_reports_selected_model(mock_get, notes_client):
    mock_get.return_value.json.return_value = {
        "models": [{"name": "llama3.2:latest"}, {"name": "qwen3:latest"}]
    }
    mock_get.return_value.raise_for_status.return_value = None

    response = notes_client.get("/api/ollama/status")

    assert response.status_code == 200
    result = response.get_json()
    assert result["status"] == "ready"
    assert result["model"] == "llama3.2"
    assert result["available_models"] == ["llama3.2:latest", "qwen3:latest"]
    assert result["message"] == "Model available in Ollama."


@patch("main.blueprints.Integrations.Ollama.routes.requests.get")
def test_integration_settings_page_lists_models_and_saved_keys(mock_get, notes_client):
    with notes_client.application.app_context():
        notes_client.application.config["OLLAMA_BASE_URL"] = "https://ollama.com"

    notes_client.post(
        "/Rover/Design/API-Keys",
        json={
            "name": "Cloud Ollama",
            "type": "ollama",
            "api_key": "cloud-api-secret",
        },
    )
    mock_get.return_value.json.return_value = {"models": [{"name": "qwen3:latest"}]}
    mock_get.return_value.raise_for_status.return_value = None

    response = notes_client.get("/api/ollama/settings")

    assert response.status_code == 200
    assert b"Current AI model" in response.data
    assert b"qwen3:latest" in response.data
    assert b"Cloud Ollama" in response.data
    assert b"required" in response.data
    assert mock_get.call_args.args[0] == "https://ollama.com/api/tags"
    assert mock_get.call_args.kwargs["headers"]["Authorization"] == (
        "Bearer cloud-api-secret"
    )
    assert b"Integrations" in notes_client.get("/Rover/Settings").data


@patch("main.blueprints.Integrations.Ollama.routes.requests.get")
def test_rover_ai_api_key_loader_selects_key_and_lists_safe_labels(
    mock_get,
    notes_client,
):
    with notes_client.application.app_context():
        notes_client.application.config["OLLAMA_BASE_URL"] = "https://ollama.com"

    saved_key = notes_client.post(
        "/Rover/Design/API-Keys",
        json={
            "name": "Work Ollama",
            "type": "ollama",
            "api_key": "private-work-key",
        },
    ).get_json()["api_key"]
    second_key = notes_client.post(
        "/Rover/Design/API-Keys",
        json={
            "name": "Personal Ollama",
            "type": "ollama",
            "api_key": "private-personal-key",
        },
    ).get_json()["api_key"]
    key_list = notes_client.get("/api/ollama/keys").get_json()
    assert key_list["active_api_key_id"] == second_key["id"]
    assert {key["name"]: key["id"] for key in key_list["keys"]} == {
        "Work Ollama": saved_key["id"],
        "Personal Ollama": second_key["id"],
    }
    with notes_client.application.app_context():
        account = Accounts.query.filter_by(email="route-notes@example.com").one()
        account.active_ollama_api_key_id = None
        account.ollama_model = "removed-model"
        db.session.commit()

    key_list = notes_client.get("/api/ollama/keys")
    assert key_list.status_code == 200
    assert key_list.get_json()["active_api_key_id"] is None
    assert b"private-work-key" not in key_list.data
    assert b"private-personal-key" not in key_list.data

    mock_get.return_value.json.return_value = {
        "models": [{"name": "qwen3:latest"}, {"name": "llama3.2"}]
    }
    mock_get.return_value.raise_for_status.return_value = None
    loaded = notes_client.post(
        "/api/ollama/key",
        json={"api_key_id": saved_key["id"]},
    )

    assert loaded.status_code == 200
    assert loaded.get_json() == {
        "model": "qwen3:latest",
        "available_models": ["qwen3:latest", "llama3.2"],
        "api_key_id": saved_key["id"],
        "api_key_name": "Work Ollama",
    }
    assert (
        notes_client.get("/api/ollama/keys").get_json()["active_api_key_id"]
        == saved_key["id"]
    )
    with notes_client.application.app_context():
        account = Accounts.query.filter_by(email="route-notes@example.com").one()
        assert account.active_ollama_api_key_id == saved_key["id"]
        assert account.ollama_model == "qwen3:latest"


@pytest.mark.parametrize(
    ("current_model", "models", "expected_model"),
    [
        ("removed-model", ["other-model", "gemma4:31b"], "gemma4:31b"),
        ("other-model", ["other-model", "gemma4:31b"], "other-model"),
        ("other-model", ["other-model:latest", "gemma4:31b"], "other-model:latest"),
        ("removed-model", ["other-model"], "other-model"),
    ],
)
@patch("main.blueprints.Integrations.Ollama.routes.requests.get")
def test_loading_ollama_key_selects_available_recommended_model(
    mock_get, notes_client, current_model, models, expected_model
):
    with notes_client.application.app_context():
        notes_client.application.config["OLLAMA_BASE_URL"] = "https://ollama.com"
        account = Accounts.query.filter_by(email="route-notes@example.com").one()
        account.ollama_model = current_model
        chatbot = Chatbot(
            user_id=account.user_id, chatbot_name="Rover AI", model_name=current_model
        )
        db.session.add(chatbot)
        db.session.commit()

    key_id = notes_client.post(
        "/Rover/Design/API-Keys",
        json={"name": "Cloud", "type": "ollama", "api_key": "test-key"},
    ).get_json()["api_key"]["id"]
    mock_get.return_value.json.return_value = {
        "models": [{"name": name} for name in models]
    }

    response = notes_client.post("/api/ollama/key", json={"api_key_id": key_id})

    assert response.status_code == 200
    assert response.get_json()["model"] == expected_model
    with notes_client.application.app_context():
        account = Accounts.query.filter_by(email="route-notes@example.com").one()
        assert account.ollama_model == expected_model
        chatbot = Chatbot.query.filter_by(user_id=account.user_id).one()
        assert chatbot.model_name == expected_model


@patch("main.blueprints.Integrations.Ollama.routes.requests.get")
def test_ollama_key_can_be_deactivated_without_contacting_ollama(mock_get, notes_client):
    with notes_client.application.app_context():
        notes_client.application.config["OLLAMA_BASE_URL"] = "https://ollama.com"

    saved = notes_client.post(
        "/Rover/Design/API-Keys",
        json={"name": "Work", "type": "ollama", "api_key": "test-key"},
    )
    assert saved.status_code == 201
    key_id = saved.get_json()["api_key"]["id"]

    assert notes_client.post("/api/ollama/key", json={}).status_code == 400
    with notes_client.application.app_context():
        account = Accounts.query.filter_by(email="route-notes@example.com").one()
        assert account.active_ollama_api_key_id == key_id
    response = notes_client.post("/api/ollama/key", json={"api_key_id": None})

    assert response.status_code == 200
    assert response.get_json()["api_key_id"] is None
    mock_get.assert_not_called()
    with notes_client.application.app_context():
        account = Accounts.query.filter_by(email="route-notes@example.com").one()
        assert account.active_ollama_api_key_id is None


@patch("main.blueprints.Integrations.Ollama.routes.requests.get")
def test_ollama_model_preference_is_per_user_and_checks_availability(
    mock_get, notes_client
):
    mock_get.return_value.json.return_value = {"models": [{"name": "qwen3:latest"}]}
    mock_get.return_value.raise_for_status.return_value = None

    unavailable = notes_client.post(
        "/api/ollama/preferences",
        json={"model": "not-installed", "api_key_id": None},
    )
    assert unavailable.status_code == 400

    saved = notes_client.post(
        "/api/ollama/preferences",
        json={"model": "qwen3:latest", "api_key_id": None},
    )
    assert saved.status_code == 200
    assert saved.get_json()["model"] == "qwen3:latest"

    with notes_client.application.app_context():
        account = Accounts.query.filter_by(email="route-notes@example.com").one()
        assert account.ollama_model == "qwen3:latest"
        assert account.active_ollama_api_key_id is None


@patch("main.blueprints.Integrations.Ollama.routes.requests.post")
def test_ollama_chat_uses_selected_model_and_decrypted_user_key(
    mock_post, notes_client
):
    with notes_client.application.app_context():
        notes_client.application.config["OLLAMA_BASE_URL"] = "https://ollama.com"

    key_response = notes_client.post(
        "/Rover/Design/API-Keys",
        json={
            "name": "Ollama Cloud",
            "type": "ollama",
            "api_key": "test-provider-secret",
        },
    )
    assert key_response.status_code == 201

    with notes_client.application.app_context():
        account = Accounts.query.filter_by(email="route-notes@example.com").one()
        account.ollama_model = "qwen3:latest"
        db.session.commit()
    session_response = notes_client.get("/api/ollama/session")
    assert session_response.status_code == 200

    mock_post.return_value.iter_lines.return_value = iter(
        [
            b'{"message":{"content":"Hello "}}',
            b'{"message":{"content":"from Ollama"}}',
            b'{"done":true}',
        ]
    )
    mock_post.return_value.raise_for_status.return_value = None

    response = notes_client.post(
        "/api/ollama/chat",
        json={"message": "Hello"},
    )

    assert response.status_code == 200
    events = [json.loads(line) for line in response.get_data(as_text=True).splitlines()]
    assert events == [
        {"token": "Hello "},
        {"token": "from Ollama"},
        {"done": True, "message": "Hello from Ollama"},
    ]
    assert response.mimetype == "application/x-ndjson"
    assert mock_post.call_args.kwargs["json"]["model"] == "qwen3:latest"
    assert mock_post.call_args.kwargs["json"]["stream"] is True
    assert mock_post.call_args.kwargs["stream"] is True
    assert mock_post.call_args.args[0] == "https://ollama.com/api/chat"
    assert mock_post.call_args.kwargs["headers"]["Authorization"] == (
        "Bearer test-provider-secret"
    )


@patch("main.services.gemini_service.requests.post")
@patch("main.services.gemini_service.requests.get")
def test_gemini_key_activation_chat_files_and_switch_back(mock_get, mock_post, notes_client):
    mock_get.return_value.status_code = 200
    mock_get.return_value.json.return_value = {
        "models": [
            {"name": "models/gemini-test-flash", "supportedGenerationMethods": ["generateContent"]},
            {"name": "models/embedding-test", "supportedGenerationMethods": ["embedContent"]},
        ]
    }
    mock_post.return_value.status_code = 200
    mock_post.return_value.json.return_value = {
        "candidates": [{"content": {"parts": [{"text": "Gemini reply"}]}, "finishReason": "STOP"}]
    }
    saved = notes_client.post(
        "/Rover/Design/API-Keys",
        json={"name": "Google", "type": "gemini", "api_key": "test-gemini-secret"},
    )
    assert saved.status_code == 201
    key_id = saved.get_json()["api_key"]["id"]
    with notes_client.application.app_context():
        account = Accounts.query.filter_by(email="route-notes@example.com").one()
        key = db.session.get(UserApiKey, key_id)
        assert account.rover_ai_provider == "ollama"
        assert account.active_ollama_api_key_id is None
        assert b"test-gemini-secret" not in key.key_ciphertext
    selected = notes_client.post("/api/ollama/gemini/preferences", json={"api_key_id": key_id})
    assert selected.status_code == 200
    assert selected.get_json()["model"] == "gemini-test-flash"
    assert selected.get_json()["available_models"] == ["gemini-test-flash"]
    assert notes_client.get("/api/ollama/session").get_json()["provider"] == "gemini"
    assert notes_client.get("/api/ollama/status").get_json()["message"] == "Model available in Gemini."
    saved_file = notes_client.post(
        "/api/ollama/chatbot/files", json={"name": "notes.txt", "content": "private text"}
    ).get_json()["file"]["id"]
    response = notes_client.post(
        "/api/ollama/chat", json={"message": "Summarize", "file_ids": [saved_file]}
    )
    assert response.status_code == 200
    assert [json.loads(line) for line in response.get_data(as_text=True).splitlines()] == [
        {"token": "Gemini reply"}, {"done": True, "message": "Gemini reply"}
    ]
    assert mock_get.call_args.args[0] == "https://generativelanguage.googleapis.com/v1beta/models"
    assert mock_post.call_args.args[0] == (
        "https://generativelanguage.googleapis.com/v1beta/models/gemini-test-flash:generateContent"
    )
    assert mock_post.call_args.kwargs["headers"]["x-goog-api-key"] == "test-gemini-secret"
    assert mock_post.call_args.kwargs["allow_redirects"] is False
    contents = mock_post.call_args.kwargs["json"]["contents"]
    assert contents == [{"role": "user", "parts": [{"text": "Summarize\n\n[Attached file: notes.txt]\nprivate text"}]}]
    response = notes_client.post("/api/ollama/chat", json={"message": "Follow up"})
    assert response.status_code == 200
    contents = mock_post.call_args.kwargs["json"]["contents"]
    assert [item["role"] for item in contents] == ["user", "model", "user"]
    assert contents[0]["parts"][0]["text"] == "Summarize"
    assert notes_client.post("/api/ollama/gemini/preferences", json={"provider": "ollama"}).status_code == 200
    assert notes_client.get("/api/ollama/session").get_json()["provider"] == "ollama"
    with notes_client.application.app_context():
        assert ChatbotMessage.query.count() == 4
        assert Accounts.query.filter_by(email="route-notes@example.com").one().ollama_model is None


@patch("main.services.gemini_service.available_models")
@patch("main.blueprints.Integrations.Ollama.routes._available_models")
@patch("main.services.gemini_service.generate_content", return_value="Chooser reply")
def test_model_chooser_selects_saved_gemini_key_without_prior_activation(
    mock_generate, mock_ollama_models, mock_gemini_models, notes_client
):
    mock_gemini_models.return_value = ["gemini-test"]
    mock_ollama_models.return_value = ["local-model"]
    with notes_client.application.app_context():
        account = Accounts.query.filter_by(email="route-notes@example.com").one()
        account.rover_ai_provider = "unselected"
        db.session.commit()
    key_id = notes_client.post(
        "/Rover/Design/API-Keys",
        json={"name": "Gemini", "type": "gemini", "api_key": "test-key"},
    ).get_json()["api_key"]["id"]
    session = notes_client.get("/api/ollama/session").get_json()
    assert session["provider"] == "unselected"
    assert session["model"] is None
    status = notes_client.get("/api/ollama/status").get_json()
    assert status["status"] == "unconfigured"
    assert notes_client.post("/api/ollama/chat", json={"message": "Hello"}).status_code == 409
    assert notes_client.post(
        "/api/ollama/chatbot/settings", json={"name": "Rover", "model": "local-model"}
    ).status_code == 409
    mock_ollama_models.assert_not_called()
    mock_gemini_models.assert_not_called()
    sources = notes_client.get("/api/ollama/model-sources").get_json()["sources"]
    assert sources == [
        {"provider": "ollama", "key_id": None, "name": "Configured endpoint", "active": False},
        {"provider": "gemini", "key_id": key_id, "name": "Gemini", "active": False},
    ]
    assert notes_client.get(f"/api/ollama/model-sources/gemini/{key_id}/models").get_json() == {
        "models": ["gemini-test"]
    }
    assert notes_client.get("/api/ollama/model-sources/ollama/local/models").get_json() == {
        "models": ["local-model"]
    }
    assert notes_client.get(f"/api/ollama/model-sources/ollama/{key_id}/models").status_code == 404
    selected = notes_client.post(
        "/api/ollama/gemini/preferences", json={"api_key_id": key_id, "model": "gemini-test"}
    )
    assert selected.status_code == 200
    assert notes_client.get("/api/ollama/session").get_json()["model"] == "gemini-test"
    response = notes_client.post("/api/ollama/chat", json={"message": "Hello"})
    assert response.status_code == 200
    assert json.loads(response.get_data(as_text=True).splitlines()[-1])["message"] == "Chooser reply"
    assert mock_generate.call_args.args[1] == "gemini-test"
    sources = notes_client.get("/api/ollama/model-sources").get_json()["sources"]
    assert sources[1]["active"] is True
    rejected = notes_client.post(
        "/api/ollama/preferences", json={"api_key_id": None, "model": "not-available"}
    )
    assert rejected.status_code == 400
    assert notes_client.get("/api/ollama/session").get_json()["provider"] == "gemini"
    selected = notes_client.post(
        "/api/ollama/preferences", json={"api_key_id": None, "model": "local-model"}
    )
    assert selected.status_code == 200
    assert notes_client.get("/api/ollama/session").get_json()["provider"] == "ollama"


@patch("main.services.gemini_service.available_models")
def test_model_chooser_rejects_foreign_sources_and_reports_provider_errors(
    mock_gemini_models, notes_client
):
    with notes_client.application.app_context():
        other = Accounts(
            email="chooser-foreign@example.com", username="ChooserForeign",
            password="hash", country_of_origin="United States",
        )
        db.session.add(other)
        db.session.flush()
        foreign = UserApiKey(
            user_id=other.user_id, key_name="Other", key_type="gemini",
            key_hash="hash", key_ciphertext=b"cipher",
            created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc),
        )
        db.session.add(foreign)
        db.session.commit()
        foreign_id = foreign.api_key_id
    assert notes_client.get(f"/api/ollama/model-sources/gemini/{foreign_id}/models").status_code == 404
    assert notes_client.get("/api/ollama/model-sources/gemini/local/models").status_code == 404
    assert notes_client.get("/api/ollama/model-sources/gemini/" + "9" * 100 + "/models").status_code == 404
    assert notes_client.get("/api/ollama/model-sources/groq/1/models").status_code == 404
    mock_gemini_models.assert_not_called()
    key_id = notes_client.post(
        "/Rover/Design/API-Keys", json={"name": "Mine", "type": "gemini", "api_key": "secret"}
    ).get_json()["api_key"]["id"]
    mock_gemini_models.side_effect = requests.Timeout()
    response = notes_client.get(f"/api/ollama/model-sources/gemini/{key_id}/models")
    assert response.status_code == 504
    assert "too long" in response.get_json()["error"]


@patch("main.blueprints.Integrations.Ollama.routes._available_models", return_value=["cloud-model"])
def test_model_chooser_cloud_sources_are_owned_and_identify_active_key(mock_models, notes_client):
    notes_client.application.config["OLLAMA_BASE_URL"] = "https://ollama.com"
    first = notes_client.post(
        "/Rover/Design/API-Keys", json={"name": "First", "type": "ollama", "api_key": "secret-1"}
    ).get_json()["api_key"]["id"]
    second = notes_client.post(
        "/Rover/Design/API-Keys", json={"name": "Second", "type": "ollama", "api_key": "secret-2"}
    ).get_json()["api_key"]["id"]
    assert notes_client.post(
        "/api/ollama/preferences", json={"api_key_id": first, "model": "cloud-model"}
    ).status_code == 200
    sources = notes_client.get("/api/ollama/model-sources").get_json()["sources"]
    assert {source["key_id"]: source["active"] for source in sources} == {first: True, second: False}
    assert b"secret" not in notes_client.get("/api/ollama/model-sources").data
    assert notes_client.get(f"/api/ollama/model-sources/ollama/{second}/models").get_json() == {
        "models": ["cloud-model"]
    }
    assert mock_models.call_args.args[0]["Authorization"] == "Bearer secret-2"
    assert notes_client.get("/api/ollama/model-sources/ollama/local/models").status_code == 404


@patch("main.blueprints.Integrations.Ollama.routes.requests.get")
def test_model_chooser_reports_malformed_ollama_model_list(mock_get, notes_client):
    mock_get.return_value.json.return_value = {"models": "invalid"}
    response = notes_client.get("/api/ollama/model-sources/ollama/local/models")
    assert response.status_code == 502
    assert "invalid model list" in response.get_json()["error"]


def test_new_account_defaults_to_unselected(notes_client):
    with notes_client.application.app_context():
        account = Accounts(
            email="new-chooser@example.com", username="NewChooser",
            password="hash", country_of_origin="United States",
        )
        db.session.add(account)
        db.session.flush()
        assert account.rover_ai_provider == "unselected"


@patch("main.services.gemini_service.requests.get")
def test_gemini_activation_rejects_wrong_keys_and_failed_model_lookup(mock_get, notes_client):
    ollama_key = notes_client.post(
        "/Rover/Design/API-Keys", json={"name": "Other", "type": "ollama", "api_key": "ollama-secret"}
    ).get_json()["api_key"]["id"]
    response = notes_client.post("/api/ollama/gemini/preferences", json={"api_key_id": ollama_key})
    assert response.status_code == 503
    mock_get.assert_not_called()
    gemini_key = notes_client.post(
        "/Rover/Design/API-Keys", json={"name": "Gemini", "type": "gemini", "api_key": "secret"}
    ).get_json()["api_key"]["id"]
    mock_get.return_value.status_code = 403
    upstream = requests.Response()
    upstream.status_code = 403
    mock_get.return_value.raise_for_status.side_effect = requests.HTTPError(response=upstream)
    response = notes_client.post("/api/ollama/gemini/preferences", json={"api_key_id": gemini_key})
    assert response.status_code == 502
    assert "Gemini rejected" in response.get_json()["error"]
    with notes_client.application.app_context():
        assert Accounts.query.filter_by(email="route-notes@example.com").one().rover_ai_provider == "ollama"


@patch("main.services.gemini_service.requests.post")
@patch("main.services.gemini_service.requests.get")
def test_gemini_rejected_reply_does_not_save_history(mock_get, mock_post, notes_client):
    mock_get.return_value.status_code = 200
    mock_get.return_value.json.return_value = {
        "models": [{"name": "models/gemini-test", "supportedGenerationMethods": ["generateContent"]}]
    }
    key_id = notes_client.post(
        "/Rover/Design/API-Keys", json={"name": "Gemini", "type": "gemini", "api_key": "secret"}
    ).get_json()["api_key"]["id"]
    notes_client.post("/api/ollama/gemini/preferences", json={"api_key_id": key_id})
    notes_client.get("/api/ollama/session")
    mock_post.return_value.status_code = 200
    mock_post.return_value.json.return_value = {"candidates": [{"finishReason": "SAFETY"}]}
    response = notes_client.post("/api/ollama/chat", json={"message": "Hello"})
    assert response.status_code == 503
    assert response.get_json()["error"] == "Gemini could not complete the response."
    with notes_client.application.app_context():
        assert ChatbotMessage.query.count() == 0


@patch("main.services.gemini_service.requests.get")
def test_gemini_rejects_foreign_key_and_invalid_model_without_switching(mock_get, notes_client):
    with notes_client.application.app_context():
        other = Accounts(
            email="other-gemini@example.com", username="OtherGemini",
            password="hashed", country_of_origin="United States",
        )
        db.session.add(other)
        db.session.flush()
        foreign = UserApiKey(
            user_id=other.user_id, key_name="Foreign", key_type="gemini",
            key_hash="hash", key_ciphertext=b"foreign",
            created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc),
        )
        db.session.add(foreign)
        db.session.commit()
        foreign_id = foreign.api_key_id
    response = notes_client.post("/api/ollama/gemini/preferences", json={"api_key_id": foreign_id})
    assert response.status_code == 503
    mock_get.assert_not_called()
    key_id = notes_client.post(
        "/Rover/Design/API-Keys", json={"name": "Mine", "type": "gemini", "api_key": "secret"}
    ).get_json()["api_key"]["id"]
    response = notes_client.post(
        "/api/ollama/gemini/preferences", json={"api_key_id": key_id, "model": "../malicious"}
    )
    assert response.status_code == 400
    mock_get.assert_not_called()
    with notes_client.application.app_context():
        assert Accounts.query.filter_by(email="route-notes@example.com").one().rover_ai_provider == "ollama"


@patch("main.blueprints.Integrations.Ollama.routes._available_models")
@patch("main.services.gemini_service.available_models")
def test_switching_from_gemini_to_ollama_preserves_ollama_model(
    mock_gemini_models, mock_ollama_models, notes_client
):
    mock_gemini_models.return_value = ["gemini-test"]
    mock_ollama_models.return_value = ["first:latest", "saved:latest"]
    ollama_key = notes_client.post(
        "/Rover/Design/API-Keys", json={"name": "Local", "type": "ollama", "api_key": "secret"}
    ).get_json()["api_key"]["id"]
    gemini_key = notes_client.post(
        "/Rover/Design/API-Keys", json={"name": "Google", "type": "gemini", "api_key": "secret"}
    ).get_json()["api_key"]["id"]
    with notes_client.application.app_context():
        account = Accounts.query.filter_by(email="route-notes@example.com").one()
        account.ollama_model = "saved:latest"
        db.session.commit()
    notes_client.get("/api/ollama/session")
    notes_client.post("/api/ollama/gemini/preferences", json={"api_key_id": gemini_key})
    response = notes_client.post("/api/ollama/key", json={"api_key_id": ollama_key})
    assert response.status_code == 200
    assert response.get_json()["model"] == "saved:latest"
    assert notes_client.get("/api/ollama/session").get_json()["provider"] == "ollama"


@patch("main.blueprints.Integrations.Ollama.routes.requests.post")
def test_ollama_cloud_payment_error_explains_billing_without_exposing_details(
    mock_post, notes_client
):
    with notes_client.application.app_context():
        notes_client.application.config["OLLAMA_BASE_URL"] = "https://ollama.com"
    notes_client.post(
        "/Rover/Design/API-Keys",
        json={"name": "Cloud", "type": "ollama", "api_key": "test-provider-secret"},
    )
    notes_client.get("/api/ollama/session")
    upstream = requests.Response()
    upstream.status_code = 402
    upstream._content = b"private provider details"
    mock_post.return_value.raise_for_status.side_effect = requests.HTTPError(
        response=upstream
    )

    response = notes_client.post("/api/ollama/chat", json={"message": "Hello"})

    assert response.status_code == 402
    assert response.get_json()["error"] == (
        "Ollama Cloud requires payment or available usage credits. "
        "Check your Ollama account billing and usage."
    )
    assert b"private provider details" not in response.data
    mock_post.return_value.close.assert_called_once()
    with notes_client.application.app_context():
        assert ChatbotMessage.query.count() == 0


@pytest.mark.parametrize("status_code", [402, 500])
@patch("main.blueprints.Integrations.Ollama.routes.requests.post")
def test_ollama_local_provider_error_remains_generic(
    mock_post, notes_client, status_code
):
    notes_client.get("/api/ollama/session")
    upstream = requests.Response()
    upstream.status_code = status_code
    mock_post.return_value.raise_for_status.side_effect = requests.HTTPError(
        response=upstream
    )

    response = notes_client.post("/api/ollama/chat", json={"message": "Hello"})

    assert response.status_code == 502
    assert response.get_json()["error"] == "Ollama could not complete the request."
    mock_post.return_value.close.assert_called_once()


@pytest.mark.parametrize(
    ("last_event", "error"),
    [
        (b'{"error":"private provider details"}', "Ollama could not complete the request."),
        (None, "Ollama ended the response before it was complete."),
    ],
)
@patch("main.blueprints.Integrations.Ollama.routes.requests.post")
def test_ollama_failed_stream_does_not_save_partial_chat(
    mock_post, notes_client, last_event, error
):
    notes_client.get("/api/ollama/session")
    lines = [b'{"message":{"content":"partial"}}']
    if last_event is not None:
        lines.append(last_event)
    mock_post.return_value.iter_lines.return_value = iter(lines)
    mock_post.return_value.raise_for_status.return_value = None

    response = notes_client.post("/api/ollama/chat", json={"message": "Hello"})

    events = [json.loads(line) for line in response.get_data(as_text=True).splitlines()]
    assert events == [
        {"token": "partial"},
        {"error": error},
    ]
    mock_post.return_value.close.assert_called_once()
    with notes_client.application.app_context():
        assert ChatbotMessage.query.count() == 0


@patch("main.blueprints.Integrations.Ollama.routes.requests.post")
def test_ollama_local_does_not_send_saved_key(mock_post, notes_client):
    notes_client.post(
        "/Rover/Design/API-Keys",
        json={
            "name": "Saved Ollama key",
            "type": "ollama",
            "api_key": "must-not-leak-to-local",
        },
    )
    mock_post.return_value.iter_lines.return_value = iter(
        [
            b'{"message":{"content":"Local response"}}',
            b'{"done":true}',
        ]
    )
    mock_post.return_value.raise_for_status.return_value = None
    assert notes_client.get("/api/ollama/session").status_code == 200

    response = notes_client.post(
        "/api/ollama/chat",
        json={"message": "Hello"},
    )

    assert response.status_code == 200
    events = [json.loads(line) for line in response.get_data(as_text=True).splitlines()]
    assert events[-1]["message"] == "Local response"
    assert mock_post.call_args.kwargs["headers"] == {}
    assert mock_post.call_args.args[0] == "http://ollama.test/api/chat"


@patch("main.blueprints.Integrations.Ollama.routes.requests.get")
def test_ollama_cloud_requires_api_key(mock_get, notes_client):
    with notes_client.application.app_context():
        notes_client.application.config["OLLAMA_BASE_URL"] = "https://ollama.com"

    response = notes_client.get("/api/ollama/status")

    assert response.status_code == 401
    assert response.get_json()["status"] == "authentication_required"
    mock_get.assert_not_called()


def test_ollama_chat_requires_session_and_rejects_long_message(notes_client):
    no_session = notes_client.post(
        "/api/ollama/chat",
        json={"message": "hello"},
    )
    assert no_session.status_code == 409

    invalid_message = notes_client.post(
        "/api/ollama/chat",
        json={"message": "x" * 20_001},
    )
    assert invalid_message.status_code == 400


@patch("main.blueprints.Integrations.Ollama.routes.requests.post")
def test_chatbot_files_are_encrypted_and_sent_only_when_selected(mock_post, notes_client):
    saved = notes_client.post(
        "/api/ollama/chatbot/files",
        json={"name": "private-notes.txt", "content": "private file contents"},
    )
    assert saved.status_code == 201
    file_id = saved.get_json()["file"]["id"]
    with notes_client.application.app_context():
        stored = db.session.get(ChatbotFile, file_id)
        assert b"private file contents" not in stored.ciphertext
        assert b"private-notes.txt" not in stored.ciphertext

    listed = notes_client.get("/api/ollama/chatbot/files")
    assert listed.get_json() == {
        "files": [{"id": file_id, "name": "private-notes.txt"}]
    }
    assert "no-store" in listed.headers["Cache-Control"]
    assert b"private file contents" not in listed.data
    assert notes_client.get("/api/ollama/session").status_code == 200
    mock_post.return_value.iter_lines.return_value = iter(
        [b'{"message":{"content":"Response"}}', b'{"done":true}']
    )
    response = notes_client.post(
        "/api/ollama/chat", json={"message": "Summarize", "file_ids": [file_id]}
    )
    assert response.status_code == 200
    response.get_data()
    message = mock_post.call_args.kwargs["json"]["messages"][-1]["content"]
    assert "private file contents" in message
    with notes_client.application.app_context():
        user_message = ChatbotMessage.query.filter_by(role="user").one()
        assert user_message.content == "Summarize"

    assert notes_client.post("/api/ollama/session/end", json={}).status_code == 200
    assert len(notes_client.get("/api/ollama/chatbot/files").get_json()["files"]) == 1
    assert notes_client.delete(f"/api/ollama/chatbot/files/{file_id}").status_code == 200
    assert notes_client.get("/api/ollama/chatbot/files").get_json()["files"] == []


def test_chatbot_files_reject_invalid_or_foreign_content(notes_client):
    for payload in [
        {"name": "../secret.txt", "content": "text"},
        {"name": "binary", "content": "text\u0000binary"},
        {"name": "large.txt", "content": "x" * (64 * 1024 + 1)},
    ]:
        assert notes_client.post(
            "/api/ollama/chatbot/files", json=payload
        ).status_code in (400, 413)

    with notes_client.application.app_context():
        other = Accounts(
            email="other-file-owner@example.com",
            username="OtherFileOwner",
            password="hashed-password",
            country_of_origin="United States",
        )
        db.session.add(other)
        db.session.flush()
        foreign_id = "00000000-0000-4000-8000-000000000001"
        db.session.add(
            ChatbotFile(file_id=foreign_id, user_id=other.user_id, ciphertext=b"secret")
        )
        db.session.commit()
    assert notes_client.get("/api/ollama/chatbot/files").get_json()["files"] == []
    assert notes_client.delete(f"/api/ollama/chatbot/files/{foreign_id}").status_code == 404
    notes_client.get("/api/ollama/session")
    response = notes_client.post(
        "/api/ollama/chat", json={"message": "Hello", "file_ids": [foreign_id]}
    )
    assert response.status_code == 404


@patch("main.blueprints.Integrations.Ollama.routes.requests.post")
def test_chatbot_file_selection_limits_and_decryption_errors(mock_post, notes_client):
    file_ids = []
    for index in range(3):
        response = notes_client.post(
            "/api/ollama/chatbot/files",
            json={"name": f"{index}.txt", "content": "x" * (64 * 1024)},
        )
        assert response.status_code == 201
        file_ids.append(response.get_json()["file"]["id"])

    notes_client.get("/api/ollama/session")
    too_large = notes_client.post(
        "/api/ollama/chat", json={"message": "Hello", "file_ids": file_ids}
    )
    assert too_large.status_code == 400
    duplicate = notes_client.post(
        "/api/ollama/chat",
        json={"message": "Hello", "file_ids": [file_ids[0], file_ids[0]]},
    )
    assert duplicate.status_code == 400
    mock_post.assert_not_called()

    with notes_client.application.app_context():
        db.session.get(ChatbotFile, file_ids[0]).ciphertext = b"corrupted"
        db.session.commit()
    assert notes_client.get("/api/ollama/chatbot/files").status_code == 503
    corrupt = notes_client.post(
        "/api/ollama/chat", json={"message": "Hello", "file_ids": [file_ids[0]]}
    )
    assert corrupt.status_code == 503
    mock_post.assert_not_called()


@patch("main.blueprints.Integrations.Ollama.routes.requests.post")
def test_chat_session_history_is_deleted_when_user_ends_session(
    mock_post, notes_client
):
    session_response = notes_client.get("/api/ollama/session")
    assert session_response.status_code == 200
    session_id = session_response.get_json()["session_id"]

    mock_post.return_value.iter_lines.side_effect = [
        iter([b'{"message":{"content":"Session reply"}}', b'{"done":true}']),
        iter([b'{"message":{"content":"Second reply"}}', b'{"done":true}']),
    ]
    mock_post.return_value.raise_for_status.return_value = None
    response = notes_client.post("/api/ollama/chat", json={"message": "Keep this?"})
    assert response.status_code == 200
    response.get_data(as_text=True)
    response = notes_client.post("/api/ollama/chat", json={"message": "Follow up"})
    assert response.status_code == 200
    response.get_data(as_text=True)
    assert mock_post.call_args.kwargs["json"]["messages"] == [
        {"role": "user", "content": "Keep this?"},
        {"role": "assistant", "content": "Session reply"},
        {"role": "user", "content": "Follow up"},
    ]

    history = notes_client.get("/api/ollama/session").get_json()
    assert history["session_id"] == session_id
    assert history["messages"] == [
        {"role": "user", "content": "Keep this?"},
        {"role": "assistant", "content": "Session reply"},
        {"role": "user", "content": "Follow up"},
        {"role": "assistant", "content": "Second reply"},
    ]

    ended = notes_client.post("/api/ollama/session/end", json={})
    assert ended.status_code == 200
    with notes_client.application.app_context():
        chat_session = db.session.get(ChatbotSession, session_id)
        assert chat_session.ended_at is not None
        assert ChatbotMessage.query.filter_by(session_id=session_id).count() == 0

    next_session = notes_client.get("/api/ollama/session").get_json()
    assert next_session["session_id"] != session_id
    assert next_session["messages"] == []


@patch("main.blueprints.Integrations.Ollama.routes.requests.get")
def test_chatbot_name_and_model_are_saved(mock_get, notes_client):
    mock_get.return_value.json.return_value = {"models": [{"name": "qwen3:latest"}]}
    mock_get.return_value.raise_for_status.return_value = None

    response = notes_client.post(
        "/api/ollama/chatbot/settings",
        json={"name": "Project Helper", "model": "qwen3:latest"},
    )

    assert response.status_code == 200
    assert response.get_json() == {"name": "Project Helper", "model": "qwen3:latest"}
    with notes_client.application.app_context():
        chatbot = Chatbot.query.one()
        assert chatbot.chatbot_name == "Project Helper"
        assert chatbot.model_name == "qwen3:latest"


def test_chatbot_folder_permissions_are_opt_in_and_saved(notes_client):
    defaults = notes_client.get("/api/ollama/session").get_json()["permissions"]
    assert defaults == {"read_folder": False, "write_folder": False}

    saved = notes_client.post(
        "/api/ollama/chatbot/permissions",
        json={"read_folder": True, "write_folder": True},
    )
    assert saved.status_code == 200
    assert saved.get_json() == {"read_folder": True, "write_folder": True}
    assert notes_client.get("/api/ollama/session").get_json()["permissions"] == {
        "read_folder": True,
        "write_folder": True,
    }
