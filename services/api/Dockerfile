FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN groupadd --system app && useradd --system --gid app --home-dir /app --no-create-home app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=app:app app ./app
COPY --chown=app:app alembic.ini ./alembic.ini
COPY --chown=app:app migrations ./migrations

USER app

EXPOSE 8000
CMD ["/bin/sh", "-c", "alembic upgrade head && if [ \"${SEED_DEMO_DATA:-false}\" = \"true\" ]; then python -m app.seed && python -m app.seed_dataset --count \"${SEED_SYNTHETIC_PATIENTS:-10000}\"; fi && exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers"]
