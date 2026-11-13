from datetime import datetime, timezone
from pathlib import Path

import pytest
from flask import Flask

from main.extensions import db
from main.models import Accounts, NoteMetadata, Notes
from main.services import notes_service
from main.services.notes_service import (
    create_note,
    delete_note,
    ensure_default_note,
    read_note_content,
    update_note,
)


@pytest.fixture
def notes_app(tmp_path):
    app = Flask(__name__)
    app.config.update(
        TESTING=True,
        SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        NOTE_STORAGE_DIR=str(tmp_path / "note-files"),
    )
    db.init_app(app)

    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


def _create_account():
    account = Accounts(
        email="notes@example.com",
        username="NotesUser",
        password="hashed-password",
        country_of_origin="United States",
    )
    db.session.add(account)
    db.session.commit()
    return account


def test_create_note_stores_markdown_and_metadata(notes_app):
    with notes_app.app_context():
        account = _create_account()
        note = create_note(account.user_id, "Plan", "Project plan", "# Plan\n\nDraft")

        assert note.note_content is None
        assert note.file_metadata.file_name.endswith(".md")
        assert note.file_metadata.size_bytes == len("# Plan\n\nDraft".encode("utf-8"))
        assert read_note_content(note) == "# Plan\n\nDraft"

        file_path = (
            Path(notes_app.config["NOTE_STORAGE_DIR"])
            / note.file_metadata.relative_path
        )
        assert file_path.is_file()
        assert file_path.read_text(encoding="utf-8") == "# Plan\n\nDraft"
        assert db.session.get(NoteMetadata, note.note_id) is not None


def test_update_replaces_markdown_and_keeps_metadata(notes_app):
    with notes_app.app_context():
        account = _create_account()
        note = create_note(account.user_id, "Plan", "Project plan", "Old text")
        old_path = (
            Path(notes_app.config["NOTE_STORAGE_DIR"])
            / note.file_metadata.relative_path
        )

        update_note(note, "Plan v2", "Updated plan", "# Updated")

        new_path = (
            Path(notes_app.config["NOTE_STORAGE_DIR"])
            / note.file_metadata.relative_path
        )
        assert note.note_name == "Plan v2"
        assert note.note_description == "Updated plan"
        assert note.file_metadata.size_bytes == len("# Updated".encode("utf-8"))
        assert note.file_metadata.updated_at >= note.file_metadata.created_at
        assert read_note_content(note) == "# Updated"
        assert not old_path.exists()
        assert new_path.read_text(encoding="utf-8") == "# Updated"


def test_delete_removes_note_metadata_and_markdown(notes_app):
    with notes_app.app_context():
        account = _create_account()
        note = create_note(account.user_id, "Temporary", "Delete me", "Content")
        file_path = (
            Path(notes_app.config["NOTE_STORAGE_DIR"])
            / note.file_metadata.relative_path
        )
        note_id = note.note_id

        delete_note(note)

        assert db.session.get(Notes, note_id) is None
        assert db.session.get(NoteMetadata, note_id) is None
        assert not file_path.exists()


def test_legacy_note_content_migrates_to_markdown_when_loaded(notes_app):
    with notes_app.app_context():
        account = _create_account()
        now = datetime.now(timezone.utc)
        note = Notes(
            user_id=account.user_id,
            note_name="Legacy",
            note_description="Old database note",
            note_content="Legacy content",
            note_created_at=now,
            note_last_modified_at=now,
        )
        db.session.add(note)
        db.session.commit()

        assert read_note_content(note) == "Legacy content"
        assert note.note_content is None
        assert note.file_metadata.file_name.endswith(".md")
        update_note(note, "Legacy", "Migrated note", "Migrated content")

        assert note.note_content is None
        assert read_note_content(note) == "Migrated content"
        assert note.file_metadata.file_name.endswith(".md")


def test_default_note_uses_database_when_markdown_storage_is_unavailable(
    notes_app, monkeypatch
):
    with notes_app.app_context():
        account = _create_account()

        def fail_file_write(*args, **kwargs):
            raise PermissionError("note storage is read-only")

        monkeypatch.setattr(notes_service, "_write_markdown_file", fail_file_write)

        note = ensure_default_note(account.user_id)

        assert note.note_name == "Empty note"
        assert note.note_content == ""
        assert note.file_metadata is None
        assert read_note_content(note) == ""


def test_create_and_update_notes_use_database_when_markdown_storage_is_unavailable(
    notes_app, monkeypatch
):
    with notes_app.app_context():
        account = _create_account()
        note = create_note(account.user_id, "Plan", "Original", "Old content")
        previous_path = (
            Path(notes_app.config["NOTE_STORAGE_DIR"])
            / note.file_metadata.relative_path
        )

        def fail_file_write(*args, **kwargs):
            raise PermissionError("note storage is read-only")

        monkeypatch.setattr(notes_service, "_write_markdown_file", fail_file_write)

        update_note(note, "Updated plan", "Updated", "New content")

        assert note.note_name == "Updated plan"
        assert note.note_description == "Updated"
        assert note.note_content == "New content"
        assert note.file_metadata is None
        assert read_note_content(note) == "New content"
        assert not previous_path.exists()

        created_note = create_note(
            account.user_id,
            "Database note",
            "Saved without filesystem",
            "Database content",
        )
        assert created_note.note_content == "Database content"
        assert created_note.file_metadata is None
