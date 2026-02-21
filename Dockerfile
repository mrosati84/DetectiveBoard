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

# Cartella upload (sovrascrivibile via env)
ENV UPLOAD_FOLDER=/app/uploads

# Crea utente non-root, cartella uploads e rende eseguibile l'entrypoint
RUN useradd -r -s /bin/false appuser \
    && mkdir -p /app/uploads \
    && chmod +x /app/entrypoint.sh \
    && chown -R appuser:appuser /app

USER appuser

EXPOSE 8080

ENTRYPOINT ["/app/entrypoint.sh"]
