# Multi-stage Dockerfile for the practice-app backend.
#
# Stage 1 (deps):   install python deps into a venv
# Stage 2 (dev):    full image with hot-reload tooling, used by docker-compose
# Stage 3 (runtime):lean production image, runs as non-root, no shell needed at runtime

ARG PYTHON_VERSION=3.12

# ---------- deps ----------
FROM python:${PYTHON_VERSION}-slim AS deps
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /srv
COPY requirements.txt ./
RUN python -m venv /opt/venv \
 && /opt/venv/bin/pip install -r requirements.txt

# ---------- dev (used by docker-compose) ----------
FROM python:${PYTHON_VERSION}-slim AS dev
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1
COPY --from=deps /opt/venv /opt/venv
WORKDIR /srv
COPY app /srv/app
COPY seed /srv/seed
EXPOSE 8080
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]

# ---------- runtime (production target) ----------
FROM python:${PYTHON_VERSION}-slim AS runtime
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    APP_ENV=prod
COPY --from=deps /opt/venv /opt/venv
WORKDIR /srv
COPY app /srv/app
COPY seed /srv/seed
RUN useradd -r -u 10001 -g nogroup app \
 && chown -R app:nogroup /srv
USER app
EXPOSE 8080
# Cloud Run injects $PORT — honor it.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
