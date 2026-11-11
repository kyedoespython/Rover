from pathlib import Path
from datetime import datetime, timedelta, timezone
import json
from unittest.mock import patch

import pytest
from flask import Flask

from main.blueprints.auth import auth_bp
from main.blueprints.home import home_bp
from main.blueprints.Integrations.Ollama import ollama_bp
from main.extensions import csrf, db, limiter, login_manager
from main.models.user import (
    Accounts,
    Authentication,
    Chatbot,
    ChatbotMessage,
    ChatbotSession,
    Notes,
    RoverAgent,
    RoverAgentMessage,
    RoverAgentSession,
    SchemaMetadata,
    UserApiKey,
    UserSchema,
)
from main.services.ollama_service import decrypt_api_key
from main.services.agent_history_cleanup import cleanup_expired_agent_history
from main.services.notes_service import create_note
from main.services import notes_service
from werkzeug.security import check_password_hash, generate_password_hash


@pytest.fixture
def notes_client(tmp_path):
    template_folder = Path(__file__).parent.parent / "main" / "templates"
    app = Flask(__name__, template_folder=str(template_folder))
    app.config.update(
        TESTING=True,
        SECRET_KEY="notes-test-secret",
        SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        NOTE_STORAGE_DIR=str(tmp_path / "note-files"),
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
        file_path = Path(notes_client.application.config["NOTE_STORAGE_DIR"]) / note.file_metadata.relative_path

    response = notes_client.get(f"/Rover/Notes?load_id={note_id}")
    assert response.status_code == 200
    assert b"# Route note\nInitial content" in response.data
    assert b"Save note" in response.data
    assert b'id="noteHeadingMenu"' in response.data
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


def test_notes_page_creates_default_note_and_sidebar_creates_named_notes(notes_client):
    page = notes_client.get("/Rover/Notes")
    assert page.status_code == 200
    assert b"Empty note" in page.data
    assert b"New note name" in page.data
    assert b"Your notes" in page.data
    assert b"scripts/Notes/Notes.js?v=3" in page.data
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
        created_note = Notes.query.filter_by(
            note_name="A note from the sidebar"
        ).one()
        assert created_note.note_content is None
        assert created_note.file_metadata is not None

    opened = notes_client.get(f"/Rover/Notes?load_id={default_note_id}")
    assert opened.status_code == 200
    assert b'id="noteContent"' in opened.data
    assert b"Double-click a line to add a heading." in opened.data


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

        first_user_id = Accounts.query.filter_by(
            email="route-notes@example.com"
        ).one().user_id
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
        assert decrypt_api_key(
            stored_key.key_ciphertext,
            stored_key.user_id,
            stored_key.api_key_id,
        ) == secret
        assert account.active_ollama_api_key_id == stored_key.api_key_id

    dashboard = notes_client.get("/DesignDashboard")
    assert dashboard.status_code == 200
    assert b"Local Ollama" in dashboard.data
    assert secret.encode() not in dashboard.data


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
    assert b"scripts/Integrations/Ollama.js?v=10" in response.data
    assert response.data.count(b'id="ollamaDrawer"') == 1
    assert b'class="button is-outlined design-side-button rover-ai-nav-button"' in response.data
    assert b"ollama-drawer-toggle" not in response.data
    assert response.data.index(b">Demo</button>") < response.data.index(b">Rover AI</button>")
    assert b'aria-expanded="false"' in response.data
    assert b'class="ollama-drawer is-minimized"' in response.data
    assert b"Rover AI" in response.data
    assert b'id="ollamaReadFile"' not in response.data
    assert b"Markdown file (auto-loads into your draft)" in response.data
    assert b"Verify your account to enable Rover AI chat." in response.data
    assert b"#designPage .api-key-dialog .label" in response.data
    assert b'id="ollamaChatInput"' in response.data and b" disabled required" in response.data
    assert b'id="ollamaChatbotModelSelect"' in response.data
    assert b'id="ollamaChatbotModelInput"' not in response.data
    assert b'id="ollamaApiKeySelect"' in response.data
    assert b'id="ollamaLoadApiKey"' in response.data
    assert b"scripts/Design/Schema.js?v=2" in response.data
    assert b'id="openSchemaEditor"' in response.data
    assert b'id="schemaEditorDialog"' in response.data
    assert b'data-schema-url="/api/schema"' in response.data
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
    assert empty.get_json()["schema"] == {"tables": [], "relationships": []}

    saved = notes_client.put("/api/schema", json={"schema": schema})
    assert saved.status_code == 200
    saved_metadata = saved.get_json()["metadata"]
    assert saved_metadata["table_count"] == 2
    assert saved_metadata["column_count"] == 3
    assert saved_metadata["relationship_count"] == 1
    assert saved_metadata["table_names"] == ["Accounts", "Orders"]
    assert saved_metadata["data_types"] == ["AutoNumber", "Number"]

    loaded = notes_client.get("/api/schema")
    assert loaded.status_code == 200
    assert loaded.get_json()["schema"] == schema
    with notes_client.application.app_context():
        stored_schema = UserSchema.query.one()
        stored_metadata = SchemaMetadata.query.one()
        assert stored_schema.schema_data == schema
        assert stored_metadata.table_count == 2
        assert stored_metadata.column_count == 3
        assert stored_metadata.relationship_count == 1
        assert stored_metadata.table_names == ["Accounts", "Orders"]
        assert stored_metadata.data_types == ["AutoNumber", "Number"]

    invalid = {
        **schema,
        "relationships": [
            {
                **schema["relationships"][0],
                "targetTableId": "missing-table",
            }
        ],
    }
    rejected = notes_client.put("/api/schema", json={"schema": invalid})
    assert rejected.status_code == 400
    assert notes_client.get("/api/schema").get_json()["schema"] == schema


def test_triple_rover_page_keeps_only_the_navigation_and_three_agent_slots(notes_client):
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
        assert RoverAgentMessage.query.filter_by(session_id=expired_session_id).count() == 0
        assert RoverAgent.query.count() == len(agents)


def test_settings_navigation_is_only_on_support_page(notes_client):
    support_page = notes_client.get("/Rover/Support")
    assert support_page.status_code == 200
    assert b'justify-content: space-between' in support_page.data
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
    with notes_client.application.app_context():
        account = Accounts.query.filter_by(email="route-notes@example.com").one()
        account.active_ollama_api_key_id = None
        account.ollama_model = "removed-model"
        db.session.commit()

    key_list = notes_client.get("/api/ollama/keys")
    assert key_list.status_code == 200
    assert key_list.get_json() == {
        "keys": [{"id": saved_key["id"], "name": "Work Ollama"}],
        "active_api_key_id": None,
    }
    assert b"private-work-key" not in key_list.data

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
    with notes_client.application.app_context():
        account = Accounts.query.filter_by(email="route-notes@example.com").one()
        assert account.active_ollama_api_key_id == saved_key["id"]
        assert account.ollama_model == "qwen3:latest"


@patch("main.blueprints.Integrations.Ollama.routes.requests.get")
def test_ollama_model_preference_is_per_user_and_checks_availability(mock_get, notes_client):
    mock_get.return_value.json.return_value = {
        "models": [{"name": "qwen3:latest"}]
    }
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
def test_ollama_chat_uses_selected_model_and_decrypted_user_key(mock_post, notes_client):
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
    events = [
        json.loads(line)
        for line in response.get_data(as_text=True).splitlines()
    ]
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
    events = [
        json.loads(line)
        for line in response.get_data(as_text=True).splitlines()
    ]
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
def test_chat_session_history_is_deleted_when_user_ends_session(mock_post, notes_client):
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
