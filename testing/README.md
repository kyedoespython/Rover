# Local testing

The existing automated pytest suite remains in `tests/`. This folder contains a
clean SQLite copy of the SQLAlchemy model schema, local React design test
materials, and an isolated Flask app for browser testing.

## Create or refresh the schema copy

From the repository root:

```powershell
.\.venv\Scripts\python.exe -m testing.schema.create_test_database
```

The generated `testing/schema/rover_test.sqlite3` contains the tables and
constraints defined by `main/models`, with no account or production data. To
rebuild that exact test fixture after changing models, pass `--reset`.

## Run the site locally

Build the React bundle, then start the isolated Flask app:

```powershell
npm run build
.\.venv\Scripts\python.exe -m testing.run_local
```

Open `http://127.0.0.1:5000` and log in with the local test account:

- Username: `LocalTester`
- Password: `LocalTest!234`

This app uses a separate SQLite copy at `testing/data/rover_local.sqlite3`,
disables rate limiting, and does not connect to production services. Use
`python -m testing.run_local --reset` to recreate the local database from the
schema fixture.

## Automated checks

```powershell
.\.venv\Scripts\python.exe -m pytest -q
npm run build
```
