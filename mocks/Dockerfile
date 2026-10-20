# syntax=docker/dockerfile:1
FROM python:3.12.8-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app/mocks
COPY mocks/requirements.lock.txt .
RUN pip install --require-hashes -r requirements.lock.txt
COPY data/synthetic /app/data/synthetic
COPY mocks/app.py .
RUN useradd --create-home --uid 10001 app
USER app
ENV SYNTHETIC_DATA=/app/data/synthetic/companies.json
EXPOSE 8001
HEALTHCHECK --interval=10s --timeout=3s --retries=5 CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8001/health').status==200 else 1)"
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8001"]
