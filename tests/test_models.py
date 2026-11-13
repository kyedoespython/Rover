from sqlalchemy import inspect

from main.extensions import db
from main import models as model_package
from main.models.auth import Authentication, PasswordResetToken
from main.models.notes import NoteMetadata, Notes
from main.models.schemas import SchemaMetadata, UserSchema, UserSchemaDatabase
from main.models.tickets import Tickets
from main.models.users import Accounts


def test_model_sections_preserve_central_imports_and_relationships():
    models = (Accounts, Authentication, PasswordResetToken, Notes, NoteMetadata, Tickets, UserSchema, UserSchemaDatabase, SchemaMetadata)

    for model in models:
        assert getattr(model_package, model.__name__) is model
        assert db.metadata.tables[model.__tablename__] is model.__table__

    assert inspect(Accounts).relationships["authentication_data"].mapper.class_ is Authentication
    assert inspect(Accounts).relationships["user_notes"].mapper.class_ is Notes
    assert inspect(Accounts).relationships["user_tickets"].mapper.class_ is Tickets
    assert inspect(Accounts).relationships["schemas"].mapper.class_ is UserSchema
    assert inspect(Accounts).relationships["schema_databases"].mapper.class_ is UserSchemaDatabase
    assert inspect(Notes).relationships["file_metadata"].mapper.class_ is NoteMetadata
    assert inspect(UserSchema).relationships["details"].mapper.class_ is SchemaMetadata