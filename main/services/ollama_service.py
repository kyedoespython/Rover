import hashlib
import json
import os

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from flask import current_app


def _encryption_key() -> bytes:
    """Derive a stable AES key, falling back to SECRET_KEY for older deployments."""
    secret = current_app.config.get("OLLAMA_API_KEY_ENCRYPTION_KEY")
    if not secret:
        secret = current_app.config.get("SECRET_KEY")
    if not isinstance(secret, str) or not secret:
        raise RuntimeError("Ollama API key encryption is not configured.")
    return hashlib.sha256(secret.encode("utf-8")).digest()


def encrypt_api_key(api_key: str, user_id: int, key_id: int) -> bytes:
    nonce = os.urandom(12)
    associated_data = f"rover-ollama:{user_id}:{key_id}".encode("ascii")
    return nonce + AESGCM(_encryption_key()).encrypt(
        nonce,
        api_key.encode("utf-8"),
        associated_data,
    )


def decrypt_api_key(ciphertext: bytes, user_id: int, key_id: int) -> str:
    nonce, encrypted = ciphertext[:12], ciphertext[12:]
    associated_data = f"rover-ollama:{user_id}:{key_id}".encode("ascii")
    try:
        plaintext = AESGCM(_encryption_key()).decrypt(
            nonce,
            encrypted,
            associated_data,
        )
        return plaintext.decode("utf-8")
    except (InvalidTag, UnicodeDecodeError) as error:
        raise RuntimeError(
            "The Ollama API key could not be decrypted. Re-enter it in the design dashboard."
        ) from error


def encrypt_chatbot_file(name: str, content: str, user_id: int, file_id: str) -> bytes:
    nonce = os.urandom(12)
    associated_data = f"rover-chatbot-file:{user_id}:{file_id}".encode("ascii")
    plaintext = json.dumps({"name": name, "content": content}).encode("utf-8")
    return nonce + AESGCM(_encryption_key()).encrypt(nonce, plaintext, associated_data)


def decrypt_chatbot_file(ciphertext: bytes, user_id: int, file_id: str) -> dict[str, str]:
    associated_data = f"rover-chatbot-file:{user_id}:{file_id}".encode("ascii")
    try:
        plaintext = AESGCM(_encryption_key()).decrypt(
            ciphertext[:12], ciphertext[12:], associated_data
        )
        result = json.loads(plaintext.decode("utf-8"))
        if not isinstance(result, dict) or not all(
            isinstance(result.get(key), str) for key in ("name", "content")
        ):
            raise ValueError("Invalid encrypted file data")
        return result
    except (InvalidTag, UnicodeDecodeError, ValueError) as error:
        raise RuntimeError("The saved file could not be decrypted.") from error
