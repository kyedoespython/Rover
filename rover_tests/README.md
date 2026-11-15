# Pre-production testing

Run commands from the repository root. This directory contains:

- `suite/`: pytest tests and Node's terminal-command tests.
- `schema/rover_test.sqlite3`: a tracked, empty model-schema fixture.
- `run_local.py`: an isolated Flask app for manual browser checks.
- `react-designs/`: a checklist for manual design testing.
- `data/`: ignored local database and note files, never production data.

## Automated checks

```powershell
.\.venv\Scripts\python.exe -m pytest -q rover_tests\suite
node --test rover_tests\suite\terminal_commands.test.mjs
npm run build
```

These are not a substitute for checking migrations, deployment settings, and
critical user flows in a staging environment; see the [project guide](../DOCUMENTATION.md).

## Manual browser checks

Build the React bundle first, then start the isolated app:

```powershell
npm run build
.\.venv\Scripts\python.exe -m rover_tests.run_local
```

Visit `http://127.0.0.1:5000` and sign in as `LocalTester` with password
`LocalTest!234`. This account is **only for local testing**. The app copies the
schema fixture to `data/rover_local.sqlite3` if needed and stores notes in
`data/notes`. Rate limiting is disabled; it does not exercise production Redis,
email delivery, production sessions, or the real deployment configuration.
Only bind this test app to localhost and never use real customer data.

To discard the local database and recreate it from the fixture, run
`.\.venv\Scripts\python.exe -m rover_tests.run_local --reset`. This does not
clear local note files. Back up anything needed first.

## Refresh the schema fixture

After model changes, regenerate the **tracked** fixture when appropriate:

```powershell
.\.venv\Scripts\python.exe -m rover_tests.schema.create_test_database --reset
```

`--reset` deletes and replaces `schema/rover_test.sqlite3`. It creates tables
from current SQLAlchemy metadata, not from migrations; review and test actual
migrations separately. Without `--reset`, the command refuses to overwrite an
existing fixture.
