import re

import requests

GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta"
MODEL_NAME = re.compile(r"gemini-[A-Za-z0-9._-]{1,120}\Z")


def available_models(api_key: str) -> list[str]:
    models = []
    page_token = None
    seen_tokens = set()
    while True:
        params = {"pageSize": 100}
        if page_token:
            params["pageToken"] = page_token
        response = requests.get(
            f"{GEMINI_API_URL}/models",
            headers={"x-goog-api-key": api_key},
            params=params,
            timeout=(3, 10),
            allow_redirects=False,
        )
        try:
            if 300 <= response.status_code < 400:
                raise RuntimeError("Gemini returned an unexpected redirect.")
            response.raise_for_status()
            payload = response.json()
        finally:
            response.close()
        if not isinstance(payload, dict) or not isinstance(payload.get("models", []), list):
            raise RuntimeError("Gemini returned an invalid model list.")
        for model in payload.get("models", []):
            if not isinstance(model, dict):
                continue
            name = model.get("name", "")
            methods = model.get("supportedGenerationMethods", [])
            if (
                isinstance(name, str)
                and name.startswith("models/")
                and MODEL_NAME.fullmatch(name[7:])
                and isinstance(methods, list)
                and "generateContent" in methods
            ):
                models.append(name[7:])
        page_token = payload.get("nextPageToken")
        if not page_token:
            return list(dict.fromkeys(models))
        if not isinstance(page_token, str) or page_token in seen_tokens:
            raise RuntimeError("Gemini returned an invalid model list page.")
        seen_tokens.add(page_token)
        if len(seen_tokens) > 20:
            raise RuntimeError("Gemini returned too many model list pages.")


def generate_content(api_key: str, model: str, messages: list[dict[str, str]]) -> str:
    if not MODEL_NAME.fullmatch(model):
        raise RuntimeError("Choose a valid Gemini model.")
    contents = [
        {
            "role": "model" if message["role"] == "assistant" else "user",
            "parts": [{"text": message["content"]}],
        }
        for message in messages
    ]
    response = requests.post(
        f"{GEMINI_API_URL}/models/{model}:generateContent",
        headers={"x-goog-api-key": api_key},
        json={"contents": contents},
        timeout=(5, 180),
        allow_redirects=False,
    )
    try:
        if 300 <= response.status_code < 400:
            raise RuntimeError("Gemini returned an unexpected redirect.")
        response.raise_for_status()
        payload = response.json()
    finally:
        response.close()
    if not isinstance(payload, dict):
        raise RuntimeError("Gemini returned an invalid response.")
    candidates = payload.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        raise RuntimeError("Gemini did not return a response; the request may have been blocked.")
    candidate = candidates[0]
    if not isinstance(candidate, dict) or candidate.get("finishReason") != "STOP":
        raise RuntimeError("Gemini could not complete the response.")
    content = candidate.get("content")
    parts = content.get("parts") if isinstance(content, dict) else None
    if not isinstance(parts, list):
        raise RuntimeError("Gemini returned an invalid response.")
    text = "".join(
        part["text"] for part in parts
        if isinstance(part, dict) and isinstance(part.get("text"), str) and not part.get("thought")
    )
    if not text:
        raise RuntimeError("Gemini returned an empty response.")
    return text
