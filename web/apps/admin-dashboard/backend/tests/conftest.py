from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from api.config import settings
from api.dependencies import get_workspace_service, reset_workspace_runtime
from api.main import app
from api.security import AUTH_RATE_LIMITER
from api.services.workspace_store import SqlAlchemyWorkspaceStore


@pytest.fixture(autouse=True)
def reset_service_state(monkeypatch):
    monkeypatch.setattr(settings, "ENABLE_DEMO_AUTH", True)
    monkeypatch.setattr(settings, "TEST_MODE", True)
    monkeypatch.setattr(settings, "EXPOSE_ERROR_DETAILS", False)
    monkeypatch.setattr(settings, "SESSION_COOKIE_SECURE", False)
    monkeypatch.setattr(settings, "SESSION_COOKIE_SAMESITE", "lax")
    monkeypatch.setattr(settings, "SESSION_COOKIE_DOMAIN", "")
    monkeypatch.setattr(settings, "AUTH_RATE_LIMIT_MAX_REQUESTS", 20)
    monkeypatch.setattr(settings, "AUTH_RATE_LIMIT_WINDOW_SECONDS", 60)
    current_store = get_workspace_service().store
    if isinstance(current_store, SqlAlchemyWorkspaceStore):
        current_store.dispose()
    data_root = Path(__file__).resolve().parent.parent / "data"
    data_root.mkdir(parents=True, exist_ok=True)
    db_path = data_root / f"workspace-test-{uuid4().hex}.sqlite3"
    for extra_path in (db_path, db_path.with_name(f"{db_path.name}-journal"), db_path.with_name(f"{db_path.name}-shm"), db_path.with_name(f"{db_path.name}-wal")):
        extra_path.unlink(missing_ok=True)
    database_url = f"sqlite+pysqlite:///{db_path.as_posix()}"
    monkeypatch.setattr(settings, "WORKSPACE_DATABASE_URL", database_url)
    monkeypatch.setattr(settings, "WORKSPACE_AUTO_SEED", True)
    reset_workspace_runtime(database_url=database_url, auto_seed=True)
    get_workspace_service().reset()
    AUTH_RATE_LIMITER.reset()
    yield
    AUTH_RATE_LIMITER.reset()
    current_store = get_workspace_service().store
    if isinstance(current_store, SqlAlchemyWorkspaceStore):
        current_store.dispose()
    for extra_path in (db_path, db_path.with_name(f"{db_path.name}-journal"), db_path.with_name(f"{db_path.name}-shm"), db_path.with_name(f"{db_path.name}-wal")):
        extra_path.unlink(missing_ok=True)


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def auth_headers(role: str | None = "guest", request_id: str = "test-request-id") -> dict[str, str]:
    headers = {
        "x-request-id": request_id,
    }
    if role is not None:
        headers["x-demo-role"] = role
    return headers


def api_headers(role: str | None = "guest", request_id: str = "test-request-id") -> dict[str, str]:
    return auth_headers(role, request_id)
