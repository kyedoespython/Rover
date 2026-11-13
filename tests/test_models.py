from pathlib import Path

from sqlalchemy import create_engine, inspect
from sqlalchemy.engine import URL

from main.extensions import db
from main import models as model_package
from main.models.FastQuery import (
    FastQueryProgress,
    FastQuerySection,
    FastQuerySectionCompletion,
)
from main.models.auth import Authentication, PasswordResetToken
from main.models.notes import NoteMetadata, Notes
from main.models.schemas import SchemaMetadata, UserSchema, UserSchemaDatabase
from main.models.tickets import Tickets
from main.models.users import Accounts


def test_model_sections_preserve_central_imports_and_relationships():
    models = (
        Accounts,
        Authentication,
        PasswordResetToken,
        Notes,
        NoteMetadata,
        Tickets,
        UserSchema,
        UserSchemaDatabase,
        SchemaMetadata,
        FastQuerySection,
        FastQueryProgress,
        FastQuerySectionCompletion,
    )

    for model in models:
        assert getattr(model_package, model.__name__) is model
        assert db.metadata.tables[model.__tablename__] is model.__table__

    assert inspect(Accounts).relationships["authentication_data"].mapper.class_ is Authentication
    assert inspect(Accounts).relationships["user_notes"].mapper.class_ is Notes
    assert inspect(Accounts).relationships["user_tickets"].mapper.class_ is Tickets
    assert inspect(Accounts).relationships["schemas"].mapper.class_ is UserSchema
    assert inspect(Accounts).relationships["schema_databases"].mapper.class_ is UserSchemaDatabase
    assert inspect(Accounts).relationships["fastquery_progress"].mapper.class_ is FastQueryProgress
    assert inspect(Notes).relationships["file_metadata"].mapper.class_ is NoteMetadata
    assert inspect(UserSchema).relationships["details"].mapper.class_ is SchemaMetadata


def test_sqlite_testing_copy_matches_model_tables_columns_and_foreign_keys():
    database_path = (
        Path(__file__).resolve().parents[1]
        / "testing"
        / "schema"
        / "rover_test.sqlite3"
    )
    assert database_path.is_file()

    engine = create_engine(URL.create("sqlite", database=str(database_path)))
    try:
        schema = inspect(engine)
        assert set(schema.get_table_names()) == set(db.metadata.tables)
        for table in db.metadata.sorted_tables:
            expected_columns = {column.name for column in table.columns}
            actual_columns = {
                column["name"] for column in schema.get_columns(table.name)
            }
            assert actual_columns == expected_columns

            expected_foreign_keys = {
                (foreign_key.parent.name, foreign_key.target_fullname)
                for column in table.columns
                for foreign_key in column.foreign_keys
            }
            actual_foreign_keys = {
                (
                    column_name,
                    f"{foreign_key['referred_table']}.{foreign_key['referred_columns'][0]}",
                )
                for foreign_key in schema.get_foreign_keys(table.name)
                for column_name in foreign_key["constrained_columns"]
            }
            assert actual_foreign_keys == expected_foreign_keys
    finally:
        engine.dispose()