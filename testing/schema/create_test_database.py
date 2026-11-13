import argparse
from pathlib import Path

from sqlalchemy import create_engine, inspect
from sqlalchemy.engine import URL

from main.extensions import db
from main import models as _models

DATABASE_PATH = Path(__file__).with_name("rover_test.sqlite3")


def create_database(reset=False):
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    if DATABASE_PATH.exists():
        if not reset:
            raise FileExistsError(
                f"{DATABASE_PATH} already exists; pass --reset to recreate this test database."
            )
        DATABASE_PATH.unlink()

    engine = create_engine(URL.create("sqlite", database=str(DATABASE_PATH)))
    try:
        db.metadata.create_all(engine)
        actual_tables = set(inspect(engine).get_table_names())
        expected_tables = set(db.metadata.tables)
        if actual_tables != expected_tables:
            raise RuntimeError(
                f"Created tables {sorted(actual_tables)}, expected {sorted(expected_tables)}."
            )
    finally:
        engine.dispose()

    print(f"Created {DATABASE_PATH} with {len(expected_tables)} model tables.")


def main():
    parser = argparse.ArgumentParser(description="Create a clean SQLite copy of the model schema.")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Replace the existing testing/schema/rover_test.sqlite3 file.",
    )
    args = parser.parse_args()
    create_database(reset=args.reset)


if __name__ == "__main__":
    main()
