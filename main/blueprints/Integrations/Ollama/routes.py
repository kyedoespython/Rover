from datetime import datetime, timezone
import json
from math import isfinite
from urllib.parse import urlsplit
from uuid import uuid4

import requests
from flask import (
    Response,
    current_app,
    jsonify,
    render_template,
    request,
    session,
    stream_with_context,
)
from flask_login import current_user, login_required
from sqlalchemy.exc import SQLAlchemyError

from main.extensions import db, limiter
from main.models.user import (
    Chatbot,
    ChatbotMessage,
    ChatbotMetadata,
    ChatbotSession,
    RoverAgent,
    RoverAgentMessage,
    RoverAgentMetadata,
    RoverAgentSession,
    UserApiKey,
)
from main.services.ollama_service import decrypt_api_key

from . import ollama_bp


class OllamaAuthenticationError(RuntimeError):
    pass


CHAT_SESSION_KEY = "rover_ai_session_id"
ROVER_AGENT_COUNT = 3
AGENT_HISTORY_DAYS = 7


def _account_is_verified() -> bool:
    authentication = current_user.authentication_data
    return bool(authentication and authentication.authenticated)


def _get_or_create_chatbot() -> Chatbot:
    chatbot = Chatbot.query.filter_by(user_id=current_user.user_id).first()
    if chatbot is None:
        chatbot = Chatbot(
            user_id=current_user.user_id,
            chatbot_name="Rover AI",
            model_name=(
                current_user.ollama_model
                or current_app.config["OLLAMA_MODEL"]
            ),
        )
        db.session.add(chatbot)
        db.session.flush()
    if chatbot.configuration is None:
        chatbot.configuration = ChatbotMetadata(chatbot_id=chatbot.chatbot_id)
        db.session.flush()
    return chatbot


def _current_chat_session(chatbot: Chatbot) -> ChatbotSession | None:
    session_id = session.get(CHAT_SESSION_KEY)
    if not isinstance(session_id, str):
        return None
    chat_session = ChatbotSession.query.filter_by(
        session_id=session_id,
        chatbot_id=chatbot.chatbot_id,
        ended_at=None,
    ).first()
    if chat_session is None:
        session.pop(CHAT_SESSION_KEY, None)
    return chat_session


def _is_ollama_cloud() -> bool:
    parsed_url = urlsplit(current_app.config["OLLAMA_BASE_URL"])
    return (
        parsed_url.scheme == "https"
        and parsed_url.hostname == "ollama.com"
        and parsed_url.port in (None, 443)
        and parsed_url.path.rstrip("/") in ("", "/api")
    )


def _ollama_url(path: str) -> str:
    base_url = current_app.config["OLLAMA_BASE_URL"].rstrip("/")
    if base_url.endswith("/api"):
        base_url = base_url[:-4]
    return f"{base_url}{path}"


def _selected_api_key():
    key_id = current_user.active_ollama_api_key_id
    if key_id is None:
        return None
    return UserApiKey.query.filter_by(
        api_key_id=key_id,
        user_id=current_user.user_id,
        key_type="ollama",
    ).first()


def _ollama_headers(api_key=None) -> dict[str, str]:
    if not _is_ollama_cloud():
        return {}
    if api_key is None:
        raise OllamaAuthenticationError(
            "Ollama Cloud requires a saved API key. Add one in the design dashboard."
        )
    if not api_key.key_ciphertext:
        raise OllamaAuthenticationError(
            "The selected API key must be saved again before it can be used."
        )
    secret = decrypt_api_key(
        api_key.key_ciphertext,
        api_key.user_id,
        api_key.api_key_id,
    )
    return {"Authorization": f"Bearer {secret}"}


def _available_models(headers: dict[str, str]) -> list[str]:
    response = requests.get(
        _ollama_url("/api/tags"),
        headers=headers,
        timeout=(3, 5),
    )
    response.raise_for_status()
    payload = response.json()
    models = payload.get("models", []) if isinstance(payload, dict) else []
    if not isinstance(models, list):
        return []
    return [
        model["name"]
        for model in models
        if isinstance(model, dict) and isinstance(model.get("name"), str)
    ]


def _get_rover_agent(agent_id: int) -> RoverAgent | None:
    return RoverAgent.query.filter_by(
        agent_id=agent_id,
        user_id=current_user.user_id,
    ).first()


def _get_agent_session(agent: RoverAgent) -> RoverAgentSession:
    chat_session = agent.chat_session
    if chat_session is not None and chat_session.first_message_at is not None:
        first_message_at = chat_session.first_message_at
        if first_message_at.tzinfo is None:
            first_message_at = first_message_at.replace(tzinfo=timezone.utc)
        if (datetime.now(timezone.utc) - first_message_at).days >= AGENT_HISTORY_DAYS:
            agent.chat_session = None
            db.session.flush()
            chat_session = None

    if chat_session is None:
        chat_session = RoverAgentSession(session_id=str(uuid4()), agent=agent)
        db.session.add(chat_session)
        db.session.flush()
    return chat_session


def _create_rover_agent_slots() -> list[RoverAgent]:
    agents = {
        agent.slot_number: agent
        for agent in RoverAgent.query.filter_by(user_id=current_user.user_id).all()
    }
    for slot_number in range(1, ROVER_AGENT_COUNT + 1):
        if slot_number not in agents:
            agent = RoverAgent(
                user_id=current_user.user_id,
                slot_number=slot_number,
                agent_name=f"Rover Agent {slot_number}",
                model_name=current_user.ollama_model or current_app.config["OLLAMA_MODEL"],
            )
            agent.configuration = RoverAgentMetadata()
            db.session.add(agent)
            db.session.flush()
            agents[slot_number] = agent

    for agent in agents.values():
        if agent.configuration is None:
            agent.configuration = RoverAgentMetadata()
        _get_agent_session(agent)
    return [agents[slot] for slot in range(1, ROVER_AGENT_COUNT + 1)]


def _agent_history(chat_session: RoverAgentSession) -> list[dict[str, str]]:
    messages = (
        RoverAgentMessage.query.filter_by(session_id=chat_session.session_id)
        .order_by(RoverAgentMessage.message_id.desc())
        .limit(100)
        .all()
    )
    messages.reverse()
    return [{"role": message.role, "content": message.content} for message in messages]


@ollama_bp.get("/status")
@login_required
@limiter.limit("30 per minute")
def status():
    if not current_user.authentication_data or not current_user.authentication_data.authenticated:
        return jsonify(error="Verify your account to use the Ollama assistant."), 403

    chatbot = Chatbot.query.filter_by(user_id=current_user.user_id).first()
    model_name = (
        chatbot.model_name
        if chatbot
        else current_user.ollama_model or current_app.config["OLLAMA_MODEL"]
    )
    selected_key = _selected_api_key()
    api_key_name = selected_key.key_name if selected_key else None
    try:
        headers = _ollama_headers(selected_key)
        db.session.commit()
        available_models = _available_models(headers)
    except OllamaAuthenticationError as error:
        return jsonify(
            status="authentication_required",
            model=model_name,
            message=str(error),
        ), 401
    except RuntimeError as error:
        return jsonify(status="error", model=model_name, message=str(error)), 503
    except requests.HTTPError as error:
        if error.response is not None and error.response.status_code in (401, 403):
            return jsonify(
                status="authentication_error",
                model=model_name,
                message="Ollama rejected the API key. Check the saved key and try again.",
            ), 502
        return jsonify(
            status="offline",
            model=model_name,
            message="Ollama is not reachable.",
        ), 503
    except requests.RequestException:
        return jsonify(
            status="offline",
            model=model_name,
            message="Ollama is not reachable.",
        ), 503
    except ValueError:
        current_app.logger.exception("Ollama returned invalid model status JSON")
        return jsonify(error="Ollama returned an invalid status response."), 502

    model_available = any(
        name == model_name or name.startswith(f"{model_name}:")
        for name in available_models
    )

    return jsonify(
        status="ready" if model_available else "model_missing",
        model=model_name,
        available_models=available_models,
        api_key_name=api_key_name if _is_ollama_cloud() else None,
        message=(
            "Model ready."
            if model_available
            else f"Model {model_name} is not available in Ollama."
        ),
    )


@ollama_bp.get("/keys")
@login_required
@limiter.limit("30 per minute")
def ollama_api_keys():
    if not _account_is_verified():
        return jsonify(error="Verify your account to configure Ollama."), 403

    api_keys = UserApiKey.query.filter_by(
        user_id=current_user.user_id,
        key_type="ollama",
    ).filter(
        UserApiKey.key_ciphertext.is_not(None)
    ).order_by(UserApiKey.created_at.desc()).all()
    return jsonify(
        keys=[
            {"id": api_key.api_key_id, "name": api_key.key_name}
            for api_key in api_keys
        ],
        active_api_key_id=current_user.active_ollama_api_key_id,
    )


@ollama_bp.post("/key")
@login_required
@limiter.limit("10 per minute")
def select_ollama_api_key():
    if not _account_is_verified():
        return jsonify(error="Verify your account to configure Ollama."), 403
    if not request.is_json:
        return jsonify(error="A JSON request is required."), 415

    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify(error="The request body must be valid JSON."), 400

    key_id = payload.get("api_key_id")
    selected_key = None
    if key_id is not None:
        if isinstance(key_id, bool) or not isinstance(key_id, int):
            return jsonify(error="Choose a valid saved API key."), 400
        selected_key = UserApiKey.query.filter_by(
            api_key_id=key_id,
            user_id=current_user.user_id,
            key_type="ollama",
        ).filter(
            UserApiKey.key_ciphertext.is_not(None)
        ).first()
        if selected_key is None:
            return jsonify(error="The selected API key was not found."), 404

    try:
        headers = _ollama_headers(selected_key)
        db.session.commit()
        available_models = _available_models(headers)
    except OllamaAuthenticationError as error:
        return jsonify(error=str(error)), 400
    except RuntimeError as error:
        return jsonify(error=str(error)), 400
    except requests.HTTPError as error:
        if error.response is not None and error.response.status_code in (401, 403):
            return jsonify(error="Ollama rejected the API key. Check the saved key and try again."), 401
        return jsonify(error="Ollama is not reachable; the key was not changed."), 503
    except requests.RequestException:
        return jsonify(error="Ollama is not reachable; the key was not changed."), 503
    except ValueError:
        current_app.logger.exception("Ollama returned invalid model list JSON")
        return jsonify(error="Ollama returned an invalid model list."), 502

    if not available_models:
        return jsonify(error="No Ollama models are available for this key."), 400

    chatbot = Chatbot.query.filter_by(user_id=current_user.user_id).first()
    current_model = (
        chatbot.model_name if chatbot else current_user.ollama_model
    )
    model_name = current_model if current_model in available_models else available_models[0]
    current_user.active_ollama_api_key_id = (
        selected_key.api_key_id if selected_key else None
    )
    current_user.ollama_model = model_name
    if chatbot is not None:
        chatbot.model_name = model_name
    db.session.commit()
    return jsonify(
        model=model_name,
        available_models=available_models,
        api_key_id=selected_key.api_key_id if selected_key else None,
        api_key_name=selected_key.key_name if selected_key else None,
    )


@ollama_bp.get("/settings")
@login_required
def integration_settings():
    if not current_user.authentication_data or not current_user.authentication_data.authenticated:
        return "Verify your account to configure Ollama.", 403

    selected_key = _selected_api_key()
    model_name = current_user.ollama_model or current_app.config["OLLAMA_MODEL"]
    try:
        headers = _ollama_headers(selected_key)
        db.session.commit()
        available_models = _available_models(headers)
        model_available = any(
            name == model_name or name.startswith(f"{model_name}:")
            for name in available_models
        )
        status_message = "Connected to Ollama." if model_available else (
            "Ollama is connected, but the selected model is unavailable."
        )
    except OllamaAuthenticationError as error:
        available_models = []
        status_message = str(error)
    except requests.HTTPError as error:
        available_models = []
        if error.response is not None and error.response.status_code in (401, 403):
            status_message = "Ollama rejected the API key. Check the saved key and try again."
        else:
            current_app.logger.exception("Unable to load Ollama integration settings")
            status_message = "Ollama is not reachable. Check its address and try again."
    except (requests.RequestException, ValueError):
        current_app.logger.exception("Unable to load Ollama integration settings")
        available_models = []
        status_message = "Ollama is not reachable. Check its address and try again."
    except RuntimeError as error:
        available_models = []
        status_message = str(error)

    api_keys = UserApiKey.query.filter_by(
        user_id=current_user.user_id,
        key_type="ollama",
    ).filter(
        UserApiKey.key_ciphertext.is_not(None)
    ).order_by(UserApiKey.created_at.desc()).all()
    return render_template(
        "Settings/Integrations.html",
        current_model=model_name,
        available_models=available_models,
        api_keys=api_keys,
        active_api_key_id=current_user.active_ollama_api_key_id,
        status_message=status_message,
        cloud_endpoint=_is_ollama_cloud(),
    )


@ollama_bp.post("/preferences")
@login_required
@limiter.limit("10 per minute")
def save_preferences():
    if not current_user.authentication_data or not current_user.authentication_data.authenticated:
        return jsonify(error="Verify your account to configure Ollama."), 403
    if not request.is_json:
        return jsonify(error="A JSON request is required."), 415

    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify(error="The request body must be valid JSON."), 400

    model_name = payload.get("model")
    key_id = payload.get("api_key_id")
    if not isinstance(model_name, str) or not model_name.strip() or len(model_name) > 128:
        return jsonify(error="Choose a valid Ollama model."), 400
    model_name = model_name.strip()

    selected_key = None
    if key_id is not None:
        if isinstance(key_id, bool) or not isinstance(key_id, int):
            return jsonify(error="Choose a valid saved API key."), 400
        selected_key = UserApiKey.query.filter_by(
            api_key_id=key_id,
            user_id=current_user.user_id,
            key_type="ollama",
        ).first()
        if selected_key is None:
            return jsonify(error="The selected API key was not found."), 404

    selected_key_id = selected_key.api_key_id if selected_key else None
    selected_key_name = selected_key.key_name if selected_key else None
    try:
        headers = _ollama_headers(selected_key)
        db.session.commit()
        available_models = _available_models(headers)
    except OllamaAuthenticationError as error:
        return jsonify(error=str(error)), 400
    except RuntimeError as error:
        return jsonify(error=str(error)), 400
    except requests.HTTPError as error:
        if error.response is not None and error.response.status_code in (401, 403):
            return jsonify(error="Ollama rejected the API key. Check the saved key and try again."), 401
        return jsonify(error="Ollama is not reachable; preferences were not changed."), 503
    except requests.RequestException:
        return jsonify(error="Ollama is not reachable; preferences were not changed."), 503
    except ValueError:
        current_app.logger.exception("Ollama returned invalid model list JSON")
        return jsonify(error="Ollama returned an invalid model list."), 502

    if model_name not in available_models:
        return jsonify(error="That model is not available in Ollama."), 400

    current_user.ollama_model = model_name
    current_user.active_ollama_api_key_id = selected_key_id
    chatbot = Chatbot.query.filter_by(user_id=current_user.user_id).first()
    if chatbot is not None:
        chatbot.model_name = model_name
    db.session.commit()
    return jsonify(model=model_name, api_key_name=selected_key_name)


@ollama_bp.get("/session")
@login_required
def get_chat_session():
    if not _account_is_verified():
        return jsonify(error="Verify your account to use the Rover AI assistant."), 403

    chatbot = _get_or_create_chatbot()
    chat_session = _current_chat_session(chatbot)
    if chat_session is None:
        chat_session = ChatbotSession(
            session_id=str(uuid4()),
            chatbot_id=chatbot.chatbot_id,
        )
        db.session.add(chat_session)
        db.session.flush()
        session[CHAT_SESSION_KEY] = chat_session.session_id

    messages = (
        ChatbotMessage.query.filter_by(session_id=chat_session.session_id)
        .order_by(ChatbotMessage.message_id.desc())
        .limit(100)
        .all()
    )
    db.session.commit()
    messages.reverse()
    return jsonify(
        session_id=chat_session.session_id,
        chatbot_name=chatbot.chatbot_name,
        model=chatbot.model_name,
        messages=[
            {"role": message.role, "content": message.content}
            for message in messages
        ],
        permissions={
            "read_folder": chatbot.configuration.allow_folder_read,
            "write_folder": chatbot.configuration.allow_folder_write,
        },
    )


@ollama_bp.post("/session/end")
@login_required
@limiter.limit("10 per minute")
def end_chat_session():
    if not _account_is_verified():
        return jsonify(error="Verify your account to use the Rover AI assistant."), 403

    chatbot = Chatbot.query.filter_by(user_id=current_user.user_id).first()
    chat_session = _current_chat_session(chatbot) if chatbot else None
    if chat_session is not None:
        chat_session.ended_at = datetime.now(timezone.utc)
        ChatbotMessage.query.filter_by(session_id=chat_session.session_id).delete(
            synchronize_session=False,
        )
        db.session.commit()
    session.pop(CHAT_SESSION_KEY, None)
    return jsonify(session_ended=True)


@ollama_bp.post("/chatbot/settings")
@login_required
@limiter.limit("10 per minute")
def save_chatbot_settings():
    if not _account_is_verified():
        return jsonify(error="Verify your account to configure Rover AI."), 403
    if not request.is_json:
        return jsonify(error="A JSON request is required."), 415

    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify(error="The request body must be valid JSON."), 400
    chatbot_name = payload.get("name")
    model_name = payload.get("model")
    if (
        not isinstance(chatbot_name, str)
        or not chatbot_name.strip()
        or len(chatbot_name.strip()) > 64
    ):
        return jsonify(error="Enter a chatbot name between 1 and 64 characters."), 400
    if (
        not isinstance(model_name, str)
        or not model_name.strip()
        or len(model_name.strip()) > 128
    ):
        return jsonify(error="Enter a valid Ollama model name."), 400
    model_name = model_name.strip()
    selected_key = _selected_api_key()
    try:
        headers = _ollama_headers(selected_key)
        db.session.commit()
        available_models = _available_models(headers)
    except OllamaAuthenticationError as error:
        return jsonify(error=str(error)), 400
    except RuntimeError as error:
        return jsonify(error=str(error)), 400
    except requests.HTTPError as error:
        if error.response is not None and error.response.status_code in (401, 403):
            return jsonify(error="Ollama rejected the API key. Check the saved key and try again."), 401
        return jsonify(error="Ollama is not reachable; settings were not changed."), 503
    except requests.RequestException:
        return jsonify(error="Ollama is not reachable; settings were not changed."), 503
    except ValueError:
        current_app.logger.exception("Ollama returned invalid model list JSON")
        return jsonify(error="Ollama returned an invalid model list."), 502

    if model_name not in available_models:
        return jsonify(error="That model is not available in Ollama."), 400

    chatbot = _get_or_create_chatbot()
    chatbot.chatbot_name = chatbot_name.strip()
    chatbot.model_name = model_name
    current_user.ollama_model = model_name
    db.session.commit()
    return jsonify(name=chatbot.chatbot_name, model=chatbot.model_name)


@ollama_bp.post("/chatbot/permissions")
@login_required
@limiter.limit("10 per minute")
def save_chatbot_permissions():
    if not _account_is_verified():
        return jsonify(error="Verify your account to configure Rover AI."), 403
    if not request.is_json:
        return jsonify(error="A JSON request is required."), 415

    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify(error="The request body must be valid JSON."), 400
    allow_read = payload.get("read_folder")
    allow_write = payload.get("write_folder")
    if not isinstance(allow_read, bool) or not isinstance(allow_write, bool):
        return jsonify(error="Choose valid folder permission settings."), 400

    chatbot = _get_or_create_chatbot()
    chatbot.configuration.allow_folder_read = allow_read
    chatbot.configuration.allow_folder_write = allow_write
    db.session.commit()
    return jsonify(read_folder=allow_read, write_folder=allow_write)


@ollama_bp.post("/chat")
@login_required
@limiter.limit("10 per minute")
def chat():
    if not _account_is_verified():
        return jsonify(error="Verify your account to use the Ollama assistant."), 403

    if not request.is_json:
        return jsonify(error="A JSON request is required."), 415

    payload = request.get_json(silent=True)
    content = payload.get("message") if isinstance(payload, dict) else None
    if not isinstance(content, str) or not content.strip() or len(content) > 20_000:
        return jsonify(error="Enter a message between 1 and 20000 characters."), 400

    chatbot = Chatbot.query.filter_by(user_id=current_user.user_id).first()
    chat_session = _current_chat_session(chatbot) if chatbot else None
    if chatbot is None or chat_session is None:
        return jsonify(error="Start a Rover AI session before sending a message."), 409

    history = (
        ChatbotMessage.query.filter_by(session_id=chat_session.session_id)
        .order_by(ChatbotMessage.message_id.desc())
        .limit(19)
        .all()
    )
    history.reverse()
    ollama_messages = [
        {"role": message.role, "content": message.content}
        for message in history
    ]
    ollama_messages.append({"role": "user", "content": content.strip()})
    selected_key = _selected_api_key()
    model_name = chatbot.model_name
    chatbot_id = chatbot.chatbot_id
    session_id = chat_session.session_id
    response = None

    def close_response():
        if response is not None:
            response.close()

    try:
        headers = _ollama_headers(selected_key)
        db.session.commit()
        response = requests.post(
            _ollama_url("/api/chat"),
            json={
                "model": model_name,
                "messages": ollama_messages,
                "stream": True,
            },
            headers=headers,
            timeout=(5, 180),
            stream=True,
        )
        response.raise_for_status()
    except requests.Timeout:
        close_response()
        return jsonify(error="Ollama took too long to respond. Please try again."), 504
    except requests.HTTPError as error:
        close_response()
        if error.response is not None and error.response.status_code in (401, 403):
            return jsonify(error="Ollama rejected the API key. Check the saved key and try again."), 502
        current_app.logger.exception("Ollama chat request failed")
        return jsonify(error="Ollama could not complete the request."), 502
    except requests.RequestException:
        close_response()
        current_app.logger.exception("Ollama chat request failed")
        return jsonify(error="Ollama could not complete the request."), 502
    except OllamaAuthenticationError as error:
        close_response()
        return jsonify(error=str(error)), 401
    except RuntimeError as error:
        close_response()
        current_app.logger.exception("The selected Ollama API key could not be decrypted")
        return jsonify(error=str(error)), 503

    def stream_chat_response():
        assistant_parts = []
        stream_completed = False
        try:
            for line in response.iter_lines(decode_unicode=True):
                if not line:
                    continue
                try:
                    if isinstance(line, bytes):
                        line = line.decode("utf-8")
                    event = json.loads(line)
                except (UnicodeDecodeError, ValueError):
                    current_app.logger.exception("Ollama returned invalid streaming JSON")
                    yield json.dumps({"error": "Ollama returned an invalid response."}) + "\n"
                    return

                if not isinstance(event, dict):
                    current_app.logger.error("Ollama returned an invalid streaming event")
                    yield json.dumps({"error": "Ollama returned an invalid response."}) + "\n"
                    return

                message = event.get("message")
                part = message.get("content") if isinstance(message, dict) else None
                if part is not None:
                    if not isinstance(part, str):
                        current_app.logger.error("Ollama returned non-text message content")
                        yield json.dumps({"error": "Ollama returned an invalid response."}) + "\n"
                        return
                    if part:
                        assistant_parts.append(part)
                        yield json.dumps({"token": part}) + "\n"
                if event.get("error"):
                    current_app.logger.error("Ollama stream reported an error")
                    yield json.dumps({"error": "Ollama could not complete the request."}) + "\n"
                    return
                if event.get("done") is True:
                    stream_completed = True
                    break

            if not stream_completed:
                current_app.logger.error("Ollama response stream ended unexpectedly")
                yield json.dumps(
                    {"error": "Ollama ended the response before it was complete."}
                ) + "\n"
                return

            assistant_message = "".join(assistant_parts)
            if not assistant_message:
                current_app.logger.error("Ollama response did not contain assistant content")
                yield json.dumps({"error": "Ollama returned an empty response."}) + "\n"
                return

            chat_session = ChatbotSession.query.filter_by(
                session_id=session_id,
                chatbot_id=chatbot_id,
                ended_at=None,
            ).first()
            if chat_session is None:
                yield json.dumps(
                    {"error": "The chat session ended before the reply was saved."}
                ) + "\n"
                return

            db.session.add_all(
                [
                    ChatbotMessage(
                        session_id=chat_session.session_id,
                        role="user",
                        content=content.strip(),
                    ),
                    ChatbotMessage(
                        session_id=chat_session.session_id,
                        role="assistant",
                        content=assistant_message,
                    ),
                ]
            )
            chat_session.last_activity_at = datetime.now(timezone.utc)
            db.session.commit()
            yield json.dumps({"done": True, "message": assistant_message}) + "\n"
        except requests.RequestException:
            current_app.logger.exception("Ollama chat stream failed")
            yield json.dumps({"error": "Ollama could not complete the request."}) + "\n"
        except SQLAlchemyError:
            db.session.rollback()
            current_app.logger.exception("Unable to save streamed Rover AI chat")
            yield json.dumps({"error": "Rover could not save the completed chat."}) + "\n"
        finally:
            response.close()

    return Response(
        stream_with_context(stream_chat_response()),
        content_type="application/x-ndjson",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@ollama_bp.get("/agents")
@login_required
@limiter.limit("10 per minute")
def get_rover_agents():
    if not _account_is_verified():
        return jsonify(error="Verify your account to use Triple Rover Mode."), 403

    agents = _create_rover_agent_slots()
    result = []
    for agent in agents:
        chat_session = agent.chat_session
        result.append(
            {
                "id": agent.agent_id,
                "slot": agent.slot_number,
                "name": agent.agent_name,
                "model": agent.model_name,
                "system_prompt": agent.configuration.system_prompt,
                "temperature": agent.configuration.temperature,
                "first_message_at": (
                    chat_session.first_message_at.isoformat()
                    if chat_session.first_message_at
                    else None
                ),
                "messages": _agent_history(chat_session),
            }
        )
    db.session.commit()
    return jsonify(agents=result, retention_days=AGENT_HISTORY_DAYS)


@ollama_bp.post("/agents/<int:agent_id>/settings")
@login_required
@limiter.limit("10 per minute")
def save_rover_agent_settings(agent_id: int):
    if not _account_is_verified():
        return jsonify(error="Verify your account to configure Triple Rover Mode."), 403
    if not request.is_json:
        return jsonify(error="A JSON request is required."), 415

    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify(error="The request body must be valid JSON."), 400
    agent_name = payload.get("name")
    model_name = payload.get("model")
    system_prompt = payload.get("system_prompt", "")
    temperature = payload.get("temperature", 0.7)
    if not isinstance(agent_name, str) or not agent_name.strip() or len(agent_name.strip()) > 64:
        return jsonify(error="Enter an agent name between 1 and 64 characters."), 400
    if not isinstance(model_name, str) or not model_name.strip() or len(model_name.strip()) > 128:
        return jsonify(error="Enter a valid Ollama model name."), 400
    if not isinstance(system_prompt, str) or len(system_prompt) > 2000:
        return jsonify(error="Agent instructions must be 2000 characters or fewer."), 400
    if (
        isinstance(temperature, bool)
        or not isinstance(temperature, (int, float))
        or not isfinite(temperature)
        or not 0 <= temperature <= 2
    ):
        return jsonify(error="Temperature must be a number from 0 to 2."), 400

    agent = _get_rover_agent(agent_id)
    if agent is None:
        return jsonify(error="That agent slot was not found."), 404

    model_name = model_name.strip()
    try:
        headers = _ollama_headers(_selected_api_key())
        db.session.commit()
        available_models = _available_models(headers)
    except OllamaAuthenticationError as error:
        return jsonify(error=str(error)), 400
    except RuntimeError as error:
        current_app.logger.exception("The selected Ollama API key could not be decrypted")
        return jsonify(error=str(error)), 503
    except requests.HTTPError as error:
        if error.response is not None and error.response.status_code in (401, 403):
            return jsonify(error="Ollama rejected the API key. Check the saved key and try again."), 401
        current_app.logger.exception("Unable to validate a Triple Rover model")
        return jsonify(error="Ollama is not reachable; agent settings were not changed."), 503
    except requests.RequestException:
        current_app.logger.exception("Unable to validate a Triple Rover model")
        return jsonify(error="Ollama is not reachable; agent settings were not changed."), 503
    except ValueError:
        current_app.logger.exception("Ollama returned invalid model list JSON")
        return jsonify(error="Ollama returned an invalid model list."), 502

    if model_name not in available_models:
        return jsonify(error="That model is not available in Ollama."), 400

    agent.agent_name = agent_name.strip()
    agent.model_name = model_name
    agent.configuration.system_prompt = system_prompt.strip()
    agent.configuration.temperature = float(temperature)
    db.session.commit()
    return jsonify(
        name=agent.agent_name,
        model=agent.model_name,
        system_prompt=agent.configuration.system_prompt,
        temperature=agent.configuration.temperature,
    )


@ollama_bp.post("/agents/<int:agent_id>/chat")
@login_required
@limiter.limit("10 per minute")
def chat_with_rover_agent(agent_id: int):
    if not _account_is_verified():
        return jsonify(error="Verify your account to use Triple Rover Mode."), 403
    if not request.is_json:
        return jsonify(error="A JSON request is required."), 415

    payload = request.get_json(silent=True)
    content = payload.get("message") if isinstance(payload, dict) else None
    if not isinstance(content, str) or not content.strip() or len(content) > 20_000:
        return jsonify(error="Enter a message between 1 and 20000 characters."), 400

    agent = _get_rover_agent(agent_id)
    if agent is None:
        return jsonify(error="That agent slot was not found."), 404

    chat_session = _get_agent_session(agent)
    history = _agent_history(chat_session)[-19:]
    ollama_messages = []
    if agent.configuration.system_prompt.strip():
        ollama_messages.append(
            {"role": "system", "content": agent.configuration.system_prompt.strip()}
        )
    ollama_messages.extend(history)
    ollama_messages.append({"role": "user", "content": content.strip()})

    try:
        headers = _ollama_headers(_selected_api_key())
        if chat_session.first_message_at is None:
            chat_session.first_message_at = datetime.now(timezone.utc)
        db.session.commit()
        response = requests.post(
            _ollama_url("/api/chat"),
            json={
                "model": agent.model_name,
                "messages": ollama_messages,
                "stream": False,
                "options": {"temperature": agent.configuration.temperature},
            },
            headers=headers,
            timeout=(5, 180),
        )
        response.raise_for_status()
        result = response.json()
    except requests.Timeout:
        return jsonify(error="Ollama took too long to respond. Please try again."), 504
    except requests.HTTPError as error:
        if error.response is not None and error.response.status_code in (401, 403):
            return jsonify(error="Ollama rejected the API key. Check the saved key and try again."), 502
        current_app.logger.exception("Triple Rover chat request failed")
        return jsonify(error="Ollama could not complete the request."), 502
    except requests.RequestException:
        current_app.logger.exception("Triple Rover chat request failed")
        return jsonify(error="Ollama could not complete the request."), 502
    except OllamaAuthenticationError as error:
        return jsonify(error=str(error)), 401
    except RuntimeError as error:
        current_app.logger.exception("The selected Ollama API key could not be decrypted")
        return jsonify(error=str(error)), 503
    except ValueError:
        current_app.logger.exception("Ollama returned an invalid response")
        return jsonify(error="Ollama returned an invalid response."), 502

    response_message = result.get("message") if isinstance(result, dict) else None
    assistant_message = (
        response_message.get("content")
        if isinstance(response_message, dict)
        else None
    )
    if not isinstance(assistant_message, str) or not assistant_message.strip():
        current_app.logger.error("Ollama response did not contain agent content")
        return jsonify(error="Ollama returned an empty response."), 502

    now = datetime.now(timezone.utc)
    chat_session.last_activity_at = now
    db.session.add_all(
        [
            RoverAgentMessage(
                session_id=chat_session.session_id,
                role="user",
                content=content.strip(),
            ),
            RoverAgentMessage(
                session_id=chat_session.session_id,
                role="assistant",
                content=assistant_message,
            ),
        ]
    )
    db.session.commit()
    return jsonify(
        message=assistant_message,
        first_message_at=chat_session.first_message_at.isoformat(),
    )
