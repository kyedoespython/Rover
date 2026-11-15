# Rover project guide

This guide is for the person maintaining Rover. It describes the repository as
it exists today, not a guarantee of how a particular hosted deployment is
configured. Start with [pre-production testing](./rover_tests/README.md) if you
want to run the application locally without production data.

## Contents

- [What Rover does](#what-rover-does)
- [How the pieces fit together](#how-the-pieces-fit-together)
- [Pages and user workflows](#pages-and-user-workflows)
- [Data and storage](#data-and-storage)
- [Security and privacy](#security-and-privacy)
- [Libraries and their uses](#libraries-and-their-uses)
- [Configuration](#configuration)
- [Development and builds](#development-and-builds)
- [Migrations and deployment](#migrations-and-deployment)
- [Testing before production](#testing-before-production)
- [Troubleshooting](#troubleshooting)

## What Rover does

Rover is a Flask application with React pages for managing notes, workspace
projects, and SQLite database designs. Users can create accounts, verify their
email, work with files and folders inside projects, import a SQLite database,
edit its schema visually, and run read-only queries against it. The site also
contains support tickets and a FastQuery learning feature. FastQuery is still
implemented even though it is not linked from the home-page button.

There is no active AI assistant integration in the current application.
Historical database migrations and old deployment data can still reference
retired integrations; do not delete migration history just because it mentions
them.

## How the pieces fit together

1. Flask's application factory in `main/__init__.py` loads `config.py`,
   initializes extensions, and registers the home and account blueprints.
2. `main/blueprints/home/routes.py` serves the home and support pages;
   `main/blueprints/auth/routes.py` handles account pages, notes, projects,
   SQLite databases, and their APIs. Flask templates mount the React pages.
3. `frontend/src/App.jsx` selects a page, `frontend/src/pages/` contains the
   page components, and `frontend/src/components/` contains shared UI including
   the Rover terminal. `frontend/src/styles.css` provides the styling.
4. SQLAlchemy models in `main/models/` describe the application database;
   `main/services/` holds account validation, email, notes, and FastQuery
   logic. `migrations/` is the Alembic upgrade history.
5. Vite builds the React app into `main/static/react/`. That directory is
   generated and ignored by Git; build it before serving the pages locally.

Other important files: `run.py` selects an environment for local Flask use;
`wsgi.py` creates the production app; `Dockerfile` builds the frontend and
Python image; `docker-compose.yml` and `nginx/` define an alternative
container-based deployment; `rover_tests/` holds tests and local test tooling.

## Pages and user workflows

- **Home and support:** the home page introduces Rover and includes an animated
  schema example. Signed-in users can submit support tickets. Tickets are
  stored in the application database; there is no ticket-management UI or
  automatic support email notification.
- **Accounts:** signup checks the submitted details and sends a verification
  code by email. After verification, the user can sign in. Password reset uses
  an emailed link and invalidates existing login sessions.
- **Workspace (`/DesignDashboard`):** create projects and organize their
  files and folders. Double-click or right-click an item for actions; use
  Shift+F10 for keyboard access. Drag items to reorganize them. Projects are
  stored in Rover's database, not as operating-system files.
- **Database configurations (`/DatabaseConfigurations`):** create and edit
  tables, columns, and visual relationships, including dragging between fields
  to connect them and selecting relationship line colors.
- **Database import and query:** upload `.sqlite3`, `.sqlite`, or `.db` files
  up to 25 MiB. Rover stores a copy; changing the original file on your computer
  does not automatically update Rover. The query interface is read-only and
  limits work and output. Schema changes rebuild the stored SQLite database
  and attempt to copy matching table and column data. Back up the original
  before editing: changes such as renames or removals can discard data, and
  this is not a general-purpose migration tool.
- **Terminal:** the workspace terminal offers project and database commands
  through Rover APIs. Type `help`; quote names or text containing spaces. It
  is not a server shell. Its Python mode runs PyScript/Pyodide in a browser
  worker with a separate temporary filesystem and state. First use needs
  internet access to the pinned CDN resources and a secure, cross-origin
  isolated workspace. Stop & reset destroys that Python session; it does not
  affect saved Rover projects. Run only trusted Python code.
- **Notes, profile and settings:** notes are editable Markdown content;
  account pages provide user-specific information and settings.
- **FastQuery:** `/Rover/FastQuery` provides SQL learning sections and progress,
  backed by an isolated demo database for each user.

## Data and storage

Rover's application database is separate from the SQLite databases users
import. The main model groups are:

| Models | Purpose |
| --- | --- |
| `Accounts`, `Authentication`, `PasswordResetToken` | Account identity, verification, login session version, and password reset state. |
| `WorkspaceProject` | Per-user project names and JSON file/folder items. |
| `UserSchemaDatabase` | Per-user SQLite bytes, schema JSON, and database metadata. |
| `UserSchema`, `SchemaMetadata` | Legacy saved schema and summary information retained for migration. |
| `Notes`, `NoteMetadata` | Note records and metadata for Markdown files. |
| `Tickets` | User-submitted support tickets. |
| `FastQuerySection`, `FastQueryProgress`, `FastQuerySectionCompletion` | Learning content and per-user progress. |

Notes are written to `NOTE_STORAGE_DIR`, or to the Flask instance's
`note_storage` directory if unset. Database records contain their file
metadata and paths. Back up both the application database **and** note files
together; backing up only one will not preserve a complete notes system.
Workspace project content and stored SQLite database copies live in the
application database, so include them in its backup. Redis holds sessions and
rate-limiter state, not the primary content database.

## Security and privacy

This is an operational overview, not a security certification or a substitute
for an independent review.

- Passwords and verification codes are hashed with Werkzeug; password reset
  tokens are stored as hashes and expire. Never store real passwords or tokens
  in tests, documentation, logs, or Git.
- Flask-Login protects signed-in routes, Flask-WTF provides CSRF protection,
  and Flask-Limiter applies limits to sensitive and API routes. Object access
  should continue to be checked against the current user whenever adding APIs.
- Production uses secure, HTTP-only, SameSite=Lax session cookies and requires
  Redis, a database URL, a sufficiently long secret, Resend configuration, and
  a public URL or domain. Production trusts one proxy hop for forwarded client
  IP and scheme: configure the proxy and its trust boundary accordingly.
- Imported SQLite files are untrusted input. Imports have size, format, and
  integrity checks; the read-only query path restricts SQLite operations and
  caps query length, work, rows, and output. Keep these controls when changing
  database features.
- Browser Python is separate from Rover's filesystem, but Python code can use
  browser APIs with the signed-in user's permissions. Do not execute untrusted
  code or treat browser isolation as a guarantee against malicious scripts.
- Use HTTPS, restricted service credentials, backups, access controls, and
  dependency/security reviews in the actual deployment. Do not expose the
  local test account or test app publicly. Check logs for email or storage
  errors without publishing personal information.

The local `Security.md` review, if present, is Git-ignored and may contain
time-sensitive findings. Reassess it against current code before relying on
it. Retired integration tables and provider keys are not automatically removed:
back up the database, retain any required historical encryption secret, and
revoke unused provider credentials before planning their removal.

## Libraries and their uses

The authoritative versions are in `requirements.txt` and `package-lock.json`.
Some entries in the Python requirements are transitive dependencies or
historical pins; an entry alone does not prove a feature is active.

| Library | Use in this project |
| --- | --- |
| Flask, Jinja2, Werkzeug | HTTP routes, templates, request handling, and password hashing. |
| Flask-SQLAlchemy, SQLAlchemy, psycopg | Models and SQL database access, including PostgreSQL in Compose. |
| Flask-Migrate and Alembic | Schema migration commands and revision history. |
| Flask-Login | Authentication and user loading. |
| Flask-Session and redis | Server-side session storage; Redis also backs rate limiting. |
| Flask-WTF, WTForms | CSRF protection and form-related infrastructure. |
| Flask-Limiter | Request rate limits. |
| python-dotenv | Loads environment variables from a local `.env` file. |
| Resend | Sends verification and password-reset emails. |
| phonenumberslite | Validates account phone numbers. |
| Gunicorn | Production WSGI server in the container. |
| pytest | Python automated tests. |
| React and React DOM | Browser UI components. |
| Vite | Frontend build tooling. |
| PyScript and Pyodide | Pinned browser-loaded runtime for the optional Python terminal; not a Python server dependency. |

Do not remove pinned dependencies based only on this table. Check imports,
transitive dependencies, deployment, and tests before changing the manifests.

## Configuration

`APP_ENV` selects `development`, `testing`, or `production`; the application
factory refuses to start without a valid environment. Environment variables
can be supplied by the host or a local, ignored `.env` file. Do not commit
secrets.

| Variable | Purpose |
| --- | --- |
| `SECRET_KEY` | Flask secret. Production requires at least 32 characters; development has an insecure fallback. |
| `DATABASE_URL` | SQLAlchemy application database connection string; required in production. Development also needs a usable URL. |
| `REDIS_URL` | Redis connection for sessions and rate limiting; required in production, defaults to localhost in development. |
| `SESSION_TYPE` | Must be `redis` in production. |
| `SESSION_PERMANENT`, `SESSION_USE_SIGNER` | Boolean session options (`true`/`false`, `1`/`0`, `yes`/`no`, or `on`/`off`). |
| `RESEND_API_KEY`, `RESEND_FROM_EMAIL` | Email API key and sender. The key is required in production. |
| `PUBLIC_BASE_URL`, `ROVER_DOMAIN` | Public base URL for password-reset links, or a domain used to construct one. Production requires one of them. |
| `NOTE_STORAGE_DIR` | Optional persistent directory for Markdown note files. |

Compose also requires `POSTGRES_PASSWORD`, `ROVER_DOMAIN`, and `CERTBOT_EMAIL`
for its PostgreSQL and certificate setup. These are Compose-specific
requirements; a Render deployment can have different infrastructure. Inspect
the actual provider configuration rather than assuming Compose is deployed.
In normal production sessions, the remember-me option lasts up to three days
of inactivity; without it the login cookie is a browser-session cookie.

## Development and builds

For a self-contained local browser workflow, use
[rover_tests/README.md](./rover_tests/README.md); it describes the deliberately
isolated test account and data. For a full development app, provision an
appropriate database and Redis, configure the variables above, install the
Python requirements into a virtual environment and the npm lockfile
dependencies, build with `npm run build`, and run Flask with `APP_ENV` set to
`development`. Real email workflows also require a working Resend setup.

The production Docker build installs Node dependencies with `npm ci`, builds
the React bundle, installs the pinned Python requirements, and runs Gunicorn
as a non-root user. The image's startup command runs `flask db upgrade` before
starting the server. Avoid committing generated bundles, local environments,
database files, test data, or credentials.

## Migrations and deployment

SQLAlchemy models describe the current intended schema; Alembic revisions
describe how existing databases get there. For a model change:

1. Back up the database and note storage, and test restoration.
2. Generate a migration with Flask-Migrate against an appropriate development
   database, then manually review it. Autogeneration is not a safe production
   migration by itself, especially with retired historical tables.
3. Apply and test the upgrade on staging with representative data. Check
   application behavior and plan a rollback or restore before release.
4. Run `flask db upgrade` in the correctly configured deployment environment
   as part of the release. Coordinate migrations so concurrent instances do
   not race. The supplied Docker/Compose commands already run an upgrade.

The tracked test SQLite fixture is generated directly from current model
metadata; passing its tests does **not** prove the migration chain works.
Keep old migration files so existing installations can upgrade.

Compose includes PostgreSQL, Redis, Nginx, Certbot, and persistent database,
note, and certificate volumes. Review DNS, proxy, persistent storage, backup,
TLS, email, and environment configuration for whichever platform is actually
used. The repository alone cannot verify live Render settings.

## Testing before production

Run the Python tests, Node terminal tests, and frontend build as documented in
[rover_tests/README.md](./rover_tests/README.md). Then, in staging, check:

1. Migration upgrade and backup/restore with representative, non-production
   data.
2. Signup, email verification, login, reset, session invalidation, and
   rate-limiting behavior with the real integrations configured.
3. Project create/edit/move/delete, notes, SQLite import, schema/relationship
   edits, and read-only queries. Check that one user cannot access another's
   resources.
4. Browser layout, keyboard access, terminal resizing and commands, Python
   worker loading/reset, and error states. See the design checklist in
   `rover_tests/react-designs/`.
5. Production HTTPS, Redis, Resend sender/domain, persistence, logs, health
   checks, and deployed environment settings.

The local test app intentionally disables rate limiting and uses a separate
SQLite database, so it cannot validate production integrations or security
configuration.

## Troubleshooting

- **Page shows no React UI:** run `npm run build` and check that the generated
  `main/static/react/` files are being served.
- **Application refuses to start:** check `APP_ENV`, the selected configuration,
  required variables, database access, and Redis. Never paste secrets into
  issue reports.
- **Verification or reset email fails:** check Resend's API key, verified sender,
  public URL, delivery status, and server logs.
- **Python terminal cannot initialize:** verify a secure context, the workspace
  COOP/COEP headers, CDN access, and browser support. Resetting the worker
  clears its state.
- **Notes disappear after redeployment:** check that `NOTE_STORAGE_DIR` points
  to persistent storage and restore both the database and note files from the
  same backup.
- **Schema fixture test fails after a model change:** review the model and
  migration separately, then refresh the test fixture using the explicit
  `--reset` procedure in the testing guide.
