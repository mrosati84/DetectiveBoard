<div align="center">
  <img src="assets/detectiveboard-logo.svg" alt="DetectiveBoard logo" width="220">
  <h1>DetectiveBoard</h1>
  <p><strong>Turn clues into a case board, then connect the dots.</strong></p>
</div>

DetectiveBoard is a Flask web application for building interactive, investigator-style cork boards. Create separate boards, pin evidence cards and notes, arrange them freely, and connect related cards with red string. Accounts keep each user's boards private, while an optional read-only sharing link makes it easy to show a finished board to someone else.

## Features

- Register and sign in with a username and password.
- Create, rename, load, and delete multiple boards.
- Add draggable evidence cards with a title, description, color, pin position, and optional JPG or PNG image.
- Add and edit draggable text notes.
- Select cards and draw or remove red-string connections between them.
- Mark cards inactive without removing them from the board.
- Publish and revoke token-based, read-only board links.
- Store board data in PostgreSQL and uploaded images on disk.

## Technology

| Area | Technology |
| --- | --- |
| Application | Python 3.13, Flask, Jinja2 |
| Client | HTMX, plain JavaScript, CSS, HTML, and SVG (no frontend build step) |
| Database | PostgreSQL 16 and `psycopg2` |
| Schema migrations | Alembic |
| Authentication | Werkzeug password hashing and JWT (`PyJWT`) |
| Configuration | `python-dotenv` |
| Abuse protection | Flask-Limiter |
| Python tooling | `uv` with a committed lockfile |
| Production server | Gunicorn |
| Containers | Docker and Docker Compose |

The complete, locked dependency set is recorded in [`uv.lock`](uv.lock); direct application dependencies are declared in [`pyproject.toml`](pyproject.toml).

## Repository structure

```text
.
├── app.py                 # Flask pages, REST API, auth, uploads, and DB access
├── templates/             # Jinja pages and reusable modal partials
│   ├── base.html
│   ├── home.html          # Landing, registration, and login UI
│   ├── index.html         # Authenticated interactive board
│   ├── shared.html        # Read-only shared board
│   └── partials/          # Server-rendered fragments and reusable modal dialogs
├── static/
│   ├── css/               # Landing-page and board styles
│   ├── js/                # Home, editable board, and shared-board behavior
│   └── uploads/           # Runtime card images (contents are gitignored)
├── assets/                # Logo and cork-board background
├── migrations/
│   ├── env.py             # Alembic database configuration
│   └── versions/          # Ordered database schema revisions
├── pyproject.toml         # Project metadata and direct dependencies
├── uv.lock                # Reproducible dependency lockfile
├── alembic.ini            # Alembic configuration
├── compose.yaml           # Local PostgreSQL service
├── Dockerfile             # Production application image
└── entrypoint.sh          # Runs migrations, then starts Gunicorn
```

The best starting points are [`app.py`](app.py) for server behavior and API routes, [`static/js/board.js`](static/js/board.js) for board interactions, and [`templates/index.html`](templates/index.html) with [`static/css/style.css`](static/css/style.css) for the board UI.

## Local development

### Prerequisites

- [Python 3.13](https://www.python.org/downloads/)
- [`uv`](https://docs.astral.sh/uv/getting-started/installation/)
- Docker with Docker Compose (recommended), or an accessible PostgreSQL server

All Python package installation and command execution in this repository uses `uv`.

### 1. Install dependencies

```bash
uv sync --frozen
```

`uv` creates and manages the local `.venv` automatically.

### 2. Configure the environment

Copy the checked-in example and replace the development secret:

```bash
cp .env.example .env
uv run python -c 'import secrets; print(secrets.token_urlsafe(48))'
```

Paste the generated value into `SECRET_KEY` in `.env`. The default database settings work with the provided Compose service:

```dotenv
DATABASE_HOST=localhost
DATABASE_PORT=5432
DATABASE_USER=postgres
DATABASE_PASSWORD=postgres
DATABASE_NAME=postgres
SECRET_KEY=replace-with-a-long-random-value
```

Optional settings:

| Variable | Default | Purpose |
| --- | --- | --- |
| `UPLOAD_FOLDER` | `static/uploads` | Filesystem location for uploaded card images |
| `RATE_LIMIT_AUTH` | `5 per minute` | Per-IP limit applied to login and registration |
| `RATE_LIMIT_STORAGE_URI` | `memory://` | Flask-Limiter backend; use a shared backend for multiple workers |

Never commit `.env`; it is already excluded by `.gitignore`.

### 3. Start PostgreSQL

```bash
docker compose up -d db
docker compose ps
```

If you use an existing PostgreSQL instance instead, update the five `DATABASE_*` values in `.env` and skip this step.

### 4. Apply migrations

```bash
uv run alembic upgrade head
```

### 5. Run the app

```bash
uv run flask --app app run --debug
```

Open <http://127.0.0.1:5000>, register an account, and create your first board. The health endpoint is available at <http://127.0.0.1:5000/health>.

### Stop local services

```bash
docker compose down
```

Add `--volumes` if you also want to delete the local PostgreSQL data volume.

## Common commands

| Task | Command |
| --- | --- |
| Sync exactly from the lockfile | `uv sync --frozen` |
| Run the development server | `uv run flask --app app run --debug` |
| Apply all migrations | `uv run alembic upgrade head` |
| Create an autogenerated migration | `uv run alembic revision --autogenerate -m "describe change"` |
| Inspect migration state | `uv run alembic current` |
| Start the local database | `docker compose up -d db` |
| Follow database logs | `docker compose logs -f db` |

## Database changes

Schema changes must be represented by Alembic revisions rather than applied manually. After changing the model/schema expectations:

```bash
uv run alembic revision --autogenerate -m "add example field"
uv run alembic upgrade head
```

Review every generated migration in `migrations/versions/` before committing it, including its downgrade path.

## Container deployment

The `Dockerfile` builds the application and starts it on port `8080`. At container startup, `entrypoint.sh` applies pending migrations and launches two Gunicorn workers. A deployment must provide:

- all required `DATABASE_*` variables and `SECRET_KEY`;
- a reachable PostgreSQL database; and
- persistent storage mounted at `/mnt/uploads` if uploaded images must survive restarts.

For example, after building the image:

```bash
docker build -t detectiveboard .
docker run --rm -p 8080:8080 --env-file .env detectiveboard
```

When the database runs on the host, remember that `DATABASE_HOST=localhost` inside a container refers to the container itself. Use a container-accessible database hostname instead.

## Security notes

- Use a long, unpredictable `SECRET_KEY`, especially outside local development.
- Shared board URLs grant read-only access to anyone who has the token; revoke sharing when it is no longer needed.
- Card uploads accept `.jpg`, `.jpeg`, and `.png` files and are limited to 1 MB by the application.
- The default in-memory rate-limit backend is suitable for local, single-process use. Configure a shared backend when deploying multiple processes or instances.

## Troubleshooting

### The app cannot connect to PostgreSQL

Confirm the database is healthy with `docker compose ps`, then compare its credentials and exposed port with `.env`. Apply migrations once connectivity is restored.

### The app exits because `SECRET_KEY` is missing

Create `.env` from `.env.example` and set `SECRET_KEY` to a non-empty random value before running any command that imports `app.py`.

### Uploaded images disappear after a deployment

Set `UPLOAD_FOLDER` to durable storage for a host deployment. The provided production container expects a persistent volume at `/mnt/uploads` and exposes it to Flask through `static/uploads`.
