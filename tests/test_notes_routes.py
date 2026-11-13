import io
import re
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import pytest
from flask import Flask
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.security import check_password_hash, generate_password_hash

from main.blueprints.auth import auth_bp
from main.blueprints.home import home_bp
from main.extensions import csrf, db, limiter, login_manager
from main.models.DBimports import (
    Accounts,
    Authentication,
    Notes,
    PasswordResetToken,
    SchemaMetadata,
    Tickets,
    UserSchemaDatabase,
    UserSchema,
)
from main.services import notes_service
from main.services.auth_service import AUTH_CODE_MAX_ATTEMPTS, Create_Auth_Code
from main.services.notes_service import create_note


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
        WTF_CSRF_ENABLED=False,
        RATELIMIT_ENABLED=False,
    )
    db.init_app(app)
    csrf.init_app(app)
    login_manager.init_app(app)
    limiter.init_app(app)
    app.register_blueprint(auth_bp)
    app.register_blueprint(home_bp)

    with app.app_context():
        db.create_all()
        account = Accounts(
            email="route-notes@example.com",
            username="RouteNotes",
            password="hashed-password",
            country_of_origin="United States",
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


def test_support_ticket_is_saved_and_duplicate_names_are_allowed(notes_client):
    payload = {"ticketType": "bug", "ticketName": " Problem ", "TicketContent": " Details "}
    first = notes_client.post("/Tickets/Rover", data=payload, follow_redirects=True)
    second = notes_client.post("/Tickets/Rover", data=payload, follow_redirects=True)
    assert first.status_code == second.status_code == 200
    assert b"Ticket #1 submitted." in first.data
    assert b"Ticket #2 submitted." in second.data
    with notes_client.application.app_context():
        account = Accounts.query.filter_by(email="route-notes@example.com").one()
        tickets = Tickets.query.order_by(Tickets.ticket_id).all()
        assert [(item.user_id, item.ticket_type, item.ticket_name, item.ticket_content) for item in tickets] == [
            (account.user_id, "bug", "Problem", "Details"),
            (account.user_id, "bug", "Problem", "Details"),
        ]


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"ticketType": "other", "ticketName": "Name", "TicketContent": "Description"},
        {"ticketType": "bug", "ticketName": " " * 2, "TicketContent": "Description"},
        {"ticketType": "bug", "ticketName": "x" * 65, "TicketContent": "Description"},
        {"ticketType": "bug", "ticketName": "Name", "TicketContent": "x" * 513},
    ],
)
def test_support_ticket_rejects_invalid_input(notes_client, payload):
    response = notes_client.post("/Tickets/Rover", data=payload)
    assert response.status_code == 400
    with notes_client.application.app_context():
        assert Tickets.query.count() == 0


def test_support_ticket_database_failure_preserves_form(notes_client):
    payload = {"ticketType": "question", "ticketName": "Help", "TicketContent": "My description"}
    with patch.object(db.session, "commit", side_effect=SQLAlchemyError("test failure")):
        response = notes_client.post("/Tickets/Rover", data=payload)
    assert response.status_code == 503
    assert b"Your ticket could not be saved" in response.data
    assert b'value="Help"' in response.data
    assert b"My description</textarea>" in response.data
    with notes_client.application.app_context():
        assert Tickets.query.count() == 0


def test_support_ticket_requires_login(notes_client):
    with notes_client.session_transaction() as session:
        session.clear()
    response = notes_client.post(
        "/Tickets/Rover",
        data={"ticketType": "bug", "ticketName": "Name", "TicketContent": "Description"},
    )
    assert response.status_code in (302, 401)
    with notes_client.application.app_context():
        assert Tickets.query.count() == 0


def test_signup_fields_have_associated_labels(notes_client):
    response = notes_client.get("/Rover/Sign%20Up")
    for field in ("email", "username", "password", "telephone", "signupCountry"):
        assert f'for="{field}"'.encode() in response.data


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


def test_dashboard_and_settings_no_longer_show_assistant_controls(notes_client):
    dashboard = notes_client.get("/DesignDashboard")
    assert dashboard.status_code == 200
    assert b'id="openSchemaEditor"' in dashboard.data
    assert b'id="openSchemaDemo"' in dashboard.data
    assert b'<form id="schemaCreateForm" class="schema-create-form">\n                    <input type="hidden" name="csrf_token"' in dashboard.data
    assert b'ollamaDrawer' not in dashboard.data
    assert b'openApiKeyDialog' not in dashboard.data
    assert b"Rover AI" not in dashboard.data

    settings = notes_client.get("/Rover/Settings")
    assert settings.status_code == 200
    assert b"No settings are available yet." in settings.data
    assert b"Saved API keys" not in settings.data


def test_schema_form_provides_its_own_valid_csrf_token(notes_client):
    notes_client.application.config["WTF_CSRF_ENABLED"] = True
    dashboard = notes_client.get("/DesignDashboard")
    form = re.search(rb'<form id="schemaCreateForm".*?</form>', dashboard.data, re.DOTALL)
    assert form is not None
    token = re.search(rb'name="csrf_token" value="([^"]+)"', form.group())
    assert token is not None
    payload = {"name": "Token test", "schema": {"tables": [], "relationships": []}}
    assert notes_client.post("/api/schema", json=payload).status_code == 400
    response = notes_client.post(
        "/api/schema",
        json=payload,
        headers={"X-CSRFToken": token.group(1).decode()},
    )
    assert response.status_code == 201


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


def test_settings_navigation_is_only_on_support_page(notes_client):
    support_page = notes_client.get("/Rover/Support")
    assert support_page.status_code == 200
    assert b"justify-content: space-between" in support_page.data
    assert b'href="/Rover/Settings"' in support_page.data

    notes_page = notes_client.get("/Rover/Notes")
    assert notes_page.status_code == 200
    assert b'href="/Rover/Settings"' not in notes_page.data
