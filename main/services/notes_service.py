import hashlib
import uuid
from datetime import datetime, timezone
from pathlib import Path

from flask import current_app
from sqlalchemy.exc import IntegrityError

from main.extensions import db
from main.models.notes import NoteMetadata, Notes


def _storage_root() -> Path:
    configured_directory = current_app.config.get("NOTE_STORAGE_DIR")
    if configured_directory:
        return Path(configured_directory).resolve()
    return (Path(current_app.instance_path) / "note_storage").resolve()


def _write_markdown_file(user_id: int, content: str) -> tuple[Path, str, str, int, str]:
    root = _storage_root()
    user_directory = root / f"user_{user_id}"
    user_directory.mkdir(parents=True, exist_ok=True)

    content_bytes = content.encode("utf-8")
    file_name = f"{uuid.uuid4().hex}.md"
    relative_path = f"user_{user_id}/{file_name}"
    file_path = user_directory / file_name
    temporary_path = user_directory / f".{uuid.uuid4().hex}.tmp"

    try:
        temporary_path.write_bytes(content_bytes)
        temporary_path.replace(file_path)
    except OSError:
        try:
            temporary_path.unlink(missing_ok=True)
        except OSError:
            current_app.logger.exception("Unable to clean up temporary note file")
        raise

    return (
        file_path,
        relative_path,
        file_name,
        len(content_bytes),
        hashlib.sha256(content_bytes).hexdigest(),
    )


def _metadata_path(metadata: NoteMetadata) -> Path:
    root = _storage_root()
    file_path = (root / metadata.relative_path).resolve()
    if not file_path.is_relative_to(root):
        raise ValueError("Note metadata references a path outside note storage")
    return file_path


def _remove_file(file_path: Path, note_id: int) -> None:
    try:
        file_path.unlink(missing_ok=True)
    except OSError:
        current_app.logger.exception(
            "Unable to remove Markdown file for note %s", note_id
        )


def read_note_content(note: Notes) -> str:
    if note.file_metadata is None:
        content = note.note_content or ""
        now = datetime.now(timezone.utc)
        file_path = None
        note_id = note.note_id
        try:
            (
                file_path,
                relative_path,
                file_name,
                size_bytes,
                sha256,
            ) = _write_markdown_file(note.user_id, content)
            note.file_metadata = NoteMetadata(
                file_name=file_name,
                relative_path=relative_path,
                size_bytes=size_bytes,
                sha256=sha256,
                content_type="text/markdown",
                created_at=now,
                updated_at=now,
            )
            note.note_content = None
            db.session.commit()
        except OSError:
            db.session.rollback()
            current_app.logger.warning(
                "Unable to migrate Markdown file for note %s; using database content",
                note_id,
                exc_info=True,
            )
            return content
        except Exception:
            db.session.rollback()
            if file_path is not None:
                _remove_file(file_path, note_id)
            raise
        return content
    return _metadata_path(note.file_metadata).read_text(encoding="utf-8")


def create_note(user_id: int, name: str, description: str, content: str) -> Notes:
    now = datetime.now(timezone.utc)
    note = Notes(
        user_id=user_id,
        note_name=name,
        note_description=description,
        note_content=None,
        note_created_at=now,
        note_last_modified_at=now,
    )
    file_path = None
    note_id = None

    try:
        db.session.add(note)
        db.session.flush()
        note_id = note.note_id
        (
            file_path,
            relative_path,
            file_name,
            size_bytes,
            sha256,
        ) = _write_markdown_file(user_id, content)
        db.session.add(
            NoteMetadata(
                note_id=note.note_id,
                file_name=file_name,
                relative_path=relative_path,
                size_bytes=size_bytes,
                sha256=sha256,
                content_type="text/markdown",
                created_at=now,
                updated_at=now,
            )
        )
        db.session.commit()
    except OSError:
        db.session.rollback()
        current_app.logger.warning(
            "Unable to write Markdown file for note belonging to user %s; "
            "saving note content in the database",
            user_id,
            exc_info=True,
        )
        note = Notes(
            user_id=user_id,
            note_name=name,
            note_description=description,
            note_content=content,
            note_created_at=now,
            note_last_modified_at=now,
        )
        db.session.add(note)
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            raise
    except Exception:
        db.session.rollback()
        if file_path is not None and note_id is not None:
            _remove_file(file_path, note_id)
        raise

    return note


def ensure_default_note(user_id: int) -> Notes:
    note = Notes.query.filter_by(user_id=user_id, note_name="Empty note").first()
    if note is not None:
        return note

    try:
        return create_note(user_id, "Empty note", "", "")
    except IntegrityError:
        db.session.rollback()
        note = Notes.query.filter_by(user_id=user_id, note_name="Empty note").first()
        if note is None:
            raise
        return note


def update_note(note: Notes, name: str, description: str, content: str) -> None:
    previous_path = (
        _metadata_path(note.file_metadata) if note.file_metadata is not None else None
    )
    file_path = None
    note_id = note.note_id
    now = datetime.now(timezone.utc)

    try:
        (
            file_path,
            relative_path,
            file_name,
            size_bytes,
            sha256,
        ) = _write_markdown_file(note.user_id, content)
    except OSError:
        current_app.logger.warning(
            "Unable to write Markdown file for note %s; saving note content "
            "in the database",
            note_id,
            exc_info=True,
        )
        note.note_name = name
        note.note_description = description
        note.note_content = content
        note.note_last_modified_at = now
        note.file_metadata = None
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            raise
        if previous_path is not None:
            _remove_file(previous_path, note_id)
        return
    except Exception:
        db.session.rollback()
        if file_path is not None:
            _remove_file(file_path, note_id)
        raise

    metadata = note.file_metadata
    if metadata is None:
        metadata = NoteMetadata(note_id=note.note_id, created_at=now)
        note.file_metadata = metadata

    note.note_name = name
    note.note_description = description
    note.note_content = None
    note.note_last_modified_at = now
    metadata.file_name = file_name
    metadata.relative_path = relative_path
    metadata.size_bytes = size_bytes
    metadata.sha256 = sha256
    metadata.content_type = "text/markdown"
    metadata.updated_at = now
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        if file_path is not None:
            _remove_file(file_path, note_id)
        raise

    if previous_path is not None and previous_path != file_path:
        _remove_file(previous_path, note_id)


def delete_note(note: Notes) -> None:
    file_path = (
        _metadata_path(note.file_metadata) if note.file_metadata is not None else None
    )
    note_id = note.note_id
    db.session.delete(note)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    if file_path is not None:
        _remove_file(file_path, note_id)
