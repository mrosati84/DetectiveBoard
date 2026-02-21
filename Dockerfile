# ──────────────────────────────────────────────
# Stage 1: builder — installa le dipendenze con uv
# ──────────────────────────────────────────────
FROM python:3.13-slim AS builder

# Copia uv dall'immagine ufficiale (nessuna installazione extra)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Copia i file di lock prima del codice per sfruttare la cache Docker
COPY pyproject.toml uv.lock ./

# Installa le dipendenze (senza il progetto stesso, per il caching)
RUN uv sync --frozen --no-dev --no-install-project

# Copia il codice e installa il progetto
COPY . .
RUN uv sync --frozen --no-dev

# ──────────────────────────────────────────────
# Stage 2: final — immagine di runtime minimale
# ──────────────────────────────────────────────
FROM python:3.13-slim

WORKDIR /app

# Copia il virtualenv già costruito dallo stage builder
COPY --from=builder /app/.venv /app/.venv

# Copia solo i file applicativi necessari a runtime
COPY --from=builder /app/app.py        ./app.py
COPY --from=builder /app/alembic.ini   ./alembic.ini
COPY --from=builder /app/entrypoint.sh ./entrypoint.sh
COPY --from=builder /app/templates     ./templates
COPY --from=builder /app/static        ./static
COPY --from=builder /app/assets        ./assets
COPY --from=builder /app/migrations    ./migrations

# Attiva il virtualenv impostando PATH
ENV VIRTUAL_ENV=/app/.venv
ENV PATH="/app/.venv/bin:$PATH"

# Buone pratiche Python in container
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Crea il mount point del volume, il symlink per il serving statico e rende
# eseguibile l'entrypoint.
# Il symlink /app/static/uploads -> /mnt/uploads permette a Flask di servire
# le immagini da /static/uploads/ leggendo direttamente dal volume Railway.
RUN mkdir -p /mnt/uploads \
    && rm -rf /app/static/uploads \
    && ln -s /mnt/uploads /app/static/uploads \
    && chmod +x /app/entrypoint.sh

EXPOSE 8080

ENTRYPOINT ["/app/entrypoint.sh"]
