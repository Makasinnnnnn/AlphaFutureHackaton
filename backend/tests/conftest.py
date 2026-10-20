"""Интеграционные тесты API идут на реальном PostgreSQL (отдельная БД) и встроенном симуляторе
внешних источников. URL БД: TEST_DATABASE_URL (по умолчанию локальный conveyor_test)."""
import importlib.util
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
os.environ["DATABASE_URL"] = os.getenv(
    "TEST_DATABASE_URL", "postgresql+psycopg://conveyor:conveyor@localhost:5432/conveyor_test"
)
os.environ["PIPELINE_STEP_DELAY_SEC"] = "0"
os.environ["PIPELINE_ENRICHMENT_RETRY_DELAY_SEC"] = "0"
os.environ["INTEGRATION_BACKOFF_SEC"] = "0"
os.environ.setdefault("SYNTHETIC_DATA", str(ROOT / "data/synthetic/companies.json"))
os.environ["MOCK_LATENCY_MS"] = "0"


def _load_mocks_app():
    spec = importlib.util.spec_from_file_location("mocks_app", ROOT / "mocks/app.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["mocks_app"] = mod
    spec.loader.exec_module(mod)
    return mod.app


@pytest.fixture(scope="session")
def mocks_transport():
    from fastapi.testclient import TestClient

    return TestClient(_load_mocks_app(), base_url="http://mocks")._transport


@pytest.fixture(scope="session")
def db_setup():
    from sqlalchemy import create_engine, text
    from sqlalchemy.engine import make_url

    url = make_url(os.environ["DATABASE_URL"])
    admin = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as c:
        c.execute(text(f'DROP DATABASE IF EXISTS "{url.database}" WITH (FORCE)'))
        c.execute(text(f'CREATE DATABASE "{url.database}"'))
    admin.dispose()

    from alembic import command
    from alembic.config import Config

    cfg = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    command.upgrade(cfg, "head")

    from app.db import SessionLocal
    from app.seed import seed

    with SessionLocal() as db:
        seed(db)
    yield


@pytest.fixture()
def api(db_setup):
    from fastapi.testclient import TestClient

    from app.main import app

    return TestClient(app)


@pytest.fixture()
def run_pipeline(mocks_transport):
    """Прогоняет воркер, пока есть заявки на автоматических этапах."""
    from app.integrations.client import IntegrationClient
    from app.worker import run_once

    client = IntegrationClient(base_url="http://mocks", transport=mocks_transport)

    def _run(max_rounds: int = 50):
        for _ in range(max_rounds):
            if run_once(batch=20, client=client) == 0:
                return
    return _run


def login(api, email: str) -> dict:
    r = api.post("/api/auth/login", json={"email": email, "password": "demo2026"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}
