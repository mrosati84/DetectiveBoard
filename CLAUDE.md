# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

All package management and script execution **must** use `uv`:

```bash
# Install dependencies
uv sync

# Run the development server
uv run flask --app app run --debug

# Run Alembic migrations
uv run alembic upgrade head

# Generate a new migration
uv run alembic revision --autogenerate -m "description"
```

## Project Overview

DetectiveBoard is a local-only Flask web app that renders an interactive cork board where users can pin cards and connect them with red yarn (investigator-style). It is **not collaborative** and requires no authentication.

## Architecture

- **`app.py`**: Flask application entry point. Serves HTML pages and API endpoints, manages DB connections.
- **`templates/`**: Jinja2 templates. `base.html` is the base layout; `index.html` extends it.
- **`static/`**: Plain CSS and JS (no preprocessors, no build step). Uploaded card images go to `static/uploads/`.
- **`assets/`**: Contains `cork_background.jpg`, used as the board background via Flask's static serving.
- **`.env`**: Required at project root. Must define DB connection vars (see below).

## Stack Constraints

- **Python 3.13**, managed with `uv`.
- **Flask** serves both HTML pages and REST API endpoints.
- **Plain CSS and JS** — no TypeScript, no bundlers, no preprocessors.
- **PostgreSQL** at `localhost:5432`. Default credentials: user `postgres`, password `postgres`, database `postgres`. All values must come from environment variables loaded via `python-dotenv`.
- **Alembic** for all database schema migrations.

## Environment Variables

The app uses `python-dotenv` to load a `.env` file from the project root. Required variables:

```
DATABASE_HOST=localhost
DATABASE_PORT=5432
DATABASE_USER=postgres
DATABASE_PASSWORD=postgres
DATABASE_NAME=postgres
```

## Key UI Behavior

- The cork board fills 100% width and height (`background-size: cover`).
- The left-side menu (show/hide toggle) manages board CRUD (load, create, delete).
- The bottom toolbar (always visible) creates board elements.
- Cards support: drag to reposition, click to select (multi-select with Shift), delete selected with Del (browser `confirm`), and connecting/disconnecting pairs via toolbar buttons.
- Red yarn connections are drawn as SVG cubic Bézier curves that sag downward to simulate gravity — not straight lines.
- Card images are uploaded (jpeg/png, max 1 MB) and saved to `static/uploads/`.
