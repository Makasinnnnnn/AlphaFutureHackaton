# syntax=docker/dockerfile:1
FROM python:3.12.8-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app/backend

COPY backend/requirements.lock.txt .
RUN pip install --require-hashes -r requirements.lock.txt

COPY data/synthetic /app/data/synthetic
COPY backend/ .
RUN useradd --create-home --uid 10001 app && chown -R app /app
USER app

ENV SYNTHETIC_DATA=/app/data/synthetic/companies.json
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --retries=5 CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/health/live').status==200 else 1)"
# миграции + справочники/синтетика, затем API
CMD ["sh", "-c", "alembic upgrade head && python -m app.seed && uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2"]
